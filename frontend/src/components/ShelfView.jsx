/**
 * ShelfView – displays a shelf photo with YOLO-highlighted products
 * (micro-navigation step).
 */
import React from 'react';

export default function ShelfView({ imageUrl, product, detections = [], onClose }) {
  return (
    <div className="shelf-view card" style={{ padding: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <h2 style={{ fontSize: '1.1rem' }}>
          📍 You've arrived!
        </h2>
        <button className="btn-outline" onClick={onClose} style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}>
          ✕ Close
        </button>
      </div>

      {product && (
        <p style={{ marginBottom: '0.75rem', color: '#5f6368' }}>
          Look for <strong>{product.name}</strong> on shelf level {product.shelf_level}.
        </p>
      )}

      {imageUrl ? (
        <img src={imageUrl} alt="Shelf view with highlighted product" />
      ) : (
        <div style={{
          background: '#e8eaed',
          borderRadius: '12px',
          padding: '3rem',
          color: '#999',
          textAlign: 'center',
        }}>
          <p style={{ fontSize: '2rem' }}>📷</p>
          <p>No shelf image available.</p>
          <p style={{ fontSize: '0.8rem' }}>Staff can upload one via the Scan tool.</p>
        </div>
      )}

      {detections.length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          <h3 style={{ fontSize: '0.9rem', marginBottom: '0.4rem' }}>Detected items:</h3>
          <ul style={{ fontSize: '0.85rem', paddingLeft: '1.2rem' }}>
            {detections.map((d, i) => (
              <li key={i}>
                {d.label} ({(d.confidence * 100).toFixed(0)}%)
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
