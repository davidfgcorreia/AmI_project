/**
 * BLE Advertiser service
 *
 * In a browser: uses localStorage for a stable session ID.
 * When running as a native Android app (Capacitor): the native plugin
 * can be wired in separately — for now the web fallback is used always.
 */

const STORAGE_KEY = 'ire_session_id';

/**
 * Returns a stable session ID for this device.
 * Generated once and persisted in localStorage.
 */
export async function getOrCreateSessionId() {
  // 1. Android app passes the native session ID as ?session= in the URL
  const urlParam = new URLSearchParams(window.location.search).get('session');
  if (urlParam) {
    localStorage.setItem(STORAGE_KEY, urlParam);
    return urlParam;
  }

  // 2. AndroidBridge fallback (in case the URL param is lost on navigation)
  if (window.AndroidBridge) {
    const nativeId = window.AndroidBridge.getSessionId();
    if (nativeId) {
      localStorage.setItem(STORAGE_KEY, nativeId);
      return nativeId;
    }
  }

  // 3. Browser / PWA: use localStorage, generate once
  let sessionId = localStorage.getItem(STORAGE_KEY);
  if (!sessionId) {
    sessionId = 'IRE-' + Math.random().toString(36).slice(2, 10).toUpperCase();
    localStorage.setItem(STORAGE_KEY, sessionId);
  }
  return sessionId;
}

/**
 * BLE advertising is only available in the native Android app.
 * In a browser the ESP32s identify the device by session ID sent
 * over WebSocket/HTTP, so advertising is not needed.
 */
export async function startBleAdvertising(_sessionId) {
  console.log('[BLE] Running in browser — advertising not available');
  return false;
}

export async function stopBleAdvertising() {
  // No-op in browser
}
