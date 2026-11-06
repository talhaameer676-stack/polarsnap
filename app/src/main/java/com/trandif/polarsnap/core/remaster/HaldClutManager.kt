package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.CapCutPreset
import java.awt.image.BufferedImage
import java.io.File
import java.io.InputStream
import javax.imageio.ImageIO

/**
 * Abstraction for asset stream loading (supports Android AssetManager or standard ClassLoader/Filesystem).
 */
interface AssetStreamProvider {
    fun openAsset(assetPath: String): InputStream?
}

/**
 * Default filesystem/classloader asset provider.
 */
class DefaultAssetStreamProvider(
    private val assetsRootDir: File = File("app/src/main/assets")
) : AssetStreamProvider {
    override fun openAsset(assetPath: String): InputStream? {
        val file = File(assetsRootDir, assetPath)
        if (file.exists() && file.isFile) {
            return file.inputStream()
        }
        return javaClass.classLoader?.getResourceAsStream(assetPath)
    }
}

/**
 * Manages extraction, caching, integrity validation, and mathematical coordinate conversion
 * of CapCut Hald CLUT Level 8 presets.
 */
class HaldClutManager(
    val cacheDirectory: File,
    private val assetProvider: AssetStreamProvider = DefaultAssetStreamProvider()
) {
    companion object {
        const val HALD_CLUT_LEVEL = 8
        const val EXPECTED_DIMENSION = 512 // 8^3 x 8^3
        const val TILES_PER_ROW = 8
        const val TILE_SIZE = 64
        const val TOTAL_CUBE_ENTRIES = 262144 // 64^3
    }

    init {
        if (!cacheDirectory.exists()) {
            cacheDirectory.mkdirs()
        }
    }

    /**
     * Retrieves the absolute cached file for the specified CapCutPreset.
     * Extracts from assets if not already cached or if invalid.
     */
    fun getLutFile(preset: CapCutPreset): File? {
        if (preset == CapCutPreset.NONE || preset.assetFileName == null) {
            return null
        }

        val targetFile = File(cacheDirectory, preset.assetFileName)
        if (isLutFileValid(targetFile)) {
            return targetFile
        }

        // Extract from asset provider
        val assetPath = "luts/${preset.assetFileName}"
        val stream = assetProvider.openAsset(assetPath)
            ?: throw IllegalStateException("Asset $assetPath not found via provider")

        stream.use { input ->
            targetFile.outputStream().use { output ->
                input.copyTo(output)
            }
        }

        if (!isLutFileValid(targetFile)) {
            targetFile.delete()
            throw IllegalStateException("Extracted LUT file ${targetFile.name} failed dimension/integrity validation")
        }

        return targetFile
    }

    /**
     * Pre-extracts and validates all bundled CapCut presets into the cache directory.
     * Returns a map of preset to verified file.
     */
    fun extractAllPresets(): Map<CapCutPreset, File> {
        val result = mutableMapOf<CapCutPreset, File>()
        for (preset in CapCutPreset.entries) {
            if (preset != CapCutPreset.NONE) {
                val file = getLutFile(preset)
                if (file != null) {
                    result[preset] = file
                }
            }
        }
        return result
    }

    /**
     * Checks if a LUT file exists, is non-empty, and has exactly 512x512 resolution.
     */
    fun isLutFileValid(file: File): Boolean {
        if (!file.exists() || !file.isFile || file.length() == 0L) {
            return false
        }
        return try {
            val img = ImageIO.read(file) ?: return false
            img.width == EXPECTED_DIMENSION && img.height == EXPECTED_DIMENSION
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Performs a 100% lossless bijective coordinate transformation from CapCut's 8x8 tiled 64^3 3D LUT
     * into FFmpeg's Hald CLUT Level 8 standard scanline layout.
     *
     * Mathematical Coordinate Mapping:
     * For each pixel (hx, hy) in the target 512x512 Hald CLUT:
     * 1. index = hy * 512 + hx
     * 2. R = index % 64
     * 3. G = (index / 64) % 64
     * 4. B = (index / 4096) % 64
     * 5. tileCol = B % 8
     * 6. tileRow = B / 8
     * 7. cx = tileCol * 64 + R
     * 8. cy = tileRow * 64 + G
     * 9. HaldCLUT[hx, hy] = CapCutLUT[cx, cy]
     */
    fun convertCapCutTiledToHaldClut(sourceTiledImage: BufferedImage): BufferedImage {
        require(sourceTiledImage.width == EXPECTED_DIMENSION && sourceTiledImage.height == EXPECTED_DIMENSION) {
            "Source tiled CapCut LUT must be ${EXPECTED_DIMENSION}x${EXPECTED_DIMENSION}, got: ${sourceTiledImage.width}x${sourceTiledImage.height}"
        }

        val haldClutImage = BufferedImage(EXPECTED_DIMENSION, EXPECTED_DIMENSION, BufferedImage.TYPE_INT_RGB)

        for (hy in 0 until EXPECTED_DIMENSION) {
            for (hx in 0 until EXPECTED_DIMENSION) {
                val index = hy * EXPECTED_DIMENSION + hx

                val r = index % TILE_SIZE
                val g = (index / TILE_SIZE) % TILE_SIZE
                val b = (index / (TILE_SIZE * TILE_SIZE)) % TILE_SIZE

                val tileCol = b % TILES_PER_ROW
                val tileRow = b / TILES_PER_ROW

                val cx = tileCol * TILE_SIZE + r
                val cy = tileRow * TILE_SIZE + g

                val rgb = sourceTiledImage.getRGB(cx, cy)
                haldClutImage.setRGB(hx, hy, rgb)
            }
        }

        return haldClutImage
    }

    /**
     * Converts an on-disk CapCut tiled LUT file and saves the converted Hald CLUT to the destination.
     */
    fun convertAndSaveLut(sourceTiledFile: File, destinationHaldFile: File): File {
        val srcImg = ImageIO.read(sourceTiledFile)
            ?: throw IllegalArgumentException("Could not decode source image: ${sourceTiledFile.absolutePath}")
        val converted = convertCapCutTiledToHaldClut(srcImg)
        ImageIO.write(converted, "png", destinationHaldFile)
        return destinationHaldFile
    }
}
