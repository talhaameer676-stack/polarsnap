package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.CapCutPreset
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File
import javax.imageio.ImageIO

class HaldClutManagerTest {

    @Test
    fun testRetrieveAllBundledLutAssets(@TempDir tempDir: File) {
        val manager = HaldClutManager(cacheDirectory = tempDir)

        val tealOrange = manager.getLutFile(CapCutPreset.TEAL_AND_ORANGE)
        assertNotNull(tealOrange)
        assertTrue(tealOrange!!.exists())
        assertEquals(512, ImageIO.read(tealOrange).width)
        assertEquals(512, ImageIO.read(tealOrange).height)

        val viralWarm = manager.getLutFile(CapCutPreset.VIRAL_WARM_POP)
        assertNotNull(viralWarm)
        assertTrue(viralWarm!!.exists())
        assertEquals(512, ImageIO.read(viralWarm).width)
        assertEquals(512, ImageIO.read(viralWarm).height)

        val moodyNoir = manager.getLutFile(CapCutPreset.MOODY_NOIR)
        assertNotNull(moodyNoir)
        assertTrue(moodyNoir!!.exists())
        assertEquals(512, ImageIO.read(moodyNoir).width)
        assertEquals(512, ImageIO.read(moodyNoir).height)

        val studioBright = manager.getLutFile(CapCutPreset.STUDIO_BRIGHT)
        assertNotNull(studioBright)
        assertTrue(studioBright!!.exists())
        assertEquals(512, ImageIO.read(studioBright).width)
        assertEquals(512, ImageIO.read(studioBright).height)

        val none = manager.getLutFile(CapCutPreset.NONE)
        assertNull(none)
    }

    @Test
    fun testExtractAllPresetsBatch(@TempDir tempDir: File) {
        val manager = HaldClutManager(cacheDirectory = tempDir)
        val extracted = manager.extractAllPresets()

        assertEquals(4, extracted.size)
        assertTrue(extracted.containsKey(CapCutPreset.TEAL_AND_ORANGE))
        assertTrue(extracted.containsKey(CapCutPreset.VIRAL_WARM_POP))
        assertTrue(extracted.containsKey(CapCutPreset.MOODY_NOIR))
        assertTrue(extracted.containsKey(CapCutPreset.STUDIO_BRIGHT))

        // Total size of extracted assets must be < 600 KB
        val totalBytes = extracted.values.sumOf { it.length() }
        assertTrue(totalBytes < 600 * 1024, "Total size of 4 Hald CLUT PNGs must be < 600 KB, was: $totalBytes bytes")
    }

    @Test
    fun testBijectiveCoordinateConversionFromTiledIdentity() {
        val manager = HaldClutManager(cacheDirectory = File("build/tmp/test_lut"))

        // Create a 512x512 CapCut 8x8 tiled identity texture
        val tiledIdentity = PixelGrid(512, 512)
        for (b in 0 until 64) {
            val tileCol = b % 8
            val tileRow = b / 8
            val tileStartX = tileCol * 64
            val tileStartY = tileRow * 64

            val bByte = (b * 255.0 / 63.0).toInt().coerceIn(0, 255)

            for (g in 0 until 64) {
                val gByte = (g * 255.0 / 63.0).toInt().coerceIn(0, 255)
                for (r in 0 until 64) {
                    val rByte = (r * 255.0 / 63.0).toInt().coerceIn(0, 255)
                    val rgb = (rByte shl 16) or (gByte shl 8) or bByte
                    tiledIdentity.setRGB(tileStartX + r, tileStartY + g, rgb)
                }
            }
        }

        // Convert to Hald CLUT Level 8
        val haldClut = manager.convertCapCutTiledToHaldClut(tiledIdentity)
        assertEquals(512, haldClut.width)
        assertEquals(512, haldClut.height)

        // Verify Hald CLUT scanline ordering
        for (sampleIdx in listOf(0, 1, 63, 64, 4095, 4096, 262143)) {
            val hx = sampleIdx % 512
            val hy = sampleIdx / 512

            val expectedR = ((sampleIdx % 64) * 255.0 / 63.0).toInt().coerceIn(0, 255)
            val expectedG = (((sampleIdx / 64) % 64) * 255.0 / 63.0).toInt().coerceIn(0, 255)
            val expectedB = (((sampleIdx / 4096) % 64) * 255.0 / 63.0).toInt().coerceIn(0, 255)

            val actualRgb = haldClut.getRGB(hx, hy)
            val actualR = (actualRgb shr 16) and 0xFF
            val actualG = (actualRgb shr 8) and 0xFF
            val actualB = actualRgb and 0xFF

            assertEquals(expectedR, actualR, "Mismatch in R channel at index $sampleIdx")
            assertEquals(expectedG, actualG, "Mismatch in G channel at index $sampleIdx")
            assertEquals(expectedB, actualB, "Mismatch in B channel at index $sampleIdx")
        }
    }
}
