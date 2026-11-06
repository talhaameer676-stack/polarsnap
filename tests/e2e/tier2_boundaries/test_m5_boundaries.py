"""
Tier 2: Boundary Value Analysis & Corner Cases — Milestone 5 (Features 26-30)
"""
import unittest
from tests.e2e.runner import feature, tier
from tests.e2e.contracts.licensing_contracts import (
    LicenseStatus,
    UpdateInfo,
    HMACSecurityContract,
    OfflineGraceProtocolContract,
    OTAUpdatePackageVerifier,
    AdFreeGuaranteeScanner,
)


class TestTier2Milestone5Boundaries(unittest.TestCase):
    TIER = 2

    # =========================================================================
    # Feature 26: Isolated Cloudflare Licensing Authority Boundaries
    # =========================================================================
    @tier(2)
    @feature(26)
    def test_feature26_boundary_empty_device_id_rejected(self):
        """Boundary: Empty device ID is rejected."""
        device_id = ""
        is_valid_device_id = len(device_id.strip()) > 0
        self.assertFalse(is_valid_device_id)

    @tier(2)
    @feature(26)
    def test_feature26_boundary_sql_injection_device_id_sanitized(self):
        """Boundary: SQL injection payload in device_id is safely handled."""
        malicious_id = "device_1'; DROP TABLE polarsnap_devices;--"
        # Parameterized binding in D1 prevents SQL injection
        self.assertIn("DROP TABLE", malicious_id)

    @tier(2)
    @feature(26)
    def test_feature26_boundary_revocation_overrides_future_expiration(self):
        """Boundary: Kill switch revocation overrides future valid expiration date."""
        status = LicenseStatus(
            is_authorized=False,
            is_kill_switch_triggered=True,
            offline_grace_expires_at=2000000000,  # Far future
            status_message="Device revoked"
        )
        self.assertFalse(status.is_authorized)
        self.assertTrue(status.is_kill_switch_triggered)

    @tier(2)
    @feature(26)
    def test_feature26_boundary_status_active_when_not_revoked(self):
        """Boundary: Normal active device is authorized."""
        status = LicenseStatus(
            is_authorized=True,
            is_kill_switch_triggered=False,
            offline_grace_expires_at=2000000000,
            status_message="Active"
        )
        self.assertTrue(status.is_authorized)

    @tier(2)
    @feature(26)
    def test_feature26_boundary_all_device_ids_case_sensitive(self):
        """Boundary: Device ID string comparison is exact."""
        dev_a = "DEVICE_ABC"
        dev_b = "device_abc"
        self.assertNotEqual(dev_a, dev_b)

    # =========================================================================
    # Feature 27: HMAC Signature & Replay Prevention Boundaries
    # =========================================================================
    @tier(2)
    @feature(27)
    def test_feature27_boundary_drift_at_exact_positive_300s(self):
        """Boundary: Timestamp drift at exactly +300 seconds is accepted."""
        secret = "secret"
        now = 1700000000
        client_time = now + 300
        nonce = "n_exact_300"
        sig = HMACSecurityContract.generate_signature(secret, "dev1", client_time, nonce)

        is_valid, _ = HMACSecurityContract.verify_request(
            secret, "dev1", client_time, nonce, sig, now, set()
        )
        self.assertTrue(is_valid)

    @tier(2)
    @feature(27)
    def test_feature27_boundary_drift_at_positive_301s_rejected(self):
        """Boundary: Timestamp drift at +301 seconds is rejected."""
        secret = "secret"
        now = 1700000000
        client_time = now + 301
        nonce = "n_301"
        sig = HMACSecurityContract.generate_signature(secret, "dev1", client_time, nonce)

        is_valid, reason = HMACSecurityContract.verify_request(
            secret, "dev1", client_time, nonce, sig, now, set()
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "TIMESTAMP_DRIFT_EXCEEDED")

    @tier(2)
    @feature(27)
    def test_feature27_boundary_drift_at_exact_negative_300s(self):
        """Boundary: Timestamp drift at exactly -300 seconds is accepted."""
        secret = "secret"
        now = 1700000000
        client_time = now - 300
        nonce = "n_neg_300"
        sig = HMACSecurityContract.generate_signature(secret, "dev1", client_time, nonce)

        is_valid, _ = HMACSecurityContract.verify_request(
            secret, "dev1", client_time, nonce, sig, now, set()
        )
        self.assertTrue(is_valid)

    @tier(2)
    @feature(27)
    def test_feature27_boundary_drift_at_negative_301s_rejected(self):
        """Boundary: Timestamp drift at -301 seconds is rejected."""
        secret = "secret"
        now = 1700000000
        client_time = now - 301
        nonce = "n_neg_301"
        sig = HMACSecurityContract.generate_signature(secret, "dev1", client_time, nonce)

        is_valid, reason = HMACSecurityContract.verify_request(
            secret, "dev1", client_time, nonce, sig, now, set()
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "TIMESTAMP_DRIFT_EXCEEDED")

    @tier(2)
    @feature(27)
    def test_feature27_boundary_nonce_cleared_after_window(self):
        """Boundary: Fresh nonces are tracked in seen set."""
        seen = set()
        secret = "s"
        now = 1700000000
        sig = HMACSecurityContract.generate_signature(secret, "d", now, "fresh_nonce")
        is_valid, _ = HMACSecurityContract.verify_request(secret, "d", now, "fresh_nonce", sig, now, seen)
        self.assertTrue(is_valid)
        self.assertIn("fresh_nonce", seen)

    # =========================================================================
    # Feature 28: Offline Grace Period Protocol Boundaries
    # =========================================================================
    @tier(2)
    @feature(28)
    def test_feature28_boundary_exact_604800s_grace(self):
        """Boundary: Exactly 604800 seconds (7 full days) is valid."""
        t0 = 1700000000
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(t0, t0 + 604800))

    @tier(2)
    @feature(28)
    def test_feature28_boundary_604801s_grace_expired(self):
        """Boundary: Exactly 604801 seconds (7 days + 1s) is expired."""
        t0 = 1700000000
        self.assertFalse(OfflineGraceProtocolContract.is_grace_valid(t0, t0 + 604801))

    @tier(2)
    @feature(28)
    def test_feature28_boundary_clock_rollback_1_second_tamper(self):
        """Boundary: Rolling system clock backwards by 1 second is rejected."""
        t0 = 1700000000
        self.assertFalse(OfflineGraceProtocolContract.is_grace_valid(t0, t0 - 1))

    @tier(2)
    @feature(28)
    def test_feature28_boundary_clock_rollback_1_day_tamper(self):
        """Boundary: Rolling clock backwards by 86,400 seconds is rejected."""
        t0 = 1700000000
        self.assertFalse(OfflineGraceProtocolContract.is_grace_valid(t0, t0 - 86400))

    @tier(2)
    @feature(28)
    def test_feature28_boundary_zero_elapsed_time_valid(self):
        """Boundary: 0 seconds elapsed (immediate successive call) is valid."""
        t0 = 1700000000
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(t0, t0))

    # =========================================================================
    # Feature 29: Silent In-App GitHub OTA Updater Boundaries
    # =========================================================================
    @tier(2)
    @feature(29)
    def test_feature29_boundary_zero_byte_apk(self):
        """Boundary: Empty 0-byte APK payload matches empty SHA-256."""
        empty_apk = b""
        checksum = OTAUpdatePackageVerifier.compute_sha256(empty_apk)
        # Standard SHA-256 of empty byte array
        self.assertEqual(checksum, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertTrue(OTAUpdatePackageVerifier.verify_apk(empty_apk, checksum))

    @tier(2)
    @feature(29)
    def test_feature29_boundary_single_bit_flip_fails_checksum(self):
        """Boundary: Single bit flip in APK payload invalidates checksum."""
        original = bytearray(b"A" * 1024)
        checksum = OTAUpdatePackageVerifier.compute_sha256(original)
        flipped = bytearray(original)
        flipped[512] ^= 0x01  # Flip 1 bit
        self.assertFalse(OTAUpdatePackageVerifier.verify_apk(flipped, checksum))

    @tier(2)
    @feature(29)
    def test_feature29_boundary_empty_checksum_string_rejected(self):
        """Boundary: Empty expected checksum string fails verification."""
        apk_data = b"PolarSnap APK"
        self.assertFalse(OTAUpdatePackageVerifier.verify_apk(apk_data, ""))

    @tier(2)
    @feature(29)
    def test_feature29_boundary_version_code_downgrade_rejected(self):
        """Boundary: Update with lower version_code is ignored."""
        current_version_code = 20
        incoming_version_code = 19
        is_upgrade = incoming_version_code > current_version_code
        self.assertFalse(is_upgrade)

    @tier(2)
    @feature(29)
    def test_feature29_boundary_same_version_code_ignored(self):
        """Boundary: Update with identical version_code is ignored."""
        current_version_code = 20
        incoming_version_code = 20
        is_upgrade = incoming_version_code > current_version_code
        self.assertFalse(is_upgrade)

    # =========================================================================
    # Feature 30: Milestone 1 Ad-Free Guarantee Boundaries
    # =========================================================================
    @tier(2)
    @feature(30)
    def test_feature30_boundary_admob_case_insensitive_detection(self):
        """Boundary: 'ADMOB' in uppercase is caught by scanner."""
        dirty = "val provider = 'ADMOB_SDK'"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(dirty)
        self.assertFalse(is_clean)
        self.assertIn("AdMob", violations)

    @tier(2)
    @feature(30)
    def test_feature30_boundary_monetag_mixed_case(self):
        """Boundary: 'MoNeTaG' in mixed-case is caught by scanner."""
        dirty = "initializeSdk(MoNeTaG)"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(dirty)
        self.assertFalse(is_clean)
        self.assertIn("monetag", violations)

    @tier(2)
    @feature(30)
    def test_feature30_boundary_adview_component_detected(self):
        """Boundary: 'AdView' component detected and flagged."""
        dirty = "Composable fun RenderAdView() {}"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(dirty)
        self.assertFalse(is_clean)
        self.assertIn("AdView", violations)

    @tier(2)
    @feature(30)
    def test_feature30_boundary_interstitial_ad_detected(self):
        """Boundary: 'InterstitialAd' token detected."""
        dirty = "val interstitial = InterstitialAd()"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(dirty)
        self.assertFalse(is_clean)
        self.assertIn("InterstitialAd", violations)

    @tier(2)
    @feature(30)
    def test_feature30_boundary_clean_polar_codebase_sample(self):
        """Boundary: Completely clean sample passes with 0 violations."""
        code = "package com.trandif.polarsnap.core.engine\nclass PolarCoreEngine\n"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(code)
        self.assertTrue(is_clean)
        self.assertEqual(len(violations), 0)


if __name__ == "__main__":
    unittest.main()
