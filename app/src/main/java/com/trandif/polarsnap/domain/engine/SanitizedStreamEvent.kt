package com.trandif.polarsnap.domain.engine

data class SanitizedStreamEvent(
    val progressPercent: Float,
    val speedFormatted: String,
    val etaFormatted: String,
    val totalSizeFormatted: String,
    val statusMessage: String
)
