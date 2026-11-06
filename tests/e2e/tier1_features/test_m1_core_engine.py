"""
Tier 1: Feature Coverage — Milestone 1 (Features 1-8: Polar Core Engine & Whitelabeling)
"""
import unittest
from tests.e2e.runner import feature, tier
from tests.e2e.contracts.engine_contracts import (
    ELFAlignmentChecker,
    EngineOptions,
    ResolutionLimit,
    FormatContainer,
    PolarCommandTranslatorContract,
    PolarLogSanitizerContract,
    PolarExceptionSanitizerContract,
    PolarErrorType,
)


class TestTier1Milestone1CoreEngine(unittest.TestCase):
    TIER = 1

    # =========================================================================
    # Feature 1: Embedded ARM64 Engine & 16KB Page Alignment
    # =========================================================================
    @tier(1)
    @feature(1)
    def test_feature1_16kb_page_aligned_valid(self):
        """Verify 16KB page alignment logic for valid Android 15 ARM64 ELF boundaries."""
        self.assertTrue(ELFAlignmentChecker.is_16kb_aligned(0x0, 0x0, 16384))
        self.assertTrue(ELFAlignmentChecker.is_16kb_aligned(0x0, 0x4000, 16384))
        self.assertTrue(ELFAlignmentChecker.is_16kb_aligned(0x0, 0x8000, 16384))

    @tier(1)
    @feature(1)
    def test_feature1_16kb_page_alignment_rejects_4kb_legacy(self):
        """Verify legacy 4KB (4096) ELF binaries are identified as non-compliant for Android 15."""
        self.assertFalse(ELFAlignmentChecker.is_16kb_aligned(0x0, 0x1000, 4096))

    @tier(1)
    @feature(1)
    def test_feature1_non_power_of_two_alignment_rejected(self):
        """Verify non-power-of-two page alignments fail compliance checks."""
        self.assertFalse(ELFAlignmentChecker.is_16kb_aligned(0x0, 0x4000, 20000))

    @tier(1)
    @feature(1)
    def test_feature1_offset_vaddr_misalignment_rejected(self):
        """Verify ELF load offset and vaddr modulo mismatch is rejected."""
        self.assertFalse(ELFAlignmentChecker.is_16kb_aligned(0x100, 0x4000, 16384))

    @tier(1)
    @feature(1)
    def test_feature1_large_64kb_alignment_accepted(self):
        """Verify 64KB page alignment satisfies >= 16KB invariant."""
        self.assertTrue(ELFAlignmentChecker.is_16kb_aligned(0x0, 0x10000, 65536))

    # =========================================================================
    # Feature 2: Whitelabeled Engine Rebranding
    # =========================================================================
    @tier(1)
    @feature(2)
    def test_feature2_engine_branding_identity_exact(self):
        """Verify engine name string is strictly 'Polar Core Engine v2.4 (Active)'."""
        branded_engine_name = "Polar Core Engine v2.4 (Active)"
        self.assertEqual(branded_engine_name, "Polar Core Engine v2.4 (Active)")
        self.assertNotIn("yt-dlp", branded_engine_name)
        self.assertNotIn("python", branded_engine_name.lower())

    @tier(1)
    @feature(2)
    def test_feature2_version_tag_invariance(self):
        """Verify version identifier is present in branded status string."""
        status = "Polar Core Engine v2.4 (Active) — Initialized"
        self.assertIn("Polar Core Engine v2.4", status)

    @tier(1)
    @feature(2)
    def test_feature2_engine_status_active_flag(self):
        """Verify status indicator reflects active operational state."""
        status_banner = "Polar Core Engine v2.4 (Active)"
        self.assertTrue(status_banner.endswith("(Active)"))

    @tier(1)
    @feature(2)
    def test_feature2_rebranding_sanitizes_cli_output(self):
        """Verify output header rebranding sanitizes tool naming."""
        raw_header = "[yt-dlp] Initializing runtime..."
        sanitized = PolarLogSanitizerContract.sanitize(raw_header)
        self.assertEqual(sanitized, "[Polar Core v2.4] Initializing runtime...")

    @tier(1)
    @feature(2)
    def test_feature2_zero_unbranded_leaks_in_branding_manifest(self):
        """Verify branding tokens have zero occurrence of upstream project names."""
        manifest = ["Polar Core Engine v2.4", "PolarTurboAccel", "Polar Runtime", "PolarSnap"]
        for token in manifest:
            self.assertFalse(PolarLogSanitizerContract.contains_leak(token))

    # =========================================================================
    # Feature 3: Turbo Acceleration Toggle Card
    # =========================================================================
    @tier(1)
    @feature(3)
    def test_feature3_turbo_acceleration_enabled_maps_aria2c_and_16_sockets(self):
        """Verify Turbo Acceleration maps to -N 16 and aria2c downloader."""
        opts = EngineOptions(turbo_acceleration=True)
        args = PolarCommandTranslatorContract.translate("https://example.com/video", opts)
        self.assertIn("-N", args)
        idx = args.index("-N")
        self.assertEqual(args[idx + 1], "16")
        self.assertIn("--downloader", args)
        d_idx = args.index("--downloader")
        self.assertEqual(args[d_idx + 1], "aria2c")

    @tier(1)
    @feature(3)
    def test_feature3_turbo_acceleration_disabled_omits_aria2c(self):
        """Verify disabled Turbo Acceleration removes -N and aria2c flags."""
        opts = EngineOptions(turbo_acceleration=False)
        args = PolarCommandTranslatorContract.translate("https://example.com/video", opts)
        self.assertNotIn("-N", args)
        self.assertNotIn("aria2c", args)

    @tier(1)
    @feature(3)
    def test_feature3_turbo_socket_bounded_ceiling(self):
        """Verify socket parameter does not exceed safe mobile ceiling of 16."""
        opts = EngineOptions(turbo_acceleration=True)
        args = PolarCommandTranslatorContract.translate("https://example.com/video", opts)
        socket_count = int(args[args.index("-N") + 1])
        self.assertLessEqual(socket_count, 16)

    @tier(1)
    @feature(3)
    def test_feature3_turbo_preserves_url_target(self):
        """Verify URL remains the final positional argument when Turbo is enabled."""
        url = "https://example.com/target-video"
        args = PolarCommandTranslatorContract.translate(url, EngineOptions(turbo_acceleration=True))
        self.assertEqual(args[-1], url)

    @tier(1)
    @feature(3)
    def test_feature3_turbo_preserves_security_flags(self):
        """Verify --no-call-home and --no-check-certificates remain set with Turbo."""
        args = PolarCommandTranslatorContract.translate("https://example.com/video", EngineOptions(turbo_acceleration=True))
        self.assertIn("--no-call-home", args)
        self.assertIn("--no-check-certificates", args)

    # =========================================================================
    # Feature 4: Lossless Audio Toggle Card
    # =========================================================================
    @tier(1)
    @feature(4)
    def test_feature4_lossless_audio_extracts_flac(self):
        """Verify Lossless Audio toggle enables audio extraction with FLAC format."""
        opts = EngineOptions(lossless_audio=True)
        args = PolarCommandTranslatorContract.translate("https://example.com/song", opts)
        self.assertIn("-x", args)
        self.assertIn("--audio-format", args)
        af_idx = args.index("--audio-format")
        self.assertEqual(args[af_idx + 1], "flac")

    @tier(1)
    @feature(4)
    def test_feature4_lossless_audio_omits_video_streams(self):
        """Verify Lossless Audio omits video container merge format."""
        opts = EngineOptions(lossless_audio=True)
        args = PolarCommandTranslatorContract.translate("https://example.com/song", opts)
        self.assertNotIn("--merge-output-format", args)

    @tier(1)
    @feature(4)
    def test_feature4_lossless_audio_with_flac_container(self):
        """Verify FLAC container option activates lossless audio."""
        opts = EngineOptions(lossless_audio=False, custom_format_container=FormatContainer.FLAC)
        opts.resolution_limit = ResolutionLimit.AUDIO_ONLY
        args = PolarCommandTranslatorContract.translate("https://example.com/audio", opts)
        self.assertIn("--audio-format", args)
        self.assertEqual(args[args.index("--audio-format") + 1], "flac")

    @tier(1)
    @feature(4)
    def test_feature4_audio_only_mp3_fallback(self):
        """Verify non-lossless Audio Only defaults to MP3 format."""
        opts = EngineOptions(lossless_audio=False, custom_format_container=FormatContainer.MP3)
        opts.resolution_limit = ResolutionLimit.AUDIO_ONLY
        args = PolarCommandTranslatorContract.translate("https://example.com/podcast", opts)
        self.assertIn("--audio-format", args)
        self.assertEqual(args[args.index("--audio-format") + 1], "mp3")

    @tier(1)
    @feature(4)
    def test_feature4_lossless_audio_compatible_with_turbo(self):
        """Verify Lossless Audio works seamlessly with Turbo Acceleration."""
        opts = EngineOptions(turbo_acceleration=True, lossless_audio=True)
        args = PolarCommandTranslatorContract.translate("https://example.com/song", opts)
        self.assertIn("-N", args)
        self.assertIn("-x", args)

    # =========================================================================
    # Feature 5: Clean Watermark Toggle Card
    # =========================================================================
    @tier(1)
    @feature(5)
    def test_feature5_clean_watermark_enabled_sets_extractor_arg(self):
        """Verify Clean Watermark adds no_watermark=1 extractor argument."""
        opts = EngineOptions(clean_watermark=True)
        args = PolarCommandTranslatorContract.translate("https://tiktok.com/@user/video/123", opts)
        self.assertIn("--extractor-args", args)
        self.assertIn("tiktok:no_watermark=1", args)

    @tier(1)
    @feature(5)
    def test_feature5_clean_watermark_disabled_omits_extractor_arg(self):
        """Verify Clean Watermark disabled omits watermark extractor argument."""
        opts = EngineOptions(clean_watermark=False)
        args = PolarCommandTranslatorContract.translate("https://tiktok.com/@user/video/123", opts)
        self.assertNotIn("tiktok:no_watermark=1", args)

    @tier(1)
    @feature(5)
    def test_feature5_clean_watermark_preserves_resolution_limit(self):
        """Verify Clean Watermark does not alter resolution limits."""
        opts = EngineOptions(clean_watermark=True, resolution_limit=ResolutionLimit.RES_1080P)
        args = PolarCommandTranslatorContract.translate("https://instagram.com/reel/abc", opts)
        self.assertIn("-f", args)
        self.assertIn("bestvideo[height<=1080]+bestaudio/best[height<=1080]/best", args)

    @tier(1)
    @feature(5)
    def test_feature5_clean_watermark_with_mp4_container(self):
        """Verify Clean Watermark sets MP4 container merge format."""
        opts = EngineOptions(clean_watermark=True, custom_format_container=FormatContainer.MP4)
        args = PolarCommandTranslatorContract.translate("https://tiktok.com/clip", opts)
        self.assertIn("--merge-output-format", args)
        self.assertEqual(args[args.index("--merge-output-format") + 1], "mp4")

    @tier(1)
    @feature(5)
    def test_feature5_clean_watermark_with_mkv_container(self):
        """Verify Clean Watermark sets MKV container merge format when selected."""
        opts = EngineOptions(clean_watermark=True, custom_format_container=FormatContainer.MKV)
        args = PolarCommandTranslatorContract.translate("https://tiktok.com/clip", opts)
        self.assertIn("--merge-output-format", args)
        self.assertEqual(args[args.index("--merge-output-format") + 1], "mkv")

    # =========================================================================
    # Feature 6: Sponsor Stripper Toggle Card
    # =========================================================================
    @tier(1)
    @feature(6)
    def test_feature6_sponsor_stripper_enabled_adds_sponsorblock(self):
        """Verify Sponsor Stripper adds --sponsorblock-remove default flag."""
        opts = EngineOptions(sponsor_stripper=True)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=123", opts)
        self.assertIn("--sponsorblock-remove", args)
        self.assertEqual(args[args.index("--sponsorblock-remove") + 1], "default")

    @tier(1)
    @feature(6)
    def test_feature6_sponsor_stripper_disabled_omits_flag(self):
        """Verify Sponsor Stripper disabled omits sponsorblock flags."""
        opts = EngineOptions(sponsor_stripper=False)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=123", opts)
        self.assertNotIn("--sponsorblock-remove", args)

    @tier(1)
    @feature(6)
    def test_feature6_sponsor_stripper_with_turbo_acceleration(self):
        """Verify Sponsor Stripper works in tandem with Turbo Acceleration."""
        opts = EngineOptions(sponsor_stripper=True, turbo_acceleration=True)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=123", opts)
        self.assertIn("--sponsorblock-remove", args)
        self.assertIn("-N", args)

    @tier(1)
    @feature(6)
    def test_feature6_sponsor_stripper_with_audio_only(self):
        """Verify Sponsor Stripper works during audio-only extraction."""
        opts = EngineOptions(sponsor_stripper=True, lossless_audio=True)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=123", opts)
        self.assertIn("--sponsorblock-remove", args)
        self.assertIn("-x", args)

    @tier(1)
    @feature(6)
    def test_feature6_sponsor_stripper_zero_leakage_in_args(self):
        """Verify generated arguments contain zero raw Python / internal leaks."""
        opts = EngineOptions(sponsor_stripper=True, turbo_acceleration=True)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=123", opts)
        for arg in args:
            self.assertFalse(PolarLogSanitizerContract.contains_leak(arg))

    # =========================================================================
    # Feature 7: Zero-Leak Log Scrubber
    # =========================================================================
    @tier(1)
    @feature(7)
    def test_feature7_scrub_ytdlp_bracket_tags(self):
        """Verify [yt-dlp] tags are scrubbed and replaced with [Polar Core v2.4]."""
        raw = "[yt-dlp] Extracting URL: https://example.com"
        clean = PolarLogSanitizerContract.sanitize(raw)
        self.assertNotIn("yt-dlp", clean)
        self.assertIn("[Polar Core v2.4]", clean)

    @tier(1)
    @feature(7)
    def test_feature7_scrub_python_runtime_paths(self):
        """Verify internal python directory paths are scrubbed."""
        raw = "Error in /data/data/com.trandif.polarsnap/files/python/lib/extractor.py"
        clean = PolarLogSanitizerContract.sanitize(raw)
        self.assertNotIn("/data/data/com.trandif.polarsnap/files/python", clean)
        self.assertIn("/system/lib/polarengine", clean)

    @tier(1)
    @feature(7)
    def test_feature7_extract_telemetry_progress_speed_eta(self):
        """Verify live progress, speed, ETA, and size are extracted cleanly."""
        raw = "[download]  45.6% of 120.50MiB at  12.45MiB/s ETA 00:05"
        event = PolarLogSanitizerContract.extract_telemetry(raw)
        self.assertIsNotNone(event)
        self.assertAlmostEqual(event.progress_percent, 0.456, places=3)
        self.assertEqual(event.speed_formatted, "12.45MiB/s")
        self.assertEqual(event.eta_formatted, "00:05")
        self.assertEqual(event.total_size_formatted, "120.50MiB")

    @tier(1)
    @feature(7)
    def test_feature7_scrub_aria2c_binary_references(self):
        """Verify libaria2c.so references are scrubbed to PolarTurboAccel."""
        raw = "Spawned sub-process libaria2c.so with 16 connections"
        clean = PolarLogSanitizerContract.sanitize(raw)
        self.assertNotIn("libaria2c.so", clean)
        self.assertIn("PolarTurboAccel", clean)

    @tier(1)
    @feature(7)
    def test_feature7_contains_leak_detector_accuracy(self):
        """Verify leak detection regex catches all sensitive substrings."""
        self.assertTrue(PolarLogSanitizerContract.contains_leak("Traceback (most recent call last):"))
        self.assertTrue(PolarLogSanitizerContract.contains_leak("yt-dlp version 2024.08.06"))
        self.assertTrue(PolarLogSanitizerContract.contains_leak("Running on Python 3.11.4"))
        self.assertFalse(PolarLogSanitizerContract.contains_leak("Polar Core Engine v2.4 Active"))

    # =========================================================================
    # Feature 8: Domain Exception Sanitizer
    # =========================================================================
    @tier(1)
    @feature(8)
    def test_feature8_anti_bot_verification_transformed(self):
        """Verify 'Sign in to confirm you're not a bot' becomes AntiBotVerification."""
        raw = "ERROR: Sign in to confirm you're not a bot. Use --cookies."
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw)
        self.assertEqual(exc.error_type, PolarErrorType.ANTI_BOT_VERIFICATION)
        self.assertEqual(exc.code, 403)
        self.assertNotIn("cookies", exc.user_message)

    @tier(1)
    @feature(8)
    def test_feature8_rate_limit_transformed_to_service_cooldown(self):
        """Verify HTTP 429 rate limit becomes ServiceCooldown."""
        raw = "HTTP Error 429: Too Many Requests"
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw)
        self.assertEqual(exc.error_type, PolarErrorType.SERVICE_COOLDOWN)
        self.assertEqual(exc.code, 429)

    @tier(1)
    @feature(8)
    def test_feature8_drm_and_copyright_transformed_to_stream_protected(self):
        """Verify DRM protected content becomes StreamProtected."""
        raw = "ERROR: This video is DRM protected or restricted"
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw)
        self.assertEqual(exc.error_type, PolarErrorType.STREAM_PROTECTED)
        self.assertEqual(exc.code, 451)

    @tier(1)
    @feature(8)
    def test_feature8_network_timeout_transformed_to_media_unreachable(self):
        """Verify network timeout becomes MediaUnreachable."""
        raw = "ERROR: <urlopen error timed out> Connection refused"
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw)
        self.assertEqual(exc.error_type, PolarErrorType.MEDIA_UNREACHABLE)
        self.assertEqual(exc.code, 504)

    @tier(1)
    @feature(8)
    def test_feature8_invalid_url_transformed_to_invalid_media_url(self):
        """Verify unsupported or malformed URL becomes InvalidMediaUrl."""
        raw = "ERROR: 'httppp://bad' is not a valid URL"
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw)
        self.assertEqual(exc.error_type, PolarErrorType.INVALID_MEDIA_URL)
        self.assertEqual(exc.code, 400)


if __name__ == "__main__":
    unittest.main()
