/**
 * WebSocket service for real-time position tracking.
 * Sends IMU data → receives fused position.
 */

let _ws = null;
let _onPosition = null;
let _reconnectTimer = null;
let _gwWs = null;
let _onGateways = null;

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

export function connectGateways(onGateways) {
  _onGateways = onGateways;

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  const url = `${proto}://${host}/ws/gateways`;

  _gwWs = new WebSocket(url);

  _gwWs.onopen = () => {
    console.log('[WS] Gateways connected');
  };

  _gwWs.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'gateways' && _onGateways) {
        _onGateways(data.items || data);
      }
    } catch (e) {
      // some messages may be plain text (pings)
      try {
        if (typeof event.data === 'string' && event.data.trim() === 'pong') {
          return;
        }
      } catch (_e) {}
      console.error('[WS] Gateways parse error:', e);
    }
  };

  _gwWs.onclose = () => {
    console.log('[WS] Gateways disconnected – reconnecting in 3 s');
    setTimeout(() => connectGateways(onGateways), 3000);
  };

  _gwWs.onerror = (err) => {
    console.error('[WS] Gateways error:', err);
    _gwWs.close();
  };
}

export function disconnectGateways() {
  if (_gwWs) {
    _gwWs.onclose = null;
    _gwWs.close();
    _gwWs = null;
  }
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
