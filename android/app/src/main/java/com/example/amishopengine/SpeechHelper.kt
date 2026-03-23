package com.example.amishopengine

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import android.webkit.WebView

/**
 * Wraps Android's native SpeechRecognizer.
 * On result, dispatches a CustomEvent to the WebView with the transcript.
 */
class SpeechHelper(private val context: Context) {

    private var recognizer: SpeechRecognizer? = null

    fun start(webView: WebView) {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.e(TAG, "Speech recognition not available on this device")
            dispatchEvent(webView, error = "Speech recognition not available")
            return
        }

        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onResults(results: Bundle) {
                    val matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    val transcript = matches?.firstOrNull() ?: ""
                    Log.i(TAG, "Result: $transcript")
                    dispatchEvent(webView, transcript = transcript)
                }

                override fun onError(error: Int) {
                    val msg = when (error) {
                        SpeechRecognizer.ERROR_NO_MATCH -> "No speech detected"
                        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech detected"
                        SpeechRecognizer.ERROR_AUDIO -> "Audio error"
                        SpeechRecognizer.ERROR_NETWORK,
                        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network error"
                        else -> "Error code $error"
                    }
                    Log.e(TAG, "Speech error: $msg")
                    dispatchEvent(webView, error = msg)
                }

                override fun onReadyForSpeech(params: Bundle?) {
                    dispatchEvent(webView, listening = true)
                }
                override fun onEndOfSpeech() {}
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
        }

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        recognizer?.startListening(intent)
    }

    fun stop() {
        recognizer?.stopListening()
    }

    fun destroy() {
        recognizer?.destroy()
        recognizer = null
    }

    private fun dispatchEvent(webView: WebView, transcript: String? = null, error: String? = null, listening: Boolean? = null) {
        val json = buildString {
            append("{")
            transcript?.let { append("\"transcript\":\"${it.replace("\"", "\\\"")}\",") }
            error?.let { append("\"error\":\"${it.replace("\"", "\\\"")}\",") }
            listening?.let { append("\"listening\":$it,") }
            if (endsWith(",")) deleteCharAt(length - 1)
            append("}")
        }
        webView.post {
            webView.evaluateJavascript(
                "window.dispatchEvent(new CustomEvent('nativeSpeech', {detail:$json}))",
                null
            )
        }
    }

    companion object {
        private const val TAG = "SpeechHelper"
    }
}
