/**
 * FloorMap - renders a 2D floor plan on a <canvas> showing:
 *   • Store outline & grid
 *   • Shelves (rectangles)
 *   • User position (blue dot)
 *   • Navigation path (animated blue line)
 *   • Target markers (red pins)
 */
import { useRef, useEffect, useCallback } from 'react';

// Physical store dimensions in metres. Keep REAL_W/REAL_H = 10×5 rotated
// so the displayed coordinate space is 5×10 (portrait) while the real
// store is 10m wide × 5m high.
const REAL_W = 10;    // metres (physical width)
const REAL_H = 5;     // metres (physical height)
// Rotate 90° for portrait phones: map long axis runs vertically
const ROTATED = true;
const STORE_W = ROTATED ? REAL_H : REAL_W;
const STORE_H = ROTATED ? REAL_W : REAL_H;

const COLORS = {
  bg: '#f0f2f5',
  grid: '#e0e0e0',
  shelf: '#90a4ae',
  shelfStroke: '#607d8b',
  path: '#1a73e8',
  user: '#1a73e8',
  userGlow: 'rgba(26,115,232,0.2)',
  target: '#ea4335',
  text: '#37474f',
};

export default function FloorMap({ shelves = [], userPos, path = [], targets = [], beacons = [] }) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const rectRef = useRef({ width: 300, height: 200 });

  // Mirror props into a ref so the stable rAF loop always reads fresh data
  // without needing to be recreated (which would cancel+restart and cause flashes).
  const dataRef = useRef({ shelves, userPos, path, targets, beacons });
  dataRef.current = { shelves, userPos, path, targets, beacons };

  // Stable draw — never recreated, reads from dataRef each frame.
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = rectRef.current.width;
    const H = rectRef.current.height;
    const { shelves, userPos, path, targets, beacons } = dataRef.current;

    const sx = W / STORE_W;
    const sy = H / STORE_H;
    const scale = Math.min(sx, sy);
    const ox = (W - STORE_W * scale) / 2;
    const oy = (H - STORE_H * scale) / 2;

    // When rotated: real (x,y) → screen (y, REAL_W - x)
    const tx = (x, y) => ROTATED ? ox + y * scale : ox + x * scale;
    const ty = (x, y) => ROTATED ? oy + (REAL_W - x) * scale : oy + (STORE_H - y) * scale;

    // Clear
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, W, H);

    // Grid (in real-world coords)
    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 0.5;
    for (let x = 0; x <= REAL_W; x++) {
      ctx.beginPath();
      ctx.moveTo(tx(x, 0), ty(x, 0));
      ctx.lineTo(tx(x, REAL_H), ty(x, REAL_H));
      ctx.stroke();
    }
    for (let y = 0; y <= REAL_H; y++) {
      ctx.beginPath();
      ctx.moveTo(tx(0, y), ty(0, y));
      ctx.lineTo(tx(REAL_W, y), ty(REAL_W, y));
      ctx.stroke();
    }

    // Store outline
    ctx.strokeStyle = '#455a64';
    ctx.lineWidth = 2;
    const outX = tx(0, 0);
    const outY = ty(REAL_W, 0);
    ctx.strokeRect(outX, outY, STORE_W * scale, STORE_H * scale);

    // Entrance label (entrance is at y=0 side of the real room)
    ctx.fillStyle = COLORS.text;
    ctx.font = `bold ${12}px sans-serif`;
    ctx.textAlign = 'center';
    const entX = tx(REAL_W / 2, -0.05);
    const entY = ty(REAL_W / 2, -0.05);
    if (ROTATED) {
      // When rotated, entrance is on the left edge — draw vertically
      ctx.save();
      ctx.translate(entX, entY);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText('ENTRANCE', 0, 0);
      ctx.restore();
    } else {
      ctx.fillText('ENTRANCE', entX, entY);
    }

    // Shelves
    shelves.forEach((s) => {
      const rw = s.width || 1;
      const rh = s.height || 0.8;
      // In rotated mode, shelf real width→screen height and vice versa
      const sw = (ROTATED ? rh : rw) * scale;
      const sh = (ROTATED ? rw : rh) * scale;
      const sxp = tx(s.x, s.y) - sw / 2;
      const syp = ty(s.x, s.y) - sh / 2;

      ctx.fillStyle = COLORS.shelf;
      ctx.strokeStyle = COLORS.shelfStroke;
      ctx.lineWidth = 1;
      // Draw perfect circle shelf with fixed 1m diameter (0.5m radius)
      const centerX = tx(s.x, s.y);
      const centerY = ty(s.x, s.y);
      const radius = 0.5 * scale; // 0.5 metres -> pixels
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = COLORS.text;
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(s.name || `S${s.id}`, tx(s.x, s.y), ty(s.x, s.y) + 3);
    });

    // Beacons / Gateways
    beacons.forEach((b) => {
      ctx.fillStyle = '#2e7d32';
      ctx.beginPath();
      ctx.arc(tx(b.x, b.y), ty(b.x, b.y), 6, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = COLORS.text;
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(b.id, tx(b.x, b.y) + 8, ty(b.x, b.y) + 4);
    });

    // Navigation path
    if (path.length > 1) {
      ctx.strokeStyle = COLORS.path;
      ctx.lineWidth = 3;
      ctx.setLineDash([8, 4]);
      ctx.beginPath();
      ctx.moveTo(tx(path[0].x, path[0].y), ty(path[0].x, path[0].y));
      for (let i = 1; i < path.length; i++) {
        ctx.lineTo(tx(path[i].x, path[i].y), ty(path[i].x, path[i].y));
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Target markers
    targets.forEach((t) => {
      ctx.fillStyle = COLORS.target;
      ctx.beginPath();
      ctx.arc(tx(t.x, t.y), ty(t.x, t.y), 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('★', tx(t.x, t.y), ty(t.x, t.y) + 4);
    });

    // User position
    if (userPos) {
      const accRadius = (userPos.accuracy || 1.5) * scale;
      ctx.fillStyle = COLORS.userGlow;
      ctx.beginPath();
      ctx.arc(tx(userPos.x, userPos.y), ty(userPos.x, userPos.y), accRadius, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = COLORS.user;
      ctx.beginPath();
      ctx.arc(tx(userPos.x, userPos.y), ty(userPos.x, userPos.y), 7, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    animRef.current = requestAnimationFrame(draw);
  }, []); // empty deps — loop is started once and never restarted

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function resize() {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      rectRef.current = { width: rect.width, height: rect.height };
    }

    resize();
    window.addEventListener('resize', resize);
    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement || canvas);

    draw();

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
      try { ro.disconnect(); } catch (e) {}
    };
  }, []); // mount/unmount only — loop is never cancelled mid-session

  return (
    <div className="map-container">
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
