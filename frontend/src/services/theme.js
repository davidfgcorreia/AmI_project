const STORAGE_KEY = 'ire_palette_v1';

const defaultPalette = ['#1a73e8', '#4a9af5', '#f5f7fa', '#ffffff', '#ff8800'];

function applyPalette(colors) {
  if (!Array.isArray(colors) || colors.length < 5) return;
  const root = document.documentElement;
  for (let i = 0; i < 5; i++) {
    root.style.setProperty(`--palette-${i}`, colors[i]);
  }
}

function savePalette(colors) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(colors));
  } catch (e) {
    console.error('Failed to save palette', e);
  }
  applyPalette(colors);
}

function loadSavedPalette() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultPalette.slice();
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length >= 5) return parsed;
  } catch (e) {
    console.error('Failed to load saved palette', e);
  }
  return defaultPalette.slice();
}

function loadAndApplySavedPalette() {
  const p = loadSavedPalette();
  applyPalette(p);
  return p;
}

export default {
  applyPalette,
  savePalette,
  loadSavedPalette,
  loadAndApplySavedPalette,
  defaultPalette,
};
