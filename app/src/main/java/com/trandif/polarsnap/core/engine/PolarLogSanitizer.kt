package com.trandif.polarsnap.core.engine

import com.trandif.polarsnap.domain.engine.SanitizedStreamEvent

/**
 * Intercepts engine stdout and stderr streams.
 * Performs deep regex scrubbing of all internal tool names ("yt-dlp", "Python", raw paths, etc.)
 * and parses technical stream output into clean, user-friendly [SanitizedStreamEvent] telemetry.
 */
object PolarLogSanitizer {

    // Regex to capture standard progress lines with speed and ETA
    private val PROGRESS_WITH_SPEED_REGEX = Regex(
        """\[download\]\s+([\d.]+)%\s+of\s+~?\s*([\d.]+)\s*([KMGT]i?B)\s+at\s+([\d.]+)\s*([KMGT]i?B/s)\s+ETA\s+([\d:]+)""",
        RegexOption.IGNORE_CASE
    )

    // Regex to capture completed download lines with elapsed time
    private val PROGRESS_COMPLETED_REGEX = Regex(
        """\[download\]\s+100(?:\.0)?%\s+of\s+~?\s*([\d.]+)\s*([KMGT]i?B)(?:\s+in\s+([\d:]+))?(?:\s+at\s+([\d.]+)\s*([KMGT]i?B/s))?""",
        RegexOption.IGNORE_CASE
    )

    // Fallback progress regex for simplified progress percentages
    private val SIMPLE_PERCENT_REGEX = Regex(
        """\[download\]\s+([\d.]+)%""",
        RegexOption.IGNORE_CASE
    )

    // Token denylist: any mention of these terms in any casing is redacted
    private val TOKEN_DENYLIST = listOf(
        Regex("""(?i)\byt[-_]?dlp\b"""),
        Regex("""(?i)\byoutube[-_]?dl\b"""),
        Regex("""(?i)\bpython(?:\s*3(?:\.\d+)?)?\b"""),
        Regex("""(?i)\bcpython\b"""),
        Regex("""(?i)\blibpython\b"""),
        Regex("""(?i)\bffmpeg\b"""),
        Regex("""(?i)\blibffmpeg\b"""),
        Regex("""(?i)\baria2c?\b"""),
        Regex("""(?i)\blibaria2c\b"""),
        Regex("""(?i)/data/(?:user/\d+|data)/[^/\s]+/files/[^\s]+"""),
        Regex("""(?i)/data/(?:user/\d+|data)/[^/\s]+/lib/[^\s]+"""),
        Regex("""(?i)io\.github\.junkfood02[^\s]*""")
    )

