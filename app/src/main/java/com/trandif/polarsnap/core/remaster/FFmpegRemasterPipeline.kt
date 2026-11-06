package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.CapCutPreset
import com.trandif.polarsnap.domain.remaster.RemasterConfig
import com.trandif.polarsnap.domain.remaster.RemasterException
import com.trandif.polarsnap.domain.remaster.RemasterPipeline
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.util.regex.Pattern

/**
 * Abstraction for executing FFmpeg CLI processes.
 */
interface FFmpegProcessExecutor {
    suspend fun execute(
        command: List<String>,
        onStdErrLine: (String) -> Unit
    ): Int
}

/**
 * Default process executor using the host OS / Android FFmpeg binary.
 */
class DefaultFFmpegProcessExecutor(
    private val ffmpegBinaryPath: String = "ffmpeg"
) : FFmpegProcessExecutor {
    override suspend fun execute(
        command: List<String>,
        onStdErrLine: (String) -> Unit
    ): Int {
        val fullCommand = listOf(ffmpegBinaryPath) + command
        val processBuilder = ProcessBuilder(fullCommand)
        processBuilder.redirectErrorStream(false)

        val process = processBuilder.start()

        val reader = BufferedReader(InputStreamReader(process.errorStream))
        reader.forEachLine { line ->
            onStdErrLine(line)
        }

        return process.waitFor()
    }
}

/**
 * High-level orchestration pipeline for video remastering, super-resolution upscaling,
 * and CapCut color grading via FFmpeg.
 */
class FFmpegRemasterPipeline(
    private val haldClutManager: HaldClutManager,
    private val encoderSelector: MediaCodecEncoderSelector = MediaCodecEncoderSelector(),
    private val filtergraphBuilder: FiltergraphBuilder = FiltergraphBuilder(),
    private val executor: FFmpegProcessExecutor = DefaultFFmpegProcessExecutor()
) : RemasterPipeline {

    companion object {
        private val DURATION_PATTERN = Pattern.compile("Duration:\\s*(\\d+):(\\d+):(\\d+\\.\\d+)")
        private val TIME_PATTERN = Pattern.compile("time=(\\d+):(\\d+):(\\d+\\.\\d+)")
    }

    /**
     * Executes the remaster transcode on the given media file.
     */
    override suspend fun processMedia(
        sourceFile: String,
        destinationFile: String,
        config: RemasterConfig,
        onProgress: (Float) -> Unit
    ): Result<String> {
        return runCatching {
            val src = File(sourceFile)
            if (!src.exists()) {
                throw RemasterException.SourceNotFoundException(sourceFile)
            }

            val dest = File(destinationFile)
            dest.parentFile?.mkdirs()

            // 1. Resolve LUT asset if preset selected
            val lutFile = if (config.colorGradingPreset != CapCutPreset.NONE) {
                haldClutManager.getLutFile(config.colorGradingPreset)
                    ?: throw RemasterException.LutAssetMissingException(
                        config.colorGradingPreset,
                        config.colorGradingPreset.assetFileName ?: "unknown"
                    )
            } else null

            // 2. Select hardware/software encoder via 3-tier fallback matrix
            val encoderSelection = encoderSelector.selectEncoder(config.targetResolution)
            val effectiveTargetResolution = encoderSelection.forcedResolution ?: config.targetResolution

            val effectiveConfig = if (effectiveTargetResolution != config.targetResolution) {
                config.copy(targetResolution = effectiveTargetResolution)
            } else {
                config
            }

            // 3. Construct 5-stage FFmpeg filtergraph with pre-upscale memory optimization
            val filtergraphResult = filtergraphBuilder.buildFiltergraph(
                config = effectiveConfig,
                lutInputIndex = 1,
                sourceWidth = 1920, // default probe resolution
                sourceHeight = 1080,
                outputPixelFormat = encoderSelection.pixelFormat
            )

            // 4. Assemble full command arguments
            val command = mutableListOf<String>()
            command.add("-y")
            command.addAll(listOf("-i", src.absolutePath))

            if (lutFile != null) {
                command.addAll(listOf("-i", lutFile.absolutePath))
            }

            command.addAll(listOf("-filter_complex", filtergraphResult.filtergraph))
            command.addAll(listOf("-map", "[out]"))
            command.addAll(listOf("-map", "0:a?")) // Passthrough audio if present

            // Video encoder arguments
            command.addAll(encoderSelection.toCliArguments())

            // Audio & container options
            command.addAll(listOf("-c:a", "copy"))
            command.addAll(listOf("-movflags", "+faststart"))
            command.add(dest.absolutePath)

            // 5. Execute with live progress parsing
            var totalDurationSeconds = 0.0
            val errorLogBuffer = StringBuilder()

            val exitCode = executor.execute(command) { line ->
                errorLogBuffer.appendLine(line)

                // Parse duration from stream headers
                if (totalDurationSeconds <= 0.0) {
                    val durationMatcher = DURATION_PATTERN.matcher(line)
                    if (durationMatcher.find()) {
                        val hours = durationMatcher.group(1).toDouble()
                        val minutes = durationMatcher.group(2).toDouble()
                        val seconds = durationMatcher.group(3).toDouble()
                        totalDurationSeconds = hours * 3600.0 + minutes * 60.0 + seconds
                    }
                }

                // Parse current transcode time
                val timeMatcher = TIME_PATTERN.matcher(line)
                if (timeMatcher.find()) {
                    val hours = timeMatcher.group(1).toDouble()
                    val minutes = timeMatcher.group(2).toDouble()
                    val seconds = timeMatcher.group(3).toDouble()
                    val currentTimeSeconds = hours * 3600.0 + minutes * 60.0 + seconds

                    if (totalDurationSeconds > 0.0) {
                        val progress = (currentTimeSeconds / totalDurationSeconds).toFloat().coerceIn(0.0f, 1.0f)
                        onProgress(progress)
                    }
                }
            }

            if (exitCode != 0) {
                throw RemasterException.TranscodeFailedException(
                    exitCode = exitCode,
                    rawError = errorLogBuffer.takeLast(1000).toString()
                )
            }

            onProgress(1.0f)
            dest.absolutePath
        }
    }

    /**
     * Helper to assemble and inspect the FFmpeg command without executing.
     */
    fun buildCommandLine(
        sourceFile: String,
        destinationFile: String,
        config: RemasterConfig,
        lutFilePath: String? = null
    ): List<String> {
        val encoderSelection = encoderSelector.selectEncoder(config.targetResolution)
        val filtergraphResult = filtergraphBuilder.buildFiltergraph(
            config = config,
            lutInputIndex = 1,
            outputPixelFormat = encoderSelection.pixelFormat
        )

        val command = mutableListOf("-y", "-i", sourceFile)
        if (lutFilePath != null && config.colorGradingPreset != CapCutPreset.NONE) {
            command.addAll(listOf("-i", lutFilePath))
        }
        command.addAll(listOf("-filter_complex", filtergraphResult.filtergraph))
        command.addAll(listOf("-map", "[out]", "-map", "0:a?"))
        command.addAll(encoderSelection.toCliArguments())
        command.addAll(listOf("-c:a", "copy", "-movflags", "+faststart", destinationFile))
        return command
    }
}
