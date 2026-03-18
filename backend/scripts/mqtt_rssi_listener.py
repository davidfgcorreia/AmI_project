#!/usr/bin/env python3
"""
Simple MQTT RSSI listener that filters by session_id and logs values.

Usage example:
  python backend/scripts/mqtt_rssi_listener.py \
    --host 192.168.100.222 --port 1883 --topic ire/ble/rssi \
    --session "A32 de David" --out backend/logs/ble_rssi_filtered.csv

The script subscribes to the MQTT topic, parses JSON payloads (strips trailing
semicolons if present), and for messages where `session_id` matches the filter
it prints and appends a timestamped row to the CSV file. It also maintains an
exponential moving average (EMA) per gateway and prints that for quick tuning.
"""

import argparse
import csv
import json
import os
import signal
import sys
import time
from collections import defaultdict

import paho.mqtt.client as mqtt


def ensure_out_file(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "gateway_id", "session_id", "rssi"])


class RSSIListener:
    def __init__(self, host, port, topic, session_filter, out_csv, ema_alpha=0.2):
        self.host = host
        self.port = port
        self.topic = topic
        self.session_filter = session_filter
        self.out_csv = out_csv
        self.ema_alpha = ema_alpha
        self.client = mqtt.Client()
        self.ema = {}  # gateway_id -> ema value
        self.running = True
        self.forward_topic = None

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT broker {self.host}:{self.port}")
            client.subscribe(self.topic)
            print(f"Subscribed to topic '{self.topic}'")
        else:
            print("Failed to connect, rc=", rc)

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="ignore").strip()
        # Some publishers may append a semicolon; strip it
        if payload.endswith(";"):
            payload = payload[:-1]

        try:
            data = json.loads(payload)
        except Exception:
            print("Received non-JSON payload:", payload)
            return

        session_id = data.get("session_id")
        if session_id != self.session_filter:
            return

        gateway = data.get("gateway_id", "")
        rssi = data.get("rssi")
        try:
            rssi = float(rssi)
        except Exception:
            print("Invalid RSSI value:", data.get("rssi"))
            return

        ts = time.time()
        # update EMA
        if gateway not in self.ema:
            self.ema[gateway] = rssi
        else:
            self.ema[gateway] = self.ema_alpha * rssi + (1 - self.ema_alpha) * self.ema[gateway]

        # append to CSV
        try:
            with open(self.out_csv, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([ts, gateway, session_id, rssi])
        except Exception as e:
            print("Failed to write CSV:", e)

        print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))} | {gateway} | rssi={rssi} | ema={self.ema[gateway]:.2f}")
        # optional forward to simulator topic
        if self.forward_topic:
            try:
                self.client.publish(self.forward_topic, json.dumps({
                    "gateway_id": gateway,
                    "session_id": session_id,
                    "rssi": rssi,
                }))
            except Exception:
                pass

    def start(self):
        ensure_out_file(self.out_csv)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        try:
            self.client.connect(self.host, self.port, keepalive=60)
        except Exception as e:
            print("Failed to connect to broker:", e)
            sys.exit(1)

        def _signal(_, __):
            print("Shutting down...")
            self.running = False
            try:
                self.client.disconnect()
            except Exception:
                pass

        signal.signal(signal.SIGINT, _signal)
        signal.signal(signal.SIGTERM, _signal)

        # Blocking network loop; will exit when self.running becomes False
        try:
            while self.running:
                # loop(timeout) processes network events and returns quickly
                self.client.loop(timeout=1.0)
        except Exception as e:
            print("MQTT loop error:", e)


def parse_args():
    p = argparse.ArgumentParser(description="MQTT RSSI listener (filter by session_id)")
    p.add_argument("--host", default="192.168.100.222", help="MQTT broker host")
    p.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    p.add_argument("--topic", default="ire/ble/rssi", help="MQTT topic to subscribe")
    p.add_argument("--session", required=False, default="A32 de David", help="Session ID to filter")
    p.add_argument("--out", default="backend/logs/ble_rssi_filtered.csv", help="CSV output file")
    p.add_argument("--ema-alpha", type=float, default=0.2, help="EMA alpha (0-1) for smoothing")
    p.add_argument("--forward", action="store_true", help="Republish filtered messages to simulator topic simulator/ble/rssi")
    p.add_argument("--sim-topic", default="simulator/ble/rssi", help="Topic to republish filtered messages to when --forward is used")
    return p.parse_args()


def main():
    args = parse_args()
    listener = RSSIListener(args.host, args.port, args.topic, args.session, args.out, args.ema_alpha)
    if getattr(args, "forward", False):
        listener.forward_topic = args.sim_topic
    listener.start()


if __name__ == "__main__":
    main()
