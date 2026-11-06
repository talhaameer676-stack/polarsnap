package com.trandif.polarsnap.core.licensing

import java.security.MessageDigest
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * High-security HMAC-SHA256 cryptographic utility for PolarSnap client requests and server verification.
 * Enforces constant-time digest comparison to prevent timing attack side-channels.
 */
class HmacSigner(
    private val secretKey: String = DEFAULT_SECRET
) {
    companion object {
        const val DEFAULT_SECRET = "polarsnap_hmac_secret_trandif_arctic_core_2026"
        private const val HMAC_ALGORITHM = "HmacSHA256"

        /**
         * Constant-time comparison between two hex strings.
         */
        fun constantTimeEquals(a: String, b: String): Boolean {
            val aBytes = a.lowercase().toByteArray(Charsets.UTF_8)
            val bBytes = b.lowercase().toByteArray(Charsets.UTF_8)
            return MessageDigest.isEqual(aBytes, bBytes)
        }
    }

    /**
     * Generates a single-use cryptographically strong nonce.
     */
    fun generateNonce(): String = UUID.randomUUID().toString()

    /**
     * Retrieves the current system epoch timestamp in seconds.
     */
    fun currentTimestampSeconds(): Long = System.currentTimeMillis() / 1000L

    /**
     * Builds canonical signing string for standard 3-field request.
     * Format: "${deviceId}:${timestamp}:${nonce}"
     */
    fun buildCanonicalRequest(deviceId: String, timestamp: Long, nonce: String): String {
        return "$deviceId:$timestamp:$nonce"
    }

    /**
     * Builds canonical signing string for extended 5-field request.
     * Format: "${deviceId}:${appVersion}:${buildNumber}:${timestamp}:${nonce}"
     */
    fun buildExtendedCanonicalRequest(
        deviceId: String,
        appVersion: String,
        buildNumber: Int,
        timestamp: Long,
        nonce: String
    ): String {
        return "$deviceId:$appVersion:$buildNumber:$timestamp:$nonce"
    }

    /**
     * Builds canonical signing string for server response verification.
     * Format: "${status}:${killSwitch}:${validUntil}:${serverTime}:${nonce}"
     */
    fun buildCanonicalResponse(
        status: String,
        killSwitch: Boolean,
        validUntil: Long,
        serverTime: Long,
        nonce: String
    ): String {
        return "$status:$killSwitch:$validUntil:$serverTime:$nonce"
    }

    /**
     * Computes HMAC-SHA256 hex digest for an arbitrary input message using the configured secret key.
     */
    fun sign(message: String, key: String = secretKey): String {
        val mac = Mac.getInstance(HMAC_ALGORITHM)
        val keySpec = SecretKeySpec(key.toByteArray(Charsets.UTF_8), HMAC_ALGORITHM)
        mac.init(keySpec)
        val hmacBytes = mac.doFinal(message.toByteArray(Charsets.UTF_8))
        return hmacBytes.joinToString("") { "%02x".format(it) }
    }

    /**
     * Verifies that the given signature matches the computed HMAC-SHA256 for the message.
     */
    fun verify(message: String, signature: String, key: String = secretKey): Boolean {
        val expected = sign(message, key)
        return constantTimeEquals(expected, signature)
    }

    /**
     * Verifies an incoming response token from the Cloudflare Worker authority.
     */
    fun verifyServerResponse(
        status: String,
        killSwitch: Boolean,
        validUntil: Long,
        serverTime: Long,
        nonce: String,
        serverSignature: String,
        key: String = secretKey
    ): Boolean {
        val canonical = buildCanonicalResponse(status, killSwitch, validUntil, serverTime, nonce)
        return verify(canonical, serverSignature, key)
    }
}
