package com.trandif.polarsnap.core.engine

import android.content.Context
import com.trandif.polarsnap.domain.engine.DownloadedArtifact
import com.trandif.polarsnap.domain.engine.EngineOptions
import com.trandif.polarsnap.domain.engine.MediaMetadata
import com.trandif.polarsnap.domain.engine.PolarEngine
import com.trandif.polarsnap.domain.engine.PolarEngineException
import com.trandif.polarsnap.domain.engine.SanitizedStreamEvent
import com.yausername.aria2c.Aria2c
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Native bridge abstraction allowing both real in-process CPython JNI execution
 * and mockable test execution.
 */
interface NativeEngineBridge {
    fun init(context: Context)
    fun initFFmpeg(context: Context)
    fun initAria2c(context: Context)
    fun execute(
        arguments: List<String>,
        processId: String,
        onProgress: (progress: Float, etaInSeconds: Long, line: String) -> Unit
    ): EngineExecutionResult
    fun destroyProcessById(processId: String): Boolean
}

data class EngineExecutionResult(
    val exitCode: Int,
    val out: String,
    val err: String,
    val elapsedTimeMs: Long
)

/**
 * Default production implementation of [NativeEngineBridge] binding to embedded youtubedl-android.
 */
class DefaultNativeEngineBridge : NativeEngineBridge {
    override fun init(context: Context) {
        YoutubeDL.getInstance().init(context.applicationContext)
    }

    override fun initFFmpeg(context: Context) {
        FFmpeg.getInstance().init(context.applicationContext)
    }

    override fun initAria2c(context: Context) {
        Aria2c.getInstance().init(context.applicationContext)
    }

    override fun execute(
        arguments: List<String>,
        processId: String,
        onProgress: (progress: Float, etaInSeconds: Long, line: String) -> Unit
    ): EngineExecutionResult {
        val request = YoutubeDLRequest(emptyList())
        for (arg in arguments) {
            request.addOption(arg)
        }

        val startTime = System.currentTimeMillis()
        val response = YoutubeDL.getInstance().execute(request, processId) { progress, etaInSeconds, line ->
            onProgress(progress, etaInSeconds, line)
        }
        val elapsedTime = System.currentTimeMillis() - startTime

        return EngineExecutionResult(
            exitCode = response.exitCode,
            out = response.out,
            err = response.err,
            elapsedTimeMs = elapsedTime
        )
    }

    override fun destroyProcessById(processId: String): Boolean {
        return YoutubeDL.getInstance().destroyProcessById(processId)
    }
}

/**
 * In-process implementation of [PolarEngine] for PolarSnap — by Trandif.
 * Features 100% whitelabeled runtime execution, CPython JNI initialization,
 * process cancellation, and zero-leak exception handling.
 */
