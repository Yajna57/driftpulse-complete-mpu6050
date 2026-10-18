"""DriftPulse software-only simulator.

    python -m scripts.simulate_data --list
    python -m scripts.simulate_data --case 7
    python -m scripts.simulate_data --case 5 --users USER002 --speed 4

See docs/SIMULATION.md for what each case does.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

from scripts.scenarios import CALIBRATION, CASES, PROFILES, Profile, UserSimulator

print_lock = threading.Lock()
stop_event = threading.Event()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DriftPulse scenario simulator (no hardware needed)")
    p.add_argument("--case", type=int, choices=sorted(CASES), help="scenario number, see --list")
    p.add_argument("--list", action="store_true", help="list all cases and exit")
    p.add_argument("--users", default=",".join(pr.user_id for pr in PROFILES),
                   help="comma-separated user IDs, run in parallel (default: USER001,USER002)")
    p.add_argument("--speed", type=float, default=1.0,
                   help="1 = real time (1 reading/s); 5 = five times faster")
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--no-reset", action="store_true",
                   help="keep the existing baseline; calibration is skipped if it is already learned")
    p.add_argument("--no-save", action="store_true", help="do not write the per-run CSV")
    return p.parse_args()


def say(text: str) -> None:
    with print_lock:
        print(text, flush=True)


def list_cases() -> None:
    print("DriftPulse simulation cases\n")
    for case in CASES.values():
        seconds = sum(p.seconds for p in case.phases)
        print(f"  {case.number}. {case.title}  ({seconds} s at --speed 1)")
        print(f"     {case.description}")
        print(f"     Expect: {case.expected}\n")
    print("Users:")
    for pr in PROFILES:
        print(f"  {pr.user_id}: {pr.label} (HR {pr.hr:.0f} bpm, RMSSD {pr.rmssd:.0f} ms, "
              f"SDNN {pr.sdnn:.0f} ms, {pr.temp:.2f} C)")
    print("\nRun one:  python -m scripts.simulate_data --case 3")


def profile_for(user_id: str, index: int) -> Profile:
    for pr in PROFILES:
        if pr.user_id == user_id:
            return pr
    return dataclasses.replace(PROFILES[index % len(PROFILES)], user_id=user_id)


def baseline_ready(api: str, user_id: str) -> bool:
    try:
        r = requests.get(f"{api}/api/v1/users/{user_id}/baseline", timeout=5)
        r.raise_for_status()
        return all(m["ready"] for m in r.json()["metrics"].values())
    except requests.RequestException:
        return False


def run_user(args: argparse.Namespace, profile: Profile, case_no: int, csv_dir: Path | None) -> None:
    api = args.api.rstrip("/")
    case = CASES[case_no]
    uid = profile.user_id

    skip_cal = False
    if args.no_reset:
        skip_cal = baseline_ready(api, uid)
    else:
        try:
            requests.post(f"{api}/api/v1/users/{uid}/reset-baseline", timeout=5).raise_for_status()
        except requests.RequestException as exc:
            say(f"[{uid}] Cannot reach the backend at {api}: {exc}")
            stop_event.set()
            return

    sim = UserSimulator(profile, case, skip_calibration=skip_cal)
    total = sim.total_seconds
    say(f"[{uid}] {profile.label}: case {case.number} '{case.title}', {total} readings"
        + (" (baseline kept, calibration skipped)" if skip_cal else f" (first {CALIBRATION.seconds} = calibration)"))

    writer = handle = None
    if csv_dir is not None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = csv_dir / f"case{case.number}_{case.key}_{uid}_{stamp}.csv"
        handle = path.open("w", newline="", encoding="utf-8")
        writer = csv.writer(handle)
        writer.writerow(["captured_at", "elapsed_s", "phase", "heart_rate_bpm", "rmssd_ms", "sdnn_ms",
                         "temperature_c", "activity", "ecg_lead_off", "ppg_ir", "accel_z_ms2", "gyro_z_rads",
                         "status", "risk_score"])
        say(f"[{uid}] CSV: {path}")

    interval = 1.0 / max(args.speed, 0.01)
    start = time.monotonic()
    last_phase = None
    try:
        for elapsed, phase_name, payload in sim.run():
            if stop_event.is_set():
                break
            delay = start + elapsed * interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)

            try:
                r = requests.post(f"{api}/api/v1/readings", json=payload, timeout=5)
                r.raise_for_status()
                hs = r.json()["health_status"]
                status, risk = hs["status"], hs["risk_score"]
            except requests.RequestException as exc:
                say(f"[{uid}] Request failed: {exc}")
                stop_event.set()
                break

            hrv = payload["hrv"] or {}
            if writer:
                writer.writerow([payload["captured_at"], elapsed, phase_name, payload["heart_rate_bpm"],
                                 hrv.get("rmssd_ms"), hrv.get("sdnn_ms"), payload["temperature_c"],
                                 payload["activity"], int(payload["ecg_lead_off"]), payload["ppg_ir"],
                                 payload["accel_z_ms2"], payload["gyro_z_rads"], status, risk])

            if phase_name != last_phase:
                say(f"[{uid}] --- phase: {phase_name} ---")
                last_phase = phase_name

            hr = payload["heart_rate_bpm"]
            temp = payload["temperature_c"]
            bad = [name for name, s in payload["sensor_status"].items() if s["state"] != "OK"]
            say(
                f"[{uid}] {elapsed:03d}/{total}s | HR {hr if hr is None else f'{hr:5.1f}'} "
                f"RMSSD {hrv.get('rmssd_ms', '  -  ')} Temp {temp if temp is None else f'{temp:.2f}'} | "
                f"{payload['activity']:<8} | {status:<11} risk {risk:3d}"
                + (f" | FAULT {' '.join(bad)}" if bad else "")
            )
    finally:
        if handle:
            handle.close()
    say(f"[{uid}] case {case.number} finished.")


def main() -> int:
    args = parse_args()
    if args.list:
        list_cases()
        return 0
    if args.case is None:
        print("Choose a case with --case N (1-8). See all cases with --list.", file=sys.stderr)
        return 2

    users = [u.strip() for u in args.users.split(",") if u.strip()]
    csv_dir = None
    if not args.no_save:
        csv_dir = Path(__file__).resolve().parents[1] / "local_logs" / "simulated"
        csv_dir.mkdir(parents=True, exist_ok=True)

    case = CASES[args.case]
    print(f"Case {case.number}: {case.title}\n{case.description}\nExpect: {case.expected}\n"
          f"Dashboard: http://localhost:5173 (pick the user in the User dropdown). Ctrl+C to stop.\n")

    threads = [
        threading.Thread(target=run_user, args=(args, profile_for(uid, i), args.case, csv_dir), daemon=True)
        for i, uid in enumerate(users)
    ]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.2)
    except KeyboardInterrupt:
        stop_event.set()
        print("\nStopping simulator...")
        for t in threads:
            t.join(timeout=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
