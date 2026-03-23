/**
 * App - Intelligent Retail Ecosystem
 * ════════════════════════════════════
 * Tabs:
 *   🗺 Map    - floor map + next stop card
 *   🛒 Queue  - full shopping list
 *   🔍 Search - product search (text + voice)
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

    apiNavigate(sessionId, { productIds: pending.map(p => p.id) })
      .then(res => {
        setNavPath(res.path);
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
      .catch(console.error);
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
  useNavigation({ userPos, nextItem, targets: navTargets, voiceEnabled });

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
        <span style={{ fontSize: '1.4rem' }}>🛒</span>
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
              <button onClick={() => setEditingSession(false)} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}>✕</button>
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
            {voiceEnabled ? '🔊' : '🔈'}
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
                <div className="next-stop-label">▶ Next stop</div>
                <div className="next-stop-body">
                  <div className="next-stop-info">
                    <span className="next-stop-name">{nextItem.name}</span>
                    <span className="next-stop-meta">
                      {nextItem.category}{nextItem.price != null ? ` · €${nextItem.price.toFixed(2)}` : ''}
                    </span>
                  </div>
                  <button className="btn-primary nav-queue-btn" onClick={() => markCollected(nextItem.id)}>
                    ✓
                  </button>
                </div>
                {pendingCount > 1 && (
                  <div className="next-stop-remaining">
                    {pendingCount - 1} more item{pendingCount - 1 > 1 ? 's' : ''} in queue
                  </div>
                )}
              </div>
            ) : queue.length > 0 ? (
              <div className="card next-stop" style={{ textAlign: 'center', color: 'var(--success)' }}>
                ✅ All items collected!
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

      </main>

      {/* Bottom nav */}
      <nav className="app-nav">
        <button className={tab === 'map' ? 'active' : ''} onClick={() => setTab('map')}>
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z"/></svg>
          Map
        </button>
        <button className={tab === 'queue' ? 'active' : ''} onClick={() => setTab('queue')}>
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>
          Queue
          {pendingCount > 0 && <span className="nav-badge">{pendingCount}</span>}
        </button>
        <button className={tab === 'search' ? 'active' : ''} onClick={() => setTab('search')}>
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
          Search
        </button>
      </nav>
    </div>
  );
}
