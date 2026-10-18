"""Simulated DriftPulse scenarios (cases 1-8) and the per-user signal generator.

Each case is a list of phases. Every run starts with a calibration phase so the
backend can learn the personal baseline (BASELINE_MIN_SAMPLES = 60 readings).
Phase values are relative to the user's own baseline profile, so the same case
looks different (but equivalent) for each user.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.activity import ActivityEstimator

SENSORS = ("AD8232", "MAX30102", "LM35", "MPU6050")


@dataclass(frozen=True)
class Profile:
    user_id: str
    label: str
    hr: float      # resting heart rate, bpm
    rmssd: float   # ms
    sdnn: float    # ms
    temp: float    # C at the LM35 placement


PROFILES = (
    Profile("USER001", "Young active adult", hr=64, rmssd=55, sdnn=60, temp=36.50),
    Profile("USER002", "Middle-aged adult", hr=76, rmssd=32, sdnn=40, temp=36.70),
)


@dataclass(frozen=True)
class Phase:
    name: str
    seconds: int
    hr: float = 1.0       # multiplier of the user's resting HR
    rmssd: float = 1.0    # multiplier of the user's RMSSD
    sdnn: float = 1.0     # multiplier of the user's SDNN
    temp: float = 0.0     # C added to the user's temperature
    ramp: int = 0         # seconds to move from the previous phase's values
    motion: str = "sit"   # sit | desk | lying | walk | run | spin | sway
    ecg: str = "normal"   # normal | noisy | infarct
    hr_noise: float = 1.2
    faults: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Case:
    number: int
    key: str
    title: str
    description: str
    expected: str
    phases: tuple[Phase, ...]


CALIBRATION = Phase("calibration", 70)


def _f(*names: str) -> frozenset[str]:
    return frozenset(names)


CASES: dict[int, Case] = {
    1: Case(
        1, "normal", "Normal user: seated rest",
        "Seated at rest. All four sensors work; values stay close to the personal baseline.",
        "CALIBRATING, then NORMAL with risk near 0 for the whole run.",
        (
            CALIBRATION,
            Phase("resting", 150),
        ),
    ),
    2: Case(
        2, "fever", "Temperature problem (fever)",
        "Temperature climbs about 1.9 C over 90 s and stays high. Heart rate rises with it "
        "(roughly 10 bpm per C) and HRV drops a little, as happens with a real fever.",
        "NORMAL, then OBSERVATION and ELEVATED while the fever rises, and ALERT on the plateau.",
        (
            CALIBRATION,
            Phase("normal", 30),
            Phase("fever rising", 90, hr=1.22, rmssd=0.75, sdnn=0.85, temp=1.9, ramp=90),
            Phase("fever plateau", 60, hr=1.22, rmssd=0.75, sdnn=0.85, temp=1.9),
        ),
    ),
    3: Case(
        3, "all-abnormal", "All vitals abnormal",
        "Heart rate up 40 %, RMSSD down 55 %, SDNN down 45 % and temperature up 1.3 C, at rest.",
        "Climbs through OBSERVATION and ELEVATED to ALERT; alerts are recorded.",
        (
            CALIBRATION,
            Phase("normal", 20),
            Phase("deteriorating", 40, hr=1.4, rmssd=0.45, sdnn=0.55, temp=1.3, ramp=40),
            Phase("all abnormal", 60, hr=1.4, rmssd=0.45, sdnn=0.55, temp=1.3),
        ),
    ),
    4: Case(
        4, "sensor-faults", "Each sensor reading wrong, one at a time",
        "Vitals stay normal, but each sensor fails in turn for 25 s: AD8232 leads off, "
        "MAX30102 no finger contact, LM35 out-of-range reading, MPU6050 not detected. Then all recover.",
        "Device panel chips turn red one at a time with the fault; status stays NORMAL because "
        "missing values are skipped, not scored.",
        (
            CALIBRATION,
            Phase("all sensors OK", 15),
            Phase("AD8232 leads off", 25, faults=_f("AD8232")),
            Phase("MAX30102 no finger", 25, faults=_f("MAX30102")),
            Phase("LM35 bad reading", 25, faults=_f("LM35")),
            Phase("MPU6050 not detected", 25, faults=_f("MPU6050")),
            Phase("all sensors OK", 20),
        ),
    ),
    5: Case(
        5, "running", "Running",
        "Warm-up walk, 90 s of running, then cool-down. Heart rate roughly doubles, HRV collapses, "
        "temperature rises 0.7 C and the ECG picks up motion noise. MPU6050 shows HIGH activity.",
        "Movement shows MODERATE (walk) and HIGH (run). The engine subtracts 20 points for HIGH activity, "
        "but the deviation is so large that status still reaches ALERT and stays there through cool-down.",
        (
            CALIBRATION,
            Phase("resting", 20),
            Phase("warm-up walk", 30, hr=1.35, rmssd=0.7, sdnn=0.8, temp=0.1, ramp=30, motion="walk", ecg="noisy"),
            Phase("running", 90, hr=2.05, rmssd=0.25, sdnn=0.35, temp=0.7, ramp=30, motion="run", ecg="noisy", hr_noise=2.5),
            Phase("cool-down walk", 40, hr=1.3, rmssd=0.6, sdnn=0.7, temp=0.4, ramp=40, motion="walk", ecg="noisy"),
        ),
    ),
    6: Case(
        6, "sleeping", "Sleeping",
        "User lies down and falls asleep: heart rate drops 18 %, HRV rises (RMSSD +40 %), "
        "skin temperature falls 0.3 C, and the MPU6050 shows a lying-down, motionless posture.",
        "Movement RESTING. Status moves to OBSERVATION (risk about 28) during sleep: low HR scores only "
        "a little, but drift detection is two-sided, so the sustained drop is still reported.",
        (
            CALIBRATION,
            Phase("awake in bed", 20, motion="lying"),
            Phase("falling asleep", 40, hr=0.82, rmssd=1.4, sdnn=1.3, temp=-0.3, ramp=40, motion="lying"),
            Phase("deep sleep", 120, hr=0.82, rmssd=1.4, sdnn=1.3, temp=-0.3, motion="lying", hr_noise=0.8),
        ),
    ),
    7: Case(
        7, "heart-attack", "Heart attack (myocardial infarction) pattern",
        "At rest, a sudden event: heart rate jumps 65 % with irregular beats, HRV collapses, "
        "and the live ECG shows ST-segment elevation and premature (wide) beats. No movement explains it.",
        "Goes to ALERT quickly with risk 75-100; alerts are recorded. Educational pattern only.",
        (
            CALIBRATION,
            Phase("resting", 30),
            Phase("onset", 20, hr=1.65, rmssd=0.3, sdnn=0.45, temp=0.15, ramp=20, ecg="infarct", hr_noise=6),
            Phase("acute event", 90, hr=1.65, rmssd=0.3, sdnn=0.45, temp=0.15, ecg="infarct", hr_noise=6),
        ),
    ),
    8: Case(
        8, "head-spin", "Head spin / dizziness",
        "The head spins rapidly (high gyroscope rotation) for 45 s, then the user sways while dizzy "
        "and slowly recovers. Heart rate rises 25 % and HRV drops during the episode.",
        "Gyroscope Z spikes and Movement shows HIGH, so the activity discount keeps status at ELEVATED "
        "while spinning. Swaying is only MODERATE, so status reaches ALERT; it returns to NORMAL after recovery.",
        (
            CALIBRATION,
            Phase("steady", 20),
            Phase("head spinning", 45, hr=1.25, rmssd=0.7, sdnn=0.8, ramp=10, motion="spin", ecg="noisy", hr_noise=2),
            Phase("dizzy, swaying", 60, hr=1.15, rmssd=0.75, sdnn=0.85, ramp=20, motion="sway"),
            Phase("recovered", 30, ramp=20),
        ),
    ),
    9: Case(
        9, "normal-desk", "Normal user: desk work",
        "Sitting at a desk reading and typing, with small hand and head movements visible on the MPU6050. "
        "Heart rate is up about 1 % and varies a little more than at rest; HRV and temperature stay at baseline.",
        "Movement stays RESTING (the small motions are below the activity thresholds) and status stays NORMAL; "
        "rarely, one random reading may flash OBSERVATION for a second.",
        (
            CALIBRATION,
            Phase("reading", 60, hr=1.005, motion="desk", hr_noise=1.3),
            Phase("typing", 90, hr=1.01, motion="desk", hr_noise=1.3, ramp=10),
            Phase("short pause", 30, motion="sit", ramp=10),
        ),
    ),
    10: Case(
        10, "normal-relaxed", "Normal user: relaxed breathing",
        "Calm, slow breathing while seated (for example, a short relaxation exercise). Heart rate "
        "eases down 1 % and is steadier, RMSSD and SDNN rise 2 %, temperature unchanged.",
        "Status stays NORMAL for the whole run.",
        (
            CALIBRATION,
            Phase("settling", 30),
            Phase("slow breathing", 120, hr=0.99, rmssd=1.02, sdnn=1.02, ramp=40, hr_noise=1.0),
            Phase("back to normal", 40, ramp=30),
        ),
    ),
}


def _motion_sample(kind: str, t: float) -> tuple[float, float, float, float, float, float]:
    g = random.gauss
    tau = 2 * math.pi
    if kind == "lying":
        return g(9.72, .02), g(.25, .02), g(.9, .02), g(0, .005), g(0, .005), g(0, .005)
    if kind == "desk":
        # Typing and small head turns: visible jitter, well below the MODERATE thresholds.
        return (g(.25, .12) + .1 * math.sin(tau * 3 * t), g(-.15, .1), g(9.78, .1),
                .08 * math.sin(tau * .3 * t) + g(0, .04), g(0, .05), .1 * math.sin(tau * .2 * t) + g(0, .03))
    if kind == "walk":
        return (.3 + 1.2 * math.sin(tau * 1.8 * t), g(-.1, .1), 9.8 + 2.0 * math.sin(tau * 3.6 * t),
                .4 * math.sin(tau * 1.8 * t), .3 * math.cos(tau * 1.8 * t), g(0, .1))
    if kind == "run":
        return (2.5 * math.sin(tau * 2.8 * t), 1.5 * math.sin(tau * 1.4 * t), 9.8 + 7.0 * math.sin(tau * 2.8 * t),
                1.6 * math.sin(tau * 2.8 * t), 1.0 * math.cos(tau * 1.4 * t), .6 * math.sin(tau * 1.4 * t))
    if kind == "spin":
        return (2.0 * math.sin(tau * .75 * t), 2.0 * math.cos(tau * .75 * t), g(9.8, .3),
                .6 * math.sin(tau * 1.3 * t), g(0, .2), 4.5 + 1.0 * math.sin(tau * .5 * t))
    if kind == "sway":
        return (.8 * math.sin(tau * .4 * t), .6 * math.cos(tau * .3 * t), g(9.78, .1),
                .6 * math.sin(tau * .4 * t), .5 * math.cos(tau * .3 * t), .3 * math.sin(tau * .2 * t))
    return g(.25, .03), g(-.15, .03), g(9.78, .03), g(0, .01), g(0, .01), g(0, .01)


def _bump(p: float, center: float, width: float) -> float:
    return math.exp(-((p - center) / width) ** 2)


class UserSimulator:
    """Generates one collector-style payload per simulated second for one user."""

    def __init__(self, profile: Profile, case: Case, skip_calibration: bool = False, sample_rate: int = 100):
        self.profile = profile
        self.case = case
        self.rate = sample_rate
        self.phases = tuple(p for p in case.phases if not (skip_calibration and p is CALIBRATION))
        self.activity = ActivityEstimator(sample_window=sample_rate * 2)
        self.t = 0.0
        self.beat_phase = 0.0
        self.beat_hr = profile.hr
        self.beat_kind = "normal"

    @property
    def total_seconds(self) -> int:
        return sum(p.seconds for p in self.phases)

    def _ecg_second(self, hr: float, style: str) -> list[int]:
        out = []
        for i in range(self.rate):
            t = self.t + i / self.rate
            self.beat_phase += (self.beat_hr / 60.0) / self.rate
            if self.beat_phase >= 1.0:
                self.beat_phase -= 1.0
                if style == "infarct":
                    self.beat_hr = hr * random.uniform(0.75, 1.3)
                    self.beat_kind = "pvc" if random.random() < 0.15 else "normal"
                else:
                    self.beat_hr = hr * random.uniform(0.97, 1.03)
                    self.beat_kind = "normal"
            p = self.beat_phase
            v = 512.0
            if self.beat_kind == "pvc":
                # Premature ventricular beat: no P wave, wide tall QRS, inverted T.
                v += 300 * _bump(p, 0.30, 0.035) - 90 * _bump(p, 0.40, 0.03) - 70 * _bump(p, 0.62, 0.07)
            else:
                v += 25 * _bump(p, 0.15, 0.025) - 30 * _bump(p, 0.27, 0.008)
                v += 260 * _bump(p, 0.30, 0.010) - 60 * _bump(p, 0.33, 0.010) + 55 * _bump(p, 0.55, 0.05)
                if style == "infarct":
                    # ST elevation: the segment between S and T stays raised.
                    v += 70 / (1 + math.exp(-(p - 0.345) * 120)) / (1 + math.exp((p - 0.6) * 60))
            if style == "noisy":
                v += 30 * math.sin(2 * math.pi * 0.6 * t) + random.gauss(0, 14)
            out.append(int(v + random.gauss(0, 4)))
        return out

    def run(self):
        """Yield (elapsed_s, phase_name, payload) for every simulated second."""
        prof = self.profile
        prev = {"hr": 1.0, "rmssd": 1.0, "sdnn": 1.0, "temp": 0.0}
        elapsed = 0
        for phase in self.phases:
            target = {"hr": phase.hr, "rmssd": phase.rmssd, "sdnn": phase.sdnn, "temp": phase.temp}
            for k in range(phase.seconds):
                frac = min(1.0, (k + 1) / phase.ramp) if phase.ramp else 1.0
                cur = {key: prev[key] + (target[key] - prev[key]) * frac for key in target}

                hr = max(35.0, prof.hr * cur["hr"] + random.gauss(0, phase.hr_noise))
                rmssd = max(4.0, prof.rmssd * cur["rmssd"] + random.gauss(0, 2.0))
                sdnn = max(5.0, prof.sdnn * cur["sdnn"] + random.gauss(0, 2.5))
                temp = prof.temp + cur["temp"] + random.gauss(0, 0.03)

                yield elapsed, phase.name, self._payload(phase, hr, rmssd, sdnn, temp)
                elapsed += 1
                self.t += 1.0
            prev = target

    def _payload(self, phase: Phase, hr: float, rmssd: float, sdnn: float, temp: float) -> dict[str, Any]:
        faults = phase.faults
        ecg_samples: list[int | None] = self._ecg_second(hr, phase.ecg)

        last_motion = (0.0,) * 6
        for i in range(self.rate):
            last_motion = _motion_sample(phase.motion, self.t + i / self.rate)
            if "MPU6050" not in faults:
                activity = self.activity.update(*last_motion)
        if "MPU6050" in faults:
            activity = "UNKNOWN"

        status: dict[str, dict[str, str]] = {}
        messages: list[str] = []

        if "AD8232" in faults:
            ecg_samples = [None] * self.rate
            hrv = None
            ecg_raw = 335
            status["AD8232"] = {"state": "LEADS_OFF", "detail": "LO+/LO- high; check electrodes and D8/D9 wiring"}
        else:
            hrv = {
                "mean_rr_ms": round(60000.0 / hr, 2),
                "rmssd_ms": round(rmssd, 2),
                "sdnn_ms": round(sdnn, 2),
                "pnn50_percent": round(max(0.0, min(90.0, (rmssd - 18) * 0.9 + random.gauss(0, 2))), 2),
                "ecg_heart_rate_bpm": round(hr, 2),
                "peak_count": int(hr),
            }
            ecg_raw = ecg_samples[-1]
            status["AD8232"] = {"state": "OK", "detail": f"raw {ecg_raw}"}

        if "MAX30102" in faults:
            ppg_ir, ppg_red, ppg_hr = int(random.gauss(14000, 600)), int(random.gauss(11000, 500)), None
            status["MAX30102"] = {"state": "NO_CONTACT", "detail": f"IR {ppg_ir} < 50000; place finger on sensor"}
        else:
            ppg_ir, ppg_red = int(random.gauss(96000, 900)), int(random.gauss(81000, 700))
            ppg_hr = hr + random.gauss(0, 1.5)
            status["MAX30102"] = {"state": "OK", "detail": f"IR {ppg_ir}"}

        if "LM35" in faults:
            bad = random.gauss(163.5, 0.6)
            temp_out = None
            status["LM35"] = {"state": "OUT_OF_RANGE", "detail": f"reads {bad:.1f} C; check LM35 OUT->A1, VCC->5V, GND"}
        else:
            temp_out = round(temp, 2)
            status["LM35"] = {"state": "OK", "detail": f"{temp_out:.2f} C"}

        if "MPU6050" in faults:
            motion: list[float | None] = [None] * 6
            messages.append("ERROR:MPU6050_NOT_FOUND")
            status["MPU6050"] = {"state": "NOT_DETECTED", "detail": "Arduino reported MPU6050 not found"}
        else:
            motion = [round(v, 3) for v in last_motion]
            status["MPU6050"] = {"state": "OK", "detail": f"az {last_motion[2]:.2f} m/s2"}

        heart_rate = hrv["ecg_heart_rate_bpm"] if hrv else (round(ppg_hr, 1) if ppg_hr else None)

        return {
            "user_id": self.profile.user_id,
            "device_id": f"SIM-CASE{self.case.number}",
            "captured_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "arduino_ms": int(self.t * 1000),
            "heart_rate_bpm": heart_rate,
            "temperature_c": temp_out,
            "ecg_raw": ecg_raw,
            "ecg_lead_off": "AD8232" in faults,
            "ppg_ir": ppg_ir,
            "ppg_red": ppg_red,
            "accel_x_ms2": motion[0],
            "accel_y_ms2": motion[1],
            "accel_z_ms2": motion[2],
            "gyro_x_rads": motion[3],
            "gyro_y_rads": motion[4],
            "gyro_z_rads": motion[5],
            "activity": activity,
            "hrv": hrv,
            "ecg_samples": ecg_samples,
            "sample_rate_hz": self.rate,
            "sensor_status": status,
            "arduino_messages": messages,
        }
