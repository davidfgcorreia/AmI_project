/**
 * NavQueue - shopping queue shown below the map.
 * Items are sorted by shortest route from the device's position.
 * Any item can be marked as collected at any time.
 */
import React from 'react';

export default function NavQueue({ queue, onCollected, onRemove, onClear }) {
  if (queue.length === 0) return null;

  const pending = queue.filter(p => !p.collected);
  const collected = queue.filter(p => p.collected);
  const allDone = pending.length === 0;

  return (
    <div className="card nav-queue">
      {/* Header */}
      <div className="nav-queue-header">
        <div>
          <span className="nav-queue-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style={{ marginRight: '0.3rem', verticalAlign: 'text-bottom' }}><path d="M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61-.25.96 0 1.1.9 2 2 2h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12.9-1.63h7.45c.75 0 1.41-.41 1.75-1.03l3.58-6.49A1.003 1.003 0 0020 4H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2s.89 2 1.99 2 2-.9 2-2-.9-2-2-2z"/></svg>
            Shopping List
          </span>
          <span className="nav-queue-count">
            {allDone ? ' · All collected!' : ` · ${collected.length}/${queue.length} done`}
          </span>
        </div>
        <button className="btn-danger nav-queue-clear" onClick={onClear}>
          Clear
        </button>
      </div>

      {/* Pending items - in optimal route order */}
      {pending.length > 0 && (
        <div className="nav-queue-list">
          {pending.map((item, idx) => (
            <div key={item.id} className={`nav-queue-item ${idx === 0 ? 'current' : ''}`}>
              <span className="nav-queue-num">{idx === 0 ? <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> : idx + 1}</span>
              <div className="nav-queue-info">
                <span className="nav-queue-name">{item.name}</span>
                <span className="nav-queue-meta">
                  {item.category}{item.price != null ? ` · \u20AC${item.price.toFixed(2)}` : ''}
                </span>
              </div>
              <div className="nav-queue-actions">
                <button className="btn-primary nav-queue-btn" onClick={() => onCollected(item.id)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                </button>
                <button className="btn-danger nav-queue-btn" onClick={() => onRemove(item.id)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Collected items */}
      {collected.length > 0 && (
        <div className="nav-queue-list" style={{ marginTop: pending.length > 0 ? '0.5rem' : 0, opacity: 0.45 }}>
          {collected.map(item => (
            <div key={item.id} className="nav-queue-item collected">
              <span className="nav-queue-num"><svg width="14" height="14" viewBox="0 0 24 24" fill="var(--success)"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></span>
              <div className="nav-queue-info">
                <span className="nav-queue-name">{item.name}</span>
                <span className="nav-queue-meta">{item.category}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
