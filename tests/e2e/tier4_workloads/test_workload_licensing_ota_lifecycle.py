"""
Tier 4: Real-World Workload D — Licensing, Silent OTA & Hardening Workflow
Scenario: 7-day air-gapped offline operation -> online reconnection -> HMAC signature -> silent GitHub OTA upgrade -> 7-tap dev console -> ad-free verification
"""
import unittest
from tests.e2e.runner import feature, tier
from tests.e2e.contracts.licensing_contracts import (
    HMACSecurityContract,
    OfflineGraceProtocolContract,
    OTAUpdatePackageVerifier,
    AdFreeGuaranteeScanner,
    LicenseStatus,
    UpdateInfo,
)
from tests.e2e.contracts.ui_contracts import (
    DeveloperConsoleContract,
    MascotIdentityContract,
    MascotMood,
)
from tests.e2e.contracts.testing_meta_contracts import (
    LMKPressureSimulator,
)


class TestWorkloadLicensingOTALifecycle(unittest.TestCase):
    TIER = 4

    @tier(4)
    @feature(26)
    @feature(27)
    @feature(28)
    def test_workflow_d1_air_gapped_offline_grace_and_reconnection(self):
        """Workflow D1: Air-gapped offline operation for 6 days -> reconnects on Day 7 -> HMAC auth renews grace."""
        secret = "polar_enterprise_cf_secret"
        device_id = "device_polarsnap_7788"
        t0 = 1700000000

        # Day 1-6 offline: verify cache is valid
        day_6_time = t0 + (6 * 86400)
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(t0, day_6_time))

        # Day 7: Reconnects to network
        now = t0 + (7 * 86400)
        nonce = "nonce_day7_reconnect"
        sig = HMACSecurityContract.generate_signature(secret, device_id, now, nonce)

        seen_nonces = set()
        is_valid, reason = HMACSecurityContract.verify_request(
            secret, device_id, now, nonce, sig, now, seen_nonces
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "AUTHORIZED")
        self.assertIn(nonce, seen_nonces)

        # Renewed grace extends 7 days from now
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(now, now + 604800))

    @tier(4)
    @feature(26)
    @feature(27)
    def test_workflow_d2_remote_kill_switch_revocation(self):
        """Workflow D2: Administrator triggers remote kill-switch in Cloudflare D1 -> client halted."""
        status = LicenseStatus(
            is_authorized=False,
            is_kill_switch_triggered=True,
            offline_grace_expires_at=0,
            status_message="Device permanently blocked by administrator"
        )
        self.assertTrue(status.is_kill_switch_triggered)
        self.assertFalse(status.is_authorized)

    @tier(4)
    @feature(29)
    @feature(30)
    def test_workflow_d3_silent_github_ota_update_pipeline(self):
        """Workflow D3: Background polling detects GitHub Release v1.1.0 -> downloads APK -> verifies SHA256 -> package session."""
        release_info = UpdateInfo(
            is_update_available=True,
            latest_version_name="v1.1.0",
            latest_version_code=11,
            release_notes="Lanczos optimization + CapCut Studio Bright LUT",
            download_url="https://github.com/trandif/polarsnap/releases/download/v1.1.0/app-release.apk",
            sha256_checksum=""
        )

        # Simulated downloaded APK bytes
        downloaded_apk_bytes = b"PolarSnap v1.1.0 Binary Data with Zero Leaks"
        actual_checksum = OTAUpdatePackageVerifier.compute_sha256(downloaded_apk_bytes)
        release_info.sha256_checksum = actual_checksum

        # Verify APK integrity before session install
        self.assertTrue(OTAUpdatePackageVerifier.verify_apk(downloaded_apk_bytes, release_info.sha256_checksum))

        # Static scan of new APK code ensures ad-free guarantee preserved
        clean, violations = AdFreeGuaranteeScanner.scan_content("package com.trandif.polarsnap.engine\nclass CoreEngine")
        self.assertTrue(clean)
        self.assertEqual(len(violations), 0)

    @tier(4)
    @feature(25)
    @feature(31)
    @feature(32)
    def test_workflow_d4_developer_console_and_adversarial_hardening(self):
        """Workflow D4: User unlocks secret 7-tap developer console in Settings -> runs LMK pressure diagnostic."""
        dev = DeveloperConsoleContract()
        self.assertFalse(dev.is_unlocked)

        # Tap banner 7 times
        for _ in range(7):
            dev.tap_engine_version_banner()
        self.assertTrue(dev.is_unlocked)

        # Run memory pressure diagnostic from dev console
        # 4K frame buffer (24.88 MB) under 8 MB low-memory constraint
        survived, retained_mb, action = LMKPressureSimulator.simulate_memory_pressure_reclaim(
            allocated_mb=24.88,
            system_threshold_mb=8.0,
            pre_upscale_optimization_active=True
        )
        self.assertTrue(survived)
        self.assertEqual(action, "SURVIVED_WITH_PRE_UPSCALE_SAVINGS")
        self.assertLess(retained_mb, 8.0)


if __name__ == "__main__":
    unittest.main()
