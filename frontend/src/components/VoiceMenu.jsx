import React, { useState, useEffect } from 'react';
import { playFile } from '../services/sound';

const BASE = import.meta.env.VITE_BACKEND_URL || '';

export default function VoiceMenu({ nextItem, userPos }) {
  const [open, setOpen] = useState(false);

  const [audioFiles, setAudioFiles] = useState([]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    async function load() {
      try {
        const res = await fetch(`${BASE}/api/audio-files`, { signal: controller.signal });
        if (!res.ok) throw new Error('Failed to fetch');
        const j = await res.json();
        if (!cancelled && j && Array.isArray(j.files)) {
          setAudioFiles(j.files);
        }
      } catch (e) {
        // ignore - leave audioFiles empty
      }
    }
    load();
    return () => { cancelled = true; controller.abort(); };
  }, []);

  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen(s => !s)} title="Voice menu" style={{ fontSize: '0.9rem', padding: '0.25rem 0.5rem', borderRadius: '6px', border: '1px solid #ccc', background: 'transparent', cursor: 'pointer' }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
      </button>
      {open && (
        <div style={{ position: 'absolute', right: 0, top: '2.2rem', background: 'white', border: '1px solid #ddd', boxShadow: '0 6px 18px rgba(0,0,0,0.08)', borderRadius: 6, zIndex: 40 }}>
          <div style={{ padding: '0.4rem 1rem 0.2rem', color: '#666', fontSize: '0.85rem' }}>Files</div>
          {audioFiles.map((f) => (
            <button key={f} onClick={() => { playFile(f); setOpen(false); }} style={{ display: 'block', padding: '0.45rem 1rem', width: '100%', textAlign: 'left', border: 'none', background: 'transparent', cursor: 'pointer' }}>{f.replace(/\.mp3$/i, '')}</button>
          ))}
        </div>
      )}
    </div>
  );
}
