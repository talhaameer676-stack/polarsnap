package com.trandif.polarsnap.domain.engine

data class EngineOptions(
    val turboAcceleration: Boolean = true,
    val losslessAudio: Boolean = false,
    val cleanWatermark: Boolean = true,
    val sponsorStripper: Boolean = true,
    val customFormatContainer: FormatContainer = FormatContainer.MP4,
    val resolutionLimit: ResolutionLimit = ResolutionLimit.RES_1080P,
    val preferredAudioFormat: String = "flac",
    val maxFragments: Int = 16,
    val customParameters: List<String> = emptyList()
)
