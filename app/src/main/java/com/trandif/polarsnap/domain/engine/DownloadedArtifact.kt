package com.trandif.polarsnap.domain.engine

data class DownloadedArtifact(
    val taskId: String,
    val filePath: String,
    val format: String,
    val fileSize: Long,
    val durationSeconds: Long = 0L,
    val title: String = ""
)
