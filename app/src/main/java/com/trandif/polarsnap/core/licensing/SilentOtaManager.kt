package com.trandif.polarsnap.core.licensing

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import com.trandif.polarsnap.domain.licensing.UpdateInfo
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest

/**
 * Interface abstraction for Android PackageInstaller session operations.
 * Allows pure unit testing of session configuration, byte transfer, and commit.
 */
interface PackageInstallerSessionDelegate {
    fun createAndCommitSession(
        packageName: String,
        apkStream: InputStream,
        requireUserAction: Int, // 0 = USER_ACTION_UNSPECIFIED, 1 = USER_ACTION_REQUIRED, 2 = USER_ACTION_NOT_REQUIRED
        onSessionCreated: (sessionId: Int) -> Unit = {}
    ): Result<Unit>
}

/**
 * Android system implementation of PackageInstallerSessionDelegate using Android framework APIs.
 */
class AndroidPackageInstallerDelegate(
    private val context: Context
) : PackageInstallerSessionDelegate {

    companion object {
        const val ACTION_INSTALL_STATUS = "com.trandif.polarsnap.ACTION_INSTALL_STATUS"
    }

    override fun createAndCommitSession(
        packageName: String,
        apkStream: InputStream,
        requireUserAction: Int,
        onSessionCreated: (sessionId: Int) -> Unit
    ): Result<Unit> {
        return try {
            val packageInstaller = context.packageManager.packageInstaller
            val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
                setAppPackageName(packageName)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    // Constant 2 corresponds to PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED
                    setRequireUserAction(requireUserAction)
                }
            }

            val sessionId = packageInstaller.createSession(params)
            onSessionCreated(sessionId)
            val session = packageInstaller.openSession(sessionId)

            session.openWrite("polarsnap_update.apk", 0, -1).use { outputStream ->
                apkStream.copyTo(outputStream)
                session.fsync(outputStream)
            }

            val intent = Intent(ACTION_INSTALL_STATUS).apply {
                setPackage(packageName)
            }
            val pendingIntent = PendingIntent.getBroadcast(
                context,
                sessionId,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
            )

            session.commit(pendingIntent.intentSender)
            session.close()
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

/**
 * Mock / In-memory PackageInstaller delegate for unit tests.
 */
class MockPackageInstallerDelegate : PackageInstallerSessionDelegate {
    var lastPackageName: String? = null
    var lastUserActionRequired: Int? = null
    var streamedByteCount: Long = 0L
    var sessionCommitted: Boolean = false
    var shouldFail: Boolean = false

    override fun createAndCommitSession(
        packageName: String,
        apkStream: InputStream,
        requireUserAction: Int,
        onSessionCreated: (sessionId: Int) -> Unit
    ): Result<Unit> {
        if (shouldFail) return Result.failure(IllegalStateException("Simulated installer failure"))
        lastPackageName = packageName
        lastUserActionRequired = requireUserAction
        onSessionCreated(101)
        val buffer = ByteArray(4096)
        var read: Int
        while (apkStream.read(buffer).also { read = it } != -1) {
            streamedByteCount += read
        }
        sessionCommitted = true
        return Result.success(Unit)
    }
}

/**
 * Manages background checking, SHA-256 cryptographic validation, and silent APK package installation.
 */
class SilentOtaManager(
    private val currentVersionCode: Int = 240,
    private val currentVersionName: String = "2.4.0",
    private val packageName: String = "com.trandif.polarsnap",
    private val installerDelegate: PackageInstallerSessionDelegate = MockPackageInstallerDelegate()
) {
    companion object {
        const val USER_ACTION_NOT_REQUIRED = 2 // PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED (API 31+)
    }

    /**
     * Checks for new software releases from the Cloudflare / GitHub Releases endpoint.
     */
    fun checkForUpdates(
        endpointUrl: String,
        httpTransport: HttpTransport
    ): Result<UpdateInfo> {
        return try {
            val checkUrl = if (endpointUrl.endsWith("/api/v1/releases/latest") || endpointUrl.endsWith("/api/v1/ota/check")) {
                endpointUrl
            } else {
                "$endpointUrl/api/v1/releases/latest?current_version=$currentVersionName&current_code=$currentVersionCode"
            }

            val response = httpTransport.execute(
                url = checkUrl,
                method = "GET",
                headers = mapOf("Accept" to "application/json"),
                body = null
            )

            if (response.statusCode != 200) {
                return Result.failure(IllegalStateException("Release check failed with HTTP ${response.statusCode}"))
            }

            val json = JSONObject(response.body)
            val latestCode = json.optInt("latest_version_code", currentVersionCode)
            val latestName = json.optString("latest_version_name", currentVersionName)
            val releaseNotes = json.optString("release_notes", "")
            val downloadUrl = json.optString("download_url", "")
            val sha256 = json.optString("sha256_checksum", "")
            val isUpdateAvailable = json.optBoolean("is_update_available", latestCode > currentVersionCode)

            val updateInfo = UpdateInfo(
                isUpdateAvailable = isUpdateAvailable,
                latestVersionName = latestName,
                latestVersionCode = latestCode,
                releaseNotes = releaseNotes,
                downloadUrl = downloadUrl,
                sha256Checksum = sha256
            )
            Result.success(updateInfo)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Computes the SHA-256 digest of a local APK file.
     */
    fun computeSha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { fis ->
            val buffer = ByteArray(8192)
            var bytesRead: Int
            while (fis.read(buffer).also { bytesRead = it } != -1) {
                digest.update(buffer, 0, bytesRead)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    /**
     * Verifies that the APK file matches the expected SHA-256 checksum exactly (case-insensitive).
     * If the checksum mismatches, the file is rejected.
     */
    fun verifyApkChecksum(apkFile: File, expectedSha256: String): Boolean {
        if (!apkFile.exists() || apkFile.length() == 0L) return false
        val computed = computeSha256(apkFile)
        return HmacSigner.constantTimeEquals(computed, expectedSha256)
    }

    /**
     * Silently installs a verified APK file using Android PackageInstaller session.
     * Enforces USER_ACTION_NOT_REQUIRED on Android 12+ (API 31+).
     */
    fun installPackageSilently(apkPath: String): Result<Unit> {
        val file = File(apkPath)
        if (!file.exists()) {
            return Result.failure(IllegalArgumentException("APK file not found at path: $apkPath"))
        }
        if (file.length() == 0L) {
            return Result.failure(IllegalArgumentException("APK file is empty: $apkPath"))
        }

        return FileInputStream(file).use { apkStream ->
            installerDelegate.createAndCommitSession(
                packageName = packageName,
                apkStream = apkStream,
                requireUserAction = USER_ACTION_NOT_REQUIRED
            )
        }
    }
}
