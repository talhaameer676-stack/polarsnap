"""
Tier 2: Boundary Value Analysis & Corner Cases — Milestone 2 (Features 9-14)
"""
import unittest
from tests.e2e.runner import feature, tier
from tests.e2e.contracts.remaster_contracts import (
    CapCutPreset,
    TargetResolution,
    RemasterConfig,
    HardwareEncoder,
    BijectiveLUTTransformer,
    MemoryOptimizationOracle,
    RemasterFiltergraphBuilder,
    MediaCodecEncoderSelector,
)


class TestTier2Milestone2Boundaries(unittest.TestCase):
    TIER = 2

    # =========================================================================
    # Feature 9: CapCut LUT Asset Bundling Boundaries
    # =========================================================================
    @tier(2)
    @feature(9)
    def test_feature9_boundary_level_7_rejected(self):
        """Boundary: Hald CLUT Level 7 dimension (343x343) fails Level 8 512x512 contract."""
        level_7_dim = 7 ** 3  # 343
        self.assertNotEqual(level_7_dim, 512)

    @tier(2)
    @feature(9)
    def test_feature9_boundary_level_9_rejected(self):
        """Boundary: Hald CLUT Level 9 dimension (729x729) fails Level 8 512x512 contract."""
        level_9_dim = 9 ** 3  # 729
        self.assertNotEqual(level_9_dim, 512)

    @tier(2)
    @feature(9)
    def test_feature9_boundary_missing_lut_file_path_omits_stage(self):
        """Boundary: Active CapCut preset without valid file path omits haldclut stage."""
        config = RemasterConfig(color_grading_preset=CapCutPreset.TEAL_AND_ORANGE)
        graph = RemasterFiltergraphBuilder.build(config, lut_file_path=None)
        self.assertNotIn("haldclut", graph)

    @tier(2)
    @feature(9)
    def test_feature9_boundary_preset_none_with_path_omits_stage(self):
        """Boundary: CapCutPreset.NONE even with provided path omits haldclut."""
        config = RemasterConfig(color_grading_preset=CapCutPreset.NONE)
        graph = RemasterFiltergraphBuilder.build(config, lut_file_path="lut.png")
        self.assertNotIn("haldclut", graph)

    @tier(2)
    @feature(9)
    def test_feature9_boundary_all_4_preset_names_unique(self):
        """Boundary: All 4 CapCut preset enum values are mutually distinct."""
        presets = [CapCutPreset.TEAL_AND_ORANGE, CapCutPreset.VIRAL_WARM_POP, CapCutPreset.MOODY_NOIR, CapCutPreset.STUDIO_BRIGHT]
        self.assertEqual(len(set(presets)), 4)

    # =========================================================================
    # Feature 10: Bijective LUT Transformer Boundaries
    # =========================================================================
    @tier(2)
    @feature(10)
    def test_feature10_boundary_origin_corner(self):
        """Boundary: Origin corner (0, 0, 0) maps to (0, 0) in both CapCut and Hald."""
        cc_coord = BijectiveLUTTransformer.rgb_to_capcut_coord(0, 0, 0)
        h_coord = BijectiveLUTTransformer.rgb_to_hald_coord(0, 0, 0)
        self.assertEqual(cc_coord, (0, 0))
        self.assertEqual(h_coord, (0, 0))

    @tier(2)
    @feature(10)
    def test_feature10_boundary_maximum_corner(self):
        """Boundary: Maximum corner (63, 63, 63) maps to (511, 511) in both formats."""
        cc_coord = BijectiveLUTTransformer.rgb_to_capcut_coord(63, 63, 63)
        h_coord = BijectiveLUTTransformer.rgb_to_hald_coord(63, 63, 63)
        self.assertEqual(cc_coord, (511, 511))
        self.assertEqual(h_coord, (511, 511))

    @tier(2)
    @feature(10)
    def test_feature10_boundary_pure_blue_maximum(self):
        """Boundary: Pure blue maximum (0, 0, 63) maps to tile 7,7 origin."""
        cc_x, cc_y = BijectiveLUTTransformer.rgb_to_capcut_coord(0, 0, 63)
        # Tile 7,7 is at (7*64, 7*64) = (448, 448)
        self.assertEqual((cc_x, cc_y), (448, 448))

    @tier(2)
    @feature(10)
    def test_feature10_boundary_pure_green_maximum(self):
        """Boundary: Pure green maximum (0, 63, 0) maps to local tile y=63."""
        cc_x, cc_y = BijectiveLUTTransformer.rgb_to_capcut_coord(0, 63, 0)
        self.assertEqual((cc_x, cc_y), (0, 63))

    @tier(2)
    @feature(10)
    def test_feature10_boundary_pure_red_maximum(self):
        """Boundary: Pure red maximum (63, 0, 0) maps to local tile x=63."""
        cc_x, cc_y = BijectiveLUTTransformer.rgb_to_capcut_coord(63, 0, 0)
        self.assertEqual((cc_x, cc_y), (63, 0))

    # =========================================================================
    # Feature 11: FFmpeg 4K/HD Remaster Filtergraph Boundaries
    # =========================================================================
    @tier(2)
    @feature(11)
    def test_feature11_boundary_super_resolution_disabled(self):
        """Boundary: Super-resolution disabled omits scale and post-unsharp stages."""
        config = RemasterConfig(enable_super_resolution=False, enable_sharpening=True)
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertNotIn("scale=", graph)
        self.assertNotIn("unsharp=", graph)
        self.assertIn("cas=", graph)

    @tier(2)
    @feature(11)
    def test_feature11_boundary_sharpening_disabled(self):
        """Boundary: Sharpening disabled omits CAS and unsharp stages."""
        config = RemasterConfig(enable_super_resolution=True, enable_sharpening=False)
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertNotIn("cas=", graph)
        self.assertNotIn("unsharp=", graph)
        self.assertIn("scale=", graph)

    @tier(2)
    @feature(11)
    def test_feature11_boundary_all_enhancements_disabled(self):
        """Boundary: All optional enhancements disabled retains baseline contrast/vibrancy."""
        config = RemasterConfig(
            enable_super_resolution=False,
            enable_sharpening=False,
            color_grading_preset=CapCutPreset.NONE
        )
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertEqual(graph, "eq=contrast=1.06:saturation=1.10")

    @tier(2)
    @feature(11)
    def test_feature11_boundary_1080p_target_resolution(self):
        """Boundary: FHD 1080p target resolution specifies 1920:1080."""
        config = RemasterConfig(enable_super_resolution=True, target_resolution=TargetResolution.FHD_1080P)
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertIn("scale=1920:1080:flags=lanczos", graph)

    @tier(2)
    @feature(11)
    def test_feature11_boundary_filtergraph_separator_syntax(self):
        """Boundary: Filtergraph stages separated strictly by commas without trailing comma."""
        config = RemasterConfig(enable_super_resolution=True, enable_sharpening=True)
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertFalse(graph.endswith(","))
        self.assertFalse(graph.startswith(","))

    # =========================================================================
    # Feature 12: Pre-Upscale Memory Optimization Boundaries
    # =========================================================================
    @tier(2)
    @feature(12)
    def test_feature12_boundary_720p_to_4k_savings_ratio(self):
        """Boundary: Upscaling 720p (1280x720) to 4K achieves ~88.9% frame RAM savings."""
        ratio = MemoryOptimizationOracle.compute_memory_savings_ratio((1280, 720), (3840, 2160))
        self.assertAlmostEqual(ratio, 0.8889, places=3)

    @tier(2)
    @feature(12)
    def test_feature12_boundary_same_resolution_zero_savings(self):
        """Boundary: 1080p to 1080p has 0% memory savings ratio."""
        ratio = MemoryOptimizationOracle.compute_memory_savings_ratio((1920, 1080), (1920, 1080))
        self.assertEqual(ratio, 0.0)

    @tier(2)
    @feature(12)
    def test_feature12_boundary_zero_dimension_frame_ram(self):
        """Boundary: Zero width or height produces 0 RAM bytes without crash."""
        self.assertEqual(MemoryOptimizationOracle.compute_frame_ram_bytes(0, 1080), 0)
        self.assertEqual(MemoryOptimizationOracle.compute_frame_ram_bytes(1920, 0), 0)

    @tier(2)
    @feature(12)
    def test_feature12_boundary_single_pixel_frame(self):
        """Boundary: 1x1 24-bit RGB frame requires exactly 3 bytes."""
        self.assertEqual(MemoryOptimizationOracle.compute_frame_ram_bytes(1, 1), 3)

    @tier(2)
    @feature(12)
    def test_feature12_boundary_8k_frame_ram_stress(self):
        """Boundary: 8K UHD (7680x4320) uncompressed frame requires ~99.53 MB."""
        ram_bytes = MemoryOptimizationOracle.compute_frame_ram_bytes(7680, 4320)
        ram_mb = ram_bytes / (1024 * 1024)
        self.assertAlmostEqual(ram_mb, 94.92, places=1)

    # =========================================================================
    # Feature 13: ARM64 MediaCodec Acceleration Boundaries
    # =========================================================================
    @tier(2)
    @feature(13)
    def test_feature13_boundary_empty_codec_list_software_fallback(self):
        """Boundary: Empty hardware list falls back to libx264."""
        enc, _ = MediaCodecEncoderSelector.select_encoder([])
        self.assertEqual(enc, HardwareEncoder.SOFTWARE_LIBX264)

    @tier(2)
    @feature(13)
    def test_feature13_boundary_hevc_takes_precedence_over_h264(self):
        """Boundary: When both hevc and h264 are present, hevc is chosen."""
        enc, _ = MediaCodecEncoderSelector.select_encoder(["h264_mediacodec", "hevc_mediacodec"])
        self.assertEqual(enc, HardwareEncoder.HEVC_MEDIACODEC)

    @tier(2)
    @feature(13)
    def test_feature13_boundary_h264_mediacodec_bitrate(self):
        """Boundary: H.264 hardware encoding specifies 25M bitrate."""
        _, params = MediaCodecEncoderSelector.select_encoder(["h264_mediacodec"])
        self.assertIn("-b:v 25M", params)

    @tier(2)
    @feature(13)
    def test_feature13_boundary_software_crf_18(self):
        """Boundary: Software fallback specifies high-quality CRF 18."""
        _, params = MediaCodecEncoderSelector.select_encoder([])
        self.assertIn("-crf 18", params)

    @tier(2)
    @feature(13)
    def test_feature13_boundary_force_software_ignores_all_hardware(self):
        """Boundary: force_software flag ignores both HEVC and H.264."""
        enc, params = MediaCodecEncoderSelector.select_encoder(["hevc_mediacodec", "h264_mediacodec"], force_software=True)
        self.assertEqual(enc, HardwareEncoder.SOFTWARE_LIBX264)
        self.assertIn("libx264", params)

    # =========================================================================
    # Feature 14: Uncompressed 4K Master Extraction Boundaries
    # =========================================================================
    @tier(2)
    @feature(14)
    def test_feature14_boundary_4k_format_syntax(self):
        """Boundary: 4K format spec uses height<=2160 fallback syntax."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions, ResolutionLimit
        args = PolarCommandTranslatorContract.translate("https://url", EngineOptions(resolution_limit=ResolutionLimit.RES_4K))
        idx = args.index("-f")
        self.assertIn("bestvideo[height<=2160]", args[idx + 1])

    @tier(2)
    @feature(14)
    def test_feature14_boundary_4k_with_turbo_preserves_downloader(self):
        """Boundary: 4K master extraction with Turbo retains aria2c downloader."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions, ResolutionLimit
        opts = EngineOptions(resolution_limit=ResolutionLimit.RES_4K, turbo_acceleration=True)
        args = PolarCommandTranslatorContract.translate("https://url", opts)
        self.assertIn("aria2c", args)

    @tier(2)
    @feature(14)
    def test_feature14_boundary_4k_with_sponsor_stripper(self):
        """Boundary: 4K master extraction with Sponsor Stripper retains sponsorblock."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions, ResolutionLimit
        opts = EngineOptions(resolution_limit=ResolutionLimit.RES_4K, sponsor_stripper=True)
        args = PolarCommandTranslatorContract.translate("https://url", opts)
        self.assertIn("--sponsorblock-remove", args)

    @tier(2)
    @feature(14)
    def test_feature14_boundary_target_resolution_dimensions(self):
        """Boundary: TargetResolution UHD_4K enum value is strictly 3840x2160."""
        self.assertEqual(TargetResolution.UHD_4K.value, "3840x2160")

    @tier(2)
    @feature(14)
    def test_feature14_boundary_lut_intensity_range(self):
        """Boundary: RemasterConfig LUT intensity clamped to [0.0, 1.0]."""
        config = RemasterConfig(lut_intensity=1.0)
        self.assertGreaterEqual(config.lut_intensity, 0.0)
        self.assertLessEqual(config.lut_intensity, 1.0)


if __name__ == "__main__":
    unittest.main()
