/**
 * API client – talks to the FastAPI backend.
 */
const BASE = '';   // proxied by Vite in dev

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Products ──
export const getProducts = (q = '') =>
  request(`/api/products?q=${encodeURIComponent(q)}`);

export const getProduct = (id) =>
  request(`/api/products/${id}`);

// ── Shelves ──
export const getShelves = () => request('/api/shelves');

// ── Navigation ──
export const navigate = (sessionId, { productIds, productQuery }) =>
  request('/api/navigate', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      product_ids: productIds || [],
      product_query: productQuery || '',
    }),
  });

// ── Shelf scan (upload image) ──
export const scanShelf = async (shelfId, imageFile, highlight = '') => {
  const form = new FormData();
  form.append('image', imageFile);
  form.append('highlight', highlight);
  const res = await fetch(`${BASE}/api/shelves/${shelfId}/scan`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

export const healthCheck = () => request('/health');
