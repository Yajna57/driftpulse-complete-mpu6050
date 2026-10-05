from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import serial

from core.activity import ActivityEstimator
from core.hrv import calculate_hrv

EXPECTED_COLUMNS = [
    "arduino_ms",
    "max30102_ir",
    "max30102_red",
    "heart_rate_bpm",
    "ecg_raw",
    "ecg_lead_off",
    "temperature_c",
    "accel_x_ms2",
    "accel_y_ms2",
    "accel_z_ms2",
    "gyro_x_rads",
    "gyro_y_rads",
    "gyro_z_rads",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DriftPulse Arduino USB collector")
    parser.add_argument("--port", required=True, help="COM3, /dev/ttyACM0, etc.")
    parser.add_argument("--user", default="USER001")
    parser.add_argument("--device", default="ARDUINO001")
    parser.add_argument("--baud", type=int, default=230400)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--sample-rate", type=float, default=100.0)
    parser.add_argument("--send-every", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def parse_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "arduino_ms": int(float(row["arduino_ms"])),
        "max30102_ir": int(float(row["max30102_ir"])),
        "max30102_red": int(float(row["max30102_red"])),
        "heart_rate_bpm": float(row["heart_rate_bpm"]),
        "ecg_raw": int(float(row["ecg_raw"])),
        "ecg_lead_off": bool(int(float(row["ecg_lead_off"]))),
        "temperature_c": float(row["temperature_c"]),
        "accel_x_ms2": float(row["accel_x_ms2"]),
        "accel_y_ms2": float(row["accel_y_ms2"]),
        "accel_z_ms2": float(row["accel_z_ms2"]),
        "gyro_x_rads": float(row["gyro_x_rads"]),
        "gyro_y_rads": float(row["gyro_y_rads"]),
        "gyro_z_rads": float(row["gyro_z_rads"]),
    }


def post_summary(api_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{api_url.rstrip('/')}/api/v1/readings",
        json=payload,
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    args = parse_args()

    log_dir = Path(__file__).resolve().parents[1] / "local_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    raw_log = log_dir / f"raw_sensor_{args.user}_{stamp}.csv"

    ecg_buffer: deque[float] = deque(maxlen=int(args.sample_rate * 60))
    activity = ActivityEstimator(sample_window=max(int(args.sample_rate * 2), 1))

    print(f"Connecting to {args.port} @ {args.baud} ...")
    ser = serial.Serial(args.port, args.baud, timeout=1)
    time.sleep(2.0)
    ser.reset_input_buffer()

    print(f"Raw CSV: {raw_log}")
    print(f"API:     {args.api}")
    print("Press Ctrl+C to stop.\n")

    header_seen = False
    last_send = 0.0
    rows_since_flush = 0

    with raw_log.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pc_timestamp", *EXPECTED_COLUMNS])

        try:
            while True:
                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                if line.startswith(("ERROR:", "WARN:")):
                    print(f"Arduino: {line}", file=sys.stderr)
                    continue

                if line.startswith("arduino_ms,"):
                    actual = line.split(",")
                    if actual != EXPECTED_COLUMNS:
                        print("Arduino header mismatch.", file=sys.stderr)
                        print("Expected:", EXPECTED_COLUMNS, file=sys.stderr)
                        print("Actual:  ", actual, file=sys.stderr)
                    header_seen = True
                    continue

                if not header_seen and line.count(",") != len(EXPECTED_COLUMNS) - 1:
                    continue
                header_seen = True

                values = line.split(",")
                if len(values) != len(EXPECTED_COLUMNS):
                    continue

                string_row = dict(zip(EXPECTED_COLUMNS, values, strict=True))
                try:
                    latest = parse_row(string_row)
                except (TypeError, ValueError):
                    continue

                timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
                writer.writerow([timestamp, *values])
                rows_since_flush += 1
                if rows_since_flush >= 100:
                    handle.flush()
                    rows_since_flush = 0

                if not latest["ecg_lead_off"]:
                    ecg_buffer.append(float(latest["ecg_raw"]))

                current_activity = activity.update(
                    latest["accel_x_ms2"],
                    latest["accel_y_ms2"],
                    latest["accel_z_ms2"],
                    latest["gyro_x_rads"],
                    latest["gyro_y_rads"],
                    latest["gyro_z_rads"],
                )

                now = time.monotonic()
                if now - last_send < args.send_every:
                    continue
                last_send = now

                hrv = calculate_hrv(list(ecg_buffer), args.sample_rate)
                ppg_hr = latest["heart_rate_bpm"] if latest["heart_rate_bpm"] > 0 else None
                heart_rate = hrv.ecg_heart_rate_bpm if hrv else ppg_hr
                ppg_available = latest["max30102_ir"] > 0 or latest["max30102_red"] > 0
                mpu_available = any(
                    latest[field] != 0.0
                    for field in (
                        "accel_x_ms2",
                        "accel_y_ms2",
                        "accel_z_ms2",
                        "gyro_x_rads",
                        "gyro_y_rads",
                        "gyro_z_rads",
                    )
                )

                payload = {
                    "user_id": args.user,
                    "device_id": args.device,
                    "captured_at": timestamp,
                    "arduino_ms": latest["arduino_ms"],
                    "heart_rate_bpm": heart_rate,
                    "temperature_c": latest["temperature_c"],
                    "ecg_raw": latest["ecg_raw"],
                    "ecg_lead_off": latest["ecg_lead_off"],
                    "ppg_ir": latest["max30102_ir"] if ppg_available else None,
                    "ppg_red": latest["max30102_red"] if ppg_available else None,
                    "accel_x_ms2": latest["accel_x_ms2"] if mpu_available else None,
                    "accel_y_ms2": latest["accel_y_ms2"] if mpu_available else None,
                    "accel_z_ms2": latest["accel_z_ms2"] if mpu_available else None,
                    "gyro_x_rads": latest["gyro_x_rads"] if mpu_available else None,
                    "gyro_y_rads": latest["gyro_y_rads"] if mpu_available else None,
                    "gyro_z_rads": latest["gyro_z_rads"] if mpu_available else None,
                    "activity": current_activity,
                    "hrv": hrv.as_dict() if hrv else None,
                }

                health_text = "dry-run"
                if not args.dry_run:
                    try:
                        result = post_summary(args.api, payload)
                        hs = result.get("health_status", {})
                        health_text = f"{hs.get('status', '?')} risk={hs.get('risk_score', '?')}"
                    except requests.RequestException as exc:
                        health_text = f"API ERROR: {exc}"

                hrv_text = "HRV warming up"
                if hrv:
                    hrv_text = f"RMSSD={hrv.rmssd_ms:.1f} SDNN={hrv.sdnn_ms:.1f}"

                print(
                    f"{timestamp} | HR={heart_rate or 0:.1f} | Temp={latest['temperature_c']:.2f}C | "
                    f"Activity={current_activity} | {hrv_text} | {health_text}"
                )

        except KeyboardInterrupt:
            print("\nStopping collector...")
        finally:
            ser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
