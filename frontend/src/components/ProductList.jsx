/**
 * ProductList – displays search results with "Navigate" buttons.
 */
import React from 'react';

const CATEGORY_ICONS = {
  Furniture: '🪑',
  Lighting: '💡',
  Kitchen: '🍳',
  Decoration: '🖼️',
  Textile: '🧶',
  General: '📦',
};

export default function ProductList({ products = [], onNavigate, onSelect }) {
  if (products.length === 0) {
    return <p style={{ textAlign: 'center', color: '#999', padding: '2rem' }}>
      Search for a product to get started.
    </p>;
  }

  return (
    <div className="product-list">
      {products.map((p) => (
        <div key={p.id} className="card product-card" onClick={() => onSelect?.(p)}>
          <div className="product-icon">
            {CATEGORY_ICONS[p.category] || '📦'}
          </div>
          <div className="product-info">
            <h3>{p.name}</h3>
            <p>{p.category} · Shelf {p.shelf_id || '—'} · Level {p.shelf_level}</p>
          </div>
          <span className="product-price">€{p.price?.toFixed(2)}</span>
          <button
            className="btn-primary"
            style={{ marginLeft: '0.5rem', fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
            onClick={(e) => { e.stopPropagation(); onNavigate(p); }}
          >
            Navigate
          </button>
        </div>
      ))}
    </div>
  );
}
