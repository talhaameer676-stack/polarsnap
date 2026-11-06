package com.trandif.polarsnap.core.remaster

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.io.File
import javax.imageio.ImageIO

class BijectiveLutMappingTest {

    @Test
    fun testMathematicalBijectiveCoordinateMappingAcrossAll262144Points() {
        val dimension = 512
        val totalPoints = dimension * dimension // 262,144 points

        // Track visited CapCut coordinates to verify 1:1 injectivity & surjectivity
        val visited = java.util.BitSet(totalPoints)

        for (hy in 0 until dimension) {
            for (hx in 0 until dimension) {
                val index = hy * dimension + hx

                // Discrete 3D cube coordinates in [0..63]
                val r = index % 64
                val g = (index / 64) % 64
                val b = (index / 4096) % 64

                assertTrue(r in 0..63, "R must be in 0..63")
                assertTrue(g in 0..63, "G must be in 0..63")
                assertTrue(b in 0..63, "B must be in 0..63")

                // Map to CapCut 8x8 tiled layout
                val tileCol = b % 8
                val tileRow = b / 8

                assertTrue(tileCol in 0..7, "tileCol must be in 0..7")
                assertTrue(tileRow in 0..7, "tileRow must be in 0..7")

                val cx = tileCol * 64 + r
                val cy = tileRow * 64 + g

                assertTrue(cx in 0..511, "cx must be in 0..511")
                assertTrue(cy in 0..511, "cy must be in 0..511")

                val capCutFlatIndex = cy * dimension + cx
                assertFalse(visited.get(capCutFlatIndex), "Collision detected at cx=$cx, cy=$cy (index=$index)")
                visited.set(capCutFlatIndex)

                // Test inverse mapping from (cx, cy) back to index & (hx, hy)
                val invR = cx % 64
                val invG = cy % 64
                val invTileCol = cx / 64
                val invTileRow = cy / 64
                val invB = invTileRow * 8 + invTileCol

                val reconstructedIndex = invB * 4096 + invG * 64 + invR
                val invHx = reconstructedIndex % dimension
                val invHy = reconstructedIndex / dimension

                assertEquals(index, reconstructedIndex, "Reconstructed index must match")
                assertEquals(hx, invHx, "Reconstructed hx must match")
                assertEquals(hy, invHy, "Reconstructed hy must match")
            }
        }

        // All 262,144 cells in CapCut must be covered (surjection)
        assertEquals(totalPoints, visited.cardinality(), "All 262,144 points must be covered")
    }

    @Test
    fun testBundledLutAssetsFilesystemCompliance() {
        val lutsDir = File("app/src/main/assets/luts")
        assertTrue(lutsDir.exists(), "Asset directory must exist")
        assertTrue(lutsDir.isDirectory, "Asset directory must be a folder")

        val expectedAssets = listOf(
            "teal_and_orange.png",
            "viral_warm_pop.png",
            "moody_noir.png",
            "studio_bright.png"
        )

        var totalSizeBytes = 0L

        for (assetName in expectedAssets) {
            val file = File(lutsDir, assetName)
            assertTrue(file.exists(), "Asset $assetName must exist")
            assertTrue(file.isFile, "Asset $assetName must be a file")
            assertTrue(file.length() > 0, "Asset $assetName must not be empty")

            val img = ImageIO.read(file)
            assertEquals(512, img.width, "Asset $assetName width must be 512")
            assertEquals(512, img.height, "Asset $assetName height must be 512")

            totalSizeBytes += file.length()
        }

        // Must be less than 600 KB total
        val maxAllowedBytes = 600L * 1024L
        assertTrue(
            totalSizeBytes < maxAllowedBytes,
            "Total LUT asset size ($totalSizeBytes bytes) must be < $maxAllowedBytes bytes (<600 KB)"
        )
    }
}
