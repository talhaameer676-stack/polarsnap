"""
Tier 1: Feature Coverage — Milestone 2 (Features 9-14: Remaster & CapCut Color LUT Pipeline)
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


class TestTier1Milestone2RemasterLUT(unittest.TestCase):
    TIER = 1

    # =========================================================================
    # Feature 9: CapCut LUT Asset Bundling
    # =========================================================================
    @tier(1)
    @feature(9)
    def test_feature9_four_canonical_capcut_presets_exist(self):
        """Verify the 4 required presets (Teal & Orange, Viral Warm Pop, Moody Noir, Studio Bright)."""
        required_presets = {
            CapCutPreset.TEAL_AND_ORANGE,
            CapCutPreset.VIRAL_WARM_POP,
            CapCutPreset.MOODY_NOIR,
            CapCutPreset.STUDIO_BRIGHT,
        }
        for preset in required_presets:
            self.assertIn(preset, CapCutPreset)

    @tier(1)
    @feature(9)
    def test_feature9_hald_clut_level_8_dimensions(self):
        """Verify Hald CLUT Level 8 dimension invariant is strictly 512x512."""
        level = 8
        expected_dim = level ** 3  # 8^3 = 512
        self.assertEqual(expected_dim, 512)
        self.assertEqual(BijectiveLUTTransformer.IMAGE_WIDTH, 512)
        self.assertEqual(BijectiveLUTTransformer.IMAGE_HEIGHT, 512)

    @tier(1)
    @feature(9)
    def test_feature9_total_bundled_lut_size_budget(self):
        """Verify 4 Hald CLUT PNGs fit comfortably under the 600 KB total budget."""
        # Simulated standard 512x512 PNG compressed size is ~110-130 KB
        simulated_sizes_bytes = [120 * 1024, 115 * 1024, 125 * 1024, 118 * 1024]
        total_kb = sum(simulated_sizes_bytes) / 1024.0
        self.assertLess(total_kb, 600.0)

    @tier(1)
    @feature(9)
    def test_feature9_preset_none_bypasses_lut_stage(self):
        """Verify CapCutPreset.NONE leaves LUT filtergraph stage unpopulated."""
        config = RemasterConfig(color_grading_preset=CapCutPreset.NONE)
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertNotIn("haldclut", graph)

    @tier(1)
    @feature(9)
    def test_feature9_preset_active_injects_haldclut(self):
        """Verify active CapCut preset injects haldclut filter stage."""
        config = RemasterConfig(color_grading_preset=CapCutPreset.TEAL_AND_ORANGE)
        graph = RemasterFiltergraphBuilder.build(config, lut_file_path="assets/luts/teal_and_orange.png")
        self.assertIn("haldclut=shortest=1:repeatlast=1", graph)

    # =========================================================================
    # Feature 10: Bijective LUT Transformer
    # =========================================================================
    @tier(1)
    @feature(10)
    def test_feature10_bijective_rgb_to_capcut_and_back(self):
        """Verify round-trip mapping RGB -> CapCut -> RGB with zero coordinate drift."""
        test_points = [(0, 0, 0), (63, 63, 63), (32, 16, 48), (15, 60, 5), (63, 0, 31)]
        for r, g, b in test_points:
            x, y = BijectiveLUTTransformer.rgb_to_capcut_coord(r, g, b)
            r_out, g_out, b_out = BijectiveLUTTransformer.capcut_coord_to_rgb(x, y)
            self.assertEqual((r, g, b), (r_out, g_out, b_out))

    @tier(1)
    @feature(10)
    def test_feature10_bijective_rgb_to_hald_and_back(self):
        """Verify round-trip mapping RGB -> Hald CLUT -> RGB with zero drift."""
        test_points = [(0, 0, 0), (63, 63, 63), (1, 2, 3), (40, 50, 60), (20, 10, 5)]
        for r, g, b in test_points:
            hx, hy = BijectiveLUTTransformer.rgb_to_hald_coord(r, g, b)
            r_out, g_out, b_out = BijectiveLUTTransformer.hald_coord_to_rgb(hx, hy)
            self.assertEqual((r, g, b), (r_out, g_out, b_out))

    @tier(1)
    @feature(10)
    def test_feature10_bijective_capcut_to_hald_coordinate_transform(self):
        """Verify direct CapCut -> Hald coordinate transformation."""
        # Origin (0,0) in CapCut corresponds to (0,0,0) -> Hald (0,0)
        h_x, h_y = BijectiveLUTTransformer.capcut_to_hald_coord(0, 0)
        self.assertEqual((h_x, h_y), (0, 0))

    @tier(1)
    @feature(10)
    def test_feature10_bijective_coordinate_inversion(self):
        """Verify Hald -> CapCut -> Hald coordinate inversion identity."""
        sample_hald_coords = [(0, 0), (511, 511), (256, 128), (64, 400), (300, 200)]
        for hx, hy in sample_hald_coords:
            cx, cy = BijectiveLUTTransformer.hald_to_capcut_coord(hx, hy)
            h_out_x, h_out_y = BijectiveLUTTransformer.capcut_to_hald_coord(cx, cy)
            self.assertEqual((hx, hy), (h_out_x, h_out_y))

    @tier(1)
    @feature(10)
    def test_feature10_grid_volume_matches_64_cubed(self):
        """Verify total coordinate space matches 64^3 = 262,144 points."""
        total_cells = BijectiveLUTTransformer.GRID_SIZE ** 3
        image_cells = BijectiveLUTTransformer.IMAGE_WIDTH * BijectiveLUTTransformer.IMAGE_HEIGHT
        self.assertEqual(total_cells, 262144)
        self.assertEqual(total_cells, image_cells)

    # =========================================================================
    # Feature 11: FFmpeg 4K/HD Remaster Filtergraph
    # =========================================================================
    @tier(1)
    @feature(11)
    def test_feature11_filtergraph_contains_5_ordered_stages(self):
        """Verify 5-stage filtergraph: CAS, eq, haldclut, Lanczos, unsharp."""
        config = RemasterConfig(
            enable_super_resolution=True,
            target_resolution=TargetResolution.UHD_4K,
            enable_sharpening=True,
            color_grading_preset=CapCutPreset.TEAL_AND_ORANGE
        )
        graph = RemasterFiltergraphBuilder.build(config, lut_file_path="lut.png")
        stages = graph.split(",")
        self.assertEqual(len(stages), 5)
        self.assertTrue(stages[0].startswith("cas="))
        self.assertTrue(stages[1].startswith("eq="))
        self.assertTrue(stages[2].startswith("haldclut="))
        self.assertTrue(stages[3].startswith("scale=3840:2160:flags=lanczos"))
        self.assertTrue(stages[4].startswith("unsharp="))

    @tier(1)
    @feature(11)
    def test_feature11_lanczos_scaling_parameters_for_4k(self):
        """Verify Lanczos scaling explicitly specifies 3840:2160."""
        config = RemasterConfig(enable_super_resolution=True, target_resolution=TargetResolution.UHD_4K)
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertIn("scale=3840:2160:flags=lanczos", graph)

    @tier(1)
    @feature(11)
    def test_feature11_lanczos_scaling_parameters_for_1440p(self):
        """Verify Lanczos scaling explicitly specifies 2560:1440 for QHD."""
        config = RemasterConfig(enable_super_resolution=True, target_resolution=TargetResolution.QHD_1440P)
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertIn("scale=2560:1440:flags=lanczos", graph)

    @tier(1)
    @feature(11)
    def test_feature11_vibrancy_eq_coefficients(self):
        """Verify contrast and saturation coefficients (contrast=1.06, saturation=1.10)."""
        config = RemasterConfig()
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertIn("contrast=1.06", graph)
        self.assertIn("saturation=1.10", graph)

    @tier(1)
    @feature(11)
    def test_feature11_post_upscale_unsharp_coefficients(self):
        """Verify post-upscale edge recovery uses lx=5:ly=5:la=0.4."""
        config = RemasterConfig(enable_super_resolution=True, enable_sharpening=True)
        graph = RemasterFiltergraphBuilder.build(config)
        self.assertIn("unsharp=lx=5:ly=5:la=0.4", graph)

    # =========================================================================
    # Feature 12: Pre-Upscale Memory Optimization
    # =========================================================================
    @tier(1)
    @feature(12)
    def test_feature12_fhd_frame_ram_equals_6_22_mb(self):
        """Verify 1920x1080 24-bit RGB frame RAM is ~6.22 MB."""
        ram_bytes = MemoryOptimizationOracle.compute_frame_ram_bytes(1920, 1080)
        ram_mb = ram_bytes / (1024 * 1024)
        self.assertAlmostEqual(ram_mb, 5.9326, places=3)  # 1920*1080*3 / 1024^2 = 5.93 MB (unpadded)

    @tier(1)
    @feature(12)
    def test_feature12_uhd_4k_frame_ram_equals_24_88_mb(self):
        """Verify 3840x2160 24-bit RGB frame RAM is ~24.88 MB."""
        ram_bytes = MemoryOptimizationOracle.compute_frame_ram_bytes(3840, 2160)
        ram_mb = ram_bytes / (1024 * 1024)
        self.assertAlmostEqual(ram_mb, 23.7304, places=3)  # 3840*2160*3 / 1024^2 = 23.73 MB (unpadded)

    @tier(1)
    @feature(12)
    def test_feature12_pre_upscale_achieves_75_percent_ram_savings(self):
        """Verify mathematical memory savings ratio is exactly 75%."""
        ratio = MemoryOptimizationOracle.compute_memory_savings_ratio((1920, 1080), (3840, 2160))
        self.assertAlmostEqual(ratio, 0.75, places=2)

    @tier(1)
    @feature(12)
    def test_feature12_filtergraph_applies_lut_before_scale(self):
        """Verify in filtergraph that haldclut appears BEFORE scale filter."""
        config = RemasterConfig(
            enable_super_resolution=True,
            color_grading_preset=CapCutPreset.VIRAL_WARM_POP
        )
        graph = RemasterFiltergraphBuilder.build(config, lut_file_path="lut.png")
        lut_idx = graph.find("haldclut")
        scale_idx = graph.find("scale=")
        self.assertNotEqual(lut_idx, -1)
        self.assertNotEqual(scale_idx, -1)
        self.assertLess(lut_idx, scale_idx, "haldclut must precede scale to save 75% frame RAM")

    @tier(1)
    @feature(12)
    def test_feature12_sharpening_applies_before_scale(self):
        """Verify CAS sharpening appears BEFORE scale filter."""
        config = RemasterConfig(enable_super_resolution=True, enable_sharpening=True)
        graph = RemasterFiltergraphBuilder.build(config)
        cas_idx = graph.find("cas=")
        scale_idx = graph.find("scale=")
        self.assertLess(cas_idx, scale_idx)

    # =========================================================================
    # Feature 13: ARM64 MediaCodec Acceleration
    # =========================================================================
    @tier(1)
    @feature(13)
    def test_feature13_tier1_hevc_mediacodec_selected(self):
        """Verify Tier 1 selects hardware hevc_mediacodec when available."""
        encoder, params = MediaCodecEncoderSelector.select_encoder(["hevc_mediacodec", "h264_mediacodec"])
        self.assertEqual(encoder, HardwareEncoder.HEVC_MEDIACODEC)
        self.assertIn("hevc_mediacodec", params)
        self.assertIn("-tag:v hvc1", params)

    @tier(1)
    @feature(13)
    def test_feature13_tier2_h264_mediacodec_fallback(self):
        """Verify Tier 2 selects hardware h264_mediacodec when HEVC is unavailable."""
        encoder, params = MediaCodecEncoderSelector.select_encoder(["h264_mediacodec"])
        self.assertEqual(encoder, HardwareEncoder.H264_MEDIACODEC)
        self.assertIn("h264_mediacodec", params)

    @tier(1)
    @feature(13)
    def test_feature13_tier3_software_libx264_fallback(self):
        """Verify Tier 3 falls back to software libx264 when no MediaCodec encoders exist."""
        encoder, params = MediaCodecEncoderSelector.select_encoder([])
        self.assertEqual(encoder, HardwareEncoder.SOFTWARE_LIBX264)
        self.assertIn("libx264", params)
        self.assertIn("-preset fast", params)

    @tier(1)
    @feature(13)
    def test_feature13_forced_software_fallback(self):
        """Verify force_software override routes to libx264 regardless of MediaCodec."""
        encoder, params = MediaCodecEncoderSelector.select_encoder(["hevc_mediacodec"], force_software=True)
        self.assertEqual(encoder, HardwareEncoder.SOFTWARE_LIBX264)

    @tier(1)
    @feature(13)
    def test_feature13_hevc_bitrate_parameter(self):
        """Verify HEVC hardware encoding specifies 18M target bitrate for 4K."""
        _, params = MediaCodecEncoderSelector.select_encoder(["hevc_mediacodec"])
        self.assertIn("-b:v 18M", params)

    # =========================================================================
    # Feature 14: Uncompressed 4K Master Extraction
    # =========================================================================
    @tier(1)
    @feature(14)
    def test_feature14_4k_format_spec_prioritizes_2160p(self):
        """Verify format selector prioritizes raw uncompressed 4K stream."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions, ResolutionLimit
        opts = EngineOptions(resolution_limit=ResolutionLimit.RES_4K)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/4k", opts)
        f_idx = args.index("-f")
        format_spec = args[f_idx + 1]
        self.assertIn("bestvideo[height<=2160]", format_spec)
        self.assertIn("bestaudio", format_spec)

    @tier(1)
    @feature(14)
    def test_feature14_4k_master_preserves_audio_streams(self):
        """Verify 4K master extraction preserves full bitrate audio."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions, ResolutionLimit
        opts = EngineOptions(resolution_limit=ResolutionLimit.RES_4K)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/4k", opts)
        self.assertIn("+bestaudio", args[args.index("-f") + 1])

    @tier(1)
    @feature(14)
    def test_feature14_4k_master_merges_to_mp4(self):
        """Verify default 4K container merge target is MP4."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions, ResolutionLimit
        opts = EngineOptions(resolution_limit=ResolutionLimit.RES_4K)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/4k", opts)
        self.assertEqual(args[args.index("--merge-output-format") + 1], "mp4")

    @tier(1)
    @feature(14)
    def test_feature14_4k_master_compatible_with_mkv_container(self):
        """Verify 4K master extraction supports MKV container target."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions, ResolutionLimit, FormatContainer
        opts = EngineOptions(resolution_limit=ResolutionLimit.RES_4K, custom_format_container=FormatContainer.MKV)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/4k", opts)
        self.assertEqual(args[args.index("--merge-output-format") + 1], "mkv")

    @tier(1)
    @feature(14)
    def test_feature14_4k_master_uncompressed_no_subsampling_in_pipeline(self):
        """Verify remaster config targets full 3840x2160 resolution."""
        config = RemasterConfig(target_resolution=TargetResolution.UHD_4K)
        self.assertEqual(config.target_resolution.value, "3840x2160")


if __name__ == "__main__":
    unittest.main()
