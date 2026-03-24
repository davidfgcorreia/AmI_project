package com.example.amishopengine

import android.webkit.JavascriptInterface

/**
 * Exposed to JavaScript as `window.AndroidBridge`.
 * The React app uses this to read/write the session ID so both
 * the native BLE advertiser and the WebView share the same ID,
 * and to trigger native speech recognition.
 */
class NativeBridge(
    private val sessionManager: SessionManager,
    private val onStartVoice: () -> Unit,
    private val onStopVoice: () -> Unit,
    private val onSpeak: (String) -> Unit,
    private val onStopSpeech: () -> Unit,
) {

    @JavascriptInterface
    fun getSessionId(): String = sessionManager.get()

    @JavascriptInterface
    fun setSessionId(id: String) = sessionManager.set(id.trim())

    @JavascriptInterface
    fun startVoiceSearch() = onStartVoice()

    @JavascriptInterface
    fun stopVoiceSearch() = onStopVoice()

    @JavascriptInterface
    fun hasNativeSpeech(): Boolean = true

    @JavascriptInterface
    fun hasNativeTTS(): Boolean = true

    @JavascriptInterface
    fun speak(text: String) = onSpeak(text)

    @JavascriptInterface
    fun stopSpeech() = onStopSpeech()
}
