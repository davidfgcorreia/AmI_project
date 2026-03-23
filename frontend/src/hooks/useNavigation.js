import { useEffect, useRef } from 'react';
import { playFile, playSound, stopAll } from '../services/sound';

function dist(a, b) {
  if (!a || !b) return Infinity;
  const dx = (a.x ?? 0) - (b.x ?? 0);
  const dy = (a.y ?? 0) - (b.y ?? 0);
  return Math.hypot(dx, dy);
}

export default function useNavigation({ userPos, nextItem, targets, voiceEnabled = true }) {
  const lastDistRef = useRef(Infinity);
  const announcedRef = useRef({ started: false, arrived: false });

  useEffect(() => {
    if (!nextItem || !userPos) return;
    if (!voiceEnabled) {
      stopAll();
      return;
    }
    const target = (targets && targets.length > 0) ? targets[0] : null;
    if (!target) return;

    const d = dist(userPos, target);
    const last = lastDistRef.current;

    // announce when navigation starts
    if (!announcedRef.current.started) {
      // Play a short "start navigation" audio file instead of TTS
      playFile('MoveForward.mp3');
      announcedRef.current.started = true;
      announcedRef.current.arrived = false;
    }

    // distance thresholds to announce crossing
    const thresholds = [10, 5, 2, 1.5];
    for (const t of thresholds) {
      if (last > t && d <= t) {
        // Use generic audio cues at distance thresholds
        if (t >= 2) {
          playFile('Frente.mp3');
        } else {
          playFile('MoveForward.mp3');
        }
        break;
      }
    }

    // arrival: stop, announce turn direction (left/right), then play item-specific sound
    if (d <= 1.2 && !announcedRef.current.arrived) {
      // ensure other sounds stop
      stopAll();
      // arrival cue
      playFile('Para.mp3');

      // Determine side (right/left) relative to user -> target vector
      const dx = (target.x ?? 0) - (userPos.x ?? 0);
      const dy = (target.y ?? 0) - (userPos.y ?? 0);
      let side;
      // Use dominant axis to decide lateral side
      if (Math.abs(dx) > Math.abs(dy)) {
        side = dx > 0 ? 'right' : 'left';
      } else {
        side = dy > 0 ? 'right' : 'left';
      }

      // play turn cue
      if (side === 'right') {
        playFile('TrunRigth.mp3');
      } else {
        playFile('TrunLeft.mp3');
      }

      // play item-specific audio using convention-based filename: item_<id>.mp3
      try {
        if (nextItem && nextItem.id) {
          playFile(`item_${nextItem.id}.mp3`);
        }
      } catch (e) {
        // ignore missing file errors — audio service handles failures silently
      }

      announcedRef.current.arrived = true;
    }

    lastDistRef.current = d;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userPos?.x, userPos?.y, nextItem?.id, targets?.length]);

  // reset announcements when nextItem changes
  useEffect(() => {
    announcedRef.current = { started: false, arrived: false };
    lastDistRef.current = Infinity;
  }, [nextItem?.id]);
}
