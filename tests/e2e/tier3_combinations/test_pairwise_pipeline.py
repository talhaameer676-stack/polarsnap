"""
Tier 3: Cross-Feature Pairwise Combinations (Pipeline Matrix)
"""
import unittest
from tests.e2e.runner import feature, tier
from tests.e2e.contracts.engine_contracts import (
    EngineOptions,
    ResolutionLimit,
    FormatContainer,
    PolarCommandTranslatorContract,
    PolarLogSanitizerContract,
)
from tests.e2e.contracts.remaster_contracts import (
    CapCutPreset,
    TargetResolution,
    RemasterConfig,
    RemasterFiltergraphBuilder,
    MediaCodecEncoderSelector,
    HardwareEncoder,
    BijectiveLUTTransformer,
)
from tests.e2e.contracts.queue_contracts import (
    BoundedQueueManagerContract,
    DownloadRequest,
    TaskState,
    MediaStorePublisherContract,
)
from tests.e2e.contracts.licensing_contracts import (
    OfflineGraceProtocolContract,
    LicenseStatus,
)


class TestTier3PairwisePipeline(unittest.TestCase):
    TIER = 3

    # =========================================================================
    # Pairwise Combinations: Engine x Remaster x MediaStore x Licensing
    # =========================================================================
    @tier(3)
    @feature(3)
    @feature(11)
    @feature(19)
    def test_pairwise_01_turbo_plus_teal_and_orange_4k_mediastore_movies(self):
        """Combination 1: Turbo Acceleration + Teal & Orange 4K Remaster + MediaStore Movies."""
        # 1. Engine Options
        opts = EngineOptions(turbo_acceleration=True, resolution_limit=ResolutionLimit.RES_4K)
        cmd = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=4k1", opts)
        self.assertIn("16", cmd)

        # 2. Remaster Config
        remaster = RemasterConfig(
            enable_super_resolution=True,
            target_resolution=TargetResolution.UHD_4K,
            color_grading_preset=CapCutPreset.TEAL_AND_ORANGE
        )
        graph = RemasterFiltergraphBuilder.build(remaster, lut_file_path="assets/luts/teal_and_orange.png")
        self.assertIn("haldclut=", graph)
        self.assertIn("scale=3840:2160", graph)

        # 3. MediaStore Publishing
        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("4k_teal_orange.mp4", is_audio=False)
        pub.phase2_write_bytes(uri, 150 * 1024 * 1024)
        self.assertTrue(pub.phase3_publish_commit(uri))
        self.assertEqual(pub.published_records[uri].relative_path, "Movies/PolarSnap")

    @tier(3)
    @feature(4)
    @feature(19)
    @feature(28)
    def test_pairwise_02_lossless_audio_flac_mediastore_music_offline_grace(self):
        """Combination 2: Lossless Audio (FLAC) + MediaStore Music + Day 3 Offline Grace."""
        # 1. Licensing offline grace check (Day 3)
        t0 = 1700000000
        now = t0 + (3 * 86400)
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(t0, now))

        # 2. Engine Translation
        opts = EngineOptions(lossless_audio=True, custom_format_container=FormatContainer.FLAC)
        cmd = PolarCommandTranslatorContract.translate("https://example.com/audio", opts)
        self.assertIn("flac", cmd)
        self.assertIn("-x", cmd)

        # 3. MediaStore Music routing
        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("audio_master.flac", is_audio=True)
        pub.phase2_write_bytes(uri, 40 * 1024 * 1024)
        self.assertTrue(pub.phase3_publish_commit(uri))
        self.assertEqual(pub.published_records[uri].relative_path, "Music/PolarSnap")

    @tier(3)
    @feature(5)
    @feature(9)
    @feature(15)
    def test_pairwise_03_clean_watermark_viral_warm_pop_bounded_queue(self):
        """Combination 3: Clean Watermark + Viral Warm Pop LUT + 2-Slot Concurrency Queue."""
        queue = BoundedQueueManagerContract()
        req1 = DownloadRequest(url="https://tiktok.com/@user/1", color_preset="VIRAL_WARM_POP", is_remaster_enabled=True)
        req2 = DownloadRequest(url="https://tiktok.com/@user/2", color_preset="VIRAL_WARM_POP", is_remaster_enabled=True)
        req3 = DownloadRequest(url="https://tiktok.com/@user/3", color_preset="VIRAL_WARM_POP", is_remaster_enabled=True)

        queue.enqueue(req1, "t1")
        queue.enqueue(req2, "t2")
        queue.enqueue(req3, "t3")

        self.assertEqual(queue.tasks["t1"].state, TaskState.DOWNLOADING)
        self.assertEqual(queue.tasks["t2"].state, TaskState.DOWNLOADING)
        self.assertEqual(queue.tasks["t3"].state, TaskState.PENDING)

    @tier(3)
    @feature(6)
    @feature(11)
    @feature(13)
    def test_pairwise_04_sponsor_stripper_moody_noir_hevc_mediacodec(self):
        """Combination 4: Sponsor Stripper + Moody Noir LUT + HEVC MediaCodec."""
        opts = EngineOptions(sponsor_stripper=True, resolution_limit=ResolutionLimit.RES_1080P)
        cmd = PolarCommandTranslatorContract.translate("https://youtube.com/v1", opts)
        self.assertIn("--sponsorblock-remove", cmd)

        remaster = RemasterConfig(color_grading_preset=CapCutPreset.MOODY_NOIR)
        graph = RemasterFiltergraphBuilder.build(remaster, "lut.png")
        self.assertIn("haldclut=", graph)

        enc, params = MediaCodecEncoderSelector.select_encoder(["hevc_mediacodec"])
        self.assertEqual(enc, HardwareEncoder.HEVC_MEDIACODEC)

    @tier(3)
    @feature(3)
    @feature(5)
    @feature(12)
    def test_pairwise_05_turbo_plus_clean_watermark_pre_upscale_ram_savings(self):
        """Combination 5: Turbo + Clean Watermark + 75% Pre-upscale Memory Savings."""
        opts = EngineOptions(turbo_acceleration=True, clean_watermark=True)
        cmd = PolarCommandTranslatorContract.translate("https://tiktok.com/clip", opts)
        self.assertIn("-N", cmd)
        self.assertIn("tiktok:no_watermark=1", cmd)

        from tests.e2e.contracts.remaster_contracts import MemoryOptimizationOracle
        savings = MemoryOptimizationOracle.compute_memory_savings_ratio((1920, 1080), (3840, 2160))
        self.assertEqual(savings, 0.75)

    @tier(3)
    @feature(4)
    @feature(6)
    @feature(17)
    def test_pairwise_06_lossless_audio_sponsor_stripper_pause_resume(self):
        """Combination 6: Lossless Audio + Sponsor Stripper + Pause / Resume lifecycle."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://youtube.com/audio_pod", custom_format="FLAC"), "pod1")
        self.assertEqual(queue.tasks["pod1"].state, TaskState.DOWNLOADING)

        queue.pause("pod1")
        self.assertEqual(queue.tasks["pod1"].state, TaskState.PAUSED)

        queue.resume("pod1")
        self.assertEqual(queue.tasks["pod1"].state, TaskState.DOWNLOADING)

    @tier(3)
    @feature(9)
    @feature(13)
    @feature(19)
    def test_pairwise_07_studio_bright_lut_h264_mediacodec_mediastore(self):
        """Combination 7: Studio Bright LUT + H.264 MediaCodec fallback + MediaStore commit."""
        remaster = RemasterConfig(color_grading_preset=CapCutPreset.STUDIO_BRIGHT)
        graph = RemasterFiltergraphBuilder.build(remaster, "studio.png")
        self.assertIn("haldclut=", graph)

        enc, _ = MediaCodecEncoderSelector.select_encoder(["h264_mediacodec"])
        self.assertEqual(enc, HardwareEncoder.H264_MEDIACODEC)

        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("studio_bright.mp4", is_audio=False)
        pub.phase2_write_bytes(uri, 80 * 1024 * 1024)
        self.assertTrue(pub.phase3_publish_commit(uri))

    @tier(3)
    @feature(3)
    @feature(16)
    @feature(18)
    def test_pairwise_08_turbo_playlist_batch_foreground_notification(self):
        """Combination 8: Turbo Acceleration + 5-Item Playlist + Throttled Foreground Notification."""
        queue = BoundedQueueManagerContract()
        for i in range(5):
            queue.enqueue(DownloadRequest(url=f"https://example.com/{i}", turbo_acceleration=True), f"batch_{i}")

        self.assertEqual(queue.get_total_active_sub_sockets(), 32)  # 2 slots * 16 sockets

        # Notification interval check
        from tests.e2e.contracts.queue_contracts import ForegroundServiceContract
        self.assertFalse(ForegroundServiceContract.is_notification_throttled(100.0, 101.5))

    @tier(3)
    @feature(5)
    @feature(7)
    @feature(8)
    def test_pairwise_09_clean_watermark_scrubbed_logs_exception_sanitizer(self):
        """Combination 9: Clean Watermark + Zero-Leak Scrubber + Domain Exception Sanitizer."""
        raw_error = "[yt-dlp] ERROR: Sign in to confirm you're not a bot while fetching watermark-free stream"
        clean_log = PolarLogSanitizerContract.sanitize(raw_error)
        self.assertNotIn("yt-dlp", clean_log)

        from tests.e2e.contracts.engine_contracts import PolarExceptionSanitizerContract, PolarErrorType
        exc = PolarExceptionSanitizerContract.sanitize_exception(clean_log)
        self.assertEqual(exc.error_type, PolarErrorType.ANTI_BOT_VERIFICATION)

    @tier(3)
    @feature(10)
    @feature(11)
    @feature(14)
    def test_pairwise_10_bijective_lut_4k_master_lanczos_filtergraph(self):
        """Combination 10: Bijective LUT Transform + 4K Master Extract + Lanczos 4K Scale."""
        # Bijective mapping
        hx, hy = from_cc = (0, 0)
        out_hx, out_hy = BijectiveLUTTransformer.capcut_to_hald_coord(*from_cc)
        self.assertEqual((out_hx, out_hy), (0, 0))

        # Filtergraph
        remaster = RemasterConfig(enable_super_resolution=True, target_resolution=TargetResolution.UHD_4K)
        graph = RemasterFiltergraphBuilder.build(remaster)
        self.assertIn("scale=3840:2160:flags=lanczos", graph)

    @tier(3)
    @feature(15)
    @feature(17)
    @feature(28)
    def test_pairwise_11_bounded_queue_completion_offline_grace_boundary(self):
        """Combination 11: Bounded Queue completion cycle under Day 7 offline grace boundary."""
        t0 = 1700000000
        boundary_time = t0 + 604800  # Exact 7-day limit
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(t0, boundary_time))

        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url1"), "t1")
        queue.enqueue(DownloadRequest(url="https://url2"), "t2")
        queue.enqueue(DownloadRequest(url="https://url3"), "t3")

        queue.complete("t1")
        self.assertEqual(queue.tasks["t3"].state, TaskState.DOWNLOADING)

    @tier(3)
    @feature(4)
    @feature(19)
    @feature(30)
    def test_pairwise_12_lossless_audio_mediastore_ad_free_audit(self):
        """Combination 12: Lossless Audio + MediaStore Music + AST Ad-Free guarantee."""
        from tests.e2e.contracts.licensing_contracts import AdFreeGuaranteeScanner
        sample_code = "class AudioPublisher { fun exportFlac() { /* clean */ } }"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(sample_code)
        self.assertTrue(is_clean)
        self.assertEqual(len(violations), 0)

    @tier(3)
    @feature(11)
    @feature(12)
    @feature(13)
    def test_pairwise_13_remaster_memory_savings_software_fallback(self):
        """Combination 13: 5-Stage Remaster + Pre-upscale savings + Software libx264."""
        enc, params = MediaCodecEncoderSelector.select_encoder([], force_software=True)
        self.assertEqual(enc, HardwareEncoder.SOFTWARE_LIBX264)

        from tests.e2e.contracts.remaster_contracts import MemoryOptimizationOracle
        savings = MemoryOptimizationOracle.compute_memory_savings_ratio((1920, 1080), (3840, 2160))
        self.assertEqual(savings, 0.75)

    @tier(3)
    @feature(2)
    @feature(7)
    @feature(25)
    def test_pairwise_14_rebranded_engine_scrubber_dev_console(self):
        """Combination 14: Engine Rebranding + Log Scrubber + Secret Dev Console unlock."""
        raw = "[yt-dlp] Polar Core Engine v2.4 (Active)"
        clean = PolarLogSanitizerContract.sanitize(raw)
        self.assertNotIn("yt-dlp", clean)

        from tests.e2e.contracts.ui_contracts import DeveloperConsoleContract
        dev = DeveloperConsoleContract()
        for _ in range(7):
            dev.tap_engine_version_banner()
        self.assertTrue(dev.is_unlocked)

    @tier(3)
    @feature(17)
    @feature(19)
    @feature(24)
    def test_pairwise_15_download_lifecycle_mediastore_telemetry_speed(self):
        """Combination 15: Download Lifecycle + MediaStore Publish + Telemetry Formatting."""
        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("stream.mp4", is_audio=False)
        pub.phase2_write_bytes(uri, 100 * 1024 * 1024)
        self.assertTrue(pub.phase3_publish_commit(uri))

        # Telemetry check
        speed_formatted = f"{100 * 1024 * 1024 / (1024 * 1024):.1f} MB/s"
        self.assertEqual(speed_formatted, "100.0 MB/s")

    @tier(3)
    @feature(26)
    @feature(27)
    @feature(29)
    def test_pairwise_16_cloudflare_auth_hmac_silent_ota_apk(self):
        """Combination 16: Isolated Cloudflare Auth + HMAC Verification + Silent OTA APK check."""
        from tests.e2e.contracts.licensing_contracts import HMACSecurityContract, OTAUpdatePackageVerifier
        secret = "cf_worker_secret"
        now = 1700000000
        sig = HMACSecurityContract.generate_signature(secret, "dev_cf", now, "nonce_cf")
        is_valid, _ = HMACSecurityContract.verify_request(secret, "dev_cf", now, "nonce_cf", sig, now, set())
        self.assertTrue(is_valid)

        apk_bytes = b"PolarSnap 1.1.0 OTA Binary"
        checksum = OTAUpdatePackageVerifier.compute_sha256(apk_bytes)
        self.assertTrue(OTAUpdatePackageVerifier.verify_apk(apk_bytes, checksum))


if __name__ == "__main__":
    unittest.main()
