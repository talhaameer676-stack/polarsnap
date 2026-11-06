package com.trandif.polarsnap.core.remaster

import com.trandif.polarsnap.domain.remaster.CapCutPreset
import java.io.File
import java.io.InputStream

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
 * Represents a 2D RGB image buffer for LUT transformations without platform AWT/Android dependencies.
 */
class PixelGrid(val width: Int, val height: Int, val pixels: IntArray = IntArray(width * height)) {
    fun getRGB(x: Int, y: Int): Int = pixels[y * width + x]
    fun setRGB(x: Int, y: Int, rgb: Int) { pixels[y * width + x] = rgb }
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
     * Checks if a LUT file exists, is non-empty, and has exactly 512x512 resolution by parsing
     * the PNG IHDR header (bytes 16-24). Works on all platforms with zero dependencies.
     */
    fun isLutFileValid(file: File): Boolean {
        if (!file.exists() || !file.isFile || file.length() < 24L) {
            return false
        }
        return try {
            file.inputStream().use { stream ->
                val header = ByteArray(24)
                val read = stream.read(header)
                if (read < 24) return false
                if (header[0] != 0x89.toByte() || header[1] != 0x50.toByte() ||
                    header[2] != 0x4E.toByte() || header[3] != 0x47.toByte()) {
                    return false
                }
                val width = ((header[16].toInt() and 0xFF) shl 24) or
                            ((header[17].toInt() and 0xFF) shl 16) or
                            ((header[18].toInt() and 0xFF) shl 8) or
                            (header[19].toInt() and 0xFF)
                val height = ((header[20].toInt() and 0xFF) shl 24) or
                             ((header[21].toInt() and 0xFF) shl 16) or
                             ((header[22].toInt() and 0xFF) shl 8) or
                             (header[23].toInt() and 0xFF)
                width == EXPECTED_DIMENSION && height == EXPECTED_DIMENSION
            }
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Performs a 100% lossless bijective coordinate transformation from CapCut's 8x8 tiled 64^3 3D LUT
     * into FFmpeg's Hald CLUT Level 8 standard scanline layout using a pure PixelGrid buffer.
     */
    fun convertCapCutTiledToHaldClut(source: PixelGrid): PixelGrid {
        require(source.width == EXPECTED_DIMENSION && source.height == EXPECTED_DIMENSION) {
            "Source tiled CapCut LUT must be ${EXPECTED_DIMENSION}x${EXPECTED_DIMENSION}, got: ${source.width}x${source.height}"
        }

        val haldClut = PixelGrid(EXPECTED_DIMENSION, EXPECTED_DIMENSION)

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

                haldClut.setRGB(hx, hy, source.getRGB(cx, cy))
            }
        }

        return haldClut
    }
}
