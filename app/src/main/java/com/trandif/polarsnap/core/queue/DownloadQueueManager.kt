package com.trandif.polarsnap.core.queue

import android.content.Context
import com.trandif.polarsnap.domain.engine.EngineOptions
import com.trandif.polarsnap.domain.engine.FormatContainer
import com.trandif.polarsnap.domain.engine.PolarEngine
import com.trandif.polarsnap.domain.engine.ResolutionLimit
import com.trandif.polarsnap.domain.queue.DownloadRequest
import com.trandif.polarsnap.domain.queue.DownloadTask
import com.trandif.polarsnap.domain.queue.QueueManager
import com.trandif.polarsnap.domain.queue.TaskState
import com.trandif.polarsnap.domain.remaster.CapCutPreset
import com.trandif.polarsnap.domain.remaster.RemasterConfig
import com.trandif.polarsnap.domain.remaster.RemasterPipeline
import com.trandif.polarsnap.domain.remaster.TargetResolution
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

class DownloadQueueManager(
    private val context: Context,
    private val polarEngine: PolarEngine,
    private val remasterPipeline: RemasterPipeline? = null,
    private val publisher: ScopedStoragePublisher = ScopedStoragePublisher(context),
    private val maxConcurrentDownloads: Int = 2,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
) : QueueManager {

    private val tasks = ConcurrentHashMap<String, DownloadTask>()
    private val activeJobs = ConcurrentHashMap<String, Job>()
    private val downloadSemaphore = Semaphore(maxConcurrentDownloads)

    override fun enqueue(request: DownloadRequest): String {
        val taskId = UUID.randomUUID().toString()
        val task = DownloadTask(
            id = taskId,
            request = request,
            state = TaskState.PENDING,
            title = request.title ?: "Preparing download..."
        )
        tasks[taskId] = task
        dispatchNext(taskId)
        return taskId
    }

    private fun dispatchNext(taskId: String) {
        val task = tasks[taskId] ?: return
        val job = scope.launch {
            downloadSemaphore.withPermit {
                executeTask(task)
            }
        }
        activeJobs[taskId] = job
    }

    private suspend fun executeTask(task: DownloadTask) {
        task.state = TaskState.DOWNLOADING
        val cacheDir = File(context.cacheDir, "downloads").apply { mkdirs() }

        val formatContainer = try {
            FormatContainer.valueOf(task.request.customFormat.uppercase())
        } catch (e: Exception) {
            FormatContainer.MP4
        }

        val resolutionLimit = try {
            ResolutionLimit.valueOf(task.request.resolutionLimit.uppercase())
        } catch (e: Exception) {
            ResolutionLimit.RES_1080P
        }

        val options = EngineOptions(
            turboAcceleration = task.request.isTurboAcceleration,
            losslessAudio = task.request.isLosslessAudio,
            cleanWatermark = task.request.isCleanWatermark,
            sponsorStripper = task.request.isSponsorStripper,
            customFormatContainer = formatContainer,
            resolutionLimit = resolutionLimit
        )

        val downloadResult = polarEngine.executeDownload(
            url = task.request.url,
            options = options,
            outputDir = cacheDir.absolutePath,
            taskId = task.id
        ) { event ->
            task.progress = event.progressPercent
        }

        downloadResult.onSuccess { artifact ->
            var finalFile = File(artifact.filePath)
            task.title = artifact.title
            task.totalBytes = artifact.fileSize

            // Remaster stage if requested
            if (task.request.isRemasterEnabled && remasterPipeline != null) {
                task.state = TaskState.REMASTERING
                val preset = try {
                    CapCutPreset.valueOf(task.request.colorPreset.uppercase())
                } catch (e: Exception) {
                    CapCutPreset.NONE
                }

                val targetRes = when (resolutionLimit) {
                    ResolutionLimit.RES_4K -> TargetResolution.UHD_4K
                    ResolutionLimit.RES_1440P -> TargetResolution.RES_1440P
                    ResolutionLimit.RES_720P -> TargetResolution.RES_720P
                    else -> TargetResolution.RES_1080P
                }

                val remasterOut = File(cacheDir, "remastered_${finalFile.name}")
                val remasterConfig = RemasterConfig(
                    enableSuperResolution = (resolutionLimit == ResolutionLimit.RES_4K),
                    targetResolution = targetRes,
                    enableSharpening = true,
                    colorGradingPreset = preset,
                    lutIntensity = 1.0f
                )

                val remasterResult = remasterPipeline.processMedia(
                    sourceFile = finalFile.absolutePath,
                    destinationFile = remasterOut.absolutePath,
                    config = remasterConfig
                ) { pct ->
                    task.progress = pct
                }

                remasterResult.onSuccess { remasteredPath ->
                    finalFile = File(remasteredPath)
                }
            }

            // Publication stage
            task.state = TaskState.FINALIZING
            if (formatContainer == FormatContainer.MP3 || formatContainer == FormatContainer.FLAC) {
                publisher.publishAudio(finalFile, task.title)
            } else {
                publisher.publishVideo(finalFile, task.title)
            }

            task.outputFile = finalFile
            task.state = TaskState.COMPLETED
            task.progress = 100f
        }.onFailure { err ->
            task.state = TaskState.FAILED
            task.errorMessage = err.message ?: "Download failed"
        }

        activeJobs.remove(task.id)
    }

    override fun pause(taskId: String): Boolean {
        val job = activeJobs[taskId]
        if (job != null && job.isActive) {
            job.cancel()
            tasks[taskId]?.state = TaskState.PAUSED
            activeJobs.remove(taskId)
            return true
        }
        return false
    }

    override fun resume(taskId: String): Boolean {
        val task = tasks[taskId] ?: return false
        if (task.state == TaskState.PAUSED || task.state == TaskState.FAILED) {
            task.state = TaskState.PENDING
            dispatchNext(taskId)
            return true
        }
        return false
    }

    override fun cancel(taskId: String): Boolean {
        val job = activeJobs[taskId]
        job?.cancel()
        activeJobs.remove(taskId)
        tasks[taskId]?.state = TaskState.CANCELLED
        return true
    }

    override fun retry(taskId: String): Boolean {
        return resume(taskId)
    }

    override fun getTask(taskId: String): DownloadTask? = tasks[taskId]
    override fun getAllTasks(): List<DownloadTask> = tasks.values.toList().sortedByDescending { it.createdAt }
    override fun getActiveTasks(): List<DownloadTask> = tasks.values.filter {
        it.state == TaskState.DOWNLOADING || it.state == TaskState.REMASTERING || it.state == TaskState.PENDING
    }
}
