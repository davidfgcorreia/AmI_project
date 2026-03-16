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
          <span className="nav-queue-title">🛒 Shopping List</span>
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
              <span className="nav-queue-num">{idx === 0 ? '▶' : idx + 1}</span>
              <div className="nav-queue-info">
                <span className="nav-queue-name">{item.name}</span>
                <span className="nav-queue-meta">
                  {item.category}{item.price != null ? ` · €${item.price.toFixed(2)}` : ''}
                </span>
              </div>
              <div className="nav-queue-actions">
                <button className="btn-primary nav-queue-btn" onClick={() => onCollected(item.id)}>
                  ✓
                </button>
                <button className="btn-danger nav-queue-btn" onClick={() => onRemove(item.id)}>
                  ✕
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
              <span className="nav-queue-num">✅</span>
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
