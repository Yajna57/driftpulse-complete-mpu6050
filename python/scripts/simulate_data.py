from __future__ import annotations

import argparse
import random
import time
from datetime import datetime

import requests


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DriftPulse software-only simulator")
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--user", default="USER001")
    p.add_argument("--seconds", type=int, default=180)
    p.add_argument("--drift-after", type=int, default=100)
    return p.parse_args()


def n(base: float, spread: float) -> float:
    return random.gauss(base, spread)


def main() -> None:
    args = parse_args()
    url = f"{args.api.rstrip('/')}/api/v1/readings"

    for second in range(args.seconds):
        drift = args.drift_after >= 0 and second >= args.drift_after

        if drift:
            hr, rmssd, sdnn, temp = n(89, 1.2), n(24, 2), n(30, 2), n(37.0, .04)
        else:
            hr, rmssd, sdnn, temp = n(69, 1.0), n(47, 2), n(52, 2.5), n(36.45, .03)

        payload = {
            "user_id": args.user,
            "device_id": "SIMULATOR",
            "captured_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "arduino_ms": second * 1000,
            "heart_rate_bpm": hr,
            "temperature_c": temp,
            "ecg_raw": int(n(520, 15)),
            "ecg_lead_off": False,
            "ppg_ir": int(n(73000, 900)),
            "ppg_red": int(n(61000, 700)),
            "accel_x_ms2": n(0.05, .02),
            "accel_y_ms2": n(-0.10, .02),
            "accel_z_ms2": n(9.78, .04),
            "gyro_x_rads": n(0.01, .01),
            "gyro_y_rads": n(0.01, .01),
            "gyro_z_rads": n(0.01, .01),
            "activity": "RESTING",
            "hrv": {
                "mean_rr_ms": 60000.0 / hr,
                "rmssd_ms": rmssd,
                "sdnn_ms": sdnn,
                "pnn50_percent": max(0.0, n(22 if not drift else 8, 2)),
                "ecg_heart_rate_bpm": hr,
                "peak_count": 30,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            hs = response.json()["health_status"]
            print(f"{second:03d}s | {hs['status']:<11} risk={hs['risk_score']:3d} HR={hr:5.1f} RMSSD={rmssd:5.1f}")
        except requests.RequestException as exc:
            print("Request failed:", exc)
            return

        time.sleep(1)


if __name__ == "__main__":
    main()
