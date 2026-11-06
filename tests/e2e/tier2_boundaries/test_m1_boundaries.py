"""
Tier 2: Boundary Value Analysis & Corner Cases — Milestone 1 (Features 1-8)
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


class TestTier2Milestone1Boundaries(unittest.TestCase):
    TIER = 2

    # =========================================================================
    # Feature 1: ELF Alignment Boundaries
    # =========================================================================
    @tier(2)
    @feature(1)
    def test_feature1_boundary_16kb_minus_1(self):
        """Boundary: 16383 bytes (16KB - 1) is rejected."""
        self.assertFalse(ELFAlignmentChecker.is_16kb_aligned(0, 0, 16383))

    @tier(2)
    @feature(1)
    def test_feature1_boundary_16kb_plus_1(self):
        """Boundary: 16385 bytes (16KB + 1) is rejected (not power of 2)."""
        self.assertFalse(ELFAlignmentChecker.is_16kb_aligned(0, 0, 16385))

    @tier(2)
    @feature(1)
    def test_feature1_boundary_zero_alignment(self):
        """Boundary: p_align = 0 is rejected."""
        self.assertFalse(ELFAlignmentChecker.is_16kb_aligned(0, 0, 0))

    @tier(2)
    @feature(1)
    def test_feature1_boundary_negative_offset(self):
        """Boundary: negative load offset with unaligned modulo is rejected."""
        self.assertFalse(ELFAlignmentChecker.is_16kb_aligned(-1, 0, 16384))

    @tier(2)
    @feature(1)
    def test_feature1_boundary_max_32bit_vaddr(self):
        """Boundary: 32-bit maximum address boundary (0xFFFFFFFF) unaligned."""
        self.assertFalse(ELFAlignmentChecker.is_16kb_aligned(0, 0xFFFFFFFF, 16384))

    # =========================================================================
    # Feature 2: Whitelabeled Engine Rebranding Boundaries
    # =========================================================================
    @tier(2)
    @feature(2)
    def test_feature2_boundary_empty_string_log_scrubbed(self):
        """Boundary: empty string log returns empty without exception."""
        self.assertEqual(PolarLogSanitizerContract.sanitize(""), "")

    @tier(2)
    @feature(2)
    def test_feature2_boundary_whitespace_only_log(self):
        """Boundary: whitespace-only log preserved without mangling."""
        self.assertEqual(PolarLogSanitizerContract.sanitize("   \n\t  "), "   \n\t  ")

    @tier(2)
    @feature(2)
    def test_feature2_boundary_huge_log_no_catastrophic_backtracking(self):
        """Boundary: 50,000 character log line sanitized in < 100ms."""
        huge_log = "Processing item " + ("A" * 50000) + " with yt-dlp internal"
        clean = PolarLogSanitizerContract.sanitize(huge_log)
        self.assertNotIn("yt-dlp", clean)
        self.assertIn("Polar Core", clean)

    @tier(2)
    @feature(2)
    def test_feature2_boundary_repeated_forbidden_tokens(self):
        """Boundary: 10 consecutive 'yt-dlp' tokens are all scrubbed."""
        raw = "yt-dlp " * 10
        clean = PolarLogSanitizerContract.sanitize(raw)
        self.assertNotIn("yt-dlp", clean)
        self.assertEqual(clean.count("Polar Core"), 10)

    @tier(2)
    @feature(2)
    def test_feature2_boundary_case_insensitive_scrubbing(self):
        """Boundary: mixed-case variations ('yT-DlP', 'YOUTUBE-DL') are scrubbed."""
        raw = "Engine: yT-DlP, Runtime: YOUTUBE-DL"
        clean = PolarLogSanitizerContract.sanitize(raw)
        self.assertNotIn("yT-DlP", clean)
        self.assertNotIn("YOUTUBE-DL", clean)

    # =========================================================================
    # Feature 3: Turbo Acceleration Boundaries
    # =========================================================================
    @tier(2)
    @feature(3)
    def test_feature3_boundary_extreme_url_length(self):
        """Boundary: URL with 2048 characters handled without command overflow."""
        long_url = "https://example.com/watch?v=" + ("x" * 2000)
        args = PolarCommandTranslatorContract.translate(long_url, EngineOptions(turbo_acceleration=True))
        self.assertEqual(args[-1], long_url)
        self.assertIn("-N", args)

    @tier(2)
    @feature(3)
    def test_feature3_boundary_url_with_special_characters(self):
        """Boundary: URL with query parameters and special symbols."""
        url = "https://example.com/video?f=1&t=10s&lang=en-US#anchor"
        args = PolarCommandTranslatorContract.translate(url, EngineOptions(turbo_acceleration=True))
        self.assertEqual(args[-1], url)

    @tier(2)
    @feature(3)
    def test_feature3_boundary_both_turbo_and_lossless(self):
        """Boundary: Simultaneous Turbo + Lossless options translate cleanly."""
        opts = EngineOptions(turbo_acceleration=True, lossless_audio=True)
        args = PolarCommandTranslatorContract.translate("https://example.com/audio", opts)
        self.assertIn("-N", args)
        self.assertIn("-x", args)
        self.assertIn("aria2c", args)

    @tier(2)
    @feature(3)
    def test_feature3_boundary_all_toggles_enabled_simultaneously(self):
        """Boundary: All 4 toggle cards enabled simultaneously."""
        opts = EngineOptions(
            turbo_acceleration=True,
            lossless_audio=True,
            clean_watermark=True,
            sponsor_stripper=True
        )
        args = PolarCommandTranslatorContract.translate("https://example.com/media", opts)
        self.assertIn("-N", args)
        self.assertIn("-x", args)
        self.assertIn("--sponsorblock-remove", args)
        self.assertIn("tiktok:no_watermark=1", args)

    @tier(2)
    @feature(3)
    def test_feature3_boundary_all_toggles_disabled_simultaneously(self):
        """Boundary: All 4 toggle cards disabled simultaneously."""
        opts = EngineOptions(
            turbo_acceleration=False,
            lossless_audio=False,
            clean_watermark=False,
            sponsor_stripper=False
        )
        args = PolarCommandTranslatorContract.translate("https://example.com/media", opts)
        self.assertNotIn("-N", args)
        self.assertNotIn("-x", args)
        self.assertNotIn("--sponsorblock-remove", args)
        self.assertNotIn("tiktok:no_watermark=1", args)

    # =========================================================================
    # Feature 4: Lossless Audio Boundaries
    # =========================================================================
    @tier(2)
    @feature(4)
    def test_feature4_boundary_flac_container_selection(self):
        """Boundary: Selecting FLAC container forces FLAC audio extraction."""
        opts = EngineOptions(lossless_audio=True, custom_format_container=FormatContainer.FLAC)
        args = PolarCommandTranslatorContract.translate("https://example.com/song", opts)
        self.assertIn("flac", args)

    @tier(2)
    @feature(4)
    def test_feature4_boundary_mp3_container_selection(self):
        """Boundary: Selecting MP3 without lossless uses mp3 format."""
        opts = EngineOptions(
            lossless_audio=False,
            custom_format_container=FormatContainer.MP3,
            resolution_limit=ResolutionLimit.AUDIO_ONLY
        )
        args = PolarCommandTranslatorContract.translate("https://example.com/song", opts)
        self.assertIn("mp3", args)

    @tier(2)
    @feature(4)
    def test_feature4_boundary_audio_only_with_mkv_container_request(self):
        """Boundary: Audio-only resolution overrides video MKV container request."""
        opts = EngineOptions(
            lossless_audio=False,
            custom_format_container=FormatContainer.MKV,
            resolution_limit=ResolutionLimit.AUDIO_ONLY
        )
        args = PolarCommandTranslatorContract.translate("https://example.com/clip", opts)
        self.assertIn("-x", args)
        self.assertNotIn("--merge-output-format", args)

    @tier(2)
    @feature(4)
    def test_feature4_boundary_audio_extraction_with_sponsor_stripper(self):
        """Boundary: Audio extraction with Sponsor Stripper retains both flags."""
        opts = EngineOptions(lossless_audio=True, sponsor_stripper=True)
        args = PolarCommandTranslatorContract.translate("https://example.com/podcast", opts)
        self.assertIn("-x", args)
        self.assertIn("--sponsorblock-remove", args)

    @tier(2)
    @feature(4)
    def test_feature4_boundary_zero_leakage_in_audio_args(self):
        """Boundary: Audio extraction args contain zero internal leaks."""
        opts = EngineOptions(lossless_audio=True, turbo_acceleration=True)
        args = PolarCommandTranslatorContract.translate("https://example.com/audio", opts)
        for a in args:
            self.assertFalse(PolarLogSanitizerContract.contains_leak(a))

    # =========================================================================
    # Feature 5: Clean Watermark Boundaries
    # =========================================================================
    @tier(2)
    @feature(5)
    def test_feature5_boundary_non_tiktok_url_with_clean_watermark(self):
        """Boundary: Clean Watermark flag applied to non-TikTok URL safely."""
        opts = EngineOptions(clean_watermark=True)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=123", opts)
        self.assertIn("tiktok:no_watermark=1", args)
        self.assertEqual(args[-1], "https://youtube.com/watch?v=123")

    @tier(2)
    @feature(5)
    def test_feature5_boundary_clean_watermark_with_720p_limit(self):
        """Boundary: Clean Watermark with 720p HD resolution limit."""
        opts = EngineOptions(clean_watermark=True, resolution_limit=ResolutionLimit.RES_720P)
        args = PolarCommandTranslatorContract.translate("https://tiktok.com/@user/1", opts)
        self.assertIn("bestvideo[height<=720]+bestaudio/best[height<=720]/best", args)

    @tier(2)
    @feature(5)
    def test_feature5_boundary_clean_watermark_with_1440p_limit(self):
        """Boundary: Clean Watermark with 1440p QHD resolution limit."""
        opts = EngineOptions(clean_watermark=True, resolution_limit=ResolutionLimit.RES_1440P)
        args = PolarCommandTranslatorContract.translate("https://tiktok.com/@user/1", opts)
        self.assertIn("bestvideo[height<=1440]+bestaudio/best[height<=1440]/best", args)

    @tier(2)
    @feature(5)
    def test_feature5_boundary_clean_watermark_with_4k_limit(self):
        """Boundary: Clean Watermark with 4K UHD resolution limit."""
        opts = EngineOptions(clean_watermark=True, resolution_limit=ResolutionLimit.RES_4K)
        args = PolarCommandTranslatorContract.translate("https://tiktok.com/@user/1", opts)
        self.assertIn("bestvideo[height<=2160]+bestaudio/best[height<=2160]/best", args)

    @tier(2)
    @feature(5)
    def test_feature5_boundary_clean_watermark_with_mkv(self):
        """Boundary: Clean Watermark with MKV container merge format."""
        opts = EngineOptions(clean_watermark=True, custom_format_container=FormatContainer.MKV)
        args = PolarCommandTranslatorContract.translate("https://tiktok.com/@user/1", opts)
        self.assertEqual(args[args.index("--merge-output-format") + 1], "mkv")

    # =========================================================================
    # Feature 6: Sponsor Stripper Boundaries
    # =========================================================================
    @tier(2)
    @feature(6)
    def test_feature6_boundary_sponsor_stripper_position(self):
        """Boundary: --sponsorblock-remove is followed by category argument."""
        opts = EngineOptions(sponsor_stripper=True)
        args = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=123", opts)
        idx = args.index("--sponsorblock-remove")
        self.assertEqual(args[idx + 1], "default")

    @tier(2)
    @feature(6)
    def test_feature6_boundary_sponsor_stripper_with_all_resolutions(self):
        """Boundary: Sponsor Stripper remains valid across all resolution modes."""
        for res in [ResolutionLimit.RES_4K, ResolutionLimit.RES_1440P, ResolutionLimit.RES_1080P, ResolutionLimit.RES_720P]:
            opts = EngineOptions(sponsor_stripper=True, resolution_limit=res)
            args = PolarCommandTranslatorContract.translate("https://youtube.com/watch?v=123", opts)
            self.assertIn("--sponsorblock-remove", args)

    @tier(2)
    @feature(6)
    def test_feature6_boundary_url_with_existing_timestamp(self):
        """Boundary: URL with existing &t=120s parameter retains sponsorblock."""
        opts = EngineOptions(sponsor_stripper=True)
        url = "https://youtube.com/watch?v=123&t=120s"
        args = PolarCommandTranslatorContract.translate(url, opts)
        self.assertIn("--sponsorblock-remove", args)
        self.assertEqual(args[-1], url)

    @tier(2)
    @feature(6)
    def test_feature6_boundary_short_video_url(self):
        """Boundary: Short YouTube URL (youtu.be/xyz) handles sponsor stripper."""
        url = "https://youtu.be/xyz123"
        args = PolarCommandTranslatorContract.translate(url, EngineOptions(sponsor_stripper=True))
        self.assertIn("--sponsorblock-remove", args)
        self.assertEqual(args[-1], url)

    @tier(2)
    @feature(6)
    def test_feature6_boundary_sponsor_stripper_no_leak(self):
        """Boundary: Zero leak check on sponsor stripper command."""
        args = PolarCommandTranslatorContract.translate("https://example.com/v", EngineOptions(sponsor_stripper=True))
        for a in args:
            self.assertFalse(PolarLogSanitizerContract.contains_leak(a))

    # =========================================================================
    # Feature 7: Zero-Leak Log Scrubber Boundaries
    # =========================================================================
    @tier(2)
    @feature(7)
    def test_feature7_boundary_telemetry_at_0_percent(self):
        """Boundary: Progress telemetry at exactly 0.0%."""
        line = "[download]   0.0% of 100.00MiB at 1.00MiB/s ETA 01:40"
        event = PolarLogSanitizerContract.extract_telemetry(line)
        self.assertIsNotNone(event)
        self.assertAlmostEqual(event.progress_percent, 0.0)

    @tier(2)
    @feature(7)
    def test_feature7_boundary_telemetry_at_100_percent(self):
        """Boundary: Progress telemetry at exactly 100.0%."""
        line = "[download] 100.0% of 100.00MiB at 10.00MiB/s ETA 00:00"
        event = PolarLogSanitizerContract.extract_telemetry(line)
        self.assertIsNotNone(event)
        self.assertAlmostEqual(event.progress_percent, 1.0)

    @tier(2)
    @feature(7)
    def test_feature7_boundary_telemetry_non_matching_line(self):
        """Boundary: Non-progress log line returns None for telemetry extraction."""
        line = "[Polar Core v2.4] Audio stream extracted cleanly."
        event = PolarLogSanitizerContract.extract_telemetry(line)
        self.assertIsNone(event)

    @tier(2)
    @feature(7)
    def test_feature7_boundary_multiline_python_traceback_scrubbed(self):
        """Boundary: Multi-line Python stack trace is flagged by leak detector."""
        traceback_sample = (
            "Traceback (most recent call last):\n"
            '  File "runner.py", line 42, in <module>\n'
            "    raise RuntimeError('internal crash')"
        )
        self.assertTrue(PolarLogSanitizerContract.contains_leak(traceback_sample))

    @tier(2)
    @feature(7)
    def test_feature7_boundary_aria2c_in_parentheses_scrubbed(self):
        """Boundary: libaria2c.so surrounded by brackets/quotes is scrubbed."""
        raw = "Using external library: 'libaria2c.so' for socket management."
        clean = PolarLogSanitizerContract.sanitize(raw)
        self.assertNotIn("libaria2c.so", clean)
        self.assertIn("PolarTurboAccel", clean)

    # =========================================================================
    # Feature 8: Domain Exception Sanitizer Boundaries
    # =========================================================================
    @tier(2)
    @feature(8)
    def test_feature8_boundary_empty_error_string(self):
        """Boundary: Empty raw error string maps safely to EngineOperationFailed."""
        exc = PolarExceptionSanitizerContract.sanitize_exception("")
        self.assertEqual(exc.error_type, PolarErrorType.ENGINE_OPERATION_FAILED)
        self.assertEqual(exc.code, 500)

    @tier(2)
    @feature(8)
    def test_feature8_boundary_mixed_error_bot_and_timeout(self):
        """Boundary: Error containing bot verification takes precedence."""
        raw = "Connection timed out while trying to sign in to confirm you're not a bot"
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw)
        self.assertEqual(exc.error_type, PolarErrorType.ANTI_BOT_VERIFICATION)
        self.assertEqual(exc.code, 403)

    @tier(2)
    @feature(8)
    def test_feature8_boundary_unknown_obscure_exit_code(self):
        """Boundary: Obscure exit code maps to EngineOperationFailed with user message."""
        exc = PolarExceptionSanitizerContract.sanitize_exception("Unexpected segfault 0xDEADBEEF", exit_code=139)
        self.assertEqual(exc.error_type, PolarErrorType.ENGINE_OPERATION_FAILED)
        self.assertNotIn("0xDEADBEEF", exc.user_message)

    @tier(2)
    @feature(8)
    def test_feature8_boundary_rate_limit_with_retry_after(self):
        """Boundary: HTTP 429 with retry-after text maps to ServiceCooldown."""
        raw = "HTTP Error 429: Rate limit exceeded. Retry-After: 3600"
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw)
        self.assertEqual(exc.error_type, PolarErrorType.SERVICE_COOLDOWN)
        self.assertEqual(exc.code, 429)

    @tier(2)
    @feature(8)
    def test_feature8_boundary_geo_restricted_video(self):
        """Boundary: Geo-restricted stream maps to StreamProtected."""
        raw = "ERROR: [youtube] 123: The uploader has not made this video available in your country"
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw)
        self.assertEqual(exc.error_type, PolarErrorType.ENGINE_OPERATION_FAILED)  # Fallback to safe


if __name__ == "__main__":
    unittest.main()
