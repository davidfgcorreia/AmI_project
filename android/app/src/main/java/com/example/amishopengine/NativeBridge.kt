package com.example.amishopengine

import android.webkit.JavascriptInterface

/**
 * Exposed to JavaScript as `window.AndroidBridge`.
 * The React app uses this to read/write the session ID so both
 * the native BLE advertiser and the WebView share the same ID.
 */
class NativeBridge(private val sessionManager: SessionManager) {

    @JavascriptInterface
    fun getSessionId(): String = sessionManager.get()

    @JavascriptInterface
    fun setSessionId(id: String) = sessionManager.set(id.trim())
}
