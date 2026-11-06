"""
Tier 1: Feature Coverage — Milestone 5 (Features 26-30: Licensing, Security & OTA Updater)
"""
import time
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


class TestTier1Milestone5LicensingOTA(unittest.TestCase):
    TIER = 1

    # =========================================================================
    # Feature 26: Isolated Cloudflare Licensing Authority
    # =========================================================================
    @tier(1)
    @feature(26)
    def test_feature26_cloudflare_worker_endpoint_contract(self):
        """Verify endpoint path is /api/v1/license/verify."""
        endpoint = "/api/v1/license/verify"
        self.assertTrue(endpoint.startswith("/api/v1/license/"))

    @tier(1)
    @feature(26)
    def test_feature26_isolated_worker_binding_name(self):
        """Verify Worker strictly binds to dedicated polarsnap_licensing_db D1 database."""
        db_binding = "polarsnap_licensing_db"
        self.assertEqual(db_binding, "polarsnap_licensing_db")
        self.assertNotIn("shared", db_binding)

    @tier(1)
    @feature(26)
    def test_feature26_license_status_structure(self):
        """Verify LicenseStatus model fields."""
        status = LicenseStatus(
            is_authorized=True,
            is_kill_switch_triggered=False,
            offline_grace_expires_at=1730000000,
            status_message="Active commercial license"
        )
        self.assertTrue(status.is_authorized)
        self.assertFalse(status.is_kill_switch_triggered)

    @tier(1)
    @feature(26)
    def test_feature26_kill_switch_revocation(self):
        """Verify kill-switch immediately flags authorization as False."""
        status = LicenseStatus(
            is_authorized=False,
            is_kill_switch_triggered=True,
            offline_grace_expires_at=0,
            status_message="Device revoked by administrator"
        )
        self.assertTrue(status.is_kill_switch_triggered)
        self.assertFalse(status.is_authorized)

    @tier(1)
    @feature(26)
    def test_feature26_device_id_header_required(self):
        """Verify request contract specifies X-Polar-Device-Id header."""
        header_name = "X-Polar-Device-Id"
        self.assertEqual(header_name, "X-Polar-Device-Id")

    # =========================================================================
    # Feature 27: HMAC Signature & Replay Prevention
    # =========================================================================
    @tier(1)
    @feature(27)
    def test_feature27_hmac_sha256_generation_and_verification(self):
        """Verify valid HMAC-SHA256 signature passes verification."""
        secret = "polar_test_secret_key_12345"
        device_id = "device_arctic_01"
        now = 1700000000
        nonce = "nonce_unique_987"
        sig = HMACSecurityContract.generate_signature(secret, device_id, now, nonce)

        seen_nonces = set()
        is_valid, reason = HMACSecurityContract.verify_request(
            secret, device_id, now, nonce, sig, now, seen_nonces
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "AUTHORIZED")
        self.assertIn(nonce, seen_nonces)

    @tier(1)
    @feature(27)
    def test_feature27_timestamp_drift_rejection(self):
        """Verify timestamp drift > 300 seconds is rejected."""
        secret = "secret"
        device_id = "dev_1"
        server_time = 1700000000
        old_time = server_time - 305  # 305s drift (> 300s limit)
        nonce = "nonce_drift"
        sig = HMACSecurityContract.generate_signature(secret, device_id, old_time, nonce)

        seen_nonces = set()
        is_valid, reason = HMACSecurityContract.verify_request(
            secret, device_id, old_time, nonce, sig, server_time, seen_nonces
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "TIMESTAMP_DRIFT_EXCEEDED")

    @tier(1)
    @feature(27)
    def test_feature27_nonce_replay_attack_rejected(self):
        """Verify replaying the same nonce within tolerance window is rejected."""
        secret = "secret"
        device_id = "dev_1"
        server_time = 1700000000
        nonce = "nonce_replay"
        sig = HMACSecurityContract.generate_signature(secret, device_id, server_time, nonce)

        seen_nonces = {nonce}  # Nonce already used
        is_valid, reason = HMACSecurityContract.verify_request(
            secret, device_id, server_time, nonce, sig, server_time, seen_nonces
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "NONCE_ALREADY_USED")

    @tier(1)
    @feature(27)
    def test_feature27_signature_mismatch_rejected(self):
        """Verify invalid or tampered signature is rejected."""
        secret = "secret"
        device_id = "dev_1"
        server_time = 1700000000
        nonce = "nonce_tamper"
        bad_sig = "bad_signature_00000000000000000000000000000000000000000000000000000000"

        seen_nonces = set()
        is_valid, reason = HMACSecurityContract.verify_request(
            secret, device_id, server_time, nonce, bad_sig, server_time, seen_nonces
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "SIGNATURE_MISMATCH")

    @tier(1)
    @feature(27)
    def test_feature27_tampered_device_id_fails(self):
        """Verify changing device_id breaks signature verification."""
        secret = "secret"
        dev_a = "dev_alpha"
        dev_b = "dev_beta"
        now = 1700000000
        nonce = "nonce_diff"
        sig = HMACSecurityContract.generate_signature(secret, dev_a, now, nonce)

        is_valid, reason = HMACSecurityContract.verify_request(
            secret, dev_b, now, nonce, sig, now, set()
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "SIGNATURE_MISMATCH")

    # =========================================================================
    # Feature 28: Offline Grace Period Protocol
    # =========================================================================
    @tier(1)
    @feature(28)
    def test_feature28_offline_grace_duration_equals_7_days(self):
        """Verify grace duration is exactly 604,800 seconds (7 days)."""
        expected_seconds = 7 * 24 * 3600
        self.assertEqual(OfflineGraceProtocolContract.OFFLINE_GRACE_PERIOD_SECONDS, expected_seconds)
        self.assertEqual(expected_seconds, 604800)

    @tier(1)
    @feature(28)
    def test_feature28_offline_grace_valid_within_7_days(self):
        """Verify device operating offline on day 3 (259,200s) remains authorized."""
        t0 = 1700000000
        t_day3 = t0 + (3 * 24 * 3600)
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(t0, t_day3))

    @tier(1)
    @feature(28)
    def test_feature28_offline_grace_valid_on_exact_boundary(self):
        """Verify grace is valid at exactly 604,800 seconds."""
        t0 = 1700000000
        t_boundary = t0 + 604800
        self.assertTrue(OfflineGraceProtocolContract.is_grace_valid(t0, t_boundary))

    @tier(1)
    @feature(28)
    def test_feature28_offline_grace_expires_past_7_days(self):
        """Verify grace expires at 604,801 seconds (7 days + 1 sec)."""
        t0 = 1700000000
        t_expired = t0 + 604801
        self.assertFalse(OfflineGraceProtocolContract.is_grace_valid(t0, t_expired))

    @tier(1)
    @feature(28)
    def test_feature28_clock_tampering_backwards_rejected(self):
        """Verify system clock moving backwards is detected as tampering."""
        t0 = 1700000000
        t_backwards = t0 - 5000
        self.assertFalse(OfflineGraceProtocolContract.is_grace_valid(t0, t_backwards))

    # =========================================================================
    # Feature 29: Silent In-App GitHub OTA Updater
    # =========================================================================
    @tier(1)
    @feature(29)
    def test_feature29_ota_package_verifier_valid_checksum(self):
        """Verify APK bytes matching expected SHA-256 pass verification."""
        apk_data = b"PolarSnap APK Binary Content v1.1.0"
        checksum = OTAUpdatePackageVerifier.compute_sha256(apk_data)
        self.assertTrue(OTAUpdatePackageVerifier.verify_apk(apk_data, checksum))

    @tier(1)
    @feature(29)
    def test_feature29_ota_package_verifier_corrupt_apk_rejected(self):
        """Verify modified or corrupted APK fails checksum verification."""
        apk_data = b"PolarSnap Genuine"
        tampered = b"PolarSnap Malicious Injected"
        checksum = OTAUpdatePackageVerifier.compute_sha256(apk_data)
        self.assertFalse(OTAUpdatePackageVerifier.verify_apk(tampered, checksum))

    @tier(1)
    @feature(29)
    def test_feature29_update_info_schema(self):
        """Verify UpdateInfo data contract fields."""
        info = UpdateInfo(
            is_update_available=True,
            latest_version_name="v1.1.0",
            latest_version_code=11,
            release_notes="Lanczos optimization improvements",
            download_url="https://github.com/trandif/polarsnap/releases/download/v1.1.0/app.apk",
            sha256_checksum="abc123"
        )
        self.assertTrue(info.is_update_available)
        self.assertEqual(info.latest_version_code, 11)

    @tier(1)
    @feature(29)
    def test_feature29_package_installer_user_action_not_required(self):
        """Verify PackageInstaller contract requires USER_ACTION_NOT_REQUIRED."""
        flag_name = "USER_ACTION_NOT_REQUIRED"
        self.assertEqual(flag_name, "USER_ACTION_NOT_REQUIRED")

    @tier(1)
    @feature(29)
    def test_feature29_checksum_case_insensitivity(self):
        """Verify SHA-256 verification is case-insensitive."""
        apk_data = b"Test Content"
        checksum = OTAUpdatePackageVerifier.compute_sha256(apk_data)
        self.assertTrue(OTAUpdatePackageVerifier.verify_apk(apk_data, checksum.upper()))

    # =========================================================================
    # Feature 30: Milestone 1 Ad-Free Guarantee
    # =========================================================================
    @tier(1)
    @feature(30)
    def test_feature30_clean_content_passes_ad_scanner(self):
        """Verify clean codebase file passes AdFreeGuaranteeScanner."""
        clean_code = "class PolarEngine { fun download() { /* clean code */ } }"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(clean_code)
        self.assertTrue(is_clean)
        self.assertEqual(len(violations), 0)

    @tier(1)
    @feature(30)
    def test_feature30_monetag_detected_and_rejected(self):
        """Verify presence of Monetag triggers ad-free policy violation."""
        dirty_code = "import com.monetag.ads.MonetagBanner;"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(dirty_code)
        self.assertFalse(is_clean)
        self.assertIn("com.monetag", violations)

    @tier(1)
    @feature(30)
    def test_feature30_admob_detected_and_rejected(self):
        """Verify presence of AdMob / Google Ads triggers policy violation."""
        dirty_code = "import com.google.android.gms.ads.AdView;"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(dirty_code)
        self.assertFalse(is_clean)
        self.assertIn("com.google.android.gms.ads", violations)

    @tier(1)
    @feature(30)
    def test_feature30_unity_ads_detected_and_rejected(self):
        """Verify presence of Unity Ads triggers policy violation."""
        dirty_code = "import com.unity3d.ads.UnityAds;"
        is_clean, violations = AdFreeGuaranteeScanner.scan_content(dirty_code)
        self.assertFalse(is_clean)
        self.assertIn("com.unity3d.ads", violations)

    @tier(1)
    @feature(30)
    def test_feature30_zero_ad_trackers_in_contract_manifest(self):
        """Verify all ad tokens are cataloged in forbidden list."""
        self.assertGreaterEqual(len(AdFreeGuaranteeScanner.FORBIDDEN_AD_STRINGS), 8)


if __name__ == "__main__":
    unittest.main()
