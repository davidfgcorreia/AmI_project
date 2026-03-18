/**
 * BLE Advertiser service
 *
 * Wraps the native BleAdvertiserPlugin (Android) so the app can:
 *   1. Obtain a stable device session ID
 *   2. Continuously advertise a BLE beacon so ESP32 gateways detect us
 *
 * Falls back gracefully in browsers / non-Android environments.
 */
import { registerPlugin } from '@capacitor/core';

const BleAdvertiser = registerPlugin('BleAdvertiser');

const STORAGE_KEY = 'ire_session_id';

/**
 * Returns a stable session ID for this device.
 * Priority:
 *   1. Native plugin (Android ID-based, survives app reinstall)
 *   2. localStorage (generated once, survives page reloads)
 *   3. Random fallback (in-memory only)
 */
export async function getOrCreateSessionId() {
  // Try native plugin first (most stable)
  try {
    const { sessionId } = await BleAdvertiser.getSessionId();
    if (sessionId) {
      localStorage.setItem(STORAGE_KEY, sessionId);
      return sessionId;
    }
  } catch {
    // Not running as native Android app
  }

  // localStorage fallback (web browser / Capacitor web)
  let sessionId = localStorage.getItem(STORAGE_KEY);
  if (!sessionId) {
    sessionId = 'IRE-' + Math.random().toString(36).slice(2, 10);
    localStorage.setItem(STORAGE_KEY, sessionId);
  }
  return sessionId;
}

/**
 * Start BLE advertising so ESP32 gateways can detect this device.
 * The advertised device name equals sessionId, which the ESP32 forwards
 * as session_id in MQTT messages to the backend.
 */
export async function startBleAdvertising(sessionId) {
  try {
    await BleAdvertiser.start({ sessionId });
    console.log('[BLE] Advertising started, session:', sessionId);
    return true;
  } catch (err) {
    console.warn('[BLE] Advertising unavailable:', err?.message ?? err);
    return false;
  }
}

/** Stop BLE advertising (called on app unmount). */
export async function stopBleAdvertising() {
  try {
    await BleAdvertiser.stop();
  } catch {
    // Ignore – may not be advertising
  }
}
