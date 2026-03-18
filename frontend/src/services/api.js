/**
 * API client - talks to the FastAPI backend.
 */
// In dev: empty (Vite proxy handles it).
// In Android build: set VITE_BACKEND_URL=http://192.168.x.x:8000
const BASE = import.meta.env.VITE_BACKEND_URL || '';

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

export const getGateways = () => request('/api/gateways');

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


export const healthCheck = () => request('/health');

