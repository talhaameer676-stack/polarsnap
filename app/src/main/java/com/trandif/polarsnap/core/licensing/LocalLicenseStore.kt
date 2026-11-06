package com.trandif.polarsnap.core.licensing

import com.trandif.polarsnap.domain.licensing.LicenseStatus

/**
 * Interface abstraction for local key-value persistence.
 * Enables both Android EncryptedSharedPreferences in production and in-memory mock stores in unit tests.
 */
interface LicenseStorageDelegate {
    fun getString(key: String, defaultValue: String?): String?
    fun putString(key: String, value: String?)
    fun getBoolean(key: String, defaultValue: Boolean): Boolean
    fun putBoolean(key: String, value: Boolean)
    fun getLong(key: String, defaultValue: Long): Long
    fun putLong(key: String, value: Long)
    fun remove(key: String)
    fun clear()
}

/**
 * In-memory storage delegate for unit tests and JVM standalone execution.
 */
class InMemoryLicenseStorageDelegate : LicenseStorageDelegate {
    private val stringMap = mutableMapOf<String, String>()
    private val boolMap = mutableMapOf<String, Boolean>()
    private val longMap = mutableMapOf<String, Long>()

    override fun getString(key: String, defaultValue: String?): String? = stringMap[key] ?: defaultValue
    override fun putString(key: String, value: String?) {
        if (value != null) stringMap[key] = value else stringMap.remove(key)
    }

    override fun getBoolean(key: String, defaultValue: Boolean): Boolean = boolMap[key] ?: defaultValue
    override fun putBoolean(key: String, value: Boolean) {
        boolMap[key] = value
    }

    override fun getLong(key: String, defaultValue: Long): Long = longMap[key] ?: defaultValue
    override fun putLong(key: String, value: Long) {
        longMap[key] = value
    }

    override fun remove(key: String) {
        stringMap.remove(key)
        boolMap.remove(key)
        longMap.remove(key)
    }

    override fun clear() {
        stringMap.clear()
        boolMap.clear()
        longMap.clear()
    }
}

/**
 * Local encrypted store enforcing the 7-day offline grace period protocol.
 * 
 * Rules:
 * 1. An authorized license grants exactly 604,800 seconds (7 days) of uninterrupted offline usage.
 * 2. If the remote kill-switch is triggered or status is REVOKED, offline grace is voided immediately.
 * 3. If the device clock moves backwards before lastVerifiedTimestamp, tampering is detected and grace is invalidated.
 */
class LocalLicenseStore(
    private val storage: LicenseStorageDelegate = InMemoryLicenseStorageDelegate()
) {
    companion object {
        const val OFFLINE_GRACE_PERIOD_SECONDS = 7 * 24 * 3600L // 604,800 seconds

        private const val KEY_STATUS = "key_license_status"
        private const val KEY_KILL_SWITCH = "key_kill_switch_triggered"
        private const val KEY_GRACE_EXPIRES_AT = "key_offline_grace_expires_at"
        private const val KEY_LAST_VERIFIED = "key_last_verified_timestamp"
        private const val KEY_TIER = "key_license_tier"
        private const val KEY_SERVER_SIG = "key_server_signature"
        private const val KEY_LAST_NONCE = "key_last_consumed_nonce"
    }

    /**
     * Persists the authoritative license state returned from the Cloudflare authority.
     */
    fun saveLicense(
        status: String,
        isKillSwitch: Boolean,
        graceExpiresAt: Long,
        verifiedAt: Long,
        tier: String = "FREE",
        signature: String? = null,
        nonce: String? = null
    ) {
        storage.putString(KEY_STATUS, status)
        storage.putBoolean(KEY_KILL_SWITCH, isKillSwitch)
        storage.putLong(KEY_GRACE_EXPIRES_AT, graceExpiresAt)
        storage.putLong(KEY_LAST_VERIFIED, verifiedAt)
        storage.putString(KEY_TIER, tier)
        storage.putString(KEY_SERVER_SIG, signature)
        storage.putString(KEY_LAST_NONCE, nonce)
    }

    /**
     * Evaluates whether the device is currently operating within the valid 7-day offline grace period.
     */
    fun isWithinGracePeriod(currentTimestampSeconds: Long): Boolean {
        val isKillSwitch = storage.getBoolean(KEY_KILL_SWITCH, false)
        if (isKillSwitch) return false

        val status = storage.getString(KEY_STATUS, null) ?: return false
        if (status != "AUTHORIZED") return false

        val lastVerified = storage.getLong(KEY_LAST_VERIFIED, 0L)
        if (lastVerified == 0L) return false

        // Clock tampering detection: system clock cannot be in the past relative to last verification
        if (currentTimestampSeconds < lastVerified) {
            return false
        }

        val graceExpiresAt = storage.getLong(KEY_GRACE_EXPIRES_AT, 0L)
        return currentTimestampSeconds <= graceExpiresAt
    }

    /**
     * Loads the current evaluated license status based on local cache and current epoch time.
     */
    fun loadStatus(currentTimestampSeconds: Long): LicenseStatus {
        val isKillSwitch = storage.getBoolean(KEY_KILL_SWITCH, false)
        val graceExpiresAt = storage.getLong(KEY_GRACE_EXPIRES_AT, 0L)

        if (isKillSwitch) {
            return LicenseStatus(
                isAuthorized = false,
                isKillSwitchTriggered = true,
                offlineGraceExpiresAt = 0L,
                statusMessage = "Application disabled by remote kill-switch."
            )
        }

        val status = storage.getString(KEY_STATUS, null)
        if (status == null) {
            return LicenseStatus(
                isAuthorized = false,
                isKillSwitchTriggered = false,
                offlineGraceExpiresAt = 0L,
                statusMessage = "Unlicensed device. Internet connection required for initial authorization."
            )
        }

        if (isWithinGracePeriod(currentTimestampSeconds)) {
            val remainingSec = graceExpiresAt - currentTimestampSeconds
            val remainingHours = remainingSec / 3600
            return LicenseStatus(
                isAuthorized = true,
                isKillSwitchTriggered = false,
                offlineGraceExpiresAt = graceExpiresAt,
                statusMessage = "Active authorization (Offline grace remaining: ~${remainingHours}h)."
            )
        }

        return LicenseStatus(
            isAuthorized = false,
            isKillSwitchTriggered = false,
            offlineGraceExpiresAt = graceExpiresAt,
            statusMessage = "7-day offline grace period expired. Internet connection required to re-verify license."
        )
    }

    /**
     * Clears all cached licensing data.
     */
    fun clear() {
        storage.clear()
    }
}
