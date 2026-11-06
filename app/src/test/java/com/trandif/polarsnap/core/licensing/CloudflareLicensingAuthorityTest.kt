package com.trandif.polarsnap.core.licensing

import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class CloudflareLicensingAuthorityTest {

    private val secret = "arctic_test_authority_secret"
    private lateinit var signer: HmacSigner
    private lateinit var store: LocalLicenseStore
    private var mockCurrentTime: Long = 1730000000L

    @Before
    fun setUp() {
        signer = HmacSigner(secretKey = secret)
        store = LocalLicenseStore(storage = InMemoryLicenseStorageDelegate())
        mockCurrentTime = 1730000000L
    }

    @Test
    fun testSuccessfulRemoteVerificationUpdatesStoreAndReturnsAuthorized() = runBlocking {
        val validUntil = mockCurrentTime + 604800L
        val mockTransport = HttpTransport { url, method, headers, body ->
            val reqJson = JSONObject(body!!)
            val nonce = reqJson.getString("nonce")

            val canonicalResp = signer.buildCanonicalResponse(
                status = "AUTHORIZED",
                killSwitch = false,
                validUntil = validUntil,
                serverTime = mockCurrentTime,
                nonce = nonce
            )
            val serverSig = signer.sign(canonicalResp)

            val respBody = JSONObject().apply {
                put("status", "AUTHORIZED")
                put("kill_switch", false)
                put("license_tier", "PRO")
                put("valid_until", validUntil)
                put("server_time", mockCurrentTime)
                put("signature", serverSig)
            }.toString()

            HttpResponse(200, respBody)
        }

        val authority = CloudflareLicensingAuthority(
            baseUrl = "https://mock.licensing.cloudflare",
            hmacSigner = signer,
            licenseStore = store,
            httpTransport = mockTransport,
            timeProvider = { mockCurrentTime }
        )

        val result = authority.verifyDeviceAuthorization("device_alpha_1")
        assertTrue(result.isSuccess)
        val status = result.getOrThrow()
        assertTrue(status.isAuthorized)
        assertFalse(status.isKillSwitchTriggered)
        assertEquals(validUntil, status.offlineGraceExpiresAt)

        // Verify local store now contains active grace
        assertTrue(store.isWithinGracePeriod(mockCurrentTime + 1000L))
    }

    @Test
    fun testServerSignatureMismatchFailsWithSecurityException() = runBlocking {
        val mockTransport = HttpTransport { _, _, _, _ ->
            val respBody = JSONObject().apply {
                put("status", "AUTHORIZED")
                put("kill_switch", false)
                put("license_tier", "PRO")
                put("valid_until", mockCurrentTime + 604800L)
                put("server_time", mockCurrentTime)
                put("signature", "invalid_forged_server_signature_12345678901234567890")
            }.toString()

            HttpResponse(200, respBody)
        }

        val authority = CloudflareLicensingAuthority(
            baseUrl = "https://mock.licensing.cloudflare",
            hmacSigner = signer,
            licenseStore = store,
            httpTransport = mockTransport,
            timeProvider = { mockCurrentTime }
        )

        val result = authority.verifyDeviceAuthorization("device_compromised")
        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is SecurityException)
    }

    @Test
    fun testNetworkFailureFallsBackToValidOfflineGrace() = runBlocking {
        // Pre-populate store with valid grace from 1 hour ago
        val t0 = mockCurrentTime - 3600L
        store.saveLicense(
            status = "AUTHORIZED",
            isKillSwitch = false,
            graceExpiresAt = t0 + 604800L,
            verifiedAt = t0,
            tier = "FREE"
        )

        // Network transport throws connection exception
        val failingTransport = HttpTransport { _, _, _, _ ->
            throw java.io.IOException("Network connection timed out (simulated airplane mode)")
        }

        val authority = CloudflareLicensingAuthority(
            baseUrl = "https://mock.licensing.cloudflare",
            hmacSigner = signer,
            licenseStore = store,
            httpTransport = failingTransport,
            timeProvider = { mockCurrentTime }
        )

        val result = authority.verifyDeviceAuthorization("device_offline")
        assertTrue(result.isSuccess)
        val status = result.getOrThrow()
        assertTrue("Device must be authorized under offline grace", status.isAuthorized)
        assertFalse(status.isKillSwitchTriggered)
        assertTrue(status.statusMessage.contains("grace", ignoreCase = true))
    }

    @Test
    fun testNetworkFailureWithExpiredGraceReturnsUnauthorized() = runBlocking {
        // Pre-populate store with grace that expired 10 seconds ago
        val t0 = mockCurrentTime - 604810L
        store.saveLicense(
            status = "AUTHORIZED",
            isKillSwitch = false,
            graceExpiresAt = t0 + 604800L,
            verifiedAt = t0
        )

        val failingTransport = HttpTransport { _, _, _, _ ->
            throw java.io.IOException("No internet connection")
        }

        val authority = CloudflareLicensingAuthority(
            baseUrl = "https://mock.licensing.cloudflare",
            hmacSigner = signer,
            licenseStore = store,
            httpTransport = failingTransport,
            timeProvider = { mockCurrentTime }
        )

        val result = authority.verifyDeviceAuthorization("device_expired")
        assertTrue(result.isSuccess)
        val status = result.getOrThrow()
        assertFalse("Expired grace must return unauthorized", status.isAuthorized)
        assertTrue(status.statusMessage.contains("expired", ignoreCase = true))
    }

    @Test
    fun testKillSwitchTriggeredRevokesDeviceImmediately() = runBlocking {
        val mockTransport = HttpTransport { _, _, _, body ->
            val reqJson = JSONObject(body!!)
            val nonce = reqJson.getString("nonce")

            val canonicalResp = signer.buildCanonicalResponse(
                status = "REVOKED",
                killSwitch = true,
                validUntil = 0L,
                serverTime = mockCurrentTime,
                nonce = nonce
            )
            val serverSig = signer.sign(canonicalResp)

            val respBody = JSONObject().apply {
                put("status", "REVOKED")
                put("kill_switch", true)
                put("license_tier", "FREE")
                put("valid_until", 0L)
                put("server_time", mockCurrentTime)
                put("signature", serverSig)
            }.toString()

            HttpResponse(200, respBody)
        }

        val authority = CloudflareLicensingAuthority(
            baseUrl = "https://mock.licensing.cloudflare",
            hmacSigner = signer,
            licenseStore = store,
            httpTransport = mockTransport,
            timeProvider = { mockCurrentTime }
        )

        val result = authority.verifyDeviceAuthorization("device_killed")
        assertTrue(result.isSuccess)
        val status = result.getOrThrow()
        assertFalse(status.isAuthorized)
        assertTrue(status.isKillSwitchTriggered)
    }
}
