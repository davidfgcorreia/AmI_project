/**
 * useVoiceSearch - voice search with native Android bridge preferred,
 * falling back to Web Speech API in browsers.
 */
import { useState, useCallback, useRef, useEffect } from 'react';

const hasNativeSpeech = () => {
  try { return !!window.AndroidBridge?.hasNativeSpeech?.(); } catch { return false; }
};

export default function useVoiceSearch(onResult) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef(null);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  // Listen for native speech results from Android SpeechHelper
  useEffect(() => {
    if (!hasNativeSpeech()) return;

    const handler = (e) => {
      const { transcript, error, listening: isListening } = e.detail;
      if (isListening) {
        setListening(true);
        return;
      }
      setListening(false);
      if (transcript) {
        onResultRef.current?.(transcript);
      }
      if (error) {
        console.warn('[Voice] Native speech error:', error);
      }
    };

    window.addEventListener('nativeSpeech', handler);
    return () => window.removeEventListener('nativeSpeech', handler);
  }, []);

  const startListening = useCallback(() => {
    // Prefer native Android speech recognition
    if (hasNativeSpeech()) {
      window.AndroidBridge.startVoiceSearch();
      return;
    }

    // Fallback: Web Speech API
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setListening(true);

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setListening(false);
      if (onResultRef.current) onResultRef.current(transcript);
    };

    recognition.onerror = (event) => {
      console.error('Speech error:', event.error);
      setListening(false);
    };

    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
  }, []);

  const stopListening = useCallback(() => {
    if (hasNativeSpeech()) {
      window.AndroidBridge.stopVoiceSearch();
      setListening(false);
      return;
    }
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setListening(false);
  }, []);

  return { listening, startListening, stopListening };
}
