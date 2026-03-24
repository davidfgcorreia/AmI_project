/**
 * WebSocket service for real-time position tracking.
 * Sends IMU data → receives fused position.
 */

let _ws = null;
let _onPosition = null;
let _onStatusChange = null;
let _reconnectTimer = null;
let _pingInterval = null;
let _lastMessageAt = 0;
let _gwWs = null;
let _onGateways = null;

// In Android builds VITE_BACKEND_URL = 'http://192.168.x.x:8000'
// so derive the WS host from that; otherwise fall back to the page host.
function wsBase() {
  const backendUrl = import.meta.env.VITE_BACKEND_URL;
  if (backendUrl) {
    return backendUrl.replace(/^http/, 'ws');
  }
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}`;
}

export function connectTracking(sessionId, onPosition, onStatusChange) {
  _onPosition = onPosition;
  _onStatusChange = onStatusChange;

  const url = `${wsBase()}/ws/track/${sessionId}`;

  _ws = new WebSocket(url);

  _ws.onopen = () => {
    console.log('[WS] Connected:', sessionId);
    _onStatusChange?.(true);
    _lastMessageAt = Date.now();

    // Ping every 2s — if no message received in 4s, force reconnect
    clearInterval(_pingInterval);
    _pingInterval = setInterval(() => {
      if (_ws && _ws.readyState === WebSocket.OPEN) {
        if (Date.now() - _lastMessageAt > 4000) {
          console.log('[WS] No data in 4s — forcing reconnect');
          _ws.close();
          return;
        }
        try { _ws.send(JSON.stringify({ type: 'ping' })); } catch (e) {}
      }
    }, 2000);
  };

  _ws.onmessage = (event) => {
    _lastMessageAt = Date.now();
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
    console.log('[WS] Disconnected – reconnecting in 1 s');
    clearInterval(_pingInterval);
    _onStatusChange?.(false);
    _reconnectTimer = setTimeout(() => connectTracking(sessionId, onPosition, onStatusChange), 1000);
  };

  _ws.onerror = (err) => {
    console.error('[WS] Error:', err);
    _ws.close();
  };
}

export function connectGateways(onGateways) {
  _onGateways = onGateways;

  const url = `${wsBase()}/ws/gateways`;

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
  clearInterval(_pingInterval);
  if (_ws) {
    _ws.onclose = null;      // prevent reconnect
    _ws.close();
    _ws = null;
  }
}

export function isConnected() {
  return _ws && _ws.readyState === WebSocket.OPEN;
}