    /**
     * Sanitizes a single log line from the engine output.
     * Returns a [SanitizedStreamEvent] if the line represents meaningful progress or status,
     * or null if the line is low-level debug noise that should not be surfaced to the UI.
     */
    fun sanitizeLine(rawLine: String): SanitizedStreamEvent? {
        val scrubbed = scrub(rawLine).trim()
        if (scrubbed.isBlank()) return null

        // 1. Check for standard download progress line
        PROGRESS_WITH_SPEED_REGEX.find(rawLine)?.let { match ->
            val (percent, size, sizeUnit, speed, speedUnit, eta) = match.destructured
            val percentFloat = percent.toFloatOrNull() ?: 0f
            return SanitizedStreamEvent(
                progressPercent = percentFloat,
                speedFormatted = "$speed $speedUnit",
                etaFormatted = eta,
                totalSizeFormatted = "$size $sizeUnit",
                statusMessage = "Downloading via Polar Core Turbo pipeline..."
            )
        }

        // 2. Check for completed download progress line
        PROGRESS_COMPLETED_REGEX.find(rawLine)?.let { match ->
            val size = match.groupValues[1]
            val sizeUnit = match.groupValues[2]
            val speed = match.groupValues.getOrNull(4).orEmpty()
            val speedUnit = match.groupValues.getOrNull(5).orEmpty()
            val formattedSpeed = if (speed.isNotEmpty()) "$speed $speedUnit" else "Max Speed"
            return SanitizedStreamEvent(
                progressPercent = 100.0f,
                speedFormatted = formattedSpeed,
                etaFormatted = "00:00",
                totalSizeFormatted = "$size $sizeUnit",
                statusMessage = "Stream capture complete. Finalizing media..."
            )
        }

        // 3. Check for simple percentage progress
        SIMPLE_PERCENT_REGEX.find(rawLine)?.let { match ->
            val percent = match.groupValues[1].toFloatOrNull() ?: 0f
            return SanitizedStreamEvent(
                progressPercent = percent,
                speedFormatted = "--",
                etaFormatted = "--",
                totalSizeFormatted = "--",
                statusMessage = "Processing media stream..."
            )
        }

        // 4. Transform internal sub-system events into clean user-facing status messages
        return when {
            rawLine.contains("[ffmpeg]", ignoreCase = true) ||
            rawLine.contains("Merging formats", ignoreCase = true) -> {
                SanitizedStreamEvent(
                    progressPercent = 99.0f,
                    speedFormatted = "--",
                    etaFormatted = "--",
                    totalSizeFormatted = "--",
                    statusMessage = "Multiplexing high-definition audio and video..."
                )
            }
            rawLine.contains("[ExtractAudio]", ignoreCase = true) ||
            rawLine.contains("Destination:", ignoreCase = true) && rawLine.contains(".flac", ignoreCase = true) -> {
                SanitizedStreamEvent(
                    progressPercent = 98.0f,
                    speedFormatted = "--",
                    etaFormatted = "--",
                    totalSizeFormatted = "--",
                    statusMessage = "Demuxing bit-perfect lossless audio..."
                )
            }
            rawLine.contains("[SponsorBlock]", ignoreCase = true) -> {
                SanitizedStreamEvent(
                    progressPercent = 99.5f,
                    speedFormatted = "--",
                    etaFormatted = "--",
                    totalSizeFormatted = "--",
                    statusMessage = "Excision of promotional segments in progress..."
                )
            }
            rawLine.contains("[download] Destination:", ignoreCase = true) -> {
                SanitizedStreamEvent(
                    progressPercent = 1.0f,
                    speedFormatted = "--",
                    etaFormatted = "--",
                    totalSizeFormatted = "--",
                    statusMessage = "Allocating Arctic media storage..."
                )
            }
            rawLine.contains("FixupM3u8", ignoreCase = true) -> {
                SanitizedStreamEvent(
                    progressPercent = 99.0f,
                    speedFormatted = "--",
                    etaFormatted = "--",
                    totalSizeFormatted = "--",
                    statusMessage = "Aligning streaming container segments..."
                )
            }
            rawLine.contains("[Metadata]", ignoreCase = true) ||
            rawLine.contains("[ThumbnailsConvertor]", ignoreCase = true) -> {
                SanitizedStreamEvent(
                    progressPercent = 99.8f,
                    speedFormatted = "--",
                    etaFormatted = "--",
                    totalSizeFormatted = "--",
                    statusMessage = "Embedding media metadata tags and cover artwork..."
                )
            }
            else -> null // Suppress internal low-level debug chatter
        }
    }

    /**
     * Deeply scrubs any string (log lines, exception messages, stack traces).
     * Replaces technical binary names, runtime paths, and python markers with clean PolarCore branding.
     * Guaranteed to leave zero instances of denylisted terms in the returned text.
     */
    fun scrub(rawText: String): String {
        var result = rawText
        for (regex in TOKEN_DENYLIST) {
            result = result.replace(regex, "PolarCore")
        }
        return result
    }

    /**
     * Validates whether a given string contains any leaked denylisted terms.
     * Returns true if completely clean (0 leaks), false if any denylisted term is present.
     */
    fun isClean(text: String): Boolean {
        return TOKEN_DENYLIST.none { it.containsMatchIn(text) }
    }
}
