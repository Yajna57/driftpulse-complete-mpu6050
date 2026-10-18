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


def sensor_status(
    latest: dict[str, Any],
    ppg_available: bool,
    mpu_available: bool,
    temperature_valid: bool,
    arduino_messages: list[str],
) -> dict[str, dict[str, str]]:
    """Plain-language per-sensor health for the dashboard."""

    def reported_missing(name: str) -> bool:
        return any(name in message for message in arduino_messages)

    i2c_stuck = reported_missing("I2C_BUS_STUCK_LOW")
    i2c_stuck_detail = "I2C bus stuck LOW: SDA/SCL shorted to GND or a module has no power"

    if ppg_available and latest["max30102_ir"] >= 50000:
        max_status = {"state": "OK", "detail": f"IR {latest['max30102_ir']}"}
    elif ppg_available:
        max_status = {"state": "NO_CONTACT", "detail": f"IR {latest['max30102_ir']} < 50000; place finger on sensor"}
    else:
        max_status = {
            "state": "NOT_DETECTED",
            "detail": i2c_stuck_detail if i2c_stuck
            else "Arduino reported MAX30102 not found" if reported_missing("MAX30102")
            else "IR/Red are 0; check SDA(A4)/SCL(A5)/power",
        }

    if latest["ecg_lead_off"]:
        ecg_status = {"state": "LEADS_OFF", "detail": "LO+/LO- high; check electrodes and D8/D9 wiring"}
    else:
        ecg_status = {"state": "OK", "detail": f"raw {latest['ecg_raw']}"}

    if temperature_valid:
        temp_status = {"state": "OK", "detail": f"{latest['temperature_c']:.2f} C"}
    else:
        temp_status = {
            "state": "OUT_OF_RANGE",
            "detail": f"reads {latest['temperature_c']:.1f} C; check LM35 OUT->A1, VCC->5V, GND",
        }

    if mpu_available:
        mpu_status = {"state": "OK", "detail": f"az {latest['accel_z_ms2']:.2f} m/s2"}
    else:
        mpu_status = {
            "state": "NOT_DETECTED",
            "detail": i2c_stuck_detail if i2c_stuck
            else "Arduino reported MPU6050 not found" if reported_missing("MPU6050")
            else "all axes 0; check SDA(A4)/SCL(A5)/power",
        }

    return {"MAX30102": max_status, "AD8232": ecg_status, "LM35": temp_status, "MPU6050": mpu_status}


