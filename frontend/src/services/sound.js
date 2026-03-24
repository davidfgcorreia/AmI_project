const sounds = {
  moveForward: '/audio/move-forward.mp3',
  turnRight: '/audio/turn-right.mp3',
  turnLeft: '/audio/turn-left.mp3',
  stop: '/audio/stop.mp3',
  continueStraight: '/audio/continue-straight.mp3',
  confirmTone: '/audio/confirm-tone.mp3',
  errorTone: '/audio/error-tone.mp3',
};

const players = {};

export function preloadSounds() {
  Object.keys(sounds).forEach((k) => {
    if (!players[k]) {
      const a = new Audio(sounds[k]);
      a.preload = 'auto';
      players[k] = a;
    }
  });
}

export function playSound(name) {
  const src = sounds[name];
  if (!src) return;
  if (!players[name]) players[name] = new Audio(src);
  const p = players[name];
  try {
    p.currentTime = 0;
    p.play().catch(() => {});
  } catch (e) {
    // ignore playback errors
  }
}

export function stopSound(name) {
  const p = players[name];
  if (p) {
    try { p.pause(); p.currentTime = 0; } catch (e) {}
  }
}

export function stopAll() {
  Object.keys(players).forEach((k) => {
    try {
      const p = players[k];
      if (p && typeof p.pause === 'function') {
        p.pause();
        p.currentTime = 0;
      }
    } catch (e) {}
  });
}

export default { preloadSounds, playSound, stopSound };

// Play an arbitrary file name located under /audio
export function playFile(filename) {
  if (!filename) return;
  const src = filename.startsWith('/') ? filename : `/audio/${filename}`;
  let key = `file:${src}`;
  if (!players[key]) players[key] = new Audio(src);
  try {
    players[key].currentTime = 0;
    players[key].play().catch(() => {});
  } catch (e) {}
}

// ── Text-to-Speech ──────────────────────────────────────────────────────────
let _ttsSupported = null;

function ttsAvailable() {
  if (_ttsSupported === null) {
    _ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  }
  return _ttsSupported;
}

function hasNativeTTS() {
  try { return window.AndroidBridge?.hasNativeTTS?.(); } catch (e) { return false; }
}

export function speak(text) {
  if (!text) return;
  // Prefer native Android TTS (WebView doesn't support speechSynthesis)
  if (hasNativeTTS()) {
    try { window.AndroidBridge.speak(text); } catch (e) {}
    return;
  }
  if (!ttsAvailable()) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.rate = 1.0;
  utt.pitch = 1.0;
  utt.volume = 1.0;
  utt.lang = 'en-US';
  window.speechSynthesis.speak(utt);
}

export function stopSpeech() {
  if (hasNativeTTS()) {
    try { window.AndroidBridge.stopSpeech(); } catch (e) {}
    return;
  }
  if (ttsAvailable()) window.speechSynthesis.cancel();
}
