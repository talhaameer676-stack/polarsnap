package com.trandif.polarsnap.core.engine

import com.trandif.polarsnap.domain.engine.PolarEngineException

/**
 * Catches technical runtime exceptions, process failures, and CLI error strings,
 * transforming them into typed, user-friendly [PolarEngineException] domain models.
 * Completely scrubs technical jargon, internal paths, and tool names.
 */
object PolarExceptionSanitizer {

    /**
     * Sanitizes any throwable into a domain [PolarEngineException].
     */
    fun sanitize(throwable: Throwable): PolarEngineException {
        if (throwable is PolarEngineException) {
            return throwable
        }

        val rawMessage = throwable.message ?: ""
        val scrubbed = PolarLogSanitizer.scrub(rawMessage)

        return when {
            // Cancellation / Destroy process
            scrubbed.contains("destroyProcessById", ignoreCase = true) ||
            scrubbed.contains("InterruptedException", ignoreCase = true) ||
            scrubbed.contains("Process cancelled", ignoreCase = true) ||
            scrubbed.contains("SIGTERM", ignoreCase = true) ||
            scrubbed.contains("SIGINT", ignoreCase = true) -> {
                PolarEngineException.ProcessCancelled(cause = throwable)
            }

            // Stream protected / authentication required
            scrubbed.contains("Private video", ignoreCase = true) ||
            scrubbed.contains("Sign in", ignoreCase = true) ||
            scrubbed.contains("login required", ignoreCase = true) ||
            scrubbed.contains("members-only", ignoreCase = true) ||
            scrubbed.contains("confirm your age", ignoreCase = true) ||
            scrubbed.contains("This video is private", ignoreCase = true) -> {
                PolarEngineException.StreamProtected(cause = throwable)
            }

            // Anti-bot challenge / CAPTCHA / Cloudflare / bot detection
            scrubbed.contains("bot", ignoreCase = true) && scrubbed.contains("confirm", ignoreCase = true) ||
            scrubbed.contains("captcha", ignoreCase = true) ||
            scrubbed.contains("Sign in to confirm you’re not a bot", ignoreCase = true) ||
            scrubbed.contains("automated queries", ignoreCase = true) -> {
                PolarEngineException.AntiBotVerification(cause = throwable)
            }

            // Media unavailable / removed / geo-blocked
            scrubbed.contains("Video unavailable", ignoreCase = true) ||
            scrubbed.contains("not available in your country", ignoreCase = true) ||
            scrubbed.contains("has been removed", ignoreCase = true) ||
            scrubbed.contains("404", ignoreCase = true) ||
            scrubbed.contains("Incomplete YouTube ID", ignoreCase = true) ||
            scrubbed.contains("Unsupported URL", ignoreCase = true) -> {
                PolarEngineException.MediaUnreachable(cause = throwable)
            }

            // Rate limiting / 429
            scrubbed.contains("HTTP Error 429", ignoreCase = true) ||
            scrubbed.contains("Too Many Requests", ignoreCase = true) ||
            scrubbed.contains("rate limit", ignoreCase = true) -> {
                PolarEngineException.ServiceCooldown(cause = throwable)
            }

            // Insufficient disk storage
            scrubbed.contains("No space left on device", ignoreCase = true) ||
            scrubbed.contains("ENOSPC", ignoreCase = true) ||
            scrubbed.contains("Disk full", ignoreCase = true) -> {
                PolarEngineException.StorageFull(cause = throwable)
            }

            // Network drops / connection issues
            scrubbed.contains("Network is unreachable", ignoreCase = true) ||
            scrubbed.contains("Unable to download webpage", ignoreCase = true) ||
            scrubbed.contains("Connection refused", ignoreCase = true) ||
            scrubbed.contains("Connection reset", ignoreCase = true) ||
            scrubbed.contains("SocketTimeoutException", ignoreCase = true) ||
            scrubbed.contains("UnknownHostException", ignoreCase = true) -> {
                PolarEngineException.ConnectionDisruption(cause = throwable)
            }

            // Default fallback: sanitized generic internal error
            else -> {
                val cleanDescription = if (scrubbed.isNotBlank()) {
                    "Polar Core was unable to extract this media stream: ${scrubbed.take(120)}"
                } else {
                    "Polar Core encountered an unrecoverable stream extraction issue."
                }
                PolarEngineException.EngineInternalError(
                    userDescription = cleanDescription,
                    cause = throwable
                )
            }
        }
    }
}
