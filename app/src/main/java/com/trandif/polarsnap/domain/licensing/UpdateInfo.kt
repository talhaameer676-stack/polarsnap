package com.trandif.polarsnap.domain.licensing

/**
 * Details of an available software update detected from the Cloudflare / GitHub Releases feed.
 *
 * @property isUpdateAvailable True if a newer version is ready for installation.
 * @property latestVersionName Semantic version string (e.g. "2.4.1").
 * @property latestVersionCode Numeric build number (e.g. 241).
 * @property releaseNotes Changelog and release summary.
 * @property downloadUrl Direct HTTPS URL for the arm64-v8a target APK binary.
 * @property sha256Checksum Expected SHA-256 hex digest for binary tamper validation.
 */
data class UpdateInfo(
    val isUpdateAvailable: Boolean,
    val latestVersionName: String,
    val latestVersionCode: Int,
    val releaseNotes: String,
    val downloadUrl: String,
    val sha256Checksum: String
)
