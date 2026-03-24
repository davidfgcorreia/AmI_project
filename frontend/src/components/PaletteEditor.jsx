import React, { useState, useEffect } from 'react';
import Theme from '../services/theme';

export default function PaletteEditor() {
  const [colors, setColors] = useState(Theme.loadSavedPalette());

  useEffect(() => {
    // live preview when colors change
    Theme.applyPalette(colors);
  }, [colors]);

  // Auto-save palette when changed (debounced) so current colorway persists
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        Theme.savePalette(colors);
      } catch (e) {
        console.error('Auto-save palette failed', e);
      }
    }, 600);
    return () => clearTimeout(t);
  }, [colors]);

  const onChange = (idx, value) => {
    const next = colors.slice();
    next[idx] = value;
    setColors(next);
  };

  const save = () => {
    Theme.savePalette(colors);
    alert('Palette saved');
  };

  const reset = () => {
    const def = Theme.defaultPalette.slice();
    setColors(def);
    Theme.applyPalette(def);
  };

  return (
    <div style={{ margin: '0.5rem 0', padding: '0.6rem', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        {colors.map((c, i) => (
          <label key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <input type="color" value={c} onChange={e => onChange(i, e.target.value)} style={{ width: '40px', height: '32px', border: 'none', padding: 0 }} />
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Slot {i + 1}</span>
          </label>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.4rem' }}>
          <button className="btn-outline" onClick={reset} style={{ minHeight: 'unset', padding: '0.4rem 0.6rem' }}>Reset</button>
          <button className="btn-primary" onClick={save} style={{ minHeight: 'unset', padding: '0.4rem 0.8rem' }}>Save</button>
        </div>
      </div>
      <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
        Palette mapping: <strong style={{ color: 'var(--text)' }}>primary</strong> = slot 1, <strong style={{ color: 'var(--text)' }}>primary-light</strong> = slot 2, <strong style={{ color: 'var(--text)' }}>background</strong> = slot 3, <strong style={{ color: 'var(--text)' }}>surface</strong> = slot 4, <strong style={{ color: 'var(--text)' }}>accent</strong> = slot 5
      </div>
    </div>
  );
}
