#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  ESP32 + Phone Simulator – Intelligent Retail Ecosystem
═══════════════════════════════════════════════════════════════

Simulates a user walking through the store while 3 ESP32 gateways
pick up BLE RSSI signals from the phone.

Two modes of operation:
  1. MQTT mode  – publishes RSSI to the MQTT broker (like real ESP32s)
  2. HTTP mode  – posts BLE readings directly to the backend REST API
                  + sends IMU data via WebSocket (like the phone)

The user follows a configurable path with realistic:
  • RSSI noise (multipath, fading)
  • Step-by-step movement with heading changes
  • IMU jitter (accelerometer / gyroscope noise)

Usage:
  python simulator.py                     # HTTP mode (no MQTT broker needed)
  python simulator.py --mqtt              # MQTT mode (requires mosquitto)
  python simulator.py --speed 0.5         # slower walk
  python simulator.py --session my-phone  # custom session ID
"""

import argparse
import asyncio
import json
import math
import random
import sys
import time
from dataclasses import dataclass

# ── Store / gateway config (mirrors backend config.py) ──────────────────

GATEWAY_POSITIONS = {
    "esp32_A": (0.0, 0.0),
    "esp32_B": (10.0, 0.0),
    "esp32_C": (5.0, 8.0),
}

BLE_TX_POWER = -59          # RSSI at 1 m (dBm)
BLE_PATH_LOSS_EXP = 2.7    # indoor path-loss exponent

STORE_WIDTH = 12.0
STORE_HEIGHT = 10.0

# ── Default walking path (waypoints in metres) ─────────────────────────
# Entrance → Aisle 1 → Aisle 2 → Aisle 3 → End-cap → back to entrance
DEFAULT_PATH = [
    (6.0, 0.5),    # entrance
    (3.0, 1.5),    # walk toward Aisle 1
    (3.0, 3.5),    # midway Aisle 1
    (3.0, 5.0),    # near Aisle 2
    (3.0, 7.0),    # end of Aisle 2
    (5.5, 8.5),    # end-cap
    (8.0, 7.0),    # cross to Aisle 3-4
    (8.0, 5.0),    # midway Aisle 4
    (8.0, 2.0),    # top of Aisle 3
    (6.0, 0.5),    # back to entrance
]


# ── Helpers ─────────────────────────────────────────────────────────────

def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def heading_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Heading in degrees (0=North/+Y, 90=East/+X)."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return math.degrees(math.atan2(dx, dy)) % 360


def distance_to_rssi(d: float) -> float:
    """Inverse of the log-distance path-loss model + Gaussian noise."""
    if d < 0.1:
        d = 0.1
    rssi = BLE_TX_POWER - 10 * BLE_PATH_LOSS_EXP * math.log10(d)
    # Add realistic noise: ±3-6 dBm (multipath, body shielding, reflections)
    noise = random.gauss(0, 3.5)
    return round(rssi + noise, 1)


def interpolate_path(waypoints: list[tuple[float, float]],
                     step_size: float = 0.65) -> list[tuple[float, float]]:
    """
    Subdivide waypoints into small steps (~step_size metres apart)
    to simulate realistic walking.
    """
    points = []
    for i in range(len(waypoints) - 1):
        a, b = waypoints[i], waypoints[i + 1]
        seg_dist = distance(a, b)
        n_steps = max(1, int(seg_dist / step_size))
        for s in range(n_steps):
            t = s / n_steps
            x = a[0] + t * (b[0] - a[0])
            y = a[1] + t * (b[1] - a[1])
            points.append((round(x, 3), round(y, 3)))
    points.append(waypoints[-1])
    return points


@dataclass
class SimState:
    """Tracks the simulated user's current state."""
    x: float = 6.0
    y: float = 0.5
    heading: float = 0.0
    step_count: int = 0
    total_steps: int = 0


# ── RSSI generation ────────────────────────────────────────────────────

def generate_rssi_readings(pos: tuple[float, float], session_id: str,
                           gateways: dict | None = None) -> list[dict]:
    """Generate one RSSI reading per gateway for the current position."""
    gateways = gateways or GATEWAY_POSITIONS
    readings = []
    for gw_id, gw_pos in gateways.items():
        d = distance(pos, gw_pos)
        rssi = distance_to_rssi(d)
        readings.append({
            "gateway_id": gw_id,
            "session_id": session_id,
            "rssi": rssi,
        })
    return readings


