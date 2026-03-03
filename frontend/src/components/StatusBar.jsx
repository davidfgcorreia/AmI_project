/**
 * StatusBar – shows connection status + accuracy badge.
 */
import React from 'react';

export default function StatusBar({ connected, accuracy }) {
  return (
    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
      <span className={`status-badge ${connected ? 'connected' : 'disconnected'}`}>
        {connected ? '● Connected' : '○ Offline'}
      </span>
      {accuracy != null && (
        <span className="status-badge connected" style={{ background: '#e8f0fe', color: '#1a73e8' }}>
          ±{accuracy.toFixed(1)} m
        </span>
      )}
    </div>
  );
}
