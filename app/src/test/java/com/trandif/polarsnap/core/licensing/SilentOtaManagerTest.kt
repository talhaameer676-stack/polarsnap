package com.trandif.polarsnap.core.licensing

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class SilentOtaManagerTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var mockInstaller: MockPackageInstallerDelegate
    private lateinit var otaManager: SilentOtaManager

    @Before
    fun setUp() {
        mockInstaller = MockPackageInstallerDelegate()
        otaManager = SilentOtaManager(
            currentVersionCode = 240,
            currentVersionName = "2.4.0",
            packageName = "com.trandif.polarsnap",
            installerDelegate = mockInstaller
        )
    }

    @Test
    fun testCheckForUpdatesParsesValidResponseAndDetectsUpdate() {
        val mockTransport = HttpTransport { _, _, _, _ ->
            val json = JSONObject().apply {
                put("is_update_available", true)
                put("latest_version_name", "2.4.1")
                put("latest_version_code", 241)
                put("release_notes", "Polar Core v2.4.1 update")
                put("download_url", "https://releases.polarsnap.app/v2.4.1.apk")
                put("sha256_checksum", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
            }.toString()
            HttpResponse(200, json)
        }

        val result = otaManager.checkForUpdates("https://releases.polarsnap.app", mockTransport)
        assertTrue(result.isSuccess)
        val update = result.getOrThrow()
        assertTrue(update.isUpdateAvailable)
        assertEquals("2.4.1", update.latestVersionName)
        assertEquals(241, update.latestVersionCode)
        assertEquals("https://releases.polarsnap.app/v2.4.1.apk", update.downloadUrl)
    }

    @Test
    fun testVerifyApkChecksumMatchesExpectedSha256() {
        val apkFile = tempFolder.newFile("genuine_app.apk")
        val content = "PolarSnap Genuine Binary Content 2.4.1".toByteArray(Charsets.UTF_8)
        apkFile.writeBytes(content)

        val expectedSha = otaManager.computeSha256(apkFile)
        assertEquals(64, expectedSha.length)

        // Case insensitive match
        assertTrue(otaManager.verifyApkChecksum(apkFile, expectedSha.lowercase()))
        assertTrue(otaManager.verifyApkChecksum(apkFile, expectedSha.uppercase()))
    }

    @Test
    fun testVerifyApkChecksumRejectsCorruptFile() {
        val apkFile = tempFolder.newFile("corrupt_app.apk")
        apkFile.writeBytes("Initial content".toByteArray(Charsets.UTF_8))
        val expectedSha = otaManager.computeSha256(apkFile)

        // Tamper with file
        apkFile.writeBytes("Tampered content injected".toByteArray(Charsets.UTF_8))

        assertFalse(otaManager.verifyApkChecksum(apkFile, expectedSha))
    }

    @Test
    fun testSilentPackageInstallerInvokesUserActionNotRequired() {
        val apkFile = tempFolder.newFile("update.apk")
        val apkData = ByteArray(16384) { 0x42 } // 16KB dummy binary
        apkFile.writeBytes(apkData)

        val result = otaManager.installPackageSilently(apkFile.absolutePath)
        assertTrue(result.isSuccess)

        // Verify installer session delegate recorded the call
        assertEquals("com.trandif.polarsnap", mockInstaller.lastPackageName)
        assertEquals(SilentOtaManager.USER_ACTION_NOT_REQUIRED, mockInstaller.lastUserActionRequired)
        assertEquals(16384L, mockInstaller.streamedByteCount)
        assertTrue(mockInstaller.sessionCommitted)
    }

    @Test
    fun testSilentPackageInstallerFailsOnMissingApk() {
        val result = otaManager.installPackageSilently("/non/existent/path/update.apk")
        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is IllegalArgumentException)
    }
}
