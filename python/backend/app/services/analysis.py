from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Alert, BaselineMetric, DriftState, HealthAnalysis, SensorReading

settings = get_settings()

# MPU6050 is context, not a baseline health metric. No GSR is used.
STD_FLOOR = {
    "heart_rate_bpm": 2.0,
    "rmssd_ms": 3.0,
    "sdnn_ms": 3.0,
    "temperature_c": 0.10,
}
REQUIRED_BASELINE_METRICS = tuple(STD_FLOOR.keys())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def reading_metric_values(reading: SensorReading) -> dict[str, float | None]:
    return {
        "heart_rate_bpm": reading.heart_rate_bpm,
        "rmssd_ms": reading.rmssd_ms,
        "sdnn_ms": reading.sdnn_ms,
        "temperature_c": reading.temperature_c,
    }


def _get_or_create_baseline(db: Session, user_id: str, metric: str) -> BaselineMetric:
    row = db.scalar(
        select(BaselineMetric).where(
            BaselineMetric.user_id == user_id,
            BaselineMetric.metric == metric,
        )
    )
    if row is None:
        row = BaselineMetric(user_id=user_id, metric=metric)
        db.add(row)
        db.flush()
    return row


def update_baseline(db: Session, user_id: str, metric: str, value: float) -> BaselineMetric:
    row = _get_or_create_baseline(db, user_id, metric)
    if row.ready:
        return row

    n = row.sample_count + 1
    delta = value - row.mean
    new_mean = row.mean + delta / n
    delta2 = value - new_mean
    new_m2 = row.m2 + delta * delta2

    row.sample_count = n
    row.mean = new_mean
    row.m2 = new_m2
    row.std = math.sqrt(new_m2 / (n - 1)) if n > 1 else 0.0
    row.ready = n >= settings.baseline_min_samples
    row.updated_at = utc_now()
    db.flush()
    return row


def get_baselines(db: Session, user_id: str) -> dict[str, BaselineMetric]:
    rows = db.scalars(select(BaselineMetric).where(BaselineMetric.user_id == user_id)).all()
    return {row.metric: row for row in rows}


def all_required_baselines_ready(rows: dict[str, BaselineMetric]) -> bool:
    return all(metric in rows and rows[metric].ready for metric in REQUIRED_BASELINE_METRICS)


def z_score(metric: str, value: float, baseline: BaselineMetric) -> float:
    std = max(float(baseline.std), STD_FLOOR.get(metric, 1.0))
    return (value - float(baseline.mean)) / std


def _get_or_create_drift_state(db: Session, user_id: str, metric: str) -> DriftState:
    row = db.scalar(
        select(DriftState).where(
            DriftState.user_id == user_id,
            DriftState.metric == metric,
        )
    )
    if row is None:
        row = DriftState(user_id=user_id, metric=metric)
        db.add(row)
        db.flush()
    return row


def update_drift(db: Session, user_id: str, metric: str, normalized_value: float) -> DriftState:
    row = _get_or_create_drift_state(db, user_id, metric)

    a = settings.ewma_alpha
    row.ewma = a * normalized_value + (1.0 - a) * row.ewma
    row.cusum_positive = max(0.0, row.cusum_positive + normalized_value - settings.cusum_k)
    row.cusum_negative = min(0.0, row.cusum_negative + normalized_value + settings.cusum_k)
    row.drift_detected = (
        abs(row.ewma) >= 2.0
        or row.cusum_positive >= settings.cusum_h
        or abs(row.cusum_negative) >= settings.cusum_h
    )
    row.updated_at = utc_now()
    db.flush()
    return row


