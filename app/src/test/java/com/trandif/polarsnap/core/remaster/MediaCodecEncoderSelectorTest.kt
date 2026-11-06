package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.TargetResolution
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class MediaCodecEncoderSelectorTest {

    @Test
    fun testTierOneSelectsHardwareHevcWhenSupported() {
        val mockProvider = object : DeviceCapabilityProvider {
            override fun isHardwareHevcSupported(width: Int, height: Int) = true
            override fun isHardwareAvcSupported(width: Int, height: Int) = true
            override fun getTotalDeviceRamBytes() = 8L * 1024L * 1024L * 1024L
        }

        val selector = MediaCodecEncoderSelector(mockProvider)
        val selection = selector.selectEncoder(TargetResolution.UHD_4K)

        assertEquals(EncoderTier.TIER_1_HARDWARE_HEVC, selection.tier)
        assertEquals("hevc_mediacodec", selection.encoderName)
        assertEquals("18M", selection.videoBitrate)
        assertEquals("26M", selection.maxBitrate)
        assertEquals("36M", selection.bufferSize)
        assertEquals("nv12", selection.pixelFormat)
        assertNull(selection.forcedResolution)
        assertTrue(selection.extraArgs.contains("-tag:v"))
        assertTrue(selection.extraArgs.contains("hvc1"))

        val cliArgs = selection.toCliArguments()
        assertTrue(cliArgs.contains("-c:v"))
        assertTrue(cliArgs.contains("hevc_mediacodec"))
        assertTrue(cliArgs.contains("-b:v"))
        assertTrue(cliArgs.contains("18M"))
    }

    @Test
    fun testTierTwoSelectsHardwareAvcWhenHevcUnsupported() {
        val mockProvider = object : DeviceCapabilityProvider {
            override fun isHardwareHevcSupported(width: Int, height: Int) = false
            override fun isHardwareAvcSupported(width: Int, height: Int) = true
            override fun getTotalDeviceRamBytes() = 8L * 1024L * 1024L * 1024L
        }

        val selector = MediaCodecEncoderSelector(mockProvider)
        val selection = selector.selectEncoder(TargetResolution.UHD_4K)

        assertEquals(EncoderTier.TIER_2_HARDWARE_AVC, selection.tier)
        assertEquals("h264_mediacodec", selection.encoderName)
        assertEquals("24M", selection.videoBitrate)
        assertEquals("32M", selection.maxBitrate)
        assertEquals("48M", selection.bufferSize)
        assertEquals("nv12", selection.pixelFormat)
        assertNull(selection.forcedResolution)
    }

    @Test
    fun testTierThreeSoftwareFourKWhenHardwareUnavailableAndRamSufficient() {
        val mockProvider = object : DeviceCapabilityProvider {
            override fun isHardwareHevcSupported(width: Int, height: Int) = false
            override fun isHardwareAvcSupported(width: Int, height: Int) = false
            override fun getTotalDeviceRamBytes() = 8L * 1024L * 1024L * 1024L // 8GB RAM (>= 6GB)
        }

        val selector = MediaCodecEncoderSelector(mockProvider)
        val selection = selector.selectEncoder(TargetResolution.UHD_4K)

        assertEquals(EncoderTier.TIER_3_SOFTWARE_4K, selection.tier)
        assertEquals("libx264", selection.encoderName)
        assertEquals(21, selection.crf)
        assertEquals("veryfast", selection.preset)
        assertEquals("yuv420p", selection.pixelFormat)
        assertNull(selection.forcedResolution, "High RAM allows 4K software transcode without downscaling")

        val cliArgs = selection.toCliArguments()
        assertTrue(cliArgs.contains("-crf"))
        assertTrue(cliArgs.contains("21"))
        assertTrue(cliArgs.contains("-preset"))
        assertTrue(cliArgs.contains("veryfast"))
    }

    @Test
    fun testTierThreeSoftwareDownscalesTo1080pWhenHardwareUnavailableAndRamLow() {
        val mockProvider = object : DeviceCapabilityProvider {
            override fun isHardwareHevcSupported(width: Int, height: Int) = false
            override fun isHardwareAvcSupported(width: Int, height: Int) = false
            override fun getTotalDeviceRamBytes() = 4L * 1024L * 1024L * 1024L // 4GB RAM (< 6GB)
        }

        val selector = MediaCodecEncoderSelector(mockProvider)
        val selection = selector.selectEncoder(TargetResolution.UHD_4K)

        assertEquals(EncoderTier.TIER_3_SOFTWARE_1080P_LOW_RAM, selection.tier)
        assertEquals("libx264", selection.encoderName)
        assertEquals(20, selection.crf)
        assertEquals("veryfast", selection.preset)
        assertEquals(TargetResolution.RES_1080P, selection.forcedResolution, "Low RAM must force downscale to 1080p to prevent LMK crash")
    }
}
