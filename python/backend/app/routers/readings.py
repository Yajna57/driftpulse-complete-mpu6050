from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SensorReading
from ..schemas import IngestResponse, ReadingCreate, ReadingOut
from ..services.analysis import analyze_reading
from ..services.live import get_live, update_live

router = APIRouter(prefix="/api/v1", tags=["readings"])


@router.get("/users")
def users(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(SensorReading.user_id, func.max(SensorReading.captured_at).label("last_reading"))
        .group_by(SensorReading.user_id)
        .order_by(func.max(SensorReading.captured_at).desc())
    ).all()
    return [{"user_id": r.user_id, "last_reading": r.last_reading} for r in rows]


@router.get("/users/{user_id}/live")
def live(user_id: str) -> dict:
    return get_live(user_id)


@router.post("/readings", response_model=IngestResponse)
def create_reading(payload: ReadingCreate, db: Session = Depends(get_db)) -> IngestResponse:
    hrv = payload.hrv
    row = SensorReading(
        user_id=payload.user_id,
        device_id=payload.device_id,
        captured_at=payload.captured_at,
        arduino_ms=payload.arduino_ms,
        heart_rate_bpm=payload.heart_rate_bpm,
        temperature_c=payload.temperature_c,
        ecg_raw=payload.ecg_raw,
        ecg_lead_off=payload.ecg_lead_off,
        ppg_ir=payload.ppg_ir,
        ppg_red=payload.ppg_red,
        accel_x_ms2=payload.accel_x_ms2,
        accel_y_ms2=payload.accel_y_ms2,
        accel_z_ms2=payload.accel_z_ms2,
        gyro_x_rads=payload.gyro_x_rads,
        gyro_y_rads=payload.gyro_y_rads,
        gyro_z_rads=payload.gyro_z_rads,
        activity=payload.activity.upper(),
        mean_rr_ms=hrv.mean_rr_ms if hrv else None,
        rmssd_ms=hrv.rmssd_ms if hrv else None,
        sdnn_ms=hrv.sdnn_ms if hrv else None,
        pnn50_percent=hrv.pnn50_percent if hrv else None,
        ecg_heart_rate_bpm=hrv.ecg_heart_rate_bpm if hrv else None,
    )
    db.add(row)
    db.flush()

    analysis = analyze_reading(db, row)
    db.commit()

    update_live(
        payload.user_id,
        payload.device_id,
        payload.ecg_samples,
        payload.sample_rate_hz,
        payload.sensor_status,
        payload.arduino_messages,
    )

    return IngestResponse(
        reading_id=row.id,
        baseline_ready=analysis.baseline_ready,
        health_status={
            "status": analysis.status,
            "risk_score": analysis.risk_score,
            "summary": analysis.summary,
            "observations": analysis.observations,
            "z_scores": analysis.z_scores,
            "drift": analysis.drift,
            "baseline_ready": analysis.baseline_ready,
            "updated_at": analysis.created_at,
            "reading_id": row.id,
        },
    )


@router.get("/users/{user_id}/latest", response_model=ReadingOut)
def latest(user_id: str, db: Session = Depends(get_db)) -> ReadingOut:
    row = db.scalar(
        select(SensorReading)
        .where(SensorReading.user_id == user_id)
        .order_by(SensorReading.captured_at.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No readings found")
    return ReadingOut.model_validate(row)


@router.get("/users/{user_id}/history", response_model=list[ReadingOut])
def history(
    user_id: str,
    minutes: int = Query(default=60, ge=1, le=1440),
    limit: int = Query(default=300, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[ReadingOut]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    rows = list(db.scalars(
        select(SensorReading)
        .where(SensorReading.user_id == user_id, SensorReading.captured_at >= cutoff)
        .order_by(SensorReading.captured_at.desc())
        .limit(limit)
    ).all())
    rows.reverse()
    return [ReadingOut.model_validate(row) for row in rows]
