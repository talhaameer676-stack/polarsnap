"""
PolarSnap Licensing, Security & OTA Contracts (Milestone 5: Features 26-30)
"""
from dataclasses import dataclass
import hashlib
import hmac
import time
from typing import Dict, Set, Optional, Tuple, List


@dataclass
class LicenseStatus:
    is_authorized: bool
    is_kill_switch_triggered: bool
    offline_grace_expires_at: int
    status_message: str


@dataclass
class UpdateInfo:
    is_update_available: bool
    latest_version_name: str
    latest_version_code: int
    release_notes: str
    download_url: str
    sha256_checksum: str


class HMACSecurityContract:
    TIMESTAMP_DRIFT_TOLERANCE_SECONDS = 300  # +/- 5 minutes

    @staticmethod
    def generate_signature(secret_key: str, device_id: str, timestamp: int, nonce: str) -> str:
        payload = f"{device_id}:{timestamp}:{nonce}".encode("utf-8")
        return hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    @staticmethod
    def verify_request(
        secret_key: str,
        device_id: str,
        timestamp: int,
        nonce: str,
        provided_signature: str,
        current_server_time: int,
        seen_nonces: Set[str]
    ) -> Tuple[bool, str]:
        # 1. Timestamp drift check
        if abs(current_server_time - timestamp) > HMACSecurityContract.TIMESTAMP_DRIFT_TOLERANCE_SECONDS:
            return False, "TIMESTAMP_DRIFT_EXCEEDED"

        # 2. Nonce replay check
        if nonce in seen_nonces:
            return False, "NONCE_ALREADY_USED"

        # 3. Signature calculation check
        expected_sig = HMACSecurityContract.generate_signature(secret_key, device_id, timestamp, nonce)
        if not hmac.compare_digest(expected_sig, provided_signature):
            return False, "SIGNATURE_MISMATCH"

        seen_nonces.add(nonce)
        return True, "AUTHORIZED"


class OfflineGraceProtocolContract:
    OFFLINE_GRACE_PERIOD_SECONDS = 7 * 24 * 3600  # 604,800 seconds (7 days)

    @staticmethod
    def is_grace_valid(last_verified_timestamp: int, current_timestamp: int) -> bool:
        elapsed = current_timestamp - last_verified_timestamp
        if elapsed < 0:
            # Clock tampering detected (time moved backwards)
            return False
        return elapsed <= OfflineGraceProtocolContract.OFFLINE_GRACE_PERIOD_SECONDS


class OTAUpdatePackageVerifier:
    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def verify_apk(data: bytes, expected_checksum: str) -> bool:
        computed = OTAUpdatePackageVerifier.compute_sha256(data)
        return hmac.compare_digest(computed.lower(), expected_checksum.lower())


class AdFreeGuaranteeScanner:
    FORBIDDEN_AD_STRINGS = [
        "com.monetag",
        "monetag",
        "com.google.android.gms.ads",
        "com.unity3d.ads",
        "com.applovin",
        "com.facebook.ads",
        "AdMob",
        "AdView",
        "BannerAd",
        "InterstitialAd",
    ]

    @staticmethod
    def scan_content(content: str) -> Tuple[bool, List[str]]:
        found_violations = []
        for term in AdFreeGuaranteeScanner.FORBIDDEN_AD_STRINGS:
            if term.lower() in content.lower():
                found_violations.append(term)
        return (len(found_violations) == 0, found_violations)
