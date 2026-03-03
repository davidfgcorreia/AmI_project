/**
 * useIMU – streams device motion / orientation via the DeviceMotion API.
 * Sends updates to the WebSocket tracking service.
 */
import { useEffect, useRef, useCallback } from 'react';
import { sendIMU } from '../services/websocket';

export default function useIMU(active = true) {
  const stepsRef = useRef(0);
  const lastAccelRef = useRef(0);
  const headingRef = useRef(0);
  const intervalRef = useRef(null);

  // Simple step detection via acceleration threshold
  const handleMotion = useCallback((e) => {
    if (!active) return;
    const a = e.accelerationIncludingGravity;
    if (!a) return;

    const mag = Math.sqrt(a.x ** 2 + a.y ** 2 + a.z ** 2);
    // Detect step: acceleration crosses threshold
    if (Math.abs(mag - lastAccelRef.current) > 3.5) {
      stepsRef.current += 1;
    }
    lastAccelRef.current = mag;
  }, [active]);

  const handleOrientation = useCallback((e) => {
    if (!active) return;
    // alpha = compass heading (0-360)
    if (e.alpha != null) {
      headingRef.current = e.alpha;
    }
  }, [active]);

  useEffect(() => {
    if (!active) return;

    // Request permission (iOS 13+)
    if (typeof DeviceMotionEvent !== 'undefined' &&
        typeof DeviceMotionEvent.requestPermission === 'function') {
      DeviceMotionEvent.requestPermission().catch(() => {});
    }
    if (typeof DeviceOrientationEvent !== 'undefined' &&
        typeof DeviceOrientationEvent.requestPermission === 'function') {
      DeviceOrientationEvent.requestPermission().catch(() => {});
    }

    window.addEventListener('devicemotion', handleMotion);
    window.addEventListener('deviceorientation', handleOrientation);

    // Send IMU data at ~5 Hz
    intervalRef.current = setInterval(() => {
      sendIMU({
        heading: headingRef.current,
        steps: stepsRef.current,
      });
      stepsRef.current = 0;   // reset per interval
    }, 200);

    return () => {
      window.removeEventListener('devicemotion', handleMotion);
      window.removeEventListener('deviceorientation', handleOrientation);
      clearInterval(intervalRef.current);
    };
  }, [active, handleMotion, handleOrientation]);
}
