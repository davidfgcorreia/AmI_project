#!/usr/bin/env python3
"""
Live MQTT listener for 2D RSSI analysis using 3 beacon receivers.

Input message format example:
  {"gateway_id":"esp32_B","session_id":"A32 de David","rssi":-89}

Behavior:
- Subscribes to an MQTT topic and only accepts session_id == "A32 de David".
- Uses terminal movement commands (w/a/s/d) to update real XY position in 1 m steps.
- Starts position next to esp32_A.
- Runs a terminal command listener: use w/a/s/d to move and 'q' to analyze+quit.

Generated graphs show distance vs RSSI correlation for each gateway and overall data.
"""

import argparse
import json
import math
import os
import signal
import sys
import threading
import time
import warnings
from dataclasses import dataclass
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import paho.mqtt.client as mqtt

SESSION_ID_FILTER = "A32 de David"

BEACON_POSITIONS: Dict[str, Tuple[float, float]] = {
    "esp32_A": (4, 1),
    "esp32_B": (0.5, 5),
    "esp32_C": (7.5, 4.5),
}


@dataclass
class Sample:
    timestamp: float
    gateway_id: str
    rssi: float
    distance_m: float
    x: float
    y: float


class XYPositionTracker:
    def __init__(
        self,
        host: str,
        port: int,
        topic: str,
        out_dir: str,
    ) -> None:
        self.host = host
        self.port = port
        self.topic = topic
        self.out_dir = out_dir

        self.client = mqtt.Client()
        self.running = True
        self.lock = threading.Lock()

        self.latest_rssi: Dict[str, float] = {}
        self.samples: List[Sample] = []

        # Start next to esp32_A as requested.
        self.current_position = [
            float(BEACON_POSITIONS["esp32_A"][0]),
            float(BEACON_POSITIONS["esp32_A"][1]),
        ]

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT broker {self.host}:{self.port}")
            client.subscribe(self.topic)
            print(f"Subscribed to topic '{self.topic}'")
            print(f"Filtering messages by session_id == '{SESSION_ID_FILTER}'")
        else:
            print(f"Failed to connect to MQTT broker, rc={rc}")

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="ignore").strip()
        if payload.endswith(";"):
            payload = payload[:-1]

        try:
            data = json.loads(payload)
        except Exception:
            print(f"Ignored non-JSON payload: {payload}")
            return

        session_id = data.get("session_id")
        if session_id != SESSION_ID_FILTER:
            return

        gateway_id = data.get("gateway_id")
        if gateway_id not in BEACON_POSITIONS:
            print(f"Ignored unknown gateway_id: {gateway_id}")
            return

        try:
            rssi = float(data.get("rssi"))
        except Exception:
            print(f"Ignored invalid RSSI value: {data.get('rssi')}")
            return

        with self.lock:
            self.latest_rssi[gateway_id] = rssi

            x, y = self.current_position
            bx, by = BEACON_POSITIONS[gateway_id]
            distance_m = math.hypot(x - bx, y - by)
            self.samples.append(
                Sample(
                    timestamp=time.time(),
                    gateway_id=gateway_id,
                    rssi=rssi,
                    distance_m=distance_m,
                    x=x,
                    y=y,
                )
            )

        print(
            f"{time.strftime('%H:%M:%S')} | {gateway_id:<7} | "
            f"rssi={rssi:6.1f} dBm | real_d={distance_m:6.2f} m | "
            f"real_pos=({x:5.2f}, {y:5.2f})"
        )

    def _move_position(self, cmd: str, step: float = 1.0) -> None:
        x, y = self.current_position
        if cmd == "w":
            y += step
        elif cmd == "s":
            y -= step
        elif cmd == "a":
            x -= step
        elif cmd == "d":
            x += step
        self.current_position = [x, y]

    def _terminal_listener(self) -> None:
        print("Terminal commands: w/a/s/d move 1 m, p prints position, q analyze+quit.")
        while self.running:
            try:
                cmd = input().strip().lower()
            except EOFError:
                break
            except KeyboardInterrupt:
                cmd = "q"

            if cmd == "q":
                print("Received 'q'. Generating graphs and exiting...")
                self.running = False
                try:
                    self.client.disconnect()
                except Exception:
                    pass
                break
            elif cmd in {"w", "a", "s", "d"}:
                with self.lock:
                    self._move_position(cmd, step=1.0)
                    x, y = self.current_position
                print(f"Moved to real position: ({x:.2f}, {y:.2f})")
            elif cmd == "p":
                with self.lock:
                    x, y = self.current_position
                    print(f"Current real position: ({x:.2f}, {y:.2f})")
                    print(f"Latest RSSI map: {self.latest_rssi}")
            elif cmd:
                print("Unknown command. Use w/a/s/d, p, or q.")

    def _setup_signals(self) -> None:
        def _handle_signal(_sig, _frame):
            print("Signal received. Stopping...")
            self.running = False
            try:
                self.client.disconnect()
            except Exception:
                pass

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def _generate_graphs(self) -> None:
        with self.lock:
            samples = list(self.samples)

        if not samples:
            print("No data collected. No graphs generated.")
            return

        os.makedirs(self.out_dir, exist_ok=True)

        by_gateway: Dict[str, List[Sample]] = {k: [] for k in BEACON_POSITIONS}
        for s in samples:
            by_gateway.setdefault(s.gateway_id, []).append(s)

        # Figure 1: Real distance vs RSSI scatter for each gateway.
        plt.figure(figsize=(10, 6))
        for gateway_id, entries in by_gateway.items():
            if not entries:
                continue
            distances = [e.distance_m for e in entries]
            rssis = [e.rssi for e in entries]
            plt.scatter(distances, rssis, s=24, alpha=0.75, label=gateway_id)

            if len(entries) >= 3:
                x_vals = np.array(distances, dtype=float)
                y_vals = np.array(rssis, dtype=float)

                valid = np.isfinite(x_vals) & np.isfinite(y_vals)
                x_vals = x_vals[valid]
                y_vals = y_vals[valid]

                # A line fit needs at least 3 valid points and non-constant x values.
                if x_vals.size >= 3 and np.unique(x_vals).size >= 2:
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("error", np.RankWarning)
                            coeff = np.polyfit(x_vals, y_vals, 1)
                        order = np.argsort(x_vals)
                        trend = np.poly1d(coeff)
                        plt.plot(x_vals[order], trend(x_vals[order]), linewidth=1.5)
                    except (np.linalg.LinAlgError, ValueError, FloatingPointError, np.RankWarning):
                        # Skip unstable fit without failing graph generation.
                        pass

        plt.title("Real Distance vs RSSI (session: A32 de David)")
        plt.xlabel("Real distance (m)")
        plt.ylabel("RSSI (dBm)")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()

        graph1 = os.path.join(self.out_dir, "distance_vs_rssi.png")
        plt.savefig(graph1, dpi=140)
        plt.close()

        # Figure 2: Real XY path and fixed beacon positions.
        plt.figure(figsize=(8, 6))
        path_x = [s.x for s in samples]
        path_y = [s.y for s in samples]
        plt.plot(path_x, path_y, "-o", markersize=3, linewidth=1, alpha=0.8, label="Real path")

        for gw, (bx, by) in BEACON_POSITIONS.items():
            plt.scatter([bx], [by], s=100, marker="^", label=f"{gw} beacon")
            plt.text(bx + 0.08, by + 0.08, gw)

        plt.title("Real XY Position Path (WASD Input)")
        plt.xlabel("X")
        plt.ylabel("Y")
        plt.axis("equal")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()

        graph2 = os.path.join(self.out_dir, "real_xy_path.png")
        plt.savefig(graph2, dpi=140)
        plt.close()

        print("Graphs generated:")
        print(f"- {graph1}")
        print(f"- {graph2}")

    def run(self) -> None:
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self._setup_signals()

        try:
            self.client.connect(self.host, self.port, keepalive=60)
        except Exception as exc:
            print(f"Failed to connect to broker: {exc}")
            sys.exit(1)

        terminal_thread = threading.Thread(target=self._terminal_listener, daemon=True)
        terminal_thread.start()

        try:
            while self.running:
                self.client.loop(timeout=1.0)
        except Exception as exc:
            print(f"MQTT loop error: {exc}")
        finally:
            self._generate_graphs()


def parse_args():
    parser = argparse.ArgumentParser(description="MQTT 2D position tracker for 3 beacons")
    parser.add_argument("--host", default="192.168.100.222", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--topic", default="ire/ble/rssi", help="MQTT topic to subscribe")
    parser.add_argument(
        "--out-dir",
        default="backend/logs",
        help="Directory where output graphs are saved",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tracker = XYPositionTracker(
        host=args.host,
        port=args.port,
        topic=args.topic,
        out_dir=args.out_dir,
    )
    tracker.run()


if __name__ == "__main__":
    main()
