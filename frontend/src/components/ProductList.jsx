/**
 * ProductList – search results with "Add to queue" buttons.
 */
import React from 'react';

const CATEGORY_ICONS = {
  'Dairy & Eggs': '🥛',
  'Juices & Drinks': '🧃',
  'Bakery': '🍞',
  'Meat & Fish': '🥩',
  'Beverages': '🥤',
  'Fresh Fruits': '🍎',
  'Fresh Vegetables': '🥦',
  'Snacks & Chips': '🍿',
  'Cereals & Breakfast': '🥣',
  'Frozen Foods': '🧊',
  'Canned Goods': '🥫',
  'Condiments & Sauces': '🧴',
  'Pasta & Rice': '🍝',
  'Personal Care': '🧼',
  'Cleaning Products': '🧹',
};

export default function ProductList({ products = [], queueIds = new Set(), onAddToQueue }) {
  if (products.length === 0) {
    return (
      <p style={{ textAlign: 'center', color: '#999', padding: '2rem' }}>
        Search for a product to get started.
      </p>
    );
  }

  return (
    <div className="product-list">
      {products.map((p) => {
        const inQueue = queueIds.has(p.id);
        return (
          <div key={p.id} className="card product-card">
            <div className="product-icon">
              {CATEGORY_ICONS[p.category] || '📦'}
            </div>
            <div className="product-info">
              <h3>{p.name}</h3>
              <p>{p.category} · Level {p.shelf_level}</p>
            </div>
            <span className="product-price">€{p.price?.toFixed(2)}</span>
            <button
              className={inQueue ? 'btn-outline nav-queue-btn' : 'btn-primary nav-queue-btn'}
              onClick={() => onAddToQueue(p)}
              disabled={inQueue}
            >
              {inQueue ? 'In queue' : '+ Queue'}
            </button>
          </div>
        );
      })}
    </div>
  );
}
