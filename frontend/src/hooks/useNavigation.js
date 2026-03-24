/**
 * useNavigation - turn-by-turn audio navigation using TTS.
 *
 * Runs on every position update to give responsive audio cues.
 * Announces the product name when navigation starts, then gives
 * turn directions at each waypoint, and announces arrival.
 */
import { useEffect, useRef } from 'react';
import { speak } from '../services/sound';

// ── Geometry helpers ─────────────────────────────────────────────────────────

function dist(a, b) {
  return Math.hypot((a.x ?? 0) - (b.x ?? 0), (a.y ?? 0) - (b.y ?? 0));
}

function bearing(a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
}

function turnDirection(fromBearing, toBearing) {
  let delta = ((toBearing - fromBearing) + 360) % 360;
  if (delta > 180) delta -= 360;

  if (Math.abs(delta) < 25) return 'continue straight';
  if (delta > 0 && delta <= 100) return 'turn right';
  if (delta > 100) return 'turn sharp right';
  if (delta < 0 && delta >= -100) return 'turn left';
  return 'turn sharp left';
}

const LEVEL_NAMES = ['bottom', 'lower', 'middle', 'upper', 'top'];
function levelName(n) { return LEVEL_NAMES[(n || 1) - 1] || `level ${n}`; }
function capitalise(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

const WAYPOINT_RADIUS = 1.5;
const ARRIVAL_RADIUS = 1.8;
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

  // Announce product name as soon as it's queued (no position needed)
  useEffect(() => {
    console.log('[NAV] start check:', { voiceEnabled, nextItem: nextItem?.name, announced: announcedStartRef.current });
    if (!voiceEnabled || !nextItem) return;
    if (announcedStartRef.current) return;
    announcedStartRef.current = true;

    const target = targets?.[0];
    console.log('[NAV] announcing start:', nextItem.name, { userPos, target });
    if (userPos && target) {
      const d = Math.round(dist(userPos, target));
      speak(`Navigating to ${nextItem.name}, about ${d} metres away.`);
    } else {
      speak(`Navigating to ${nextItem.name}.`);
    }
    lastSpokeRef.current = Date.now() / 1000;
    waypointIdxRef.current = 1;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextItem?.id, voiceEnabled]);

  // Turn-by-turn on position updates
  useEffect(() => {
    if (!voiceEnabled || !userPos || !nextItem || path.length < 2) return;

    const target = targets?.[0];
    if (!target) return;
    if (arrivedRef.current) return;

    const now = Date.now() / 1000;
    const canSpeak = (now - lastSpokeRef.current) >= MIN_SPEAK_INTERVAL;

    // ── Arrival check ────────────────────────────────────────────────────
    const dTarget = dist(userPos, target);
    if (dTarget <= ARRIVAL_RADIUS) {
      arrivedRef.current = true;
      const level = levelName(nextItem.shelf_level);
      speak(`You have arrived. ${nextItem.name} is on the ${level} shelf.`);
      lastSpokeRef.current = now;
      return;
    }

    // ── Waypoint progression ─────────────────────────────────────────────
    let idx = waypointIdxRef.current;
    if (idx >= path.length || !canSpeak) return;

    const dWaypoint = dist(userPos, path[idx]);
    if (dWaypoint > WAYPOINT_RADIUS) return;

    const nextIdx = idx + 1;
    if (nextIdx >= path.length) {
      waypointIdxRef.current = path.length;
      return;
    }

    const fromBear = bearing(path[idx - 1], path[idx]);
    const toBear = bearing(path[idx], path[nextIdx]);
    const turn = turnDirection(fromBear, toBear);

    const waypointsLeft = path.length - nextIdx;
    if (waypointsLeft <= 2) {
      speak(`${capitalise(turn)}, almost there.`);
    } else {
      speak(`${capitalise(turn)}.`);
    }
    lastSpokeRef.current = now;
    waypointIdxRef.current = nextIdx;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userPos?.x, userPos?.y, nextItem?.id, path.length, voiceEnabled]);
}
