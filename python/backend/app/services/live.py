from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

# In-memory live view of each device: recent raw ECG samples and per-sensor status.
# This is display-only data and is intentionally not stored in PostgreSQL.
ECG_WINDOW_SAMPLES = 1000  # 10 s @ 100 Hz


@dataclass
class LiveState:
    device_id: str = ""
    last_seen: datetime | None = None
    sample_rate_hz: float = 100.0
    ecg_samples: deque[int | None] = field(default_factory=lambda: deque(maxlen=ECG_WINDOW_SAMPLES))
    sensor_status: dict[str, dict] = field(default_factory=dict)
    arduino_messages: list[str] = field(default_factory=list)


_lock = threading.Lock()
_states: dict[str, LiveState] = {}


def update_live(
    user_id: str,
    device_id: str,
    ecg_samples: list[int | None] | None,
    sample_rate_hz: float | None,
    sensor_status: dict[str, dict] | None,
    arduino_messages: list[str] | None,
) -> None:
    with _lock:
        state = _states.setdefault(user_id, LiveState())
        state.device_id = device_id
        state.last_seen = datetime.now(timezone.utc)
        if sample_rate_hz:
            state.sample_rate_hz = sample_rate_hz
        if ecg_samples:
            state.ecg_samples.extend(ecg_samples)
        if sensor_status is not None:
            state.sensor_status = sensor_status
        if arduino_messages is not None:
            state.arduino_messages = arduino_messages[-10:]


def get_live(user_id: str) -> dict:
    with _lock:
        state = _states.get(user_id)
        if state is None:
            return {
                "user_id": user_id,
                "connected": False,
                "device_id": None,
                "last_seen": None,
                "seconds_since_last": None,
                "sample_rate_hz": 100.0,
                "ecg_samples": [],
                "sensor_status": {},
                "arduino_messages": [],
            }
        age = (datetime.now(timezone.utc) - state.last_seen).total_seconds() if state.last_seen else None
        return {
            "user_id": user_id,
            "connected": age is not None and age <= 5.0,
            "device_id": state.device_id,
            "last_seen": state.last_seen,
            "seconds_since_last": round(age, 1) if age is not None else None,
            "sample_rate_hz": state.sample_rate_hz,
            "ecg_samples": list(state.ecg_samples),
            "sensor_status": state.sensor_status,
            "arduino_messages": state.arduino_messages,
        }
