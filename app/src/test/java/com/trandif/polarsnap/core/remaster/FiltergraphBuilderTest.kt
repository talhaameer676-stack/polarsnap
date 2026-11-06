package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.CapCutPreset
import com.trandif.polarsnap.domain.remaster.RemasterConfig
import com.trandif.polarsnap.domain.remaster.TargetResolution
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class FiltergraphBuilderTest {

    private val builder = FiltergraphBuilder()

    @Test
    fun testFullFiveStageFiltergraphWithTealAndOrangeFullIntensity() {
        val config = RemasterConfig(
            enableSuperResolution = true,
            targetResolution = TargetResolution.UHD_4K,
            enableSharpening = true,
            colorGradingPreset = CapCutPreset.TEAL_AND_ORANGE,
            lutIntensity = 1.0f
        )

        val result = builder.buildFiltergraph(
            config = config,
            lutInputIndex = 1,
            sourceWidth = 1920,
            sourceHeight = 1080,
            outputPixelFormat = "nv12"
        )

        // Verify all 5 stages are active
        assertEquals(5, result.stages.size)
        assertTrue(result.stages.contains(FilterStage.CAS_SHARPENING))
        assertTrue(result.stages.contains(FilterStage.EQ_VIBRANCE))
        assertTrue(result.stages.contains(FilterStage.HALDCLUT_GRADING))
        assertTrue(result.stages.contains(FilterStage.LANCZOS_SCALING))
        assertTrue(result.stages.contains(FilterStage.UNSHARP_RECOVERY))

        // Verify 2 inputs required (video + LUT)
        assertEquals(2, result.inputCount)
        assertTrue(result.usesHaldClut)

        // Verify filter elements
        val fg = result.filtergraph
        assertTrue(fg.contains("cas=strength=0.50"), "Should contain CAS sharpening")
        assertTrue(fg.contains("eq=contrast=1.06:saturation=1.10"), "Should contain contrast/vibrance eq")
        assertTrue(fg.contains("[1:v]haldclut=shortest=1:repeatlast=1"), "Should bind input 1:v to haldclut")
        assertTrue(fg.contains("scale=w=3840:h=2160:force_original_aspect_ratio=decrease:flags=lanczos"), "Should contain Lanczos 4K scaling")
        assertTrue(fg.contains("pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=black"), "Should contain aspect letterbox padding")
        assertTrue(fg.contains("unsharp=lx=5:ly=5:la=0.40:cx=5:cy=5:ca=0.20"), "Should contain unsharp edge recovery")
        assertTrue(fg.contains("format=nv12[out]"), "Should format output to nv12")
    }

    @Test
    fun testIntensityBlendingFiltergraphWhenIntensityLessThanOne() {
        val config = RemasterConfig(
            enableSuperResolution = true,
            targetResolution = TargetResolution.UHD_4K,
            enableSharpening = true,
            colorGradingPreset = CapCutPreset.VIRAL_WARM_POP,
            lutIntensity = 0.75f
        )

        val result = builder.buildFiltergraph(config)
        val fg = result.filtergraph

        assertTrue(fg.contains("split=2[orig][to_lut]"), "Should split pre-stream for blending")
        assertTrue(fg.contains("[to_lut][1:v]haldclut=shortest=1:repeatlast=1[graded_raw]"), "Should grade split stream")
        assertTrue(fg.contains("[orig][graded_raw]blend=all_mode=normal:all_opacity=0.75[graded]"), "Should blend with opacity 0.75")
    }

    @Test
    fun testFiltergraphWithoutLutPresetNone() {
        val config = RemasterConfig(
            enableSuperResolution = true,
            targetResolution = TargetResolution.UHD_4K,
            enableSharpening = true,
            colorGradingPreset = CapCutPreset.NONE
        )

        val result = builder.buildFiltergraph(config)

        assertFalse(result.usesHaldClut)
        assertEquals(1, result.inputCount)
        assertFalse(result.filtergraph.contains("haldclut"))
        assertEquals(4, result.stages.size)
    }

    @Test
    fun testFiltergraphWithoutSharpening() {
        val config = RemasterConfig(
            enableSuperResolution = true,
            targetResolution = TargetResolution.UHD_4K,
            enableSharpening = false,
            colorGradingPreset = CapCutPreset.MOODY_NOIR
        )

        val result = builder.buildFiltergraph(config)
        val fg = result.filtergraph

        assertFalse(fg.contains("cas="))
        assertFalse(fg.contains("unsharp="))
        assertTrue(fg.contains("eq=contrast=1.06:saturation=1.10"))
        assertTrue(fg.contains("haldclut="))
        assertTrue(fg.contains("scale="))
    }

    @Test
    fun testPortraitOrientationAspectRatioSafeTargetDimensions() {
        // Portrait 9:16 video (e.g. 1080x1920)
        val (w, h) = builder.resolveTargetDimensions(1080, 1920, TargetResolution.UHD_4K)
        assertEquals(2160, w, "Portrait width should be 2160")
        assertEquals(3840, h, "Portrait height should be 3840")

        // Landscape 16:9 video (e.g. 1920x1080)
        val (lw, lh) = builder.resolveTargetDimensions(1920, 1080, TargetResolution.UHD_4K)
        assertEquals(3840, lw, "Landscape width should be 3840")
        assertEquals(2160, lh, "Landscape height should be 2160")
    }

    @Test
    fun testPreUpscaleMemoryOptimizationGuaranteesSeventyFivePercentSavings() {
        // 1080p source -> 4K target
        val report = builder.verifyPreUpscaleMemorySavings(1920, 1080, TargetResolution.UHD_4K)

        // 1920 * 1080 * 3 = 6,220,800 bytes (~6.22 MB)
        assertEquals(6220800L, report.preUpscaleFrameBytes)

        // 3840 * 2160 * 3 = 24,883,200 bytes (~24.88 MB)
        assertEquals(24883200L, report.postUpscaleFrameBytes)

        // Saved bytes: 24,883,200 - 6,220,800 = 18,662,400 bytes (~18.66 MB)
        assertEquals(18662400L, report.bytesSavedPerFrame)

        // 18,662,400 / 24,883,200 = exactly 75.0%
        assertEquals(75.0f, report.savingsPercent, 0.001f)

        // Verify filter order in generated filtergraph:
        // Pre-upscale filters ([pre], [graded]) must appear before [scaled]
        val result = builder.buildFiltergraph(
            RemasterConfig(
                enableSuperResolution = true,
                colorGradingPreset = CapCutPreset.TEAL_AND_ORANGE
            )
        )

        val casIdx = result.filtergraph.indexOf("cas=")
        val eqIdx = result.filtergraph.indexOf("eq=")
        val haldIdx = result.filtergraph.indexOf("haldclut=")
        val scaleIdx = result.filtergraph.indexOf("scale=")
        val unsharpIdx = result.filtergraph.indexOf("unsharp=")

        assertTrue(casIdx < scaleIdx, "CAS sharpening must occur before Lanczos scaling")
        assertTrue(eqIdx < scaleIdx, "Equalization must occur before Lanczos scaling")
        assertTrue(haldIdx < scaleIdx, "Hald CLUT color grading must occur before Lanczos scaling")
        assertTrue(scaleIdx < unsharpIdx, "Lanczos scaling must occur before post-upscale unsharp recovery")
    }
}
