/**
 * useNavigation - turn-by-turn audio navigation using TTS.
 *
 * Analyses the A* path to compute turn directions (left / right / straight)
 * and announces them as the user approaches each waypoint.  On arrival at
 * a target shelf it announces the product name and shelf level.
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

// How close (metres) the user must be to a waypoint to trigger the next instruction
const WAYPOINT_RADIUS = 1.5;
// How close to the target shelf to announce arrival
const ARRIVAL_RADIUS = 1.8;

// ── Hook ─────────────────────────────────────────────────────────────────────

export default function useNavigation({ userPos, nextItem, path = [], targets = [], voiceEnabled = true }) {
  // Index of the path waypoint the user is currently heading toward
  const waypointIdxRef = useRef(0);
  const announcedStartRef = useRef(false);
  const arrivedRef = useRef(false);
  const lastItemIdRef = useRef(null);

  // Reset when the target product changes
  useEffect(() => {
    if (nextItem?.id !== lastItemIdRef.current) {
      waypointIdxRef.current = 0;
      announcedStartRef.current = false;
      arrivedRef.current = false;
      lastItemIdRef.current = nextItem?.id ?? null;
    }
  }, [nextItem?.id]);

  useEffect(() => {
    if (!voiceEnabled) { stopSpeech(); return; }
    if (!userPos || !nextItem || path.length < 2) return;

    const target = targets?.[0];
    if (!target) return;

    // ── Arrival check ────────────────────────────────────────────────────
    const dTarget = dist(userPos, target);
    if (dTarget <= ARRIVAL_RADIUS && !arrivedRef.current) {
      arrivedRef.current = true;
      const level = levelName(nextItem.shelf_level);
      speak(`You have arrived. ${nextItem.name} is on the ${level} shelf.`);
      return;
    }
    if (arrivedRef.current) return; // already arrived, wait for next item

    // ── Start announcement ───────────────────────────────────────────────
    if (!announcedStartRef.current) {
      announcedStartRef.current = true;
      const remaining = Math.round(dTarget);
      speak(`Navigating to ${nextItem.name}, about ${remaining} metres away.`);
      waypointIdxRef.current = 1;
      return;
    }

    // ── Waypoint progression ─────────────────────────────────────────────
    let idx = waypointIdxRef.current;
    if (idx >= path.length) return;

    const dWaypoint = dist(userPos, path[idx]);
    if (dWaypoint > WAYPOINT_RADIUS) return; // not there yet

    // User reached waypoint idx — advance and announce next turn
    const nextIdx = idx + 1;
    if (nextIdx >= path.length) {
      // Last waypoint is the target — arrival will be handled above
      waypointIdxRef.current = path.length;
      return;
    }

    // Compute turn from current segment to next segment
    const prevBear = bearing(path[idx - 1] || path[idx], path[idx]);
    const nextBear = bearing(path[idx], path[nextIdx]);
    const turn = turnDirection(prevBear, nextBear);

    // Estimate remaining distance
    let remaining = 0;
    for (let i = idx; i < path.length - 1; i++) {
      remaining += dist(path[i], path[i + 1]);
    }

    if (remaining < 3) {
      speak(`${capitalise(turn)}, almost there.`);
    } else {
      speak(`${capitalise(turn)}.`);
    }

    waypointIdxRef.current = nextIdx;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userPos?.x, userPos?.y, nextItem?.id, path.length, voiceEnabled]);
}

// ── Small helpers ────────────────────────────────────────────────────────────

function compassWord(deg) {
  const dirs = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];
  return dirs[Math.round(deg / 45) % 8];
}

function capitalise(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
