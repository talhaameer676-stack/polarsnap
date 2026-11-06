package com.trandif.polarsnap.core.engine

import com.trandif.polarsnap.domain.engine.EngineOptions
import com.trandif.polarsnap.domain.engine.FormatContainer
import com.trandif.polarsnap.domain.engine.ResolutionLimit

/**
 * Translates high-level PolarSnap user-facing cards into technical engine CLI parameters.
 * Encapsulates all technical command generation so presentation layers remain 100% whitelabeled.
 */
class PolarCommandTranslator {

    /**
     * Translates high-level [EngineOptions] and context parameters into a sanitized argument list.
     *
     * @param targetUrl The media URL to download
     * @param options The user card toggle configurations
     * @param outputDir The destination directory on the device
     * @return List of command line arguments for the engine execution
     */
    fun translate(
        targetUrl: String,
        options: EngineOptions,
        outputDir: String
    ): List<String> {
        val args = mutableListOf<String>()

        // 1. Base Engine Directives & Output Destination
        args.add("--no-mtime")
        args.add("--embed-metadata")
        args.add("--embed-thumbnail")
        args.add("--no-warnings")
        args.add("-o")
        val cleanOutputDir = outputDir.trimEnd('/', '\\')
        args.add("$cleanOutputDir/%(title).200B [%(id)s].%(ext)s")

        // 2. Card 1: Turbo Acceleration Mapping
        if (options.turboAcceleration) {
            val fragments = options.maxFragments.coerceIn(2, 32).toString()
            args.add("-N")
            args.add(fragments)
            args.add("--concurrent-fragments")
            args.add(fragments)
            args.add("--downloader")
            args.add("libaria2c.so")
            args.add("--downloader-args")
            args.add("aria2c:-s $fragments -x $fragments -k 1M -j $fragments")
        }

        // 3. Card 2: Lossless Audio Mapping vs Video Container Resolution
        if (options.losslessAudio || options.resolutionLimit == ResolutionLimit.RES_AUDIO_ONLY) {
            args.add("-x")
            val audioFormat = when {
                options.customFormatContainer.isAudio -> options.customFormatContainer.extension
                options.preferredAudioFormat.isNotBlank() -> options.preferredAudioFormat
                else -> "flac"
            }
            args.add("--audio-format")
            args.add(audioFormat)
            args.add("--audio-quality")
            args.add("0") // Maximum bit-rate / VBR 0
        } else {
            val ext = options.customFormatContainer.extension
            args.add("--remux-video")
            args.add(ext)
            args.add("-f")
            args.add(buildFormatSelector(options.resolutionLimit, ext))
        }

        // 4. Card 3: Clean Watermark Mapping (Stealth CDN extraction)
        if (options.cleanWatermark) {
            args.add("--extractor-args")
            args.add("tiktok:app_version=20.9.0;api_hostname=api22-normal-c-alisg.tiktokv.com")
        }

        // 5. Card 4: Sponsor Stripper Mapping (SponsorBlock segment excision)
        if (options.sponsorStripper) {
            args.add("--sponsorblock-remove")
            args.add("sponsor,intro,outro,selfpromo,preview,filler")
        }

        // Append any safe custom parameters if present
        for (customParam in options.customParameters) {
            if (customParam.isNotBlank()) {
                args.add(customParam.trim())
            }
        }

        // Target URL as final parameter
        args.add(targetUrl.trim())

        return args
    }

    /**
     * Translates metadata extraction requests.
     */
    fun translateMetadata(targetUrl: String): List<String> {
        return listOf(
            "--dump-json",
            "--no-playlist",
            "--no-warnings",
            "--skip-download",
            targetUrl.trim()
        )
    }

    private fun buildFormatSelector(resolutionLimit: ResolutionLimit, containerExt: String): String {
        val maxPixels = resolutionLimit.maxVerticalPixels
        return when {
            maxPixels > 0 -> {
                "bestvideo[height<=$maxPixels][ext=$containerExt]+bestaudio/bestvideo[height<=$maxPixels]+bestaudio/best[height<=$maxPixels]/best"
            }
            else -> "bestvideo[ext=$containerExt]+bestaudio/bestvideo+bestaudio/best"
        }
    }
}
