/**
 * WebSocket service for real-time position tracking.
 * Sends IMU data → receives fused position.
 */

let _ws = null;
let _onPosition = null;
let _reconnectTimer = null;

export function connectTracking(sessionId, onPosition) {
  _onPosition = onPosition;

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  const url = `${proto}://${host}/ws/track/${sessionId}`;

  _ws = new WebSocket(url);

  _ws.onopen = () => {
    console.log('[WS] Connected:', sessionId);
  };

  _ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'position' && _onPosition) {
        _onPosition(data);
      }
    } catch (e) {
      console.error('[WS] Parse error:', e);
    }
  };

  _ws.onclose = () => {
    console.log('[WS] Disconnected – reconnecting in 3 s');
    _reconnectTimer = setTimeout(() => connectTracking(sessionId, onPosition), 3000);
  };

  _ws.onerror = (err) => {
    console.error('[WS] Error:', err);
    _ws.close();
  };
}

export function sendIMU(data) {
  if (_ws && _ws.readyState === WebSocket.OPEN) {
    _ws.send(JSON.stringify({ type: 'imu', ...data }));
  }
}

export function disconnectTracking() {
  clearTimeout(_reconnectTimer);
  if (_ws) {
    _ws.onclose = null;      // prevent reconnect
    _ws.close();
    _ws = null;
  }
}

export function isConnected() {
  return _ws && _ws.readyState === WebSocket.OPEN;
}
