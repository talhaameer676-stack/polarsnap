package com.trandif.polarsnap.domain.licensing

/**
 * Represents the current authorization and licensing state of a PolarSnap client device.
 *
 * @property isAuthorized True if the device has an active, valid license or is within offline grace.
 * @property isKillSwitchTriggered True if the remote kill-switch has been triggered by the authority.
 * @property offlineGraceExpiresAt Epoch timestamp (in seconds) until which offline grace remains valid.
 * @property statusMessage Human-readable status or error message describing the license condition.
 */
data class LicenseStatus(
    val isAuthorized: Boolean,
    val isKillSwitchTriggered: Boolean,
    val offlineGraceExpiresAt: Long,
    val statusMessage: String
) {
    val isRevoked: Boolean
        get() = isKillSwitchTriggered || !isAuthorized
}