def generate_imu_data(state: SimState) -> dict:
    """Generate a simulated IMU packet (like the phone would send)."""
    return {
        "type": "imu",
        "heading": round(state.heading + random.gauss(0, 2), 1),  # ±2° jitter
        "steps": state.step_count,
        "accel_x": round(random.gauss(0, 0.3), 2),
        "accel_y": round(random.gauss(0, 0.3), 2),
        "accel_z": round(9.81 + random.gauss(0, 0.15), 2),
        "gyro_alpha": round(state.heading + random.gauss(0, 1), 1),
        "gyro_beta": round(random.gauss(0, 0.5), 2),
        "gyro_gamma": round(random.gauss(0, 0.5), 2),
    }


# ── Console visualisation ──────────────────────────────────────────────

def print_store_map(pos: tuple[float, float], gateways: dict):
    """Print a simple ASCII map of the store with user position."""
    W, H = 40, 20  # characters
    grid = [['·' for _ in range(W)] for _ in range(H)]

    # Border
    for c in range(W):
        grid[0][c] = '─'
        grid[H - 1][c] = '─'
    for r in range(H):
        grid[r][0] = '│'
        grid[r][W - 1] = '│'
    grid[0][0] = '┌'; grid[0][W-1] = '┐'
    grid[H-1][0] = '└'; grid[H-1][W-1] = '┘'

    # Gateways
    for gw_id, gw_pos in gateways.items():
        c = max(1, min(W - 2, int(gw_pos[0] / STORE_WIDTH * (W - 2)) + 1))
        r = max(1, min(H - 2, H - 2 - int(gw_pos[1] / STORE_HEIGHT * (H - 2))))
        label = gw_id[-1]  # A, B, C
        grid[r][c] = label

    # User
    uc = max(1, min(W - 2, int(pos[0] / STORE_WIDTH * (W - 2)) + 1))
    ur = max(1, min(H - 2, H - 2 - int(pos[1] / STORE_HEIGHT * (H - 2))))
    grid[ur][uc] = '◉'

    print('\033[2J\033[H', end='')  # clear screen
    print('  ╔══ Store Simulator ══╗')
    for row in grid:
        print('  ' + ''.join(row))
    print(f'  User: ({pos[0]:.1f}, {pos[1]:.1f}) m')


# ── Static mode ────────────────────────────────────────────────────────

async def run_static_mode(session_id: str, pos: tuple[float, float],
                          interval: float, backend_url: str, quiet: bool,
                          gateways: dict | None = None):
    """Posts fixed RSSI readings forever from a single position."""
    import httpx

    active_gateways = gateways or GATEWAY_POSITIONS

    async with httpx.AsyncClient(base_url=backend_url, timeout=5) as client:
        print(f'\n  Broadcasting static position {pos} … (Ctrl+C to stop)\n')
        step = 0
        while True:
            readings = generate_rssi_readings(pos, session_id, active_gateways)
            if not quiet:
                rssi_str = '  '.join(f'{r["gateway_id"][-1]}:{r["rssi"]:+.0f}dBm' for r in readings)
                print(f'  [{step}] pos={pos}  {rssi_str}')
            for reading in readings:
                try:
                    await client.post('/api/ble/reading', json=reading)
                except Exception:
                    pass
            step += 1
            await asyncio.sleep(interval)


# ── HTTP mode (no MQTT) ────────────────────────────────────────────────

