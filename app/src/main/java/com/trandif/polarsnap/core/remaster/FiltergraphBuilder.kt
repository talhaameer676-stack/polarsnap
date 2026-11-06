package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.CapCutPreset
import com.trandif.polarsnap.domain.remaster.MemoryOptimizationReport
import com.trandif.polarsnap.domain.remaster.RemasterConfig
import com.trandif.polarsnap.domain.remaster.TargetResolution
import java.util.Locale

/**
 * Filter stages executed in the 5-stage FFmpeg remaster pipeline.
 */
enum class FilterStage(val stageNumber: Int, val stageName: String, val isPreUpscale: Boolean) {
    CAS_SHARPENING(1, "Contrast Adaptive Sharpening (AMD FidelityFX CAS)", true),
    EQ_VIBRANCE(2, "Dynamic Range & Vibrance Equalization", true),
    HALDCLUT_GRADING(3, "Hald CLUT Color Grading & Intensity Blending", true),
    LANCZOS_SCALING(4, "Aspect-Ratio Safe Lanczos Super-Resolution Scaling", false),
    UNSHARP_RECOVERY(5, "Post-Upscale High-Frequency Edge Polish", false)
}

/**
 * Output model containing the generated filtergraph string, input bindings,
 * verified filter stages, and memory optimization metrics.
 */
data class FiltergraphResult(
    val filtergraph: String,
    val inputCount: Int,
    val stages: List<FilterStage>,
    val memoryReport: MemoryOptimizationReport,
    val usesHaldClut: Boolean,
    val targetWidth: Int,
    val targetHeight: Int
)

/**
 * Constructs studio-grade FFmpeg filtergraphs for 4K/HD remastering and CapCut color grading.
 *
 * Pre-Upscale Memory Optimization:
 * Color grading (Hald CLUT) and detail enhancement (CAS, eq) are applied strictly BEFORE
 * Lanczos super-resolution scaling.
 *
 * Frame RAM calculations (RGB24 / NV12 equivalent buffer):
 * - 1080p frame (1920x1080x3): ~6.22 MB (6,220,800 bytes)
 * - 4K frame (3840x2160x3): ~24.88 MB (24,883,200 bytes)
 * Pre-upscale processing saves 18.66 MB per frame buffer in the multi-stage filtergraph (~75% reduction),
 * preventing Android Low Memory Killer (LMK) aborts during 4K transcode.
 */