def post_summary(api_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{api_url.rstrip('/')}/api/v1/readings",
        json=payload,
        timeout=2,
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
    # Raw ECG since the last summary, sent for the live waveform (None = leads off).
    ecg_since_send: list[int | None] = []
    arduino_messages: list[str] = []
    activity = ActivityEstimator(sample_window=max(int(args.sample_rate * 2), 1))

    print(f"Connecting to {args.port} @ {args.baud} ...")
    ser = serial.Serial(args.port, args.baud, timeout=1)
    # Opening the port resets the Arduino. Start reading immediately (no flush)
    # so ERROR:/WARN: sensor messages and the CSV header are not discarded.

    print(f"Raw CSV: {raw_log}")
    print(f"API:     {args.api}")
    print("Press Ctrl+C to stop.\n")

    header_seen = False
    last_send = 0.0
    last_input_at = time.monotonic()
    last_row_at = last_input_at
    last_diagnostic_at = last_input_at
    last_flush_at = last_input_at
    last_line = "(no serial data received)"
    invalid_lines_reported = 0

    with raw_log.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pc_timestamp", *EXPECTED_COLUMNS])
        handle.flush()

        try:
            while True:
                raw = ser.readline()
                if not raw:
                    now = time.monotonic()
                    if now - last_input_at >= 5 and now - last_diagnostic_at >= 5:
                        print(
                            f"No serial data received from {args.port}; check the selected COM port, "
                            "uploaded sketch, and baud rate.",
                            file=sys.stderr,
                        )
                        last_diagnostic_at = now
                    continue

                last_input_at = time.monotonic()
                line = raw.decode("utf-8", errors="ignore").strip()
                last_line = line[:160]
                if not line:
                    continue
                if line.startswith("INFO:"):
                    print(f"Arduino: {line}")
                    if line == "INFO:DRIFTPULSE_BOOT":
                        arduino_messages.clear()
                    continue
                if line.startswith(("ERROR:", "WARN:")):
                    print(f"Arduino: {line}", file=sys.stderr)
                    if line not in arduino_messages:
                        arduino_messages.append(line)
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
                    if invalid_lines_reported < 3:
                        print(f"Skipping unexpected serial line: {last_line!r}", file=sys.stderr)
                        invalid_lines_reported += 1
                    continue

                string_row = dict(zip(EXPECTED_COLUMNS, values, strict=True))
                try:
                    latest = parse_row(string_row)
                except (TypeError, ValueError):
                    if invalid_lines_reported < 3:
                        print(f"Skipping non-numeric sensor row: {last_line!r}", file=sys.stderr)
                        invalid_lines_reported += 1
                    continue

                last_row_at = time.monotonic()
                timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
                writer.writerow([timestamp, *values])
                if last_row_at - last_flush_at >= 1:
                    handle.flush()
                    last_flush_at = last_row_at

                if latest["ecg_lead_off"]:
                    ecg_buffer.clear()
                    ecg_since_send.append(None)
                else:
                    ecg_buffer.append(float(latest["ecg_raw"]))
                    ecg_since_send.append(latest["ecg_raw"])

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
                current_activity = (
                    activity.update(
                        latest["accel_x_ms2"],
                        latest["accel_y_ms2"],
                        latest["accel_z_ms2"],
                        latest["gyro_x_rads"],
                        latest["gyro_y_rads"],
                        latest["gyro_z_rads"],
                    )
                    if mpu_available
                    else "UNKNOWN"
                )

                now = time.monotonic()
                if now - last_send < args.send_every:
                    continue
                last_send = now

                hrv = calculate_hrv(list(ecg_buffer), args.sample_rate)
                ppg_hr = latest["heart_rate_bpm"] if latest["heart_rate_bpm"] > 0 else None
                heart_rate = hrv.ecg_heart_rate_bpm if hrv else ppg_hr
                ppg_available = latest["max30102_ir"] > 0 or latest["max30102_red"] > 0
                temperature_valid = 0.0 <= latest["temperature_c"] <= 60.0
                temperature_text = (
                    f"{latest['temperature_c']:.2f}C"
                    if temperature_valid
                    else f"INVALID({latest['temperature_c']:.2f}C)"
                )

                payload = {
                    "user_id": args.user,
                    "device_id": args.device,
                    "captured_at": timestamp,
                    "arduino_ms": latest["arduino_ms"],
                    "heart_rate_bpm": heart_rate,
                    "temperature_c": latest["temperature_c"] if temperature_valid else None,
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
                    "ecg_samples": ecg_since_send[-2000:],
                    "sample_rate_hz": args.sample_rate,
                    "sensor_status": sensor_status(
                        latest, ppg_available, mpu_available, temperature_valid, arduino_messages
                    ),
                    "arduino_messages": arduino_messages,
                }
                ecg_since_send = []

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

                bad = [
                    f"{name}:{info['state']}"
                    for name, info in payload["sensor_status"].items()
                    if info["state"] != "OK"
                ]
                print(
                    f"{timestamp} | HR={heart_rate or 0:.1f} | Temp={temperature_text} | "
                    f"Activity={current_activity} | {hrv_text} | {health_text}"
                    + (f" | CHECK {' '.join(bad)}" if bad else "")
                )

        except KeyboardInterrupt:
            print("\nStopping collector...")
        finally:
            ser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
