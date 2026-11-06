package com.trandif.polarsnap.domain.engine

import android.content.Context

interface PolarEngine {
    val engineVersion: String
        get() = "Polar Core Engine v2.4 (Active)"

    suspend fun initialize(context: Context): Result<Unit>
    suspend fun fetchMetadata(url: String): Result<MediaMetadata>
    suspend fun executeDownload(
        url: String,
        options: EngineOptions,
        outputDir: String,
        taskId: String = java.util.UUID.randomUUID().toString(),
        onProgress: (SanitizedStreamEvent) -> Unit
    ): Result<DownloadedArtifact>
    suspend fun cancelDownload(taskId: String): Result<Unit>
    fun isInitialized(): Boolean
}
