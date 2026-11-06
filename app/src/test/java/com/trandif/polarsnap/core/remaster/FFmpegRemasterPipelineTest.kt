package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.CapCutPreset
import com.trandif.polarsnap.domain.remaster.RemasterConfig
import com.trandif.polarsnap.domain.remaster.RemasterException
import com.trandif.polarsnap.domain.remaster.TargetResolution
import kotlinx.coroutines.runBlocking
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File

class FFmpegRemasterPipelineTest {

    @Test
    fun testBuildCommandLineAssemblesCompleteArgs() {
        val manager = HaldClutManager(File("build/tmp/test_pipeline"))
        val pipeline = FFmpegRemasterPipeline(haldClutManager = manager)

        val config = RemasterConfig(
            enableSuperResolution = true,
            targetResolution = TargetResolution.UHD_4K,
            enableSharpening = true,
            colorGradingPreset = CapCutPreset.TEAL_AND_ORANGE
        )

        val cmd = pipeline.buildCommandLine(
            sourceFile = "input.mp4",
            destinationFile = "output.mp4",
            config = config,
            lutFilePath = "lut.png"
        )

        assertTrue(cmd.contains("-y"))
        assertTrue(cmd.contains("-i"))
        assertTrue(cmd.contains("input.mp4"))
        assertTrue(cmd.contains("lut.png"))
        assertTrue(cmd.contains("-filter_complex"))
        assertTrue(cmd.contains("-map"))
        assertTrue(cmd.contains("[out]"))
        assertTrue(cmd.contains("-c:v"))
        assertTrue(cmd.contains("-c:a"))
        assertTrue(cmd.contains("copy"))
        assertTrue(cmd.contains("-movflags"))
        assertTrue(cmd.contains("+faststart"))
        assertTrue(cmd.contains("output.mp4"))
    }

    @Test
    fun testProcessMediaExecutesAndReportsProgress(@TempDir tempDir: File) = runBlocking {
        val manager = HaldClutManager(tempDir)
        val sourceFile = File(tempDir, "source.mp4").apply { writeText("dummy source media") }
        val destFile = File(tempDir, "remastered.mp4")

        val progressUpdates = mutableListOf<Float>()

        val mockExecutor = object : FFmpegProcessExecutor {
            override suspend fun execute(
                command: List<String>,
                onStdErrLine: (String) -> Unit
            ): Int {
                // Simulate FFmpeg progress output
                onStdErrLine("Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'source.mp4':")
                onStdErrLine("  Duration: 00:00:10.00, start: 0.000000, bitrate: 1200 kb/s")
                onStdErrLine("frame=   50 fps=0.0 q=0.0 size=     256KiB time=00:00:02.00 bitrate=1048.6kbits/s speed=3.99x")
                onStdErrLine("frame=  125 fps=0.0 q=0.0 size=     640KiB time=00:00:05.00 bitrate=1048.6kbits/s speed=4.01x")
                onStdErrLine("frame=  200 fps=0.0 q=0.0 size=    1024KiB time=00:00:08.00 bitrate=1048.6kbits/s speed=4.00x")
                onStdErrLine("frame=  250 fps=0.0 q=-0.0 Lsize=   1280KiB time=00:00:10.00 bitrate=1048.6kbits/s speed=4.02x")

                // Touch destination file
                destFile.writeText("remastered output")
                return 0
            }
        }

        val pipeline = FFmpegRemasterPipeline(
            haldClutManager = manager,
            executor = mockExecutor
        )

        val result = pipeline.processMedia(
            sourceFile = sourceFile.absolutePath,
            destinationFile = destFile.absolutePath,
            config = RemasterConfig(colorGradingPreset = CapCutPreset.NONE),
            onProgress = { progressUpdates.add(it) }
        )

        assertTrue(result.isSuccess)
        assertEquals(destFile.absolutePath, result.getOrNull())
        assertTrue(progressUpdates.isNotEmpty())
        assertEquals(1.0f, progressUpdates.last(), "Final progress must reach 1.0f (100%)")
        // Check intermediate progress was tracked
        assertTrue(progressUpdates.any { it in 0.18f..0.22f })
        assertTrue(progressUpdates.any { it in 0.48f..0.52f })
    }

    @Test
    fun testProcessMediaThrowsWhenSourceNotFound(@TempDir tempDir: File) = runBlocking {
        val manager = HaldClutManager(tempDir)
        val pipeline = FFmpegRemasterPipeline(haldClutManager = manager)

        val result = pipeline.processMedia(
            sourceFile = File(tempDir, "non_existent.mp4").absolutePath,
            destinationFile = File(tempDir, "out.mp4").absolutePath,
            config = RemasterConfig(),
            onProgress = {}
        )

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is RemasterException.SourceNotFoundException)
    }

    @Test
    fun testProcessMediaThrowsWhenTranscodeFails(@TempDir tempDir: File) = runBlocking {
        val manager = HaldClutManager(tempDir)
        val sourceFile = File(tempDir, "source.mp4").apply { writeText("dummy media") }

        val failingExecutor = object : FFmpegProcessExecutor {
            override suspend fun execute(
                command: List<String>,
                onStdErrLine: (String) -> Unit
            ): Int {
                onStdErrLine("Error while opening encoder for output stream #0:0 - maybe incorrect parameters")
                return 1 // Failure exit code
            }
        }

        val pipeline = FFmpegRemasterPipeline(
            haldClutManager = manager,
            executor = failingExecutor
        )

        val result = pipeline.processMedia(
            sourceFile = sourceFile.absolutePath,
            destinationFile = File(tempDir, "out.mp4").absolutePath,
            config = RemasterConfig(colorGradingPreset = CapCutPreset.NONE),
            onProgress = {}
        )

        assertTrue(result.isFailure)
        val exception = result.exceptionOrNull()
        assertTrue(exception is RemasterException.TranscodeFailedException)
        val transcodeException = exception as RemasterException.TranscodeFailedException
        assertEquals(1, transcodeException.exitCode)
        assertTrue(transcodeException.rawError.contains("Error while opening encoder"))
    }
}
