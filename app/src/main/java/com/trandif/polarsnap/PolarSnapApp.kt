package com.trandif.polarsnap

import android.app.Application
import com.trandif.polarsnap.core.engine.PolarCoreEngine
import com.trandif.polarsnap.core.queue.DownloadQueueManager
import com.trandif.polarsnap.core.remaster.FFmpegRemasterPipeline
import com.trandif.polarsnap.core.remaster.HaldClutManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.io.File

class PolarSnapApp : Application() {

    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    lateinit var queueManager: DownloadQueueManager
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this

        val polarEngine = PolarCoreEngine.getInstance()
        val haldClutManager = HaldClutManager(File(cacheDir, "luts"))
        val remasterPipeline = FFmpegRemasterPipeline(haldClutManager)
        queueManager = DownloadQueueManager(
            context = this,
            polarEngine = polarEngine,
            remasterPipeline = remasterPipeline
        )

        // Initialize Polar Core Engine asynchronously on startup
        applicationScope.launch {
            polarEngine.initialize(this@PolarSnapApp)
        }
    }

    companion object {
        lateinit var instance: PolarSnapApp
            private set
    }
}
