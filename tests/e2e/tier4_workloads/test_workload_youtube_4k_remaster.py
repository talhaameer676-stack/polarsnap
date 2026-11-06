"""
Tier 4: Real-World Workload A — YouTube 4K Remaster Workflow
Scenario: YouTube 4K URL paste -> bottom sheet -> Teal & Orange CapCut grading -> 4K Lanczos remaster -> MediaStore export
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
    MemoryOptimizationOracle,
    BijectiveLUTTransformer,
)
from tests.e2e.contracts.queue_contracts import (
    BoundedQueueManagerContract,
    DownloadRequest,
    TaskState,
    DownloadPhase,
    MediaStorePublisherContract,
)
from tests.e2e.contracts.ui_contracts import (
    MascotIdentityContract,
    MascotMood,
    ArcticPaletteContract,
)


class TestWorkloadYouTube4KRemaster(unittest.TestCase):
    TIER = 4

    @tier(4)
    @feature(1)
    @feature(2)
    @feature(3)
    @feature(9)
    @feature(10)
    @feature(11)
    @feature(12)
    @feature(13)
    @feature(14)
    @feature(19)
    @feature(22)
    @feature(23)
    def test_workflow_a1_youtube_4k_teal_and_orange_complete_pipeline(self):
        """Workflow A1: YouTube 4K link -> bottom sheet -> Teal & Orange LUT -> 4K Lanczos -> MediaStore."""
        url = "https://youtube.com/watch?v=arctic_nature_4k"

        # Step 1: User pastes URL in Home Screen paste dock
        self.assertTrue(url.startswith("https://"))

        # Step 2: Configure in Bottom Sheet (4K Ultra, MP4, Turbo on, Teal & Orange preset)
        engine_opts = EngineOptions(
            turbo_acceleration=True,
            clean_watermark=False,
            sponsor_stripper=True,
            custom_format_container=FormatContainer.MP4,
            resolution_limit=ResolutionLimit.RES_4K
        )
        remaster_config = RemasterConfig(
            enable_super_resolution=True,
            target_resolution=TargetResolution.UHD_4K,
            enable_sharpening=True,
            color_grading_preset=CapCutPreset.TEAL_AND_ORANGE
        )

        # Step 3: Engine command translation
        engine_args = PolarCommandTranslatorContract.translate(url, engine_opts)
        self.assertIn("-N", engine_args)
        self.assertIn("16", engine_args)
        self.assertIn("bestvideo[height<=2160]+bestaudio/best[height<=2160]/best", engine_args)
        self.assertIn("--sponsorblock-remove", engine_args)
        self.assertFalse(PolarLogSanitizerContract.contains_leak(" ".join(engine_args)))

        # Step 4: LUT coordinate verification (Bijective transformation)
        cc_origin = BijectiveLUTTransformer.capcut_to_hald_coord(0, 0)
        self.assertEqual(cc_origin, (0, 0))

        # Step 5: Remaster Filtergraph construction (Pre-upscale memory savings)
        filtergraph = RemasterFiltergraphBuilder.build(remaster_config, lut_file_path="assets/luts/teal_and_orange.png")
        self.assertIn("cas=strength=0.5", filtergraph)
        self.assertIn("eq=contrast=1.06:saturation=1.10", filtergraph)
        self.assertIn("haldclut=", filtergraph)
        self.assertIn("scale=3840:2160:flags=lanczos", filtergraph)
        self.assertIn("unsharp=lx=5:ly=5:la=0.4", filtergraph)

        # Confirm 75% frame RAM savings
        savings = MemoryOptimizationOracle.compute_memory_savings_ratio((1920, 1080), (3840, 2160))
        self.assertEqual(savings, 0.75)

        # Step 6: Hardware encoder selection (HEVC MediaCodec)
        enc, enc_params = MediaCodecEncoderSelector.select_encoder(["hevc_mediacodec", "h264_mediacodec"])
        self.assertEqual(enc, HardwareEncoder.HEVC_MEDIACODEC)
        self.assertIn("hevc_mediacodec", enc_params)

        # Step 7: Queue scheduling & active execution
        queue = BoundedQueueManagerContract()
        task = queue.enqueue(DownloadRequest(url=url, turbo_acceleration=True), "task_4k_01")
        self.assertEqual(task.state, TaskState.DOWNLOADING)
        self.assertEqual(task.assigned_slot, 0)

        # Step 8: Scoped Storage MediaStore two-phase publishing
        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("Arctic_Nature_4K_Remaster.mp4", is_audio=False)
        self.assertEqual(pub.published_records[uri].is_pending, 1)

        # Write 250 MB transcode stream
        file_bytes = 250 * 1024 * 1024
        self.assertTrue(pub.phase2_write_bytes(uri, file_bytes))

        # Phase 3 reveal
        self.assertTrue(pub.phase3_publish_commit(uri))
        self.assertEqual(pub.published_records[uri].is_pending, 0)
        self.assertEqual(pub.published_records[uri].relative_path, "Movies/PolarSnap")

        # Step 9: Queue task completion
        queue.complete("task_4k_01")
        self.assertEqual(queue.tasks["task_4k_01"].state, TaskState.COMPLETED)

    @tier(4)
    @feature(3)
    @feature(6)
    @feature(7)
    @feature(18)
    def test_workflow_a2_youtube_4k_live_telemetry_and_sponsor_splicing(self):
        """Workflow A2: YouTube 4K stream with Sponsor Stripper + Live telemetry extraction."""
        url = "https://youtube.com/watch?v=tech_review_4k"
        opts = EngineOptions(
            turbo_acceleration=True,
            sponsor_stripper=True,
            resolution_limit=ResolutionLimit.RES_4K
        )
        cmd = PolarCommandTranslatorContract.translate(url, opts)
        self.assertIn("--sponsorblock-remove", cmd)

        # Simulate live progress stream events
        sample_logs = [
            "[download]  10.0% of 200.00MiB at  15.20MiB/s ETA 00:12",
            "[download]  50.0% of 200.00MiB at  18.50MiB/s ETA 00:06",
            "[download] 100.0% of 200.00MiB at  22.10MiB/s ETA 00:00",
        ]
        events = []
        for line in sample_logs:
            event = PolarLogSanitizerContract.extract_telemetry(line)
            self.assertIsNotNone(event)
            events.append(event)

        self.assertAlmostEqual(events[0].progress_percent, 0.10)
        self.assertAlmostEqual(events[1].progress_percent, 0.50)
        self.assertAlmostEqual(events[2].progress_percent, 1.00)
        self.assertEqual(events[1].speed_formatted, "18.50MiB/s")

    @tier(4)
    @feature(13)
    @feature(14)
    @feature(19)
    def test_workflow_a3_youtube_4k_mediacodec_fallback_to_h264(self):
        """Workflow A3: 4K Remastering with MediaCodec fallback to H.264 when HEVC is busy."""
        # System only supports h264_mediacodec
        enc, enc_params = MediaCodecEncoderSelector.select_encoder(["h264_mediacodec"])
        self.assertEqual(enc, HardwareEncoder.H264_MEDIACODEC)
        self.assertIn("h264_mediacodec", enc_params)

        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("4k_h264.mp4", is_audio=False)
        pub.phase2_write_bytes(uri, 180 * 1024 * 1024)
        self.assertTrue(pub.phase3_publish_commit(uri))
        self.assertEqual(pub.published_records[uri].relative_path, "Movies/PolarSnap")

    @tier(4)
    @feature(17)
    @feature(19)
    @feature(21)
    def test_workflow_a4_youtube_4k_user_cancellation_mid_remaster(self):
        """Workflow A4: User cancels 4K download mid-remaster -> cleans up state cleanly."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://youtube.com/4k_heavy"), "task_cancel")
        self.assertEqual(queue.tasks["task_cancel"].state, TaskState.DOWNLOADING)

        # User hits Cancel
        queue.cancel("task_cancel")
        self.assertEqual(queue.tasks["task_cancel"].state, TaskState.CANCELLED)
        self.assertIsNone(queue.tasks["task_cancel"].assigned_slot)

        # Verify mascot returns to empty vault
        mood = MascotIdentityContract.resolve_mood(
            is_online=True, is_queue_empty=True, active_downloads_count=0, is_remastering_active=False
        )
        self.assertEqual(mood, MascotMood.SLEEPING_EMPTY_VAULT)


if __name__ == "__main__":
    unittest.main()
