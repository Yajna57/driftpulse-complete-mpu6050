from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Alert, BaselineMetric, HealthAnalysis
from ..schemas import HealthStatusOut
from ..services.analysis import REQUIRED_BASELINE_METRICS, reset_user_analysis

router = APIRouter(prefix="/api/v1", tags=["health"])
settings = get_settings()


@router.get("/users/{user_id}/health-status", response_model=HealthStatusOut)
def health_status(user_id: str, db: Session = Depends(get_db)) -> HealthStatusOut:
    row = db.scalar(
        select(HealthAnalysis)
        .where(HealthAnalysis.user_id == user_id)
        .order_by(HealthAnalysis.created_at.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No health analysis found")

    return HealthStatusOut(
        status=row.status,
        risk_score=row.risk_score,
        summary=row.summary,
        observations=row.observations,
        z_scores=row.z_scores,
        drift=row.drift,
        baseline_ready=row.baseline_ready,
        updated_at=row.created_at,
        reading_id=row.reading_id,
    )


@router.get("/users/{user_id}/baseline")
def baseline(user_id: str, db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(
        select(BaselineMetric).where(BaselineMetric.user_id == user_id)
    ).all()
    by_metric = {row.metric: row for row in rows}

    return {
        "user_id": user_id,
        "required_samples": settings.baseline_min_samples,
        "metrics": {
            metric: {
                "mean": round(by_metric[metric].mean, 4) if metric in by_metric else 0.0,
                "std": round(by_metric[metric].std, 4) if metric in by_metric else 0.0,
                "sample_count": by_metric[metric].sample_count if metric in by_metric else 0,
                "ready": by_metric[metric].ready if metric in by_metric else False,
            }
            for metric in REQUIRED_BASELINE_METRICS
        },
    }


@router.get("/users/{user_id}/alerts")
def alerts(user_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Alert)
        .where(Alert.user_id == user_id)
        .order_by(Alert.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": row.id,
            "severity": row.severity,
            "type": row.alert_type,
            "message": row.message,
            "created_at": row.created_at,
            "resolved": row.resolved,
        }
        for row in rows
    ]


@router.post("/users/{user_id}/reset-baseline")
def reset_baseline(user_id: str, db: Session = Depends(get_db)) -> dict:
    reset_user_analysis(db, user_id)
    db.commit()
    return {
        "user_id": user_id,
        "status": "reset",
        "message": "Baseline, drift state, analyses and alerts reset. Sensor-reading history was kept.",
    }
