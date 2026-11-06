package com.trandif.polarsnap.domain.engine

enum class ResolutionLimit(val maxVerticalPixels: Int, val label: String) {
    RES_4K(2160, "4K Ultra HD"),
    RES_1440P(1440, "1440p QHD"),
    RES_1080P(1080, "1080p FHD"),
    RES_720P(720, "720p HD"),
    RES_AUDIO_ONLY(0, "Audio Only")
}
