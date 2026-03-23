package com.example.amishopengine

import android.Manifest
import android.annotation.SuppressLint
import android.content.pm.PackageManager
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {

    private lateinit var webView: WebView
    private lateinit var bleAdvertiser: BleAdvertiser
    private lateinit var imuManager: ImuManager
    private lateinit var sessionManager: SessionManager

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        sessionManager = SessionManager(this)
        bleAdvertiser  = BleAdvertiser(this)
        imuManager     = ImuManager(this)

        webView = WebView(this).apply {
            settings.apply {
                javaScriptEnabled    = true
                domStorageEnabled    = true
                mixedContentMode     = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                mediaPlaybackRequiresUserGesture = false
            }
            webViewClient = WebViewClient()
            addJavascriptInterface(NativeBridge(sessionManager), "AndroidBridge")
        }
        setContentView(webView)

        // Navigate within the React SPA on back press; exit only when at root
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack()
                else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        // Load the page first — BLE/IMU start after permissions are confirmed
        webView.loadUrl("$FRONTEND_URL?session=${sessionManager.getOrCreate()}")

        // Start IMU immediately — evaluateJavascript is silently ignored until
        // the page finishes loading, so no harm in starting early
        imuManager.start { heading, steps, dt ->
            runOnUiThread {
                webView.evaluateJavascript(
                    """window.dispatchEvent(new CustomEvent('nativeImu',
                        {detail:{heading:$heading,steps:$steps,dt:$dt}}))""",
                    null
                )
            }
        }

        // BLE advertising requires BLUETOOTH_CONNECT permission for adapter.setName().
        // Only start if already granted; otherwise wait for the dialog result.
        if (blePermissionsGranted()) {
            bleAdvertiser.start(sessionManager.getOrCreate())
        } else {
            ActivityCompat.requestPermissions(this, BLE_PERMISSIONS, REQ_BLE)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        bleAdvertiser.stop()
        imuManager.stop()
    }

    private fun blePermissionsGranted() = BLE_PERMISSIONS.all {
        ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
    }

    @Deprecated("Deprecated in Java")
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_BLE && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            bleAdvertiser.start(sessionManager.getOrCreate())
        }
    }

    companion object {
        // ── Change this to your laptop/server IP before building ──────────────
        const val FRONTEND_URL = "http://192.168.1.100:3000"
        // ──────────────────────────────────────────────────────────────────────
        private const val REQ_BLE = 1
        private val BLE_PERMISSIONS = arrayOf(
            Manifest.permission.BLUETOOTH_ADVERTISE,
            Manifest.permission.BLUETOOTH_CONNECT,
            Manifest.permission.BLUETOOTH_SCAN,
            Manifest.permission.ACTIVITY_RECOGNITION,
        )
    }
}
