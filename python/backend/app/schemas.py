from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HRVInput(BaseModel):
    mean_rr_ms: float
    rmssd_ms: float
    sdnn_ms: float
    pnn50_percent: float
    ecg_heart_rate_bpm: float
    peak_count: int | None = None


class ReadingCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    device_id: str = Field(default="ARDUINO001", max_length=64)
    captured_at: datetime
    arduino_ms: int | None = None

    heart_rate_bpm: float | None = None
    temperature_c: float | None = None
    ecg_raw: int | None = None
    ecg_lead_off: bool = False
    ppg_ir: int | None = None
    ppg_red: int | None = None

    accel_x_ms2: float | None = None
    accel_y_ms2: float | None = None
    accel_z_ms2: float | None = None
    gyro_x_rads: float | None = None
    gyro_y_rads: float | None = None
    gyro_z_rads: float | None = None
    activity: str = "UNKNOWN"

    hrv: HRVInput | None = None

    # Live display data (kept in memory only, not stored in the database).
    # ecg_samples: raw AD8232 values since the previous summary; null = leads off.
    ecg_samples: list[int | None] | None = Field(default=None, max_length=2000)
    sample_rate_hz: float | None = None
    # e.g. {"MAX30102": {"state": "OK", "detail": "..."}}
    sensor_status: dict[str, dict] | None = None
    arduino_messages: list[str] | None = None


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    device_id: str
    captured_at: datetime
    heart_rate_bpm: float | None
    temperature_c: float | None
    ecg_raw: int | None
    ecg_lead_off: bool
    ppg_ir: int | None
    ppg_red: int | None
    accel_x_ms2: float | None
    accel_y_ms2: float | None
    accel_z_ms2: float | None
    gyro_x_rads: float | None
    gyro_y_rads: float | None
    gyro_z_rads: float | None
    activity: str
    mean_rr_ms: float | None
    rmssd_ms: float | None
    sdnn_ms: float | None
    pnn50_percent: float | None
    ecg_heart_rate_bpm: float | None


class HealthStatusOut(BaseModel):
    status: str
    risk_score: int
    summary: str
    observations: list[str]
    z_scores: dict[str, float | None]
    drift: dict
    baseline_ready: bool
    updated_at: datetime | None = None
    reading_id: int | None = None


class IngestResponse(BaseModel):
    reading_id: int
    baseline_ready: bool
    health_status: HealthStatusOut
