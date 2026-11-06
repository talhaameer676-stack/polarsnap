package com.trandif.polarsnap.domain.remaster

/**
 * CapCut-grade cinematic color presets mapped to pre-compiled Hald CLUT Level 8 assets.
 */
enum class CapCutPreset(val displayName: String, val assetFileName: String?) {
    NONE("Original", null),
    TEAL_AND_ORANGE("Teal & Orange", "teal_and_orange.png"),
    VIRAL_WARM_POP("Viral Warm Pop", "viral_warm_pop.png"),
    MOODY_NOIR("Moody Noir", "moody_noir.png"),
    STUDIO_BRIGHT("Studio Bright", "studio_bright.png")
}

/**
 * Super-resolution scaling target dimensions.
 */
enum class TargetResolution(val width: Int, val height: Int, val label: String) {
    RES_720P(1280, 720, "720p HD"),
    RES_1080P(1920, 1080, "1080p FHD"),
    RES_1440P(2560, 1440, "1440p 2K"),
    UHD_4K(3840, 2160, "4K UHD")
}

/**
 * Configuration payload for the PolarSnap remaster pipeline.
 */
data class RemasterConfig(
    val enableSuperResolution: Boolean = true, // Lanczos 4K upscale
    val targetResolution: TargetResolution = TargetResolution.UHD_4K,
    val enableSharpening: Boolean = true,
    val colorGradingPreset: CapCutPreset = CapCutPreset.NONE,
    val lutIntensity: Float = 1.0f // 0.0f .. 1.0f
) {
    init {
        require(lutIntensity in 0.0f..1.0f) {
            "LUT intensity must be within [0.0, 1.0], was: $lutIntensity"
        }
    }
}

/**
 * High-level contract for media remastering and color grading.
 */
interface RemasterPipeline {
    suspend fun processMedia(
        sourceFile: String,
        destinationFile: String,
        config: RemasterConfig,
        onProgress: (Float) -> Unit
    ): Result<String>
}

/**
 * Typed domain exceptions for remaster pipeline error sanitization.
 */
sealed class RemasterException(message: String, cause: Throwable? = null) : Exception(message, cause) {
    class SourceNotFoundException(filePath: String) :
        RemasterException("Remaster source media file not found: $filePath")

    class LutAssetMissingException(preset: CapCutPreset, path: String) :
        RemasterException("Required Hald CLUT asset for preset ${preset.displayName} is missing at: $path")

    class TranscodeFailedException(val exitCode: Int, val rawError: String) :
        RemasterException("Remaster transcode failed with exit code $exitCode: $rawError")

    class HardwareCodecException(val codec: String, val reason: String) :
        RemasterException("Hardware codec $codec failed: $reason")

    class TranscodeCancelledException :
        RemasterException("Remaster transcode operation was cancelled")
}

/**
 * Telemetry report proving pre-upscale RAM savings.
 */
data class MemoryOptimizationReport(
    val sourceResolution: String,
    val targetResolution: String,
    val preUpscaleFrameBytes: Long,
    val postUpscaleFrameBytes: Long,
    val bytesSavedPerFrame: Long,
    val savingsPercent: Float,
    val description: String
)
