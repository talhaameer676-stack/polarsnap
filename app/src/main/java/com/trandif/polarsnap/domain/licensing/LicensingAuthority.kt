package com.trandif.polarsnap.domain.licensing

/**
 * Public interface contract for remote device licensing, kill-switch verification,
 * and silent in-app OTA update orchestration.
 */
interface LicensingAuthority {
    /**
     * Verifies device authorization against the isolated Cloudflare authority.
     * Falls back to the local encrypted grace period if network is unavailable.
     */
    suspend fun verifyDeviceAuthorization(deviceId: String): Result<LicenseStatus>

    /**
     * Checks for new software releases and retrieves release verification metadata.
     */
    suspend fun checkForOtaUpdate(): Result<UpdateInfo>

    /**
     * Silently installs a verified APK package via Android PackageInstaller session.
     */
    suspend fun installOtaUpdateSilently(apkPath: String): Result<Unit>
}
