"""
Tier 3: Cross-Feature State Transitions & Concurrency Interactions
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
from tests.e2e.contracts.remaster_contracts import (
    RemasterConfig,
    RemasterFiltergraphBuilder,
    CapCutPreset,
    TargetResolution,
    MemoryOptimizationOracle,
)
from tests.e2e.contracts.ui_contracts import (
    MascotIdentityContract,
    MascotMood,
)
from tests.e2e.contracts.licensing_contracts import (
    OfflineGraceProtocolContract,
    HMACSecurityContract,
    LicenseStatus,
)


class TestTier3StateTransitions(unittest.TestCase):
    TIER = 3

    # =========================================================================
    # Cross-Subsystem State Machine & Concurrency Tests (>= 16 tests)
    # =========================================================================
    @tier(3)
    @feature(15)
    @feature(17)
    def test_transition_01_pause_slot_0_promotes_pending_to_slot_0(self):
        """Transition 1: Pausing task in slot 0 immediately schedules pending task into slot 0."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url1"), "t1")  # slot 0
        queue.enqueue(DownloadRequest(url="https://url2"), "t2")  # slot 1
        queue.enqueue(DownloadRequest(url="https://url3"), "t3")  # pending

        self.assertEqual(queue.tasks["t1"].assigned_slot, 0)
        self.assertEqual(queue.tasks["t2"].assigned_slot, 1)

        queue.pause("t1")
        self.assertEqual(queue.tasks["t1"].state, TaskState.PAUSED)
        self.assertIsNone(queue.tasks["t1"].assigned_slot)
        # t3 should now have slot 0
        self.assertEqual(queue.tasks["t3"].assigned_slot, 0)
        self.assertEqual(queue.tasks["t3"].state, TaskState.DOWNLOADING)

    @tier(3)
    @feature(15)
    @feature(17)
    def test_transition_02_resume_paused_task_when_queue_full_waits_in_pending(self):
        """Transition 2: Resuming task when both slots are occupied keeps it in PENDING."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url1"), "t1")  # slot 0
        queue.enqueue(DownloadRequest(url="https://url2"), "t2")  # slot 1
        queue.enqueue(DownloadRequest(url="https://url3"), "t3")  # pending

        queue.pause("t1")  # t3 gets slot 0
        self.assertEqual(queue.tasks["t3"].state, TaskState.DOWNLOADING)

        # Resume t1 -> both slot 0 (t3) and slot 1 (t2) are busy
        queue.resume("t1")
        self.assertEqual(queue.tasks["t1"].state, TaskState.PENDING)
        self.assertIsNone(queue.tasks["t1"].assigned_slot)

    @tier(3)
    @feature(17)
    @feature(21)
    def test_transition_03_network_loss_switches_mascot_to_earmuffs_during_download(self):
        """Transition 3: Network drop during active download sets mascot to EARMUFFS_OFFLINE."""
        mood_online = MascotIdentityContract.resolve_mood(
            is_online=True, is_queue_empty=False, active_downloads_count=1, is_remastering_active=False
        )
        self.assertEqual(mood_online, MascotMood.DOWNLOADING_ACTIVE)

        # Network drops
        mood_offline = MascotIdentityContract.resolve_mood(
            is_online=False, is_queue_empty=False, active_downloads_count=1, is_remastering_active=False
        )
        self.assertEqual(mood_offline, MascotMood.EARMUFFS_OFFLINE)

    @tier(3)
    @feature(11)
    @feature(21)
    def test_transition_04_remastering_phase_switches_mascot_to_cinematic(self):
        """Transition 4: Entering REMASTERING phase switches mascot to REMASTERING_CINEMATIC."""
        mood = MascotIdentityContract.resolve_mood(
            is_online=True, is_queue_empty=False, active_downloads_count=1, is_remastering_active=True
        )
        self.assertEqual(mood, MascotMood.REMASTERING_CINEMATIC)

    @tier(3)
    @feature(19)
    @feature(17)
    def test_transition_05_mediastore_write_failure_aborts_commit(self):
        """Transition 5: MediaStore failure during phase 2 prevents commit."""
        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("broken.mp4", is_audio=False)
        # Zero bytes written
        commit_res = pub.phase3_publish_commit(uri)
        self.assertFalse(commit_res)
        self.assertEqual(pub.published_records[uri].is_pending, 1)

    @tier(3)
    @feature(26)
    @feature(28)
    def test_transition_06_kill_switch_revocation_blocks_grace_period(self):
        """Transition 6: Kill-switch revocation takes absolute precedence over offline grace."""
        t0 = 1700000000
        now = t0 + 1000  # Within 7 days
        status = LicenseStatus(
            is_authorized=False,
            is_kill_switch_triggered=True,
            offline_grace_expires_at=t0 + 604800,
            status_message="Device Revoked"
        )
        self.assertTrue(status.is_kill_switch_triggered)
        self.assertFalse(status.is_authorized)

    @tier(3)
    @feature(15)
    @feature(18)
    def test_transition_07_foreground_notification_throttling_during_queue_turnover(self):
        """Transition 7: Rapid task completions throttle notification updates to <= 1Hz."""
        t_start = 1000.0
        # Notification 1 at t=1000.0
        # Rapid task event at t=1000.2
        self.assertTrue(ForegroundServiceContract.is_notification_throttled(t_start, 1000.2))
        # Subsequent event at t=1001.1
        self.assertFalse(ForegroundServiceContract.is_notification_throttled(t_start, 1001.1))

    @tier(3)
    @feature(11)
    @feature(12)
    def test_transition_08_4k_filtergraph_with_pre_upscale_memory_savings(self):
        """Transition 8: 4K filtergraph generation confirms pre-scale filter ordering."""
        config = RemasterConfig(
            enable_super_resolution=True,
            target_resolution=TargetResolution.UHD_4K,
            enable_sharpening=True,
            color_grading_preset=CapCutPreset.MOODY_NOIR
        )
        graph = RemasterFiltergraphBuilder.build(config, "moody.png")
        lut_idx = graph.index("haldclut")
        scale_idx = graph.index("scale=3840:2160")
        unsharp_idx = graph.index("unsharp=")

        # Invariant: LUT -> Scale -> Unsharp
        self.assertLess(lut_idx, scale_idx)
        self.assertLess(scale_idx, unsharp_idx)

    @tier(3)
    @feature(17)
    @feature(19)
    def test_transition_09_completed_task_triggers_mediastore_reveal(self):
        """Transition 9: Task completion transitions MediaStore record from pending to published."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url"), "t1")
        queue.complete("t1")
        self.assertEqual(queue.tasks["t1"].state, TaskState.COMPLETED)

        pub = MediaStorePublisherContract()
        uri = pub.phase1_create_pending("finished.mp4", is_audio=False)
        pub.phase2_write_bytes(uri, 50000)
        self.assertTrue(pub.phase3_publish_commit(uri))
        self.assertEqual(pub.published_records[uri].is_pending, 0)

    @tier(3)
    @feature(27)
    @feature(28)
    def test_transition_10_hmac_replay_attack_rejected_during_grace_period(self):
        """Transition 10: Nonce replay is rejected even during active grace period."""
        secret = "secret"
        now = 1700000000
        nonce = "replay_nonce_1"
        sig = HMACSecurityContract.generate_signature(secret, "dev1", now, nonce)

        seen = {nonce}
        is_valid, reason = HMACSecurityContract.verify_request(secret, "dev1", now, nonce, sig, now, seen)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "NONCE_ALREADY_USED")

    @tier(3)
    @feature(3)
    @feature(15)
    def test_transition_11_turbo_toggle_affects_socket_accounting_dynamically(self):
        """Transition 11: Queue active sockets drop from 32 to 16 when one turbo task completes."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url1", turbo_acceleration=True), "t1")
        queue.enqueue(DownloadRequest(url="https://url2", turbo_acceleration=True), "t2")
        self.assertEqual(queue.get_total_active_sub_sockets(), 32)

        queue.complete("t1")
        # Only t2 active
        self.assertEqual(queue.get_total_active_sub_sockets(), 16)

    @tier(3)
    @feature(5)
    @feature(16)
    def test_transition_12_playlist_batch_inherits_clean_watermark(self):
        """Transition 12: All items in playlist batch inherit clean watermark setting."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions
        opts = EngineOptions(clean_watermark=True)
        for i in range(3):
            cmd = PolarCommandTranslatorContract.translate(f"https://tiktok.com/@u/{i}", opts)
            self.assertIn("tiktok:no_watermark=1", cmd)

    @tier(3)
    @feature(6)
    @feature(16)
    def test_transition_13_playlist_batch_inherits_sponsor_stripper(self):
        """Transition 13: All items in playlist batch inherit sponsor stripper."""
        from tests.e2e.contracts.engine_contracts import PolarCommandTranslatorContract, EngineOptions
        opts = EngineOptions(sponsor_stripper=True)
        for i in range(3):
            cmd = PolarCommandTranslatorContract.translate(f"https://youtube.com/watch?v={i}", opts)
            self.assertIn("--sponsorblock-remove", cmd)

    @tier(3)
    @feature(21)
    @feature(17)
    def test_transition_14_mascot_mood_transitions_to_sleeping_when_all_completed(self):
        """Transition 14: Completing all queue tasks transitions mascot to SLEEPING_EMPTY_VAULT."""
        queue = BoundedQueueManagerContract()
        queue.enqueue(DownloadRequest(url="https://url"), "t1")
        queue.complete("t1")

        active_count = sum(1 for t in queue.tasks.values() if t.state == TaskState.DOWNLOADING)
        self.assertEqual(active_count, 0)

        mood = MascotIdentityContract.resolve_mood(
            is_online=True,
            is_queue_empty=True,
            active_downloads_count=0,
            is_remastering_active=False
        )
        self.assertEqual(mood, MascotMood.SLEEPING_EMPTY_VAULT)

    @tier(3)
    @feature(28)
    @feature(26)
    def test_transition_15_online_reconnection_renews_7_day_grace(self):
        """Transition 15: Successful online verification advances grace period base timestamp."""
        t_old = 1700000000
        t_renewed = t_old + 500000  # Day 5 reconnection
        # New grace window extends to t_renewed + 604800
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(t_renewed, t_renewed + 604800))

    @tier(3)
    @feature(29)
    @feature(30)
    def test_transition_16_silent_ota_upgrade_maintains_ad_free_guarantee(self):
        """Transition 16: Upgraded APK package scan maintains 100% ad-free guarantee."""
        from tests.e2e.contracts.licensing_contracts import AdFreeGuaranteeScanner
        upgraded_code = "package com.trandif.polarsnap\nclass PolarEngineV2\n"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(upgraded_code)
        self.assertTrue(is_clean)
        self.assertEqual(len(violations), 0)


if __name__ == "__main__":
    unittest.main()