async def run_http_mode(session_id: str, path: list[tuple[float, float]],
                        interval: float, backend_url: str, quiet: bool,
                        gateways: dict | None = None):
    """
    Posts BLE readings to the backend API and sends IMU via WebSocket.
    This simulates both the ESP32s and the phone at once.
    """
    import httpx
    import websockets  # type: ignore

    active_gateways = gateways or GATEWAY_POSITIONS
    state = SimState(x=path[0][0], y=path[0][1])
    steps = interpolate_path(path)

    # Connect WebSocket for IMU
    ws_url = backend_url.replace('http', 'ws') + f'/ws/track/{session_id}'
    ws = None
    try:
        ws = await websockets.connect(ws_url)
        print(f'  ✔ WebSocket connected: {ws_url}')
    except Exception as e:
        print(f'  ⚠ WebSocket failed ({e}) – will use HTTP only')

    async with httpx.AsyncClient(base_url=backend_url, timeout=5) as client:
        print(f'\n  Simulating {len(steps)} steps … (Ctrl+C to stop)\n')

        for i, pos in enumerate(steps):
            prev = (state.x, state.y)
            state.x, state.y = pos
            state.heading = heading_between(prev, pos) if distance(prev, pos) > 0.01 else state.heading
            state.step_count = 1 if distance(prev, pos) > 0.3 else 0
            state.total_steps += state.step_count

            # 1. Generate & post BLE RSSI (simulates selected ESP32 gateways)
            readings = generate_rssi_readings(pos, session_id, active_gateways)

            if not quiet:
                print_store_map(pos, active_gateways)
                rssi_str = '  '.join(f'{r["gateway_id"][-1]}:{r["rssi"]:+.0f}dBm' for r in readings)
                print(f'  Step {i+1}/{len(steps)}  heading={state.heading:.0f}°  {rssi_str}')

            # Post each reading (simulates selected ESP32s sending data)
            for reading in readings:
                try:
                    await client.post('/api/ble/reading', json=reading)
                except Exception:
                    pass  # backend may not have this endpoint yet

            # 2. Send IMU via WebSocket (simulates phone)
            if ws:
                try:
                    imu = generate_imu_data(state)
                    await ws.send(json.dumps(imu))
                    # Read position response
                    resp = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    if not quiet:
                        data = json.loads(resp)
                        print(f'  → Fused position: ({data.get("x", "?")}, {data.get("y", "?")}) ±{data.get("accuracy", "?")}m')
                except Exception:
                    pass

            await asyncio.sleep(interval)

    if ws:
        await ws.close()

    print(f'\n  ✔ Simulation complete – {state.total_steps} steps taken')


# ── MQTT mode ──────────────────────────────────────────────────────────

async def run_mqtt_mode(session_id: str, path: list[tuple[float, float]],
                        interval: float, broker_host: str, broker_port: int,
                        quiet: bool, backend_url: str = "http://localhost:8000",
                        gateways: dict | None = None):
    """
    Publishes RSSI to MQTT broker (like real ESP32 gateways).
    Also sends IMU via WebSocket (like the phone).
    """
    try:
        import aiomqtt  # type: ignore[import-untyped]
    except ImportError:
        print('  ✗ aiomqtt not installed. Run: pip install aiomqtt')
        sys.exit(1)

    import websockets  # type: ignore

    active_gateways = gateways or GATEWAY_POSITIONS
    state = SimState(x=path[0][0], y=path[0][1])
    steps = interpolate_path(path)

    # Connect WebSocket for IMU (just like the phone app does)
    ws_url = backend_url.replace('http', 'ws') + f'/ws/track/{session_id}'
    ws = None
    try:
        ws = await websockets.connect(ws_url)
        print(f'  ✔ WebSocket connected: {ws_url}')
    except Exception as e:
        print(f'  ⚠ WebSocket failed ({e}) – MQTT-only, no fused position feedback')

    async with aiomqtt.Client(hostname=broker_host, port=broker_port) as mqtt:
        print(f'  ✔ MQTT connected: {broker_host}:{broker_port}')
        print(f'  Simulating {len(steps)} steps … (Ctrl+C to stop)\n')

        for i, pos in enumerate(steps):
            prev = (state.x, state.y)
            state.x, state.y = pos
            state.heading = heading_between(prev, pos) if distance(prev, pos) > 0.01 else state.heading
            state.step_count = 1 if distance(prev, pos) > 0.3 else 0
            state.total_steps += state.step_count

            readings = generate_rssi_readings(pos, session_id, active_gateways)

            if not quiet:
                print_store_map(pos, active_gateways)
                rssi_str = '  '.join(f'{r["gateway_id"][-1]}:{r["rssi"]:+.0f}dBm' for r in readings)
                print(f'  Step {i+1}/{len(steps)}  heading={state.heading:.0f}°  {rssi_str}')

            # Publish each gateway reading to MQTT (simulates ESP32 gateways)
            for reading in readings:
                await mqtt.publish(
                    "ire/ble/rssi",
                    payload=json.dumps(reading).encode(),
                )

            # Send IMU via WebSocket (simulates the phone)
            if ws:
                try:
                    imu = generate_imu_data(state)
                    await ws.send(json.dumps(imu))
                    resp = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    if not quiet:
                        data = json.loads(resp)
                        print(f'  → Fused position: ({data.get("x", "?")}, {data.get("y", "?")}) ±{data.get("accuracy", "?")}m')
                except Exception:
                    pass

            await asyncio.sleep(interval)

    if ws:
        await ws.close()

    print(f'\n  ✔ Simulation complete – {state.total_steps} steps')


