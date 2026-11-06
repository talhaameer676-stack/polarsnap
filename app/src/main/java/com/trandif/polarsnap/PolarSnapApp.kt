package com.trandif.polarsnap

import android.app.Application
import com.trandif.polarsnap.core.engine.PolarCoreEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class PolarSnapApp : Application() {

    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        instance = this

        // Initialize Polar Core Engine asynchronously on startup
        applicationScope.launch {
            PolarCoreEngine.getInstance().initialize(this@PolarSnapApp)
        }
    }

    companion object {
        lateinit var instance: PolarSnapApp
            private set
    }
}