def classify_risk(
    z_scores: dict[str, float | None],
    drift_states: dict[str, DriftState],
    activity: str,
) -> tuple[int, str, str, list[str]]:
    score = 0
    observations: list[str] = []

    hr_z = z_scores.get("heart_rate_bpm")
    rmssd_z = z_scores.get("rmssd_ms")
    sdnn_z = z_scores.get("sdnn_ms")
    temp_z = z_scores.get("temperature_c")

    if hr_z is not None and hr_z >= 2.0:
        score += 25
        observations.append("Heart rate is elevated relative to the personalized baseline.")
    elif hr_z is not None and hr_z <= -2.0:
        score += 8
        observations.append("Heart rate is below the personalized baseline.")

    if rmssd_z is not None and rmssd_z <= -2.0:
        score += 30
        observations.append("RMSSD is lower than the personalized HRV baseline.")

    if sdnn_z is not None and sdnn_z <= -2.0:
        score += 10
        observations.append("SDNN is lower than the personalized HRV baseline.")

    if temp_z is not None and temp_z >= 2.0:
        score += 15
        observations.append("Temperature is elevated relative to the personalized baseline.")

    drifting = [name for name, row in drift_states.items() if row.drift_detected]
    if len(drifting) >= 2:
        score += 20
        observations.append("Sustained drift is present in multiple physiological metrics.")
    elif len(drifting) == 1:
        score += 5
        observations.append(f"Sustained drift is present in {drifting[0].replace('_', ' ')}.")

    activity = activity.upper()
    if activity == "HIGH":
        score -= 20
        observations.append("High physical activity was detected and may explain part of the change.")
    elif activity == "MODERATE":
        score -= 8
        observations.append("Moderate physical activity was detected and included as context.")

    score = max(0, min(100, score))

    if score <= 25:
        status = "NORMAL"
        summary = "Measurements are close to the established personalized baseline."
    elif score <= 50:
        status = "OBSERVATION"
        summary = "Minor physiological changes are being observed relative to baseline."
    elif score <= 75:
        status = "ELEVATED"
        summary = "A sustained physiological deviation from baseline was detected."
    else:
        status = "ALERT"
        summary = "Multiple sustained physiological deviations require attention and rechecking."

    if not observations:
        observations.append("No significant personalized-baseline deviation was detected in the current window.")

    return score, status, summary, observations


def _maybe_create_alert(db: Session, user_id: str, status: str, summary: str) -> None:
    if status not in {"ELEVATED", "ALERT"}:
        return

    cutoff = utc_now() - timedelta(minutes=5)
    existing = db.scalar(
        select(Alert)
        .where(
            Alert.user_id == user_id,
            Alert.severity == status,
            Alert.created_at >= cutoff,
        )
        .order_by(Alert.created_at.desc())
    )
    if existing is None:
        db.add(
            Alert(
                user_id=user_id,
                severity=status,
                alert_type="PHYSIOLOGICAL_DRIFT",
                message=summary,
            )
        )


def analyze_reading(db: Session, reading: SensorReading) -> HealthAnalysis:
    values = reading_metric_values(reading)

    for metric, value in values.items():
        if value is not None and math.isfinite(value):
            update_baseline(db, reading.user_id, metric, float(value))

    baselines = get_baselines(db, reading.user_id)
    ready = all_required_baselines_ready(baselines)

    if not ready:
        progress = {
            metric: {
                "samples": baselines[metric].sample_count if metric in baselines else 0,
                "required": settings.baseline_min_samples,
                "ready": baselines[metric].ready if metric in baselines else False,
            }
            for metric in REQUIRED_BASELINE_METRICS
        }
        analysis = HealthAnalysis(
            user_id=reading.user_id,
            reading_id=reading.id,
            status="CALIBRATING",
            risk_score=0,
            summary="Collecting personalized baseline data.",
            observations=["Keep sensors stable and minimize movement during initial baseline collection."],
            z_scores={},
            drift={"baseline_progress": progress},
            baseline_ready=False,
        )
        db.add(analysis)
        db.flush()
        return analysis

    z_scores: dict[str, float | None] = {}
    drift_states: dict[str, DriftState] = {}

    for metric, value in values.items():
        baseline = baselines.get(metric)
        if value is None or baseline is None or not baseline.ready:
            z_scores[metric] = None
            continue

        z = z_score(metric, float(value), baseline)
        z_scores[metric] = round(z, 4)
        drift_states[metric] = update_drift(db, reading.user_id, metric, z)

    risk_score, status, summary, observations = classify_risk(
        z_scores,
        drift_states,
        reading.activity,
    )

    drift_payload: dict[str, Any] = {
        metric: {
            "ewma": round(row.ewma, 4),
            "cusum_positive": round(row.cusum_positive, 4),
            "cusum_negative": round(row.cusum_negative, 4),
            "drift_detected": row.drift_detected,
        }
        for metric, row in drift_states.items()
    }

    analysis = HealthAnalysis(
        user_id=reading.user_id,
        reading_id=reading.id,
        status=status,
        risk_score=risk_score,
        summary=summary,
        observations=observations,
        z_scores=z_scores,
        drift=drift_payload,
        baseline_ready=True,
    )
    db.add(analysis)
    _maybe_create_alert(db, reading.user_id, status, summary)
    db.flush()
    return analysis


def reset_user_analysis(db: Session, user_id: str) -> None:
    db.execute(delete(BaselineMetric).where(BaselineMetric.user_id == user_id))
    db.execute(delete(DriftState).where(DriftState.user_id == user_id))
    db.execute(delete(HealthAnalysis).where(HealthAnalysis.user_id == user_id))
    db.execute(delete(Alert).where(Alert.user_id == user_id))
