from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    device_id: Mapped[str] = mapped_column(String(64), default="ARDUINO001")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    arduino_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heart_rate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    ecg_raw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ecg_lead_off: Mapped[bool] = mapped_column(Boolean, default=False)
    ppg_ir: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ppg_red: Mapped[int | None] = mapped_column(Integer, nullable=True)

    accel_x_ms2: Mapped[float | None] = mapped_column(Float, nullable=True)
    accel_y_ms2: Mapped[float | None] = mapped_column(Float, nullable=True)
    accel_z_ms2: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyro_x_rads: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyro_y_rads: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyro_z_rads: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity: Mapped[str] = mapped_column(String(32), default="UNKNOWN")

    mean_rr_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmssd_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    sdnn_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnn50_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    ecg_heart_rate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)


Index("ix_sensor_user_captured", SensorReading.user_id, SensorReading.captured_at.desc())


class BaselineMetric(Base):
    __tablename__ = "baseline_metrics"
    __table_args__ = (UniqueConstraint("user_id", "metric", name="uq_baseline_user_metric"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    metric: Mapped[str] = mapped_column(String(64), index=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    mean: Mapped[float] = mapped_column(Float, default=0.0)
    m2: Mapped[float] = mapped_column(Float, default=0.0)
    std: Mapped[float] = mapped_column(Float, default=0.0)
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DriftState(Base):
    __tablename__ = "drift_states"
    __table_args__ = (UniqueConstraint("user_id", "metric", name="uq_drift_user_metric"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    metric: Mapped[str] = mapped_column(String(64), index=True)
    ewma: Mapped[float] = mapped_column(Float, default=0.0)
    cusum_positive: Mapped[float] = mapped_column(Float, default=0.0)
    cusum_negative: Mapped[float] = mapped_column(Float, default=0.0)
    drift_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class HealthAnalysis(Base):
    __tablename__ = "health_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    reading_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    status: Mapped[str] = mapped_column(String(32))
    risk_score: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(512))
    observations: Mapped[list] = mapped_column(JSON, default=list)
    z_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    drift: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_ready: Mapped[bool] = mapped_column(Boolean, default=False)


Index("ix_analysis_user_created", HealthAnalysis.user_id, HealthAnalysis.created_at.desc())


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    severity: Mapped[str] = mapped_column(String(32))
    alert_type: Mapped[str] = mapped_column(String(64), default="PHYSIOLOGICAL_DRIFT")
    message: Mapped[str] = mapped_column(String(512))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
