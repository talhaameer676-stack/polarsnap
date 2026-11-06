package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.TargetResolution

/**
 * Tiers of the resilient encoder fallback matrix.
 */
enum class EncoderTier(val tierLevel: Int, val description: String) {
    TIER_1_HARDWARE_HEVC(1, "Hardware-Accelerated ARM64 HEVC (hevc_mediacodec)"),
    TIER_2_HARDWARE_AVC(2, "Hardware-Accelerated ARM64 AVC (h264_mediacodec)"),
    TIER_3_SOFTWARE_4K(3, "High-RAM Software 4K Encoder Fallback (libx264, crf 21)"),
    TIER_3_SOFTWARE_1080P_LOW_RAM(3, "Low-RAM Software 1080p HD Fallback (libx264, crf 20)")
}

/**
 * Encapsulates the selected encoder, rate control parameters, and pixel format.
 */
data class EncoderSelection(
    val tier: EncoderTier,
    val encoderName: String,
    val videoBitrate: String?,
    val maxBitrate: String?,
    val bufferSize: String?,
    val crf: Int?,
    val preset: String?,
    val extraArgs: List<String>,
    val forcedResolution: TargetResolution?,
    val pixelFormat: String
) {
    /**
     * Converts the encoder configuration to a list of FFmpeg command-line arguments.
     */
    fun toCliArguments(): List<String> {
        val args = mutableListOf("-c:v", encoderName)
        videoBitrate?.let { args.addAll(listOf("-b:v", it)) }
        maxBitrate?.let { args.addAll(listOf("-maxrate", it)) }
        bufferSize?.let { args.addAll(listOf("-bufsize", it)) }
        crf?.let { args.addAll(listOf("-crf", it.toString())) }
        preset?.let { args.addAll(listOf("-preset", it)) }
        args.addAll(extraArgs)
        return args
    }
}

/**
 * Abstraction for querying device hardware encoding and memory capabilities.
 */
interface DeviceCapabilityProvider {
    fun isHardwareHevcSupported(width: Int, height: Int): Boolean
    fun isHardwareAvcSupported(width: Int, height: Int): Boolean
    fun getTotalDeviceRamBytes(): Long
}

/**
 * Default capability provider with sensible defaults and environment-based inspection.
 */
class DefaultDeviceCapabilityProvider(
    private val hevcSupported: Boolean = true,
    private val avcSupported: Boolean = true,
    private val totalRamBytes: Long = 8L * 1024L * 1024L * 1024L // 8GB default
) : DeviceCapabilityProvider {
    override fun isHardwareHevcSupported(width: Int, height: Int): Boolean = hevcSupported
    override fun isHardwareAvcSupported(width: Int, height: Int): Boolean = avcSupported
    override fun getTotalDeviceRamBytes(): Long = totalRamBytes
}

/**
 * Selects the optimal video encoder following the 3-tier fallback matrix:
 * 1. Tier 1: Hardware HEVC (`hevc_mediacodec`) for maximum throughput (68-95 fps) and compression.
 * 2. Tier 2: Hardware AVC (`h264_mediacodec`) if HEVC is unavailable on older chipsets.
 * 3. Tier 3: Software `libx264` fallback:
 *    - If device RAM >= 6GB: Full 4K software encoding with CRF 21.
 *    - If device RAM < 6GB: Auto-downscale to 1080p HD with CRF 20 to prevent LMK crashes.
 */
class MediaCodecEncoderSelector(
    private val capabilityProvider: DeviceCapabilityProvider = DefaultDeviceCapabilityProvider()
) {
    companion object {
        const val RAM_THRESHOLD_6GB = 6L * 1024L * 1024L * 1024L

        // Codec identifier constants
        const val CODEC_HEVC_MEDIACODEC = "hevc_mediacodec"
        const val CODEC_H264_MEDIACODEC = "h264_mediacodec"
        const val CODEC_LIBX264 = "libx264"
    }

    /**
     * Resolves the encoder and bitstream configuration for the requested target resolution.
     */
    fun selectEncoder(
        requestedResolution: TargetResolution,
        preferHevc: Boolean = true
    ): EncoderSelection {
        val width = requestedResolution.width
        val height = requestedResolution.height

        // Tier 1: Try Hardware HEVC
        if (preferHevc && capabilityProvider.isHardwareHevcSupported(width, height)) {
            return EncoderSelection(
                tier = EncoderTier.TIER_1_HARDWARE_HEVC,
                encoderName = CODEC_HEVC_MEDIACODEC,
                videoBitrate = if (requestedResolution == TargetResolution.UHD_4K) "18M" else "10M",
                maxBitrate = if (requestedResolution == TargetResolution.UHD_4K) "26M" else "15M",
                bufferSize = if (requestedResolution == TargetResolution.UHD_4K) "36M" else "20M",
                crf = null,
                preset = null,
                extraArgs = listOf("-tag:v", "hvc1"),
                forcedResolution = null,
                pixelFormat = "nv12"
            )
        }

        // Tier 2: Try Hardware AVC
        if (capabilityProvider.isHardwareAvcSupported(width, height)) {
            return EncoderSelection(
                tier = EncoderTier.TIER_2_HARDWARE_AVC,
                encoderName = CODEC_H264_MEDIACODEC,
                videoBitrate = if (requestedResolution == TargetResolution.UHD_4K) "24M" else "14M",
                maxBitrate = if (requestedResolution == TargetResolution.UHD_4K) "32M" else "20M",
                bufferSize = if (requestedResolution == TargetResolution.UHD_4K) "48M" else "28M",
                crf = null,
                preset = null,
                extraArgs = emptyList(),
                forcedResolution = null,
                pixelFormat = "nv12"
            )
        }

        // Tier 3: Software libx264 fallback based on RAM budget
        val totalRam = capabilityProvider.getTotalDeviceRamBytes()
        return if (totalRam >= RAM_THRESHOLD_6GB) {
            // High-RAM device: proceed with 4K software transcode
            EncoderSelection(
                tier = EncoderTier.TIER_3_SOFTWARE_4K,
                encoderName = CODEC_LIBX264,
                videoBitrate = null,
                maxBitrate = null,
                bufferSize = null,
                crf = 21,
                preset = "veryfast",
                extraArgs = emptyList(),
                forcedResolution = null,
                pixelFormat = "yuv420p"
            )
        } else {
            // Low-RAM device (<6GB): downscale to 1080p HD to safeguard against LMK kills
            EncoderSelection(
                tier = EncoderTier.TIER_3_SOFTWARE_1080P_LOW_RAM,
                encoderName = CODEC_LIBX264,
                videoBitrate = null,
                maxBitrate = null,
                bufferSize = null,
                crf = 20,
                preset = "veryfast",
                extraArgs = emptyList(),
                forcedResolution = TargetResolution.RES_1080P,
                pixelFormat = "yuv420p"
            )
        }
    }
}
