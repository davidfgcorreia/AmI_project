/**
 * useNavigation - turn-by-turn audio navigation using TTS.
 *
 * Runs on every position update (~10 Hz) to give responsive audio cues.
 * Tracks which path waypoint the user is heading toward and announces
 * turns as they reach each one. On arrival at the target shelf it
 * announces the product name and shelf level.
 */
import { useEffect, useRef } from 'react';
import { speak, stopSpeech } from '../services/sound';

// ── Geometry helpers ─────────────────────────────────────────────────────────

function dist(a, b) {
  return Math.hypot((a.x ?? 0) - (b.x ?? 0), (a.y ?? 0) - (b.y ?? 0));
}

/** Angle in degrees from point a to point b (0 = +Y / north, 90 = +X / east). */
function bearing(a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
}

/**
 * Given the bearing of the segment the user is currently on and the bearing
 * of the next segment, return a human-readable turn instruction.
 */
function turnDirection(fromBearing, toBearing) {
  let delta = ((toBearing - fromBearing) + 360) % 360;
  if (delta > 180) delta -= 360; // normalise to [-180, 180]

  if (Math.abs(delta) < 25) return 'continue straight';
  if (delta > 0 && delta <= 100) return 'turn right';
  if (delta > 100) return 'turn sharp right';
  if (delta < 0 && delta >= -100) return 'turn left';
  return 'turn sharp left';
}

const LEVEL_NAMES = ['bottom', 'lower', 'middle', 'upper', 'top'];
function levelName(n) { return LEVEL_NAMES[(n || 1) - 1] || `level ${n}`; }

function capitalise(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

// How close (metres) the user must be to a waypoint to trigger the next instruction
const WAYPOINT_RADIUS = 1.5;
// How close to the target shelf to announce arrival
const ARRIVAL_RADIUS = 1.8;
// Minimum seconds between spoken instructions to avoid spamming
const MIN_SPEAK_INTERVAL = 2.0;

// ── Hook ─────────────────────────────────────────────────────────────────────

export default function useNavigation({ userPos, nextItem, path = [], targets = [], voiceEnabled = true }) {
  const waypointIdxRef = useRef(0);
  const announcedStartRef = useRef(false);
  const arrivedRef = useRef(false);
  const lastItemIdRef = useRef(null);
  const lastSpokeRef = useRef(0);

  // Reset when the target product changes
  useEffect(() => {
    if (nextItem?.id !== lastItemIdRef.current) {
      waypointIdxRef.current = 0;
      announcedStartRef.current = false;
      arrivedRef.current = false;
      lastItemIdRef.current = nextItem?.id ?? null;
    }
  }, [nextItem?.id]);

  // Main navigation loop — runs on every position update
  useEffect(() => {
    if (!voiceEnabled) { stopSpeech(); return; }
    if (!userPos || !nextItem || path.length < 2) return;

    const target = targets?.[0];
    if (!target) return;

    const now = Date.now() / 1000;
    const canSpeak = (now - lastSpokeRef.current) >= MIN_SPEAK_INTERVAL;

    function say(text) {
      if (!canSpeak) return;
      speak(text);
      lastSpokeRef.current = now;
    }

    // ── Arrival check ────────────────────────────────────────────────────
    const dTarget = dist(userPos, target);
    if (dTarget <= ARRIVAL_RADIUS && !arrivedRef.current) {
      arrivedRef.current = true;
      const level = levelName(nextItem.shelf_level);
      speak(`You have arrived. ${nextItem.name} is on the ${level} shelf.`);
      lastSpokeRef.current = now;
      return;
    }
    if (arrivedRef.current) return;

    // ── Start announcement ───────────────────────────────────────────────
    if (!announcedStartRef.current) {
      announcedStartRef.current = true;
      const remaining = Math.round(dTarget);
      speak(`Navigating to ${nextItem.name}, about ${remaining} metres away.`);
      lastSpokeRef.current = now;
      waypointIdxRef.current = 1;
      return;
    }

    // ── Waypoint progression ─────────────────────────────────────────────
    let idx = waypointIdxRef.current;
    if (idx >= path.length) return;

    const dWaypoint = dist(userPos, path[idx]);
    if (dWaypoint > WAYPOINT_RADIUS) return; // not there yet

    // User reached waypoint — advance and announce next turn
    const nextIdx = idx + 1;
    if (nextIdx >= path.length) {
      // Last waypoint is the target — arrival will be handled above
      waypointIdxRef.current = path.length;
      return;
    }

    // Compute turn direction from current segment to next segment
    const fromBear = bearing(path[idx - 1], path[idx]);
    const toBear = bearing(path[idx], path[nextIdx]);
    const turn = turnDirection(fromBear, toBear);

    const waypointsLeft = path.length - nextIdx;
    if (waypointsLeft <= 2) {
      say(`${capitalise(turn)}, almost there.`);
    } else {
      say(`${capitalise(turn)}.`);
    }

    waypointIdxRef.current = nextIdx;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userPos?.x, userPos?.y, nextItem?.id, path.length, voiceEnabled]);
}
