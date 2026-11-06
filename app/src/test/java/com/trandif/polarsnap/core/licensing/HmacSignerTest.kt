package com.trandif.polarsnap.core.licensing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class HmacSignerTest {

    private lateinit var signer: HmacSigner
    private val testSecret = "arctic_test_secret_key_98765"

    @Before
    fun setUp() {
        signer = HmacSigner(secretKey = testSecret)
    }

    @Test
    fun testGenerateNonceProducesUniqueStrings() {
        val nonce1 = signer.generateNonce()
        val nonce2 = signer.generateNonce()
        assertNotNull(nonce1)
        assertNotNull(nonce2)
        assertNotEquals(nonce1, nonce2)
        assertEquals(36, nonce1.length) // Standard UUID length
    }

    @Test
    fun testCanonicalRequestFormatting() {
        val canonical = signer.buildCanonicalRequest("dev123", 1730000000L, "nonce-abc")
        assertEquals("dev123:1730000000:nonce-abc", canonical)
    }

    @Test
    fun testExtendedCanonicalRequestFormatting() {
        val canonical = signer.buildExtendedCanonicalRequest("dev123", "2.4.0", 240, 1730000000L, "nonce-xyz")
        assertEquals("dev123:2.4.0:240:1730000000:nonce-xyz", canonical)
    }

    @Test
    fun testCanonicalResponseFormatting() {
        val canonical = signer.buildCanonicalResponse("AUTHORIZED", false, 1730604800L, 1730000000L, "nonce-abc")
        assertEquals("AUTHORIZED:false:1730604800:1730000000:nonce-abc", canonical)
    }

    @Test
    fun testHmacSha256SignAndVerifySuccess() {
        val message = "dev123:1730000000:nonce-abc"
        val signature = signer.sign(message)
        assertNotNull(signature)
        assertEquals(64, signature.length) // SHA-256 hex length

        val isValid = signer.verify(message, signature)
        assertTrue("Signature should verify successfully", isValid)
    }

    @Test
    fun testHmacSha256TamperedMessageFails() {
        val original = "dev123:1730000000:nonce-abc"
        val tampered = "dev123:1730000001:nonce-abc"
        val signature = signer.sign(original)

        val isValid = signer.verify(tampered, signature)
        assertFalse("Tampered message signature must be rejected", isValid)
    }

    @Test
    fun testHmacSha256TamperedSignatureFails() {
        val message = "dev123:1730000000:nonce-abc"
        val invalidSignature = "0".repeat(64)

        val isValid = signer.verify(message, invalidSignature)
        assertFalse("Invalid signature must fail", isValid)
    }

    @Test
    fun testServerResponseVerification() {
        val status = "AUTHORIZED"
        val killSwitch = false
        val validUntil = 1730604800L
        val serverTime = 1730000000L
        val nonce = "test-nonce-1"

        val canonical = signer.buildCanonicalResponse(status, killSwitch, validUntil, serverTime, nonce)
        val serverSig = signer.sign(canonical)

        val verified = signer.verifyServerResponse(status, killSwitch, validUntil, serverTime, nonce, serverSig)
        assertTrue(verified)

        // Kill switch flip must fail verification if signature doesn't match
        val tamperedVerified = signer.verifyServerResponse(status, true, validUntil, serverTime, nonce, serverSig)
        assertFalse(tamperedVerified)
    }

    @Test
    fun testConstantTimeComparison() {
        assertTrue(HmacSigner.constantTimeEquals("abcdef123456", "abcdef123456"))
        assertTrue(HmacSigner.constantTimeEquals("ABCDEF", "abcdef"))
        assertFalse(HmacSigner.constantTimeEquals("abcdef123456", "abcdef123457"))
        assertFalse(HmacSigner.constantTimeEquals("abc", "abcdef"))
    }

    private fun assertNotNull(obj: Any?) {
        assertTrue(obj != null)
    }
}
