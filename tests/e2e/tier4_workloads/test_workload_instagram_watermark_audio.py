"""
Tier 4: Real-World Workload B — Instagram/TikTok Watermark & Lossless Audio Workflow
Scenario: Social media short clip URL paste -> clean watermark toggle -> lossless FLAC extract -> Scoped Storage Music export
"""
import unittest
from tests.e2e.runner import feature, tier
from tests.e2e.contracts.engine_contracts import (
    EngineOptions,
    ResolutionLimit,
    FormatContainer,
    PolarCommandTranslatorContract,
    PolarLogSanitizerContract,
    PolarExceptionSanitizerContract,
    PolarErrorType,
)
from tests.e2e.contracts.remaster_contracts import (
    CapCutPreset,
    RemasterConfig,
    RemasterFiltergraphBuilder,
)
from tests.e2e.contracts.queue_contracts import (
    BoundedQueueManagerContract,
    DownloadRequest,
    TaskState,
    MediaStorePublisherContract,
)
from tests.e2e.contracts.ui_contracts import (
    MascotIdentityContract,
    MascotMood,
)
from tests.e2e.contracts.licensing_contracts import (
    AdFreeGuaranteeScanner,
)


class TestWorkloadInstagramWatermarkAudio(unittest.TestCase):
    TIER = 4

    @tier(4)
    @feature(2)
    @feature(4)
    @feature(5)
    @feature(17)
    @feature(19)
    @feature(22)
    def test_workflow_b1_tiktok_clean_watermark_lossless_audio_flac(self):
        """Workflow B1: TikTok URL -> Clean Watermark -> Lossless Audio FLAC -> MediaStore Music."""
        url = "https://www.tiktok.com/@creator/video/71234567890"

        # 1. User configures Lossless Audio + Clean Watermark
        opts = EngineOptions(
            turbo_acceleration=True,
            lossless_audio=True,
            clean_watermark=True,
            custom_format_container=FormatContainer.FLAC
        )
        args = PolarCommandTranslatorContract.translate(url, opts)
        self.assertIn("-x", args)
        self.assertIn("--audio-format", args)
        self.assertIn("flac", args)
        self.assertIn("tiktok:no_watermark=1", args)
        self.assertFalse(PolarLogSanitizerContract.contains_leak(" ".join(args)))

        # 2. Queue & Process
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url=url, custom_format="FLAC"), "audio_task_01")
        self.assertEqual(queue.tasks["audio_task_01"].state, TaskState.DOWNLOADING)

        # 3. MediaStore Music Export
        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("TikTok_Audio_Clean.flac", is_audio=True)
        self.assertEqual(pub.published_records[uri].relative_path, "Music/PolarSnap")
        self.assertEqual(pub.published_records[uri].mime_type, "audio/flac")

        # Write 15 MB lossless audio stream
        self.assertTrue(pub.phase2_write_bytes(uri, 15 * 1024 * 1024))
        self.assertTrue(pub.phase3_publish_commit(uri))
        self.assertEqual(pub.published_records[uri].is_pending, 0)

        queue.complete("audio_task_01")
        self.assertEqual(queue.tasks["audio_task_01"].state, TaskState.COMPLETED)

    @tier(4)
    @feature(5)
    @feature(9)
    @feature(19)
    def test_workflow_b2_instagram_reel_viral_warm_pop_remaster(self):
        """Workflow B2: Instagram Reel -> Clean Watermark -> Viral Warm Pop CapCut grading -> Movies export."""
        url = "https://www.instagram.com/reel/Cxyz123abc"
        opts = EngineOptions(clean_watermark=True, custom_format_container=FormatContainer.MP4)
        args = PolarCommandTranslatorContract.translate(url, opts)
        self.assertIn("tiktok:no_watermark=1", args)
        self.assertIn("mp4", args)

        remaster = RemasterConfig(
            enable_super_resolution=False,  # Keep native 1080p
            color_grading_preset=CapCutPreset.VIRAL_WARM_POP
        )
        graph = RemasterFiltergraphBuilder.build(remaster, "assets/luts/viral_warm_pop.png")
        self.assertIn("haldclut=", graph)
        self.assertNotIn("scale=", graph)

        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("Reel_ViralWarmPop.mp4", is_audio=False)
        pub.phase2_write_bytes(uri, 45 * 1024 * 1024)
        self.assertTrue(pub.phase3_publish_commit(uri))
        self.assertEqual(pub.published_records[uri].relative_path, "Movies/PolarSnap")

    @tier(4)
    @feature(7)
    @feature(8)
    def test_workflow_b3_watermark_extraction_anti_bot_error_sanitization(self):
        """Workflow B3: Upstream bot detection during short video extraction cleanly sanitized."""
        raw_output = (
            "[yt-dlp] Downloading webpage: https://tiktok.com/@bot_guard\n"
            "ERROR: Sign in to confirm you're not a bot. Use cookies to authenticate."
        )
        # 1. Scrub log
        clean_log = PolarLogSanitizerContract.sanitize(raw_output)
        self.assertNotIn("yt-dlp", clean_log)
        self.assertIn("Polar Core", clean_log)

        # 2. Sanitize domain exception
        exc = PolarExceptionSanitizerContract.sanitize_exception(clean_log)
        self.assertEqual(exc.error_type, PolarErrorType.ANTI_BOT_VERIFICATION)
        self.assertEqual(exc.code, 403)
        self.assertNotIn("cookies", exc.user_message)
        self.assertIn("anti-bot verification", exc.user_message)

    @tier(4)
    @feature(4)
    @feature(30)
    def test_workflow_b4_lossless_audio_zero_ad_trackers_verification(self):
        """Workflow B4: Lossless audio pipeline undergoes static ad-free audit."""
        audio_pipeline_code = """
        package com.trandif.polarsnap.core.engine
        class LosslessAudioExtractor {
            fun extractFlac(source: String): ByteArray {
                return byteArrayOf(0x66, 0x4C, 0x61, 0x43) // fLaC
            }
        }
        """
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(audio_pipeline_code)
        self.assertTrue(is_clean)
        self.assertEqual(len(violations), 0)


if __name__ == "__main__":
    unittest.main()