class FiltergraphBuilder(
    val casStrength: Float = 0.50f,
    val eqContrast: Float = 1.06f,
    val eqSaturation: Float = 1.10f,
    val unsharpLumaMatrix: Int = 5,
    val unsharpLumaAmount: Float = 0.40f,
    val unsharpChromaMatrix: Int = 5,
    val unsharpChromaAmount: Float = 0.20f
) {

    init {
        require(casStrength in 0.0f..1.0f) { "CAS strength must be in [0.0, 1.0], was: $casStrength" }
        require(eqContrast > 0.0f) { "Contrast must be positive, was: $eqContrast" }
        require(eqSaturation >= 0.0f) { "Saturation must be non-negative, was: $eqSaturation" }
    }

    /**
     * Calculates the estimated uncompressed RGB frame buffer memory footprint in bytes.
     */
    fun calculateEstimatedFrameMemory(width: Int, height: Int, bytesPerPixel: Int = 3): Long {
        require(width > 0 && height > 0) { "Dimensions must be positive" }
        return width.toLong() * height.toLong() * bytesPerPixel.toLong()
    }

    /**
     * Evaluates and returns a verified memory savings report comparing pre-upscale vs post-upscale filtering.
     */
    fun verifyPreUpscaleMemorySavings(
        sourceWidth: Int,
        sourceHeight: Int,
        targetResolution: TargetResolution
    ): MemoryOptimizationReport {
        val (effectiveTargetW, effectiveTargetH) = resolveTargetDimensions(
            sourceWidth,
            sourceHeight,
            targetResolution
        )

        val preBytes = calculateEstimatedFrameMemory(sourceWidth, sourceHeight)
        val postBytes = calculateEstimatedFrameMemory(effectiveTargetW, effectiveTargetH)
        val savedBytes = (postBytes - preBytes).coerceAtLeast(0L)
        val savingsPercent = if (postBytes > 0) (savedBytes.toFloat() / postBytes.toFloat()) * 100f else 0f

        return MemoryOptimizationReport(
            sourceResolution = "${sourceWidth}x${sourceHeight}",
            targetResolution = "${effectiveTargetW}x${effectiveTargetH}",
            preUpscaleFrameBytes = preBytes,
            postUpscaleFrameBytes = postBytes,
            bytesSavedPerFrame = savedBytes,
            savingsPercent = savingsPercent,
            description = String.format(
                Locale.US,
                "Pre-upscale color grading saves %.2f MB per frame (%.1f%% RAM savings) relative to post-upscale processing.",
                savedBytes.toDouble() / (1024.0 * 1024.0),
                savingsPercent
            )
        )
    }

    /**
     * Resolves the target scaling bounding box while respecting aspect orientation (landscape vs portrait).
     */
    fun resolveTargetDimensions(
        sourceWidth: Int,
        sourceHeight: Int,
        targetResolution: TargetResolution
    ): Pair<Int, Int> {
        val isPortrait = sourceHeight > sourceWidth
        val baseW = targetResolution.width
        val baseH = targetResolution.height

        return if (isPortrait) {
            val portraitW = minOf(baseW, baseH)
            val portraitH = maxOf(baseW, baseH)
            Pair(portraitW, portraitH)
        } else {
            val landscapeW = maxOf(baseW, baseH)
            val landscapeH = minOf(baseW, baseH)
            Pair(landscapeW, landscapeH)
        }
    }

    /**
     * Builds the complete 5-stage FFmpeg filtergraph string according to the given configuration.
     *
     * @param config Remaster options (preset, intensity, sharpening, super-resolution)
     * @param lutInputIndex Zero-based FFmpeg input index for the Hald CLUT asset (typically 1 when present)
     * @param sourceWidth Input media horizontal resolution
     * @param sourceHeight Input media vertical resolution
     * @param outputPixelFormat Output format tag (defaults to "nv12" for Android MediaCodec)
     */
    fun buildFiltergraph(
        config: RemasterConfig,
        lutInputIndex: Int = 1,
        sourceWidth: Int = 1920,
        sourceHeight: Int = 1080,
        outputPixelFormat: String = "nv12"
    ): FiltergraphResult {
        val activeStages = mutableListOf<FilterStage>()
        val segments = mutableListOf<String>()

        val (targetW, targetH) = resolveTargetDimensions(
            sourceWidth,
            sourceHeight,
            config.targetResolution
        )

        // Stage 1 & 2: Pre-Enhancement (Sharpening & Vibrance) at SOURCE RESOLUTION (Pre-upscale)
        var currentOutput = "0:v"
        val preFilters = mutableListOf<String>()

        if (config.enableSharpening) {
            preFilters.add(String.format(Locale.US, "cas=strength=%.2f", casStrength))
            activeStages.add(FilterStage.CAS_SHARPENING)
        }

        preFilters.add(String.format(Locale.US, "eq=contrast=%.2f:saturation=%.2f", eqContrast, eqSaturation))
        activeStages.add(FilterStage.EQ_VIBRANCE)

        val preOutTag = "pre"
        segments.add("[$currentOutput]${preFilters.joinToString(",")}[$preOutTag]")
        currentOutput = preOutTag

        // Stage 3: Hald CLUT Color Grading at SOURCE RESOLUTION
        val usesHaldClut = config.colorGradingPreset != CapCutPreset.NONE
        if (usesHaldClut) {
            activeStages.add(FilterStage.HALDCLUT_GRADING)
            val lutInputTag = "$lutInputIndex:v"

            if (config.lutIntensity >= 0.999f) {
                // Direct 100% Hald CLUT mapping
                val gradedTag = "graded"
                segments.add("[$currentOutput][$lutInputTag]haldclut=shortest=1:repeatlast=1[$gradedTag]")
                currentOutput = gradedTag
            } else {
                // Intensity blending: split pre-stream, grade one copy, blend back with opacity
                val splitOrig = "orig"
                val splitToLut = "to_lut"
                val rawGraded = "graded_raw"
                val blendedTag = "graded"

                segments.add("[$currentOutput]split=2[$splitOrig][$splitToLut]")
                segments.add("[$splitToLut][$lutInputTag]haldclut=shortest=1:repeatlast=1[$rawGraded]")
                segments.add(
                    String.format(
                        Locale.US,
                        "[%s][%s]blend=all_mode=normal:all_opacity=%.2f[%s]",
                        splitOrig,
                        rawGraded,
                        config.lutIntensity,
                        blendedTag
                    )
                )
                currentOutput = blendedTag
            }
        }

        // Stage 4: Aspect-Ratio Safe Lanczos Super-Resolution Scaling
        if (config.enableSuperResolution) {
            activeStages.add(FilterStage.LANCZOS_SCALING)
            val scaleFilter = String.format(
                Locale.US,
                "scale=w=%d:h=%d:force_original_aspect_ratio=decrease:flags=lanczos",
                targetW,
                targetH
            )
            val padFilter = String.format(
                Locale.US,
                "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black",
                targetW,
                targetH
            )
            val scaledTag = "scaled"
            segments.add("[$currentOutput]$scaleFilter,$padFilter[$scaledTag]")
            currentOutput = scaledTag
        }

        // Stage 5: Post-Upscale Texture Polish (Unsharp Edge Recovery + Color Space Format)
        val postFilters = mutableListOf<String>()
        if (config.enableSharpening) {
            activeStages.add(FilterStage.UNSHARP_RECOVERY)
            postFilters.add(
                String.format(
                    Locale.US,
                    "unsharp=lx=%d:ly=%d:la=%.2f:cx=%d:cy=%d:ca=%.2f",
                    unsharpLumaMatrix,
                    unsharpLumaMatrix,
                    unsharpLumaAmount,
                    unsharpChromaMatrix,
                    unsharpChromaMatrix,
                    unsharpChromaAmount
                )
            )
        }

        if (outputPixelFormat.isNotBlank()) {
            postFilters.add("format=$outputPixelFormat")
        }

        val outTag = "out"
        segments.add("[$currentOutput]${postFilters.joinToString(",")}[$outTag]")

        val fullFiltergraph = segments.joinToString(";")
        val memoryReport = verifyPreUpscaleMemorySavings(sourceWidth, sourceHeight, config.targetResolution)

        return FiltergraphResult(
            filtergraph = fullFiltergraph,
            inputCount = if (usesHaldClut) 2 else 1,
            stages = activeStages,
            memoryReport = memoryReport,
            usesHaldClut = usesHaldClut,
            targetWidth = targetW,
            targetHeight = targetH
        )
    }
}
