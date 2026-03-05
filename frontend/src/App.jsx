/**
 * App – Intelligent Retail Ecosystem PWA
 * ═══════════════════════════════════════
 * Main application shell with tab navigation:
 *   🗺 Map    – live floor map + navigation
 *   🔍 Search – product search (text + voice)
 *   📷 Scan   – staff shelf scanner
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import FloorMap from './components/FloorMap';
import SearchBar from './components/SearchBar';
import ProductList from './components/ProductList';
import ShelfView from './components/ShelfView';
import StatusBar from './components/StatusBar';
import ScanUpload from './components/ScanUpload';
import { getProducts, getShelves, navigate as apiNavigate } from './services/api';
import { connectTracking, disconnectTracking, isConnected } from './services/websocket';
import useIMU from './hooks/useIMU';

function generateSessionId() {
  return 'ire-user';
}

export default function App() {
  // ── State ──
  const [tab, setTab] = useState('map');
  const [sessionId] = useState(() => generateSessionId());
  const [userPos, setUserPos] = useState(null);
  const [shelves, setShelves] = useState([]);
  const [products, setProducts] = useState([]);
  const [navPath, setNavPath] = useState([]);
  const [navTargets, setNavTargets] = useState([]);
  const [navProducts, setNavProducts] = useState([]);
  const [shelfView, setShelfView] = useState(null); // { imageUrl, product, detections }
  const [wsConnected, setWsConnected] = useState(false);
  const checkIntervalRef = useRef(null);

  // ── IMU streaming ──
  useIMU(tab === 'map');

  // ── Startup: fetch shelves & connect WS ──
  useEffect(() => {
    getShelves().then(setShelves).catch(console.error);

    connectTracking(sessionId, (pos) => {
      setUserPos(pos);
    });

    // Periodic connection check
    checkIntervalRef.current = setInterval(() => {
      setWsConnected(isConnected());
    }, 2000);

    return () => {
      disconnectTracking();
      clearInterval(checkIntervalRef.current);
    };
  }, [sessionId]);

  // ── Search handler ──
  const handleSearch = useCallback(async (query) => {
    try {
      const results = await getProducts(query);
      setProducts(results);
      setTab('search'); // switch to search tab to show results
    } catch (err) {
      console.error('Search failed:', err);
    }
  }, []);

  // ── Navigate to product ──
  const handleNavigate = useCallback(async (product) => {
    try {
      const res = await apiNavigate(sessionId, { productIds: [product.id] });
      setNavPath(res.path);
      setNavProducts(res.products);
      // Mark target positions
      const targets = res.path.length > 0
        ? [res.path[res.path.length - 1]]
        : [];
      setNavTargets(targets);
      setShelfView(
        res.shelf_image_url
          ? { imageUrl: res.shelf_image_url, product, detections: [] }
          : null
      );
      setTab('map'); // switch to map to show path
    } catch (err) {
      alert('Navigation failed: ' + err.message);
    }
  }, [sessionId]);

  // ── Multi-product navigation ──
  const handleNavigateAll = useCallback(async () => {
    if (products.length === 0) return;
    try {
      const ids = products.map((p) => p.id);
      const res = await apiNavigate(sessionId, { productIds: ids });
      setNavPath(res.path);
      setNavProducts(res.products);
      setNavTargets(
        res.products
          .filter((p) => p.shelf_id)
          .map((_, i) => res.path[Math.min(i * Math.floor(res.path.length / res.products.length), res.path.length - 1)])
      );
      setTab('map');
    } catch (err) {
      alert('Multi-navigate failed: ' + err.message);
    }
  }, [products, sessionId]);

  // ── Clear navigation ──
  const clearNav = () => {
    setNavPath([]);
    setNavTargets([]);
    setNavProducts([]);
    setShelfView(null);
  };

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <span style={{ fontSize: '1.4rem' }}>🛒</span>
        <h1>Store Navigator</h1>
        <div style={{ marginLeft: 'auto' }}>
          <StatusBar connected={wsConnected} accuracy={userPos?.accuracy} />
        </div>
      </header>

      {/* Body */}
      <main className="app-body">
        {tab === 'map' && (
          <>
            <SearchBar onSearch={handleSearch} />
            <FloorMap
              shelves={shelves}
              userPos={userPos}
              path={navPath}
              targets={navTargets}
            />

            {navPath.length > 0 && (
              <div className="card" style={{ marginTop: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong>Navigating</strong>
                    <span style={{ color: '#5f6368', marginLeft: '0.5rem', fontSize: '0.85rem' }}>
                      {navProducts.map((p) => p.name).join(' → ')}
                    </span>
                  </div>
                  <button className="btn-danger" onClick={clearNav}
                    style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {shelfView && (
              <div style={{ marginTop: '0.75rem' }}>
                <ShelfView
                  imageUrl={shelfView.imageUrl}
                  product={shelfView.product}
                  detections={shelfView.detections}
                  onClose={() => setShelfView(null)}
                />
              </div>
            )}
          </>
        )}

        {tab === 'search' && (
          <>
            <SearchBar onSearch={handleSearch} />
            {products.length > 1 && (
              <button
                className="btn-primary"
                style={{ width: '100%', marginBottom: '0.75rem' }}
                onClick={handleNavigateAll}
              >
                🗺 Navigate to all {products.length} items
              </button>
            )}
            <ProductList
              products={products}
              onNavigate={handleNavigate}
              onSelect={(p) => handleNavigate(p)}
            />
          </>
        )}

        {tab === 'scan' && (
          <ScanUpload shelves={shelves} />
        )}
      </main>

      {/* Bottom nav */}
      <nav className="app-nav">
        <button className={tab === 'map' ? 'active' : ''} onClick={() => setTab('map')}>
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z"/></svg>
          Map
        </button>
        <button className={tab === 'search' ? 'active' : ''} onClick={() => setTab('search')}>
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
          Search
        </button>
        <button className={tab === 'scan' ? 'active' : ''} onClick={() => setTab('scan')}>
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 15.2l3.2-2.13V7.87L12 5.73 8.8 7.87v5.2L12 15.2zM17 1H7c-1.1 0-2 .9-2 2v18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V3c0-1.1-.9-2-2-2zm0 18H7V5h10v14z"/></svg>
          Scan
        </button>
      </nav>
    </div>
  );
}
