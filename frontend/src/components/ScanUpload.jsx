/**
 * ScanUpload – staff tool to photograph shelves and trigger YOLO analysis.
 */
import React, { useState, useRef } from 'react';
import { scanShelf } from '../services/api';

export default function ScanUpload({ shelves = [] }) {
  const [shelfId, setShelfId] = useState('');
  const [highlight, setHighlight] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef(null);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file || !shelfId) return;

    setLoading(true);
    try {
      const res = await scanShelf(Number(shelfId), file, highlight);
      setResult(res);
    } catch (err) {
      alert('Scan failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: '1rem' }}>
      <h2 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>📷 Shelf Scanner (Staff)</h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <select value={shelfId} onChange={(e) => setShelfId(e.target.value)}>
          <option value="">Select shelf…</option>
          {shelves.map((s) => (
            <option key={s.id} value={s.id}>{s.name} (Aisle {s.aisle})</option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Highlight product label (optional)"
          value={highlight}
          onChange={(e) => setHighlight(e.target.value)}
        />

        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          style={{ fontSize: '0.85rem' }}
        />

        <button
          className="btn-primary"
          onClick={handleUpload}
          disabled={loading || !shelfId}
        >
          {loading ? 'Analysing…' : 'Upload & Analyse'}
        </button>
      </div>

      {result && (
        <div style={{ marginTop: '1rem' }}>
          <img
            src={result.image_url}
            alt="Analysed shelf"
            style={{ width: '100%', borderRadius: '8px' }}
          />
          <p style={{ fontSize: '0.85rem', marginTop: '0.5rem', color: '#5f6368' }}>
            {result.detections.length} object(s) detected.
          </p>
        </div>
      )}
    </div>
  );
}
