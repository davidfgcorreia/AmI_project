/**
 * App - Intelligent Retail Ecosystem
 * ════════════════════════════════════
 * Tabs:
 *   Map    - floor map + next stop card
 *   Queue  - full shopping list
 *   Search - product search (text + voice)
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import FloorMap from './components/FloorMap';
import SearchBar from './components/SearchBar';
import ProductList from './components/ProductList';
import NavQueue from './components/NavQueue';
import StatusBar from './components/StatusBar';
import VoiceMenu from './components/VoiceMenu';
import { getProducts, getShelves, getGateways, navigate as apiNavigate } from './services/api';
import { connectTracking, disconnectTracking, connectGateways, disconnectGateways } from './services/websocket';
import { getOrCreateSessionId, startBleAdvertising, stopBleAdvertising } from './services/ble';
import useIMU from './hooks/useIMU';
import useNavigation from './hooks/useNavigation';
import AdminPanel from './components/AdminPanel';

export default function App() {
  const [tab, setTab] = useState('map');
  const [sessionId, setSessionId] = useState(null);
  const [userPos, setUserPos] = useState(null);
  const [shelves, setShelves] = useState([]);
  const [beacons, setBeacons] = useState([]);
  const [products, setProducts] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(() => {
    try { return localStorage.getItem('ire_voice_enabled') !== 'false'; } catch (e) { return true; }
  });

  const [queue, setQueue] = useState([]);
  const [navPath, setNavPath] = useState([]);
  const [navTargets, setNavTargets] = useState([]);
  const lastPendingKeyRef = useRef('');

  useIMU(tab === 'map');

  // ── Step 1: Resolve session ID and start BLE advertising ──
  // getOrCreateSessionId() tries the native plugin first, then localStorage.
  // startBleAdvertising() makes the device continuously visible to ESP32 gateways.
  useEffect(() => {
    let cancelled = false;
    getOrCreateSessionId().then(sid => {
      if (cancelled) return;
      setSessionId(sid);
      startBleAdvertising(sid);
    });
    return () => {
      cancelled = true;
      stopBleAdvertising();
    };
  }, []);

  // ── Step 2: Connect WebSocket and load static data once session ID is ready ──
  useEffect(() => {
    if (!sessionId) return;
    getShelves().then(setShelves).catch(console.error);
    getGateways().then(setBeacons).catch(console.error);
    connectTracking(sessionId, setUserPos, setWsConnected);
    connectGateways((items) => setBeacons(items || []));
    return () => {
      disconnectTracking();
      disconnectGateways();
    };
  }, [sessionId]);

  // Dev helper: expose a global function to simulate user position from the
  // browser console. Only active in non-production environments.
  useEffect(() => {
    if (process.env.NODE_ENV === 'production') return;
    // attach helper
    window.__simulateUserPos = (pos) => {
      try {
        if (!pos || typeof pos !== 'object') return console.warn('provide {x,y,accuracy}');
        setUserPos({ x: Number(pos.x) || 0, y: Number(pos.y) || 0, accuracy: Number(pos.accuracy) || 1.5 });
      } catch (e) {
        console.error(e);
      }
    };
    window.__clearSim = () => setUserPos(null);
    return () => {
      try { delete window.__simulateUserPos; delete window.__clearSim; } catch (e) {}
    };
  }, []);

  // Dev oscillation helper: oscillate user along the aisle (X axis) between
  // minX and maxX. Call `window.__oscillateUserAisle({minX, maxX, periodMs})`.
  useEffect(() => {
    if (process.env.NODE_ENV === 'production') return;
    let oscTimer = null;
    // store constants matching FloorMap
    const REAL_W = 10;
    const REAL_H = 5;
    const centreY = REAL_H / 2;

    window.__oscillateUserAisle = (opts = {}) => {
      const minX = Number(opts.minX ?? 0.5);
      const maxX = Number(opts.maxX ?? (REAL_W - 0.5));
      const period = Number(opts.periodMs ?? 4000); // ms for full cycle
      if (oscTimer) clearInterval(oscTimer);
      const stepMs = 50;
      const start = performance.now();
      oscTimer = setInterval(() => {
        const t = performance.now();
        const phase = ((t - start) % period) / period; // 0..1
        // sin-based smooth back-and-forth in [minX..maxX]
        const x = minX + (maxX - minX) * 0.5 * (1 + Math.sin(2 * Math.PI * phase - Math.PI / 2));
        setUserPos({ x, y: centreY, accuracy: 1.0 });
      }, stepMs);
      // convenience stop function
      window.__stopOscillate = () => {
        if (oscTimer) { clearInterval(oscTimer); oscTimer = null; }
      };
      return window.__stopOscillate;
    };

    return () => {
      try { if (oscTimer) clearInterval(oscTimer); delete window.__oscillateUserAisle; delete window.__stopOscillate; } catch (e) {}
    };
  }, []);

  // When there is no session (e.g. during dev or before a user connects),
  // default the displayed user position to the store center so the map
  // shows a sensible location. These values match FloorMap's REAL_W/REAL_H.
  useEffect(() => {
    if (sessionId) return;
    setUserPos({ x: 10 / 2, y: 5 / 2, accuracy: 1.5 });
  }, [sessionId]);

  // ── Re-route when the SET of pending items changes ──
  useEffect(() => {
    if (!sessionId) return;
    const pending = queue.filter(p => !p.collected);
    const pendingKey = pending.map(p => p.id).sort().join(',');

    if (pending.length === 0) {
      lastPendingKeyRef.current = '';
      setNavPath([]);
      setNavTargets([]);
      return;
    }

    if (pendingKey === lastPendingKeyRef.current) return;
    lastPendingKeyRef.current = pendingKey;

    // Fast client-side optimizer: nearest-neighbour seed + 2-opt refinement to reduce total route length
    const optimizeLocal = (items, startPos) => {
      const shelvesMap = Object.fromEntries(shelves.map(s => [s.id, s]));
      const pts = items.map(it => {
        const shelf = shelvesMap[it.shelf_id];
        return { item: it, x: shelf ? shelf.x : (it.x || 0), y: shelf ? shelf.y : (it.y || 0) };
      });

      // Euclidean distance
      const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

      // Nearest-neighbour seed
      const remaining = pts.slice();
      const seedOrder = [];
      let cur = startPos ? { x: startPos.x, y: startPos.y } : { x: 0, y: 0 };
      while (remaining.length) {
        let bestIdx = 0;
        let bestD = Infinity;
        for (let i = 0; i < remaining.length; i++) {
          const d = dist(remaining[i], cur);
          if (d < bestD) { bestD = d; bestIdx = i; }
        }
        const picked = remaining.splice(bestIdx, 1)[0];
        seedOrder.push(picked);
        cur = { x: picked.x, y: picked.y };
      }

      // Prepare coords array for 2-opt (retain item with coords)
      let coords = seedOrder.map(p => ({ x: p.x, y: p.y, item: p.item }));

      // Route length from start through coords
      const routeLength = (arr) => {
        let L = 0;
        let prev = startPos ? { x: startPos.x, y: startPos.y } : { x: 0, y: 0 };
        for (let i = 0; i < arr.length; i++) {
          L += dist(prev, arr[i]);
          prev = arr[i];
        }
        return L;
      };

      // 2-opt improvement
      let improved = true;
      let iter = 0;
      const maxIter = 1000;
      while (improved && iter < maxIter) {
        improved = false;
        iter++;
        const n = coords.length;
        for (let i = 0; i < n - 1; i++) {
          for (let j = i + 1; j < n; j++) {
            const a = (i === 0) ? (startPos ? { x: startPos.x, y: startPos.y } : { x: 0, y: 0 }) : coords[i - 1];
            const b = coords[i];
            const c = coords[j];
            const d = (j === n - 1) ? null : coords[j + 1];

            const before = dist(a, b) + (d ? dist(c, d) : 0);
            const after = dist(a, c) + (d ? dist(b, d) : 0);
            if (after + 1e-9 < before) {
              // reverse segment i..j
              coords = coords.slice(0, i).concat(coords.slice(i, j + 1).reverse(), coords.slice(j + 1));
              improved = true;
              break;
            }
          }
          if (improved) break;
        }
      }

      return coords.map(c => c.item);
    };

    // Compute start position from current userPos if available
    const start = userPos ? { x: userPos.x, y: userPos.y } : null;
    // Apply local optimization immediately for snappy UI
    const localReordered = optimizeLocal(pending, start);
    setQueue(prev => {
      const collectedItems = prev.filter(p => p.collected);
      return [...localReordered, ...collectedItems];
    });
    // Build a quick local navPath/targets from shelves so the map updates immediately.
    // Prepend the current user position as the route start so the path visibly
    // originates from the user and only the start point needs frequent updates.
    try {
      const shelvesMap = Object.fromEntries(shelves.map(s => [s.id, s]));
      const localPath = localReordered
        .map(p => shelvesMap[p.shelf_id])
        .filter(Boolean)
        .map(s => ({ x: s.x, y: s.y }));
      const start = userPos ? { x: userPos.x, y: userPos.y } : { x: 5, y: 2.5 };
      setNavPath([start, ...localPath]);
      setNavTargets(localPath.slice());
    } catch (e) {
      // ignore
    }

    // Also ask backend for an optimized route (authoritative)
    apiNavigate(sessionId, { productIds: pending.map(p => p.id) })
      .then(res => {
        // Backend path may include its own start; replace the first point with
        // the current user position so the route originates from where the
        // user actually is (or the centre fallback).
        const rp = res.path || [];
        const start = userPos ? { x: userPos.x, y: userPos.y } : { x: 5, y: 2.5 };
        const adjusted = rp.length ? rp.slice() : [];
        if (adjusted.length) adjusted[0] = start;
        setNavPath(adjusted.length ? adjusted : rp);
        setQueue(prev => {
          const collectedItems = prev.filter(p => p.collected);
          const pendingMap = Object.fromEntries(prev.filter(p => !p.collected).map(p => [p.id, p]));
          const reordered = res.products.map(p => pendingMap[p.id] ?? p);
          return [...reordered, ...collectedItems];
        });
        setNavTargets(
          res.products
            .map(p => shelves.find(s => s.id === p.shelf_id))
            .filter(Boolean)
            .map(s => ({ x: s.x, y: s.y }))
        );
      })
      .catch(err => {
        // backend failed — keep local ordering and log
        console.error('navigate failed, using local route', err);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queue, sessionId]);

  // ── Queue actions ──
  const addToQueue = useCallback((product) => {
    setQueue(prev => {
      if (prev.find(p => p.id === product.id)) return prev;
      return [...prev, { ...product, collected: false }];
    });
    setTab('map');
  }, []);

  const addAllToQueue = useCallback(() => {
    setQueue(prev => {
      const existingIds = new Set(prev.map(p => p.id));
      const newItems = products
        .filter(p => !existingIds.has(p.id))
        .map(p => ({ ...p, collected: false }));
      return [...prev, ...newItems];
    });
    setTab('map');
  }, [products]);

  const markCollected = useCallback((productId) => {
    setQueue(prev => prev.map(p => p.id === productId ? { ...p, collected: true } : p));
  }, []);

  const removeFromQueue = useCallback((productId) => {
    setQueue(prev => prev.filter(p => p.id !== productId));
  }, []);

  const clearQueue = useCallback(() => {
    setQueue([]);
    setNavPath([]);
    setNavTargets([]);
  }, []);

  // Update navPath's start point when the user's position changes so the map
  // shows a smooth moving origin without recomputing the whole route.
  useEffect(() => {
    if (!userPos) return;
    setNavPath(prev => {
      if (!prev || prev.length === 0) return prev;
      const start = { x: userPos.x, y: userPos.y };
      const dx = prev[0].x - start.x;
      const dy = prev[0].y - start.y;
      if (Math.hypot(dx, dy) < 0.001) return prev; // already up-to-date
      const copy = prev.slice();
      copy[0] = start;
      return copy;
    });
  }, [userPos]);

  // ── Search ──
  const handleSearch = useCallback(async (query) => {
    try {
      const results = await getProducts(query);
      setProducts(results);
      setTab('search');
    } catch (err) {
      console.error('Search failed:', err);
    }
  }, []);

  const pending = queue.filter(p => !p.collected);
  const nextItem = pending[0] ?? null;
  const pendingCount = pending.length;

  // speak navigation instructions based on position and next target
  useNavigation({ userPos, nextItem, path: navPath, targets: navTargets, voiceEnabled });

  const [editingSession, setEditingSession] = useState(false);
  const [sessionInput, setSessionInput] = useState('');

  const openSessionEdit = () => {
    setSessionInput(sessionId || '');
    setEditingSession(true);
  };

  const saveSessionId = () => {
    const trimmed = sessionInput.trim();
    if (!trimmed) return;
    localStorage.setItem('ire_session_id', trimmed);
    setSessionId(trimmed);
    setEditingSession(false);
    disconnectTracking();
    connectTracking(trimmed, setUserPos, setWsConnected);
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <svg style={{ width: '1.4rem', height: '1.4rem' }} viewBox="0 0 24 24" fill="currentColor"><path d="M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61-.25.96 0 1.1.9 2 2 2h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12.9-1.63h7.45c.75 0 1.41-.41 1.75-1.03l3.58-6.49A1.003 1.003 0 0020 4H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2s.89 2 1.99 2 2-.9 2-2-.9-2-2-2z"/></svg>
        <h1>Store Navigator</h1>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {editingSession ? (
            <>
              <input
                autoFocus
                value={sessionInput}
                onChange={e => setSessionInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') saveSessionId(); if (e.key === 'Escape') setEditingSession(false); }}
                style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem', width: '8rem', borderRadius: '4px', border: '1px solid #aaa' }}
              />
              <button onClick={saveSessionId} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}>OK</button>
              <button onClick={() => setEditingSession(false)} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', display: 'inline-flex', alignItems: 'center' }}><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg></button>
            </>
          ) : (
            <span
              onClick={openSessionEdit}
              title="Tap to change session ID"
              style={{ fontSize: '0.6rem', color: 'var(--text-secondary)', cursor: 'pointer', maxWidth: '7rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {sessionId ?? '…'}
            </span>
          )}
          <VoiceMenu
            nextItem={nextItem ? { ...nextItem, x: navTargets[0]?.x, y: navTargets[0]?.y } : null}
            userPos={userPos}
          />
          <button
            onClick={() => {
              const next = !voiceEnabled;
              try { localStorage.setItem('ire_voice_enabled', String(next)); } catch (e) {}
              setVoiceEnabled(next);
            }}
            title={voiceEnabled ? 'Disable voice guidance' : 'Enable voice guidance'}
            style={{ fontSize: '0.9rem', padding: '0.25rem 0.5rem', borderRadius: '6px', border: '1px solid #ccc', background: 'transparent', cursor: 'pointer' }}
          >
            {voiceEnabled
              ? <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
              : <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>
            }
          </button>
          <StatusBar connected={wsConnected} accuracy={userPos?.accuracy} />
        </div>
      </header>

      <main className="app-body">

        {/* ── Map tab: map + next stop ── */}
        {tab === 'map' && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <FloorMap
              shelves={shelves}
              userPos={userPos}
              path={navPath}
              targets={navTargets}
              beacons={beacons}
            />
            {nextItem ? (
              <div className="card next-stop">
                <div className="next-stop-label"><svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style={{ marginRight: '0.3rem', verticalAlign: 'middle' }}><path d="M8 5v14l11-7z"/></svg>Next stop</div>
                <div className="next-stop-body">
                  <div className="next-stop-info">
                    <span className="next-stop-name">{nextItem.name}</span>
                    <span className="next-stop-meta">
                      {nextItem.category}{nextItem.price != null ? ` · €${nextItem.price.toFixed(2)}` : ''}
                    </span>
                  </div>
                  <button className="btn-primary nav-queue-btn" onClick={() => markCollected(nextItem.id)}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                  </button>
                </div>
                {pendingCount > 1 && (
                  <div className="next-stop-remaining">
                    {pendingCount - 1} more item{pendingCount - 1 > 1 ? 's' : ''} in queue
                  </div>
                )}
              </div>
            ) : queue.length > 0 ? (
              <div className="card next-stop" style={{ textAlign: 'center', color: 'var(--success)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style={{ marginRight: '0.4rem' }}><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                All items collected!
                <button className="btn-outline" style={{ marginLeft: '1rem', fontSize: '0.8rem', minHeight: 'unset', padding: '0.3rem 0.7rem' }} onClick={clearQueue}>
                  Clear
                </button>
              </div>
            ) : (
              <div className="card next-stop" style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                Search for products and add them to your queue.
              </div>
            )}
          </div>
        )}

        {/* ── Queue tab ── */}
        {tab === 'queue' && (
          <NavQueue
            queue={queue}
            onCollected={markCollected}
            onRemove={removeFromQueue}
            onClear={clearQueue}
          />
        )}

        {/* ── Search tab ── */}
        {tab === 'search' && (
          <>
            <SearchBar onSearch={handleSearch} />
            {products.length > 1 && (
              <button
                className="btn-primary"
                style={{ width: '100%', marginBottom: '0.75rem' }}
                onClick={addAllToQueue}
              >
                + Add all {products.length} items to queue
              </button>
            )}
            <ProductList
              products={products}
              queueIds={new Set(queue.map(p => p.id))}
              onAddToQueue={addToQueue}
            />
          </>
        )}

        {/* ── Admin tab ── */}
        {tab === 'admin' && <AdminPanel />}

      </main>

      {/* Bottom nav */}
      <nav className="app-nav">
        <button className={tab === 'map' ? 'active' : ''} onClick={() => setTab('map')} aria-label="Map">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z"/></svg>
        </button>
        <button className={tab === 'queue' ? 'active' : ''} onClick={() => setTab('queue')} aria-label="Queue">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>
          {pendingCount > 0 && <span className="nav-badge">{pendingCount}</span>}
        </button>
        <button className={tab === 'search' ? 'active' : ''} onClick={() => setTab('search')} aria-label="Search">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        </button>
        <button className={tab === 'admin' ? 'active' : ''} onClick={() => setTab('admin')} aria-label="Staff">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.49.49 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 00-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1115.6 12 3.61 3.61 0 0112 15.6z"/></svg>
        </button>
      </nav>
    </div>
  );
}
