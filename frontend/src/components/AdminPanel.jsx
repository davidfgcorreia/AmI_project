/**
 * AdminPanel - Staff-friendly management of shelves and products.
 * No technical knowledge required: tap to edit, drag-free forms.
 */
import React, { useState, useEffect, useCallback } from 'react';

const BASE = import.meta.env.VITE_BACKEND_URL || '';

// ── API helpers ──────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function postJSON(url, body) {
  const res = await fetch(`${BASE}${url}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function putJSON(url, body) {
  const res = await fetch(`${BASE}${url}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function deleteReq(url) {
  const res = await fetch(`${BASE}${url}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`${res.status}`);
}

// ── Shelf form ───────────────────────────────────────────────────────────────

const EMPTY_SHELF = { name: '', aisle: '', x: '', y: '', width: '1.0', height: '0.5', shape: 'circle' };

function ShelfForm({ initial, onSave, onCancel }) {
  const [f, setF] = useState(initial || EMPTY_SHELF);
  const set = (k, v) => setF(prev => ({ ...prev, [k]: v }));

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({ ...f, x: parseFloat(f.x), y: parseFloat(f.y), width: parseFloat(f.width), height: parseFloat(f.height), shape: f.shape });
  };

  return (
    <form className="admin-form" onSubmit={handleSubmit}>
      <label>Name <input value={f.name} onChange={e => set('name', e.target.value)} required /></label>
      <label>Aisle <input value={f.aisle} onChange={e => set('aisle', e.target.value)} required /></label>
      <div className="admin-row">
        <label>X (m) <input type="number" step="0.1" value={f.x} onChange={e => set('x', e.target.value)} required /></label>
        <label>Y (m) <input type="number" step="0.1" value={f.y} onChange={e => set('y', e.target.value)} required /></label>
      </div>
      <label>Shape
        <select value={f.shape} onChange={e => set('shape', e.target.value)}>
          <option value="circle">Circle</option>
          <option value="rect">Rectangle</option>
        </select>
      </label>
      <div className="admin-row">
        <label>Width (m) <input type="number" step="0.1" value={f.width} onChange={e => set('width', e.target.value)} required /></label>
        <label>Height (m) <input type="number" step="0.1" value={f.height} onChange={e => set('height', e.target.value)} required /></label>
      </div>
      <div className="admin-actions">
        <button type="submit" className="btn-primary">Save</button>
        <button type="button" className="btn-outline" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

// ── Product form ─────────────────────────────────────────────────────────────

const EMPTY_PRODUCT = { name: '', category: 'General', price: '', shelf_id: '', shelf_level: '1', x_offset: '0', in_stock: true };
const LEVEL_LABELS = ['Bottom', 'Lower', 'Middle', 'Upper', 'Top'];

function ProductForm({ initial, shelves, onSave, onCancel }) {
  const [f, setF] = useState(initial || EMPTY_PRODUCT);
  const set = (k, v) => setF(prev => ({ ...prev, [k]: v }));

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      ...f,
      price: parseFloat(f.price) || 0,
      shelf_id: f.shelf_id ? parseInt(f.shelf_id) : null,
      shelf_level: parseInt(f.shelf_level) || 1,
      x_offset: parseFloat(f.x_offset) || 0,
    });
  };

  return (
    <form className="admin-form" onSubmit={handleSubmit}>
      <label>Product name <input value={f.name} onChange={e => set('name', e.target.value)} required /></label>
      <label>Category <input value={f.category} onChange={e => set('category', e.target.value)} /></label>
      <label>Price <input type="number" step="0.01" min="0" value={f.price} onChange={e => set('price', e.target.value)} /></label>
      <label>Shelf
        <select value={f.shelf_id} onChange={e => set('shelf_id', e.target.value)}>
          <option value="">-- None --</option>
          {shelves.map(s => <option key={s.id} value={s.id}>{s.name} (Aisle {s.aisle})</option>)}
        </select>
      </label>
      <label>Shelf level
        <select value={f.shelf_level} onChange={e => set('shelf_level', e.target.value)}>
          {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n} - {LEVEL_LABELS[n - 1]}</option>)}
        </select>
      </label>
      <label className="admin-checkbox">
        <input type="checkbox" checked={f.in_stock} onChange={e => set('in_stock', e.target.checked)} />
        In stock
      </label>
      <div className="admin-actions">
        <button type="submit" className="btn-primary">Save</button>
        <button type="button" className="btn-outline" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────

export default function AdminPanel() {
  const [section, setSection] = useState('shelves'); // 'shelves' | 'products'
  const [shelves, setShelves] = useState([]);
  const [products, setProducts] = useState([]);
  const [editing, setEditing] = useState(null); // { type, item } or null
  const [adding, setAdding] = useState(false);
  const [filterShelf, setFilterShelf] = useState('');

  const loadShelves = useCallback(() => fetchJSON('/api/shelves').then(setShelves).catch(console.error), []);
  const loadProducts = useCallback(() => fetchJSON('/api/products').then(setProducts).catch(console.error), []);

  useEffect(() => { loadShelves(); loadProducts(); }, [loadShelves, loadProducts]);

  // ── Shelf CRUD ──
  const saveShelf = async (data) => {
    try {
      if (editing?.item?.id) {
        await putJSON(`/api/shelves/${editing.item.id}`, data);
      } else {
        await postJSON('/api/shelves', data);
      }
      setEditing(null); setAdding(false);
      loadShelves();
    } catch (e) { alert('Failed to save shelf: ' + e.message); }
  };

  const deleteShelf = async (id) => {
    if (!confirm('Delete this shelf and unassign all its products?')) return;
    try { await deleteReq(`/api/shelves/${id}`); loadShelves(); loadProducts(); }
    catch (e) { alert('Failed to delete: ' + e.message); }
  };

  // ── Product CRUD ──
  const saveProduct = async (data) => {
    try {
      if (editing?.item?.id) {
        await putJSON(`/api/products/${editing.item.id}`, data);
      } else {
        await postJSON('/api/products', data);
      }
      setEditing(null); setAdding(false);
      loadProducts();
    } catch (e) { alert('Failed to save product: ' + e.message); }
  };

  const deleteProduct = async (id) => {
    if (!confirm('Delete this product?')) return;
    try { await deleteReq(`/api/products/${id}`); loadProducts(); }
    catch (e) { alert('Failed to delete: ' + e.message); }
  };

  const shelfMap = Object.fromEntries(shelves.map(s => [s.id, s]));
  const filteredProducts = filterShelf
    ? products.filter(p => String(p.shelf_id) === filterShelf)
    : products;

  return (
    <div className="admin-panel">
      <div className="admin-tabs">
        <button className={section === 'shelves' ? 'active' : ''} onClick={() => { setSection('shelves'); setEditing(null); setAdding(false); }}>
          Shelves ({shelves.length})
        </button>
        <button className={section === 'products' ? 'active' : ''} onClick={() => { setSection('products'); setEditing(null); setAdding(false); }}>
          Products ({products.length})
        </button>
      </div>

      {/* ── SHELVES ── */}
      {section === 'shelves' && (
        <>
          {(editing || adding) ? (
            <ShelfForm
              initial={editing?.item ? { name: editing.item.name, aisle: editing.item.aisle, x: String(editing.item.x), y: String(editing.item.y), width: String(editing.item.width), height: String(editing.item.height), shape: editing.item.shape || 'circle' } : null}
              onSave={saveShelf}
              onCancel={() => { setEditing(null); setAdding(false); }}
            />
          ) : (
            <>
              <button className="btn-primary" style={{ width: '100%', marginBottom: '0.5rem' }} onClick={() => setAdding(true)}>
                + Add shelf
              </button>
              <div className="admin-list">
                {shelves.map(s => (
                  <div key={s.id} className="admin-card">
                    <div className="admin-card-info">
                      <strong>{s.name}</strong>
                      <span className="admin-meta">Aisle {s.aisle} | Position ({s.x}, {s.y})</span>
                      <span className="admin-meta">{products.filter(p => p.shelf_id === s.id).length} products</span>
                    </div>
                    <div className="admin-card-actions">
                      <button onClick={() => setEditing({ type: 'shelf', item: s })}>Edit</button>
                      <button className="danger" onClick={() => deleteShelf(s.id)}>Del</button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {/* ── PRODUCTS ── */}
      {section === 'products' && (
        <>
          {(editing || adding) ? (
            <ProductForm
              initial={editing?.item ? {
                name: editing.item.name, category: editing.item.category,
                price: String(editing.item.price), shelf_id: String(editing.item.shelf_id || ''),
                shelf_level: String(editing.item.shelf_level || 1),
                x_offset: String(editing.item.x_offset || 0), in_stock: editing.item.in_stock,
              } : null}
              shelves={shelves}
              onSave={saveProduct}
              onCancel={() => { setEditing(null); setAdding(false); }}
            />
          ) : (
            <>
              <button className="btn-primary" style={{ width: '100%', marginBottom: '0.5rem' }} onClick={() => setAdding(true)}>
                + Add product
              </button>
              <div style={{ marginBottom: '0.5rem' }}>
                <select value={filterShelf} onChange={e => setFilterShelf(e.target.value)} style={{ width: '100%', padding: '0.4rem', borderRadius: '6px', border: '1px solid #ccc' }}>
                  <option value="">All shelves</option>
                  {shelves.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div className="admin-list">
                {filteredProducts.map(p => (
                  <div key={p.id} className="admin-card">
                    <div className="admin-card-info">
                      <strong>{p.name}</strong>
                      <span className="admin-meta">
                        {shelfMap[p.shelf_id]?.name || 'Unassigned'} | Level {p.shelf_level} ({LEVEL_LABELS[(p.shelf_level || 1) - 1]})
                      </span>
                      <span className="admin-meta">
                        {p.category} | {p.price?.toFixed(2)} | {p.in_stock ? 'In stock' : 'Out of stock'}
                      </span>
                    </div>
                    <div className="admin-card-actions">
                      <button onClick={() => setEditing({ type: 'product', item: p })}>Edit</button>
                      <button className="danger" onClick={() => deleteProduct(p.id)}>Del</button>
                    </div>
                  </div>
                ))}
                {filteredProducts.length === 0 && (
                  <div style={{ textAlign: 'center', color: '#888', padding: '1rem' }}>No products found.</div>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
