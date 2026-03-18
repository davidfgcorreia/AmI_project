#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════
  IRE Calibration Tool — Data Collection
═══════════════════════════════════════════════════════════

Two modes:

  distance  — Stand at known distances from each ESP32 and record
              the RSSI your phone produces.  Produces the curve
              needed to tune BLE_TX_POWER and BLE_FAR_DBM_PER_M.

  survey    — Stand at known (x, y) positions on a floor grid and
              record what position the system estimates.  Shows you
              where the system is accurate and where it drifts.

Prerequisites:
  pip install httpx websockets

Usage:
  # Step 1 – calibrate each gateway one by one
  python calibrate.py distance --gateway esp32_A --session YOUR_SESSION_ID
  python calibrate.py distance --gateway esp32_B --session YOUR_SESSION_ID
  python calibrate.py distance --gateway esp32_C --session YOUR_SESSION_ID

  # Step 2 – position accuracy survey
  python calibrate.py survey --session YOUR_SESSION_ID

  # Then run analyse.py to get suggested config values
"""

import argparse
import asyncio
import csv
import json
import math
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND_HTTP = "http://localhost:8000"
BACKEND_WS   = "ws://localhost:8000"

# Distances (metres) to measure at for the distance calibration
DISTANCE_STEPS = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
RECORD_SECS    = 20   # seconds to collect samples at each point
POLL_INTERVAL  = 0.4  # seconds between buffer polls

OUT_DIR = Path(__file__).parent / "data"


# ── Helpers ────────────────────────────────────────────────────────────────

def banner(text: str):
    w = 56
    print("\n" + "═" * w)
    print(f"  {text}")
    print("═" * w)


def info(text: str):
    print(f"  {text}")


def prompt(text: str) -> str:
    return input(f"\n  ▶ {text}: ").strip()


async def fetch_buffer(session_id: str) -> dict[str, float]:
    """Return {gateway_id: smoothed_rssi} for the session."""
    try:
        import httpx
        async with httpx.AsyncClient(base_url=BACKEND_HTTP, timeout=3) as c:
            r = await c.get("/api/ble/buffer")
            buf = r.json()
            return buf.get(session_id, {})
    except Exception as e:
        print(f"  ✗ Buffer fetch failed: {e}")
        return {}


async def live_rssi(session_id: str, gateway_id: str | None = None, secs: int = 5):
    """Show live RSSI for *secs* seconds so the user can confirm signal."""
    info(f"Showing live RSSI for {secs}s …")
    end = time.monotonic() + secs
    while time.monotonic() < end:
        buf = await fetch_buffer(session_id)
        if gateway_id:
            val = buf.get(gateway_id)
            line = f"    {gateway_id}: {val:+.1f} dBm" if val is not None else f"    {gateway_id}: (no signal)"
        else:
            parts = [f"{gw}: {v:+.1f}" for gw, v in sorted(buf.items())]
            line = "    " + "   ".join(parts) if parts else "    (no readings)"
        print(f"\r{line}   ", end="", flush=True)
        await asyncio.sleep(POLL_INTERVAL)
    print()


async def record_samples(session_id: str, gateway_id: str, secs: int) -> list[float]:
    """Collect raw RSSI samples from one gateway for *secs* seconds."""
    samples: list[float] = []
    end = time.monotonic() + secs
    while time.monotonic() < end:
        buf = await fetch_buffer(session_id)
        val = buf.get(gateway_id)
        if val is not None:
            samples.append(val)
        remaining = int(end - time.monotonic())
        print(f"\r    Collecting … {remaining:2d}s  ({len(samples)} samples)", end="", flush=True)
        await asyncio.sleep(POLL_INTERVAL)
    print()
    return samples


# ── Distance calibration ────────────────────────────────────────────────────

async def run_distance(gateway_id: str, session_id: str, duration: int = RECORD_SECS):
    banner(f"Distance calibration — {gateway_id}")
    info(f"Session ID : {session_id}")
    info(f"Backend    : {BACKEND_HTTP}")
    info("")
    info("WHAT TO DO:")
    info("  • Hold your phone at chest height in front of you.")
    info("  • Walk to each distance from the ESP32 and stand still.")
    info("  • Measure the distance on the floor (tape is best).")
    info("  • Keep your body between you and the ESP32 for worst-case signal.")
    info("  • Repeat each distance 2-3 times if you have time (just run again).")

    prompt("Press ENTER when the backend is running and your phone is advertising")

    info("Checking live signal …")
    await live_rssi(session_id, gateway_id, secs=4)

    buf = await fetch_buffer(session_id)
    if gateway_id not in buf:
        info(f"✗  No reading from {gateway_id}. Check that:")
        info(f"   • The backend is running (http://localhost:8000)")
        info(f"   • The ESP32 {gateway_id} is powered and connected to MQTT")
        info(f"   • Your session ID matches what the ESP32 sees")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"distance_{gateway_id}_{ts}.csv"

    rows: list[dict] = []

    for dist in DISTANCE_STEPS:
        info(f"─────────────────────────────────")
        info(f"  Next distance: {dist} m from {gateway_id}")
        prompt(f"Stand {dist} m away, then press ENTER to start recording")

        samples = await record_samples(session_id, gateway_id, duration)
        if len(samples) < 5:
            info(f"  ✗  Too few samples ({len(samples)}). Skipping this distance.")
            continue

        mean = statistics.mean(samples)
        stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
        median = statistics.median(samples)

        info(f"  ✔  {len(samples)} samples  mean={mean:+.1f} dBm  median={median:+.1f} dBm  std=±{stdev:.1f} dBm")

        for s in samples:
            rows.append({
                "gateway_id": gateway_id,
                "distance_m": dist,
                "rssi": round(s, 2),
                "timestamp": datetime.now().isoformat(),
            })

    if not rows:
        info("No data collected. Exiting.")
        sys.exit(1)

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["gateway_id", "distance_m", "rssi", "timestamp"])
        writer.writeheader()
        writer.writerows(rows)

    info(f"\n  ✔  Saved {len(rows)} rows → {path}")
    info(f"  Run: python analyse.py  to get suggested config values.")


# ── Position survey ─────────────────────────────────────────────────────────

async def get_estimated_position(session_id: str) -> tuple[float, float, float] | None:
    """Connect to WS for one position reading."""
    try:
        import websockets
        url = f"{BACKEND_WS}/ws/track/{session_id}"
        async with websockets.connect(url, open_timeout=3) as ws:
            end = time.monotonic() + 5
            while time.monotonic() < end:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(raw)
                    if data.get("type") == "position":
                        return data["x"], data["y"], data.get("accuracy", 0)
                except asyncio.TimeoutError:
                    break
    except Exception:
        pass
    return None


async def run_survey(session_id: str):
    banner("Position accuracy survey")
    info(f"Session ID : {session_id}")
    info("")
    info("WHAT TO DO:")
    info("  • Mark a grid on the floor every 1–2 metres (tape/chalk).")
    info("  • Stand at each marked point and enter its coordinates.")
    info("  • Use the same coordinate system as the store (origin at bottom-left).")
    info("  • Stand still for the recording period.")
    info("  • Aim for at least 10–15 points spread across the whole room.")

    prompt("Press ENTER when ready")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"survey_{ts}.csv"

    rows: list[dict] = []
    point_num = 0

    info("Type 'done' when finished.\n")

    while True:
        point_num += 1
        info(f"─── Point {point_num} ───────────────────────")
        raw = prompt("Your actual position: x y  (e.g. '3.5 2.0', or 'done')")
        if raw.lower() in ("done", "q", "exit", ""):
            break

        try:
            parts = raw.split()
            actual_x, actual_y = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            info("  ✗  Enter two numbers separated by a space, e.g. '3.5 2.0'")
            point_num -= 1
            continue

        # Show live RSSI so they can see all 3 gateways are receiving
        await live_rssi(session_id, secs=3)

        # Collect RSSI samples
        buf = await fetch_buffer(session_id)
        if not buf:
            info("  ✗  No BLE readings. Check backend and ESP32s.")
            point_num -= 1
            continue

        # Collect position estimates over 10 seconds
        info("  Recording position estimates …")
        estimates: list[tuple[float, float, float]] = []
        end_t = time.monotonic() + 10
        while time.monotonic() < end_t:
            est = await get_estimated_position(session_id)
            if est:
                estimates.append(est)
            remaining = int(end_t - time.monotonic())
            print(f"\r    {remaining}s remaining  ({len(estimates)} estimates)", end="", flush=True)
            await asyncio.sleep(1.2)
        print()

        # Also grab raw RSSI snapshot
        buf = await fetch_buffer(session_id)

        if not estimates:
            info("  ✗  No position estimates. Trilateration may be failing.")
            rssi_str = "  ".join(f"{gw}:{v:+.1f}" for gw, v in sorted(buf.items()))
            info(f"     Raw RSSI: {rssi_str}")
            point_num -= 1
            continue

        # Average the estimates
        est_xs = [e[0] for e in estimates]
        est_ys = [e[1] for e in estimates]
        est_x  = statistics.mean(est_xs)
        est_y  = statistics.mean(est_ys)
        acc    = statistics.mean(e[2] for e in estimates)

        error = math.sqrt((est_x - actual_x)**2 + (est_y - actual_y)**2)

        info(f"  Actual:    ({actual_x:.2f}, {actual_y:.2f})")
        info(f"  Estimated: ({est_x:.2f}, {est_y:.2f})  ±{acc:.2f} m")
        info(f"  Error:     {error:.2f} m  {'✔' if error < 1.0 else '⚠' if error < 2.0 else '✗'}")

        rssi_str = "  ".join(f"{gw}:{v:+.1f}" for gw, v in sorted(buf.items()))
        info(f"  Raw RSSI:  {rssi_str}")

        for est in estimates:
            rows.append({
                "actual_x":   actual_x,
                "actual_y":   actual_y,
                "est_x":      round(est[0], 3),
                "est_y":      round(est[1], 3),
                "accuracy":   round(est[2], 3),
                "error_m":    round(math.sqrt((est[0]-actual_x)**2 + (est[1]-actual_y)**2), 3),
                **{f"rssi_{gw}": round(v, 1) for gw, v in buf.items()},
                "timestamp":  datetime.now().isoformat(),
            })

    if not rows:
        info("No data collected.")
        sys.exit(0)

    # Write CSV with a consistent field set
    all_fields = list(dict.fromkeys(
        ["actual_x", "actual_y", "est_x", "est_y", "accuracy", "error_m"]
        + [k for k in rows[0] if k.startswith("rssi_")]
        + ["timestamp"]
    ))
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    errors = [r["error_m"] for r in rows]
    info(f"\n  ✔  Saved {len(rows)} rows → {path}")
    info(f"  Mean error : {statistics.mean(errors):.2f} m")
    info(f"  Max error  : {max(errors):.2f} m")
    info(f"  <1m        : {100*sum(1 for e in errors if e<1)/len(errors):.0f}%  of estimates")
    info(f"\n  Run: python analyse.py  for a full breakdown.")


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    global BACKEND_HTTP, BACKEND_WS
    parser = argparse.ArgumentParser(
        description="IRE calibration data collector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    dist_p = sub.add_parser("distance", help="Calibrate RSSI-to-distance model")
    dist_p.add_argument("--gateway",  required=True, choices=["esp32_A", "esp32_B", "esp32_C"])
    dist_p.add_argument("--session",  required=True, help="BLE session ID (e.g. IRE-a3b4c5d6)")
    dist_p.add_argument("--backend",  default=BACKEND_HTTP)
    dist_p.add_argument("--duration", type=int, default=RECORD_SECS, help="Seconds per distance step")

    surv_p = sub.add_parser("survey", help="Measure position accuracy across the room")
    surv_p.add_argument("--session", required=True, help="BLE session ID")
    surv_p.add_argument("--backend", default=BACKEND_HTTP)

    args = parser.parse_args()

    if hasattr(args, "backend"):
        BACKEND_HTTP = args.backend
        BACKEND_WS   = args.backend.replace("http", "ws")

    try:
        if args.mode == "distance":
            asyncio.run(run_distance(args.gateway, args.session, args.duration))
        elif args.mode == "survey":
            asyncio.run(run_survey(args.session))
    except KeyboardInterrupt:
        print("\n\n  Stopped.")


if __name__ == "__main__":
    main()
