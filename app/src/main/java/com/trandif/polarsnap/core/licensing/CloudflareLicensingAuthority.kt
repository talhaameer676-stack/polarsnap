package com.trandif.polarsnap.core.licensing

import com.trandif.polarsnap.domain.licensing.LicenseStatus
import com.trandif.polarsnap.domain.licensing.LicensingAuthority
import com.trandif.polarsnap.domain.licensing.UpdateInfo
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * Interface abstraction for network transport.
 * Supports direct HttpURLConnection in production and deterministic mock responses in unit tests.
 */
fun interface HttpTransport {
    fun execute(
        url: String,
        method: String,
        headers: Map<String, String>,
        body: String?
    ): HttpResponse
}

data class HttpResponse(
    val statusCode: Int,
    val body: String
)

/**
 * Default HttpURLConnection transport for Android runtime.
 */
class DefaultHttpTransport : HttpTransport {
    override fun execute(
        url: String,
        method: String,
        headers: Map<String, String>,
        body: String?
    ): HttpResponse {
        val connection = URL(url).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 8000
            connection.readTimeout = 8000
            headers.forEach { (k, v) -> connection.setRequestProperty(k, v) }

            if (body != null && (method == "POST" || method == "PUT")) {
                connection.doOutput = true
                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                    writer.write(body)
                    writer.flush()
                }
            }

            val statusCode = connection.responseCode
            val inputStream = if (statusCode in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream ?: connection.inputStream
            }

            val responseBody = BufferedReader(InputStreamReader(inputStream, Charsets.UTF_8)).use { reader ->
                reader.readText()
            }

            return HttpResponse(statusCode, responseBody)
        } finally {
            connection.disconnect()
        }
    }
}

/**
 * Remote licensing client communicating with the isolated Cloudflare Worker licensing authority.
 * Coordinates cryptographic signing, replay prevention, and 7-day offline grace fallback.
 */
class CloudflareLicensingAuthority(
    private val baseUrl: String = "https://licensing.polarsnap.app",
    private val hmacSigner: HmacSigner = HmacSigner(),
    private val licenseStore: LocalLicenseStore = LocalLicenseStore(),
    private val otaManager: SilentOtaManager = SilentOtaManager(),
    private val httpTransport: HttpTransport = DefaultHttpTransport(),
    private val appVersion: String = "2.4.0",
    private val buildNumber: Int = 240,
    private val timeProvider: () -> Long = { System.currentTimeMillis() / 1000L }
) : LicensingAuthority {

    override suspend fun verifyDeviceAuthorization(deviceId: String): Result<LicenseStatus> {
        val now = timeProvider()
        val nonce = hmacSigner.generateNonce()

        // Build canonical request and compute HMAC-SHA256 signature
        val canonicalReq = hmacSigner.buildExtendedCanonicalRequest(
            deviceId = deviceId,
            appVersion = appVersion,
            buildNumber = buildNumber,
            timestamp = now,
            nonce = nonce
        )
        val signature = hmacSigner.sign(canonicalReq)

        val requestPayload = JSONObject().apply {
            put("device_hash", deviceId)
            put("app_version", appVersion)
            put("build_number", buildNumber)
            put("timestamp", now)
            put("nonce", nonce)
            put("signature", signature)
        }.toString()

        val headers = mapOf(
            "Content-Type" to "application/json",
            "X-Polar-Device-Id" to deviceId,
            "X-Polar-Signature" to signature
        )

        try {
            val response = httpTransport.execute(
                url = "$baseUrl/api/v1/license/verify",
                method = "POST",
                headers = headers,
                body = requestPayload
            )

            if (response.statusCode == 200) {
                val json = JSONObject(response.body)
                val status = json.getString("status")
                val killSwitch = json.getBoolean("kill_switch")
                val validUntil = json.getLong("valid_until")
                val serverTime = json.getLong("server_time")
                val serverSig = json.getString("signature")
                val tier = json.optString("license_tier", "FREE")

                // Cryptographically verify server response token
                val isServerValid = hmacSigner.verifyServerResponse(
                    status = status,
                    killSwitch = killSwitch,
                    validUntil = validUntil,
                    serverTime = serverTime,
                    nonce = nonce,
                    serverSignature = serverSig
                )

                if (!isServerValid) {
                    return Result.failure(
                        SecurityException("Server signature mismatch. Authority response may be intercepted or forged.")
                    )
                }

                // Persist verified license state
                licenseStore.saveLicense(
                    status = status,
                    isKillSwitch = killSwitch,
                    graceExpiresAt = validUntil,
                    verifiedAt = now,
                    tier = tier,
                    signature = serverSig,
                    nonce = nonce
                )

                val licenseStatus = LicenseStatus(
                    isAuthorized = status == "AUTHORIZED" && !killSwitch,
                    isKillSwitchTriggered = killSwitch,
                    offlineGraceExpiresAt = validUntil,
                    statusMessage = if (killSwitch) {
                        "Application disabled by remote kill-switch."
                    } else if (status == "REVOKED") {
                        "Device authorization revoked."
                    } else if (status == "OUTDATED_VERSION") {
                        "Client update required to reactivate authorization."
                    } else {
                        "Device authorized successfully."
                    }
                )
                return Result.success(licenseStatus)
            } else if (response.statusCode == 409) {
                // Nonce replay error
                return Result.failure(SecurityException("Nonce replay detected by licensing authority."))
            } else if (response.statusCode == 401) {
                return Result.failure(SecurityException("Unauthorized: HMAC signature rejected by authority."))
            } else {
                // Server returned non-200, attempt grace fallback
                return fallbackToGrace(now, "Authority returned HTTP ${response.statusCode}")
            }
        } catch (e: Exception) {
            // Network failure / unreachable authority -> fall back to 7-day offline grace period
            return fallbackToGrace(now, "Network unreachable: ${e.message}")
        }
    }

    private fun fallbackToGrace(now: Long, reason: String): Result<LicenseStatus> {
        val cached = licenseStore.loadStatus(now)
        if (cached.isKillSwitchTriggered) {
            return Result.success(cached)
        }
        if (licenseStore.isWithinGracePeriod(now)) {
            val graceStatus = LicenseStatus(
                isAuthorized = true,
                isKillSwitchTriggered = false,
                offlineGraceExpiresAt = cached.offlineGraceExpiresAt,
                statusMessage = "Offline grace period active ($reason)."
            )
            return Result.success(graceStatus)
        }
        return Result.success(
            LicenseStatus(
                isAuthorized = false,
                isKillSwitchTriggered = false,
                offlineGraceExpiresAt = cached.offlineGraceExpiresAt,
                statusMessage = "Offline grace period expired ($reason). Connection required."
            )
        )
    }

    override suspend fun checkForOtaUpdate(): Result<UpdateInfo> {
        return otaManager.checkForUpdates(baseUrl, httpTransport)
    }

    override suspend fun installOtaUpdateSilently(apkPath: String): Result<Unit> {
        return otaManager.installPackageSilently(apkPath)
    }
}
