package com.trandif.polarsnap.domain.engine

data class MediaMetadata(
    val id: String,
    val title: String,
    val channel: String,
    val durationSeconds: Long,
    val thumbnailUrl: String,
    val availableResolutions: List<String> = emptyList(),
    val rawExt: String = "mp4",
    val description: String = "",
    val viewCount: Long = 0L
)
