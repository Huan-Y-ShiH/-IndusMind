"""
IoT Data Simulator for IndusMind.

Generates realistic sensor data for 200 wind turbines across 4 wind farms
and pushes readings to Module A's prediction API (via Module C gateway).

Usage:
    python simulator.py                              # push every 5s
    python simulator.py --interval 2 --target http://localhost:8003
"""

import argparse
import json
import math
import random
import time
from datetime import datetime, timezone

import requests
import yaml


# ── Load config ──────────────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Sensor data generation ───────────────────────────────────────────

class SensorGenerator:
    """Generate realistic sensor readings for a wind turbine."""

    def __init__(self, device_id: str, seed: int | None = None):
        self.device_id = device_id
        self.seed = seed or hash(device_id) % 10000
        random.seed(self.seed)
        self._t = 0  # time step counter

    def next_reading(self) -> dict:
        """Produce one SensorReading snapshot with 21 fields."""
        self._t += 1
        t_factor = self._t * 0.05  # slow drift over time
        noise = lambda scale: random.gauss(0, scale)  # noqa: E731

        reading = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vibration_x": _clamp(0.08 + 0.04 * math.sin(t_factor) + noise(0.03), 0, 5),
            "vibration_y": _clamp(0.06 + 0.03 * math.sin(t_factor + 1) + noise(0.03), 0, 5),
            "vibration_z": _clamp(0.04 + 0.02 * math.sin(t_factor + 2) + noise(0.02), 0, 5),
            "temperature": _clamp(62 + 8 * math.sin(t_factor * 0.3) + noise(2), 20, 120),
            "rpm": _clamp(1480 + 30 * math.sin(t_factor * 0.2) + noise(10), 0, 3000),
            "pressure": _clamp(2.35 + 0.3 * math.sin(t_factor * 0.15) + noise(0.05), 0, 10),
            "flow_rate": _clamp(12.0 + 1.5 * math.sin(t_factor * 0.25) + noise(0.3), 0, 50),
            "current": _clamp(4.5 + 0.5 * math.sin(t_factor * 0.2) + noise(0.1), 0, 20),
            "voltage": _clamp(380 + noise(0.5), 350, 420),
            "power": _clamp(1.7 + 0.2 * math.sin(t_factor * 0.2) + noise(0.05), 0, 10),
            "noise_level": _clamp(72 + 10 * math.sin(t_factor * 0.1) + noise(2), 40, 130),
            "humidity": _clamp(45 + 10 * math.sin(t_factor * 0.05) + noise(2), 0, 100),
            "oil_temperature": _clamp(52 + 6 * math.sin(t_factor * 0.3) + noise(1), 30, 100),
            "bearing_temperature": _clamp(58 + 8 * math.sin(t_factor * 0.3) + noise(1.5), 30, 120),
            "displacement_x": _clamp(0.001 + 0.002 * math.sin(t_factor) + noise(0.0005), 0, 0.05),
            "displacement_y": _clamp(0.002 + 0.002 * math.sin(t_factor + 1) + noise(0.0005), 0, 0.05),
            "displacement_z": _clamp(0.001 + 0.002 * math.sin(t_factor + 2) + noise(0.0005), 0, 0.05),
            "torque": _clamp(11 + 1.5 * math.sin(t_factor * 0.2) + noise(0.3), 0, 30),
            "load": _clamp(0.65 + 0.15 * math.sin(t_factor * 0.2) + noise(0.03), 0, 1),
            "status_code": 0,
            "phase_current_l1": _clamp(4.5 + 0.3 * math.sin(t_factor * 0.2) + noise(0.08), 0, 20),
            "phase_current_l2": _clamp(4.5 + 0.3 * math.sin(t_factor * 0.2 + 2) + noise(0.08), 0, 20),
            "phase_current_l3": _clamp(4.5 + 0.3 * math.sin(t_factor * 0.2 + 4) + noise(0.08), 0, 20),
        }

        # Occasionally inject anomalies for ~3% of devices
        if random.random() < 0.03:
            reading["vibration_x"] *= random.uniform(2, 5)
            reading["vibration_y"] *= random.uniform(2, 5)
            reading["vibration_z"] *= random.uniform(2, 5)
            reading["temperature"] += random.uniform(10, 30)
            reading["bearing_temperature"] += random.uniform(10, 25)
            reading["noise_level"] += random.uniform(15, 35)
            reading["status_code"] = 1

        return reading


def _clamp(val: float, lo: float, hi: float) -> float:
    return round(max(lo, min(hi, val)), 4)


# ── Main loop ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="IndusMind IoT Simulator")
    parser.add_argument(
        "--interval", type=float, default=5.0,
        help="Push interval in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--target", type=str, default="http://localhost:8003",
        help="Gateway URL (default: http://localhost:8003)",
    )
    parser.add_argument(
        "--config", type=str, default="config.yaml",
        help="Path to config file",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    devices = config.get("devices", [])

    # Create sensor generators per device
    generators: dict[str, SensorGenerator] = {}
    for device in devices:
        dev_id = device["id"]
        generators[dev_id] = SensorGenerator(dev_id)

    print(f"[Simulator] Loaded {len(generators)} devices from config")
    print(f"[Simulator] Target: {args.target}")
    print(f"[Simulator] Interval: {args.interval}s")
    print("[Simulator] Starting data push...")

    session = requests.Session()
    anomaly_endpoint = f"{args.target}/api/v1/predict/anomaly"

    while True:
        for dev_id, gen in generators.items():
            reading = gen.next_reading()
            payload = {
                "device_id": dev_id,
                "sensor_data": reading,
            }
            try:
                resp = session.post(
                    anomaly_endpoint,
                    json=payload,
                    timeout=10,
                )
                if resp.status_code != 200:
                    print(f"[WARN] {dev_id}: HTTP {resp.status_code}")
            except requests.RequestException as e:
                print(f"[ERROR] {dev_id}: {e}")

        print(f"[Simulator] Pushed {len(generators)} readings, sleeping {args.interval}s...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
