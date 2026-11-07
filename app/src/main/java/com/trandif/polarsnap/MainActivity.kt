package com.trandif.polarsnap

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import com.trandif.polarsnap.core.queue.DownloadQueueManager
import com.trandif.polarsnap.domain.queue.DownloadRequest
import com.trandif.polarsnap.domain.queue.DownloadTask
import com.trandif.polarsnap.domain.queue.TaskState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class MainActivity : Activity() {

    private lateinit var webView: WebView
    private val activityScope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var currentScreen: String = "home"

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Set modern dark status bar and window background
        window.apply {
            clearFlags(WindowManager.LayoutParams.FLAG_TRANSLUCENT_STATUS)
            addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS)
            statusBarColor = Color.parseColor("#0B0F19")
            navigationBarColor = Color.parseColor("#0B0F19")
            decorView.setBackgroundColor(Color.parseColor("#0B0F19"))
        }

        // Initialize hardware-accelerated WebView container
        val rootLayout = FrameLayout(this).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(Color.parseColor("#0B0F19"))
        }

        webView = WebView(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(Color.parseColor("#0B0F19"))
            isVerticalScrollBarEnabled = false
            isHorizontalScrollBarEnabled = false

            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                databaseEnabled = true
                allowFileAccess = true
                allowContentAccess = true
                loadWithOverviewMode = true
                useWideViewPort = true
                cacheMode = WebSettings.LOAD_DEFAULT
                mediaPlaybackRequiresUserGesture = false
            }

            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val url = request.url.toString()
                    if (url.startsWith("file:///android_asset/")) {
                        return false
                    }
                    // External link handling
                    try {
                        val browserIntent = Intent(Intent.ACTION_VIEW, request.url)
                        startActivity(browserIntent)
                    } catch (_: Exception) {}
                    return true
                }

                override fun onPageFinished(view: WebView, url: String) {
                    super.onPageFinished(view, url)
                    injectScriptHooks(view)
                }
            }

            addJavascriptInterface(PolarWebAppInterface(), "PolarSnap")
        }

        rootLayout.addView(webView)
        setContentView(rootLayout)

        // Initial launch on Home screen
        loadScreen("home")
    }

    private fun loadScreen(screen: String) {
        currentScreen = screen
        val assetUrl = "file:///android_asset/web/$screen/code.html"
        webView.loadUrl(assetUrl)
    }

    private fun injectScriptHooks(view: WebView) {
        val js = """
            (function() {
                document.querySelectorAll('[data-path], [data-screen]').forEach(function(el) {
                    el.addEventListener('click', function(e) {
                        var target = el.getAttribute('data-path') || el.getAttribute('data-screen');
                        if (target && window.PolarSnap) {
                            window.PolarSnap.navigate(target);
                        }
                    });
                });
            })();
        """.trimIndent()
        view.evaluateJavascript(js, null)
    }

    inner class PolarWebAppInterface {

        @JavascriptInterface
        fun navigate(screen: String) {
            runOnUiThread {
                loadScreen(screen)
            }
        }

        @JavascriptInterface
        fun getClipboardText(): String {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
            val item = clipboard?.primaryClip?.getItemAt(0)
            return item?.text?.toString() ?: ""
        }

        @JavascriptInterface
        fun showToast(message: String) {
            runOnUiThread {
                Toast.makeText(this@MainActivity, message, Toast.LENGTH_SHORT).show()
            }
        }

        @JavascriptInterface
        fun startDownload(url: String, format: String, isRemaster: Boolean, lutPreset: String) {
            runOnUiThread {
                Toast.makeText(this@MainActivity, "Polar Core: Enqueueing capture...", Toast.LENGTH_SHORT).show()
                activityScope.launch {
                    try {
                        val req = DownloadRequest(
                            url = url,
                            customFormat = format,
                            isRemasterEnabled = isRemaster,
                            colorPreset = lutPreset,
                            isTurboAcceleration = true
                        )
                        PolarSnapApp.instance.queueManager.enqueue(req)
                        withContext(Dispatchers.Main) {
                            Toast.makeText(this@MainActivity, "Download started! Opening library...", Toast.LENGTH_SHORT).show()
                            loadScreen("downloads")
                        }
                    } catch (e: Exception) {
                        withContext(Dispatchers.Main) {
                            Toast.makeText(this@MainActivity, "Engine: ${e.message}", Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
        }

        @JavascriptInterface
        fun getActiveCount(): Int {
            return try {
                PolarSnapApp.instance.queueManager.getActiveTasks().size
            } catch (_: Exception) {
                0
            }
        }

        @JavascriptInterface
        fun getTasksJson(): String {
            return try {
                val tasks = PolarSnapApp.instance.queueManager.getAllTasks()
                val jsonArr = JSONArray()
                for (t in tasks) {
                    val obj = JSONObject().apply {
                        put("id", t.id)
                        put("title", t.title)
                        put("progress", t.progress)
                        put("state", t.state.name)
                        put("speed", t.speedBytesPerSec)
                        put("eta", t.etaSeconds)
                    }
                    jsonArr.put(obj)
                }
                jsonArr.toString()
            } catch (_: Exception) {
                "[]"
            }
        }

        @JavascriptInterface
        fun pauseTask(taskId: String): Boolean {
            return PolarSnapApp.instance.queueManager.pause(taskId)
        }

        @JavascriptInterface
        fun resumeTask(taskId: String): Boolean {
            return PolarSnapApp.instance.queueManager.resume(taskId)
        }

        @JavascriptInterface
        fun cancelTask(taskId: String): Boolean {
            return PolarSnapApp.instance.queueManager.cancel(taskId)
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (currentScreen != "home") {
            loadScreen("home")
        } else if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
