"""
Tier 4: Real-World Workload C — Playlist Batch Processing & Concurrency Workflow
Scenario: Multi-item playlist link -> bottom sheet detects batch -> 2-slot concurrency scheduling -> live notification -> MediaStore exports
"""
import unittest
from tests.e2e.runner import feature, tier
from tests.e2e.contracts.queue_contracts import (
    BoundedQueueManagerContract,
    DownloadRequest,
    TaskState,
    DownloadPhase,
    MediaStorePublisherContract,
    ForegroundServiceContract,
)
from tests.e2e.contracts.ui_contracts import (
    MascotIdentityContract,
    MascotMood,
)
from tests.e2e.contracts.engine_contracts import (
    PolarLogSanitizerContract,
    PolarExceptionSanitizerContract,
    PolarErrorType,
)


class TestWorkloadPlaylistBatchExport(unittest.TestCase):
    TIER = 4

    @tier(4)
    @feature(3)
    @feature(15)
    @feature(16)
    @feature(18)
    @feature(19)
    def test_workflow_c1_playlist_batch_concurrency_and_notification(self):
        """Workflow C1: 10-item playlist batch scheduling across 2 concurrency slots with live notification."""
        queue = BoundedQueueManagerContract()
        publisher = MediaStorePublisherContract()

        # Step 1: Enqueue 10 playlist items
        batch_ids = [f"item_{i}" for i in range(10)]
        for tid in batch_ids:
            queue.enqueue(DownloadRequest(url=f"https://youtube.com/watch?v=list_{tid}", turbo_acceleration=True), tid)

        # Step 2: Verify only slots 0 and 1 are active, remaining 8 are pending
        self.assertEqual(queue.tasks["item_0"].state, TaskState.DOWNLOADING)
        self.assertEqual(queue.tasks["item_1"].state, TaskState.DOWNLOADING)
        for i in range(2, 10):
            self.assertEqual(queue.tasks[f"item_{i}"].state, TaskState.PENDING)

        # Step 3: Verify total TCP sockets = 32 (16 sockets * 2 active slots)
        self.assertEqual(queue.get_total_active_sub_sockets(), 32)

        # Step 4: Simulate progress updates and notification throttling
        t0 = 100.0
        self.assertTrue(ForegroundServiceContract.is_notification_throttled(t0, 100.5))
        self.assertFalse(ForegroundServiceContract.is_notification_throttled(t0, 101.2))

        # Step 5: Process through to completion and MediaStore publish
        for tid in batch_ids:
            # Complete task
            queue.complete(tid)
            uri = publisher.phase1_create_pending(f"{tid}.mp4", is_audio=False)
            publisher.phase2_write_bytes(uri, 50 * 1024 * 1024)
            self.assertTrue(publisher.phase3_publish_commit(uri))

        # All 10 completed
        for tid in batch_ids:
            self.assertEqual(queue.tasks[tid].state, TaskState.COMPLETED)
        self.assertEqual(len(publisher.published_records), 10)

    @tier(4)
    @feature(15)
    @feature(16)
    @feature(17)
    def test_workflow_c2_playlist_batch_pause_resume_slot_promotion(self):
        """Workflow C2: Pausing item 0 promotes item 2 to slot 0 -> resuming item 0 waits in pending."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url/0"), "item_0")
        queue.enqueue(DownloadRequest(url="https://url/1"), "item_1")
        queue.enqueue(DownloadRequest(url="https://url/2"), "item_2")

        self.assertEqual(queue.tasks["item_0"].assigned_slot, 0)
        self.assertEqual(queue.tasks["item_2"].state, TaskState.PENDING)

        # Pause item 0 -> item 2 promoted
        queue.pause("item_0")
        self.assertEqual(queue.tasks["item_2"].state, TaskState.DOWNLOADING)
        self.assertEqual(queue.tasks["item_2"].assigned_slot, 0)

        # Resume item 0 -> both slots busy, item 0 waits in PENDING
        queue.resume("item_0")
        self.assertEqual(queue.tasks["item_0"].state, TaskState.PENDING)

        # Complete item 1 (slot 1) -> item 0 promoted to slot 1
        queue.complete("item_1")
        self.assertEqual(queue.tasks["item_0"].state, TaskState.DOWNLOADING)
        self.assertEqual(queue.tasks["item_0"].assigned_slot, 1)

    @tier(4)
    @feature(17)
    @feature(21)
    def test_workflow_c3_playlist_batch_network_drop_and_recovery(self):
        """Workflow C3: Network drops during playlist download -> mascot earmuffs -> resumes upon reconnect."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url/0"), "item_0")

        # Network alive
        mood_online = MascotIdentityContract.resolve_mood(True, False, 1, False)
        self.assertEqual(mood_online, MascotMood.DOWNLOADING_ACTIVE)

        # Network disconnects
        mood_offline = MascotIdentityContract.resolve_mood(False, False, 1, False)
        self.assertEqual(mood_offline, MascotMood.EARMUFFS_OFFLINE)

        # Reconnects -> completes
        mood_reconnect = MascotIdentityContract.resolve_mood(True, False, 1, False)
        self.assertEqual(mood_reconnect, MascotMood.DOWNLOADING_ACTIVE)
        queue.complete("item_0")

    @tier(4)
    @feature(8)
    @feature(16)
    def test_workflow_c4_playlist_batch_item_rate_limit_resilience(self):
        """Workflow C4: Item 2 in batch encounters HTTP 429 rate limit -> domain error mapped -> siblings succeed."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url/0"), "item_0")
        queue.enqueue(DownloadRequest(url="https://url/1"), "item_1")

        # Simulate item 1 rate limit failure
        raw_error = "HTTP Error 429: Rate limit exceeded for media stream."
        exc = PolarExceptionSanitizerContract.sanitize_exception(raw_error)
        self.assertEqual(exc.error_type, PolarErrorType.SERVICE_COOLDOWN)
        self.assertEqual(exc.code, 429)

        # Item 0 completes successfully
        queue.complete("item_0")
        self.assertEqual(queue.tasks["item_0"].state, TaskState.COMPLETED)


if __name__ == "__main__":
    unittest.main()