# ── BLE reading REST endpoint (add to backend if missing) ─────────────

BLE_ENDPOINT_CODE = '''
# Add this to backend/app/routers/tracking.py (or a new router):

@router.post("/api/ble/reading")
async def post_ble_reading(reading: BLEReading):
    """Accept a BLE RSSI reading (from ESP32 or simulator)."""
    from ..services.mqtt_client import get_ble_buffer
    buf = get_ble_buffer()
    if reading.session_id not in buf:
        buf[reading.session_id] = {}
    buf[reading.session_id][reading.gateway_id] = reading.rssi
    return {"status": "ok"}
'''


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='ESP32 + Phone Simulator for the Intelligent Retail Ecosystem',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
examples:
  python simulator.py                          # HTTP mode, default path
  python simulator.py --mqtt                   # publish via MQTT
  python simulator.py --speed 0.3 --quiet      # fast, no map display
  python simulator.py --session my-phone-123   # custom session ID
  python simulator.py --loop                   # repeat path forever
        ''',
    )
    parser.add_argument('--mqtt', action='store_true',
                        help='Use MQTT mode (publishes to broker like real ESP32s)')
    parser.add_argument('--broker', default='localhost',
                        help='MQTT broker host (default: localhost)')
    parser.add_argument('--broker-port', type=int, default=1883,
                        help='MQTT broker port (default: 1883)')
    parser.add_argument('--backend', default='http://localhost:8000',
                        help='Backend URL for HTTP mode (default: http://localhost:8000)')
    parser.add_argument('--session', default=f'sim-{random.randint(1000,9999)}',
                        help='BLE session ID (default: random)')
    parser.add_argument('--speed', type=float, default=0.8,
                        help='Seconds between steps (default: 0.8)')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress the ASCII map display')
    parser.add_argument('--loop', action='store_true',
                        help='Loop the path indefinitely')
    parser.add_argument('--static', nargs=2, type=float, metavar=('X', 'Y'),
                        help='Broadcast a fixed RSSI from position X Y forever (e.g. --static 5 4)')
    parser.add_argument('--gateways', nargs='+', metavar='GW',
                        help='Only simulate these gateways (e.g. --gateways esp32_C)')
    args = parser.parse_args()

    path = DEFAULT_PATH

    if args.gateways:
        unknown = [g for g in args.gateways if g not in GATEWAY_POSITIONS]
        if unknown:
            print(f'  ✗ Unknown gateway(s): {", ".join(unknown)}')
            print(f'    Valid options: {", ".join(GATEWAY_POSITIONS.keys())}')
            sys.exit(1)
        active_gateways = {g: GATEWAY_POSITIONS[g] for g in args.gateways}
    else:
        active_gateways = None  # all gateways

    print('═' * 54)
    print('  Intelligent Retail Ecosystem – Simulator')
    print('═' * 54)
    print(f'  Mode:       {"MQTT" if args.mqtt else "HTTP"}')
    print(f'  Session ID: {args.session}')
    print(f'  Step delay: {args.speed}s')
    gw_names = ", ".join(active_gateways.keys()) if active_gateways else ", ".join(GATEWAY_POSITIONS.keys())
    print(f'  Gateways:   {gw_names}')
    print(f'  Path:       {len(path)} waypoints → {len(interpolate_path(path))} steps')
    print('─' * 54)

    try:
        if args.static:
            static_pos = tuple(args.static)
            print(f'  Static pos: {static_pos}')
            print('─' * 54)
            asyncio.run(run_static_mode(
                args.session, static_pos, args.speed,
                args.backend, args.quiet,
                gateways=active_gateways,
            ))
        while True:
            if args.mqtt:
                asyncio.run(run_mqtt_mode(
                    args.session, path, args.speed,
                    args.broker, args.broker_port, args.quiet,
                    backend_url=args.backend,
                    gateways=active_gateways,
                ))
            else:
                asyncio.run(run_http_mode(
                    args.session, path, args.speed,
                    args.backend, args.quiet,
                    gateways=active_gateways,
                ))
            if not args.loop:
                break
            print('\n  ↻ Looping path …\n')
    except KeyboardInterrupt:
        print('\n  Stopped.')


if __name__ == '__main__':
    main()