class PolarCoreEngine(
    private val bridge: NativeEngineBridge = DefaultNativeEngineBridge(),
    private val translator: PolarCommandTranslator = PolarCommandTranslator()
) : PolarEngine {

    private val initialized = AtomicBoolean(false)

    override fun isInitialized(): Boolean = initialized.get()

    override suspend fun initialize(context: Context): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            if (!initialized.get()) {
                bridge.init(context)
                runCatching { bridge.initFFmpeg(context) }
                runCatching { bridge.initAria2c(context) }
                initialized.set(true)
            }
        }.fold(
            onSuccess = { Result.success(Unit) },
            onFailure = { error ->
                Result.failure(PolarExceptionSanitizer.sanitize(error))
            }
        )
    }

    override suspend fun fetchMetadata(url: String): Result<MediaMetadata> = withContext(Dispatchers.IO) {
        runCatching {
            val processId = UUID.randomUUID().toString()
            val args = translator.translateMetadata(url)
            val result = bridge.execute(args, processId) { _, _, _ -> }

            if (result.exitCode != 0) {
                throw PolarEngineException.EngineInternalError(
                    userDescription = PolarLogSanitizer.scrub(result.err.ifBlank { result.out })
                )
            }

            parseMetadataJson(result.out, url)
        }.fold(
            onSuccess = { Result.success(it) },
            onFailure = { error ->
                Result.failure(PolarExceptionSanitizer.sanitize(error))
            }
        )
    }

    override suspend fun executeDownload(
        url: String,
        options: EngineOptions,
        outputDir: String,
        taskId: String,
        onProgress: (SanitizedStreamEvent) -> Unit
    ): Result<DownloadedArtifact> = withContext(Dispatchers.IO) {
        runCatching {
            val dir = File(outputDir)
            if (!dir.exists()) {
                dir.mkdirs()
            }

            val commandArgs = translator.translate(url, options, outputDir)

            val result = bridge.execute(commandArgs, taskId) { _, _, line ->
                val event = PolarLogSanitizer.sanitizeLine(line)
                if (event != null) {
                    onProgress(event)
                }
            }

            if (result.exitCode != 0) {
                throw PolarEngineException.EngineInternalError(
                    userDescription = PolarLogSanitizer.scrub(result.err.ifBlank { result.out })
                )
            }

            // Identify the downloaded artifact
            val artifactFile = locateDownloadedFile(dir, taskId, options)
            val extension = artifactFile.extension.ifBlank { options.customFormatContainer.extension }

            DownloadedArtifact(
                taskId = taskId,
                filePath = artifactFile.absolutePath,
                format = extension,
                fileSize = artifactFile.length(),
                durationSeconds = 0L,
                title = artifactFile.nameWithoutExtension
            )
        }.fold(
            onSuccess = { Result.success(it) },
            onFailure = { error ->
                Result.failure(PolarExceptionSanitizer.sanitize(error))
            }
        )
    }

    override suspend fun cancelDownload(taskId: String): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            bridge.destroyProcessById(taskId)
            Unit
        }.fold(
            onSuccess = { Result.success(Unit) },
            onFailure = { error ->
                Result.failure(PolarExceptionSanitizer.sanitize(error))
            }
        )
    }

    private fun parseMetadataJson(jsonString: String, fallbackUrl: String): MediaMetadata {
        val root = JSONObject(jsonString.trim())
        val id = root.optString("id", UUID.randomUUID().toString())
        val title = root.optString("title", "Polar Captured Media")
        val channel = root.optString("uploader", root.optString("channel", "Polar Creator"))
        val duration = root.optLong("duration", 0L)
        val thumbnail = root.optString("thumbnail", "")
        val rawExt = root.optString("ext", "mp4")
        val description = root.optString("description", "")
        val viewCount = root.optLong("view_count", 0L)

        val resolutions = mutableListOf<String>()
        val formats = root.optJSONArray("formats")
        if (formats != null) {
            for (i in 0 until formats.length()) {
                val formatObj = formats.optJSONObject(i) ?: continue
                val height = formatObj.optInt("height", 0)
                if (height > 0) {
                    val label = when {
                        height >= 2160 -> "4K (${height}p)"
                        height >= 1440 -> "1440p"
                        height >= 1080 -> "1080p FHD"
                        height >= 720 -> "720p HD"
                        else -> "${height}p"
                    }
                    if (!resolutions.contains(label)) {
                        resolutions.add(label)
                    }
                }
            }
        }

        return MediaMetadata(
            id = id,
            title = title,
            channel = channel,
            durationSeconds = duration,
            thumbnailUrl = thumbnail,
            availableResolutions = resolutions,
            rawExt = rawExt,
            description = description,
            viewCount = viewCount
        )
    }

    private fun locateDownloadedFile(outputDir: File, taskId: String, options: EngineOptions): File {
        val files = outputDir.listFiles()?.filter { it.isFile }?.sortedByDescending { it.lastModified() }
        if (!files.isNullOrEmpty()) {
            // First check if any file contains the taskId
            val matched = files.firstOrNull { it.name.contains(taskId) }
            if (matched != null) return matched
            // Otherwise return the most recently modified file in outputDir
            return files.first()
        }
        // Fallback placeholder if directory is empty
        val ext = options.customFormatContainer.extension
        return File(outputDir, "polar_media_$taskId.$ext")
    }

    companion object {
        @Volatile
        private var instance: PolarCoreEngine? = null

        fun getInstance(bridge: NativeEngineBridge = DefaultNativeEngineBridge()): PolarCoreEngine {
            return instance ?: synchronized(this) {
                instance ?: PolarCoreEngine(bridge).also { instance = it }
            }
        }
    }
}
