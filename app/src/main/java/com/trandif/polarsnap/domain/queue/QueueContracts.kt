package com.trandif.polarsnap.domain.queue

import java.io.File

enum class TaskState {
    PENDING,
    FETCHING_METADATA,
    DOWNLOADING,
    REMASTERING,
    FINALIZING,
    PAUSED,
    COMPLETED,
    FAILED,
    CANCELLED
}

data class DownloadRequest(
    val url: String = "",
    val title: String? = null,
    val customFormat: String = "MP4",
    val resolutionLimit: String = "RES_1080P",
    val isTurboAcceleration: Boolean = true,
    val isLosslessAudio: Boolean = false,
    val isCleanWatermark: Boolean = false,
    val isSponsorStripper: Boolean = false,
    val isRemasterEnabled: Boolean = false,
    val colorPreset: String = "NONE"
)

data class DownloadTask(
    val id: String,
    val request: DownloadRequest,
    var state: TaskState = TaskState.PENDING,
    var title: String = "",
    var progress: Float = 0f,
    var speedBytesPerSec: Long = 0L,
    var etaSeconds: Long = 0L,
    var downloadedBytes: Long = 0L,
    var totalBytes: Long = 0L,
    var errorMessage: String? = null,
    var outputFile: File? = null,
    val createdAt: Long = System.currentTimeMillis()
)

interface QueueManager {
    fun enqueue(request: DownloadRequest): String
    fun pause(taskId: String): Boolean
    fun resume(taskId: String): Boolean
    fun cancel(taskId: String): Boolean
    fun retry(taskId: String): Boolean
    fun getTask(taskId: String): DownloadTask?
    fun getAllTasks(): List<DownloadTask>
    fun getActiveTasks(): List<DownloadTask>
}
