"""
Alerts & Outbreak Early Warning Router.
Manages actionable surveillance alerts and enforces DHO review workflows.
"""

from typing import Optional, List
from datetime import datetime
import re
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models.alert import Alert
from backend.models.surveillance import WeeklySurveillance
from backend.models.user import User
from backend.schemas.alert import (
    AlertItem, AlertQueueResponse, AcknowledgeAlertRequest, AcknowledgeAlertResponse
)
from backend.security import get_current_user, require_role

router = APIRouter(prefix="/api/alerts", tags=["Early Warnings & Alerts"])


@router.get("/queue", response_model=AlertQueueResponse)
def get_alert_queue(
    disease: Optional[str] = Query(None),
    district_pcode: Optional[str] = Query(None),
    alert_level: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns filtered queue of early warning alerts for public health officers.
    Includes live badge counts for Priority Review, Watch, and Acknowledged items.
    """
    query = db.query(Alert)

    if isinstance(disease, str) and disease.strip():
        query = query.filter(Alert.disease == disease.strip().capitalize())
    if isinstance(district_pcode, str) and district_pcode.strip():
        query = query.filter(Alert.district_pcode == district_pcode.strip().upper())
    if isinstance(alert_level, str) and alert_level.strip():
        query = query.filter(Alert.alert_level == alert_level.strip().lower())
    if acknowledged is not None and isinstance(acknowledged, bool):
        query = query.filter(Alert.acknowledged == acknowledged)

    alerts = query.order_by(desc(Alert.created_at)).all()

    # Compute breakdown counts
    active_warnings = sum(1 for a in alerts if not a.acknowledged and a.alert_level in ["priority_review", "watch"])
    priority_count = sum(1 for a in alerts if a.alert_level == "priority_review" and not a.acknowledged)
    watch_count = sum(1 for a in alerts if a.alert_level == "watch" and not a.acknowledged)
    ack_count = sum(1 for a in alerts if a.acknowledged)

    alert_items = []
    for a in alerts:
        d_name = a.district.name if a.district else "District"
        d_div = a.district.division if a.district else "Division"

        # Look up cases from surveillance or extract from details
        surv = db.query(WeeklySurveillance).filter(
            WeeklySurveillance.district_pcode == a.district_pcode,
            WeeklySurveillance.disease == a.disease,
            WeeklySurveillance.year == a.year,
            WeeklySurveillance.epi_week == a.epi_week
        ).first()
        cases_obs = float(surv.total_cases) if (surv and surv.total_cases is not None) else None
        if cases_obs is None and a.details:
            m = re.search(r"(\d+)\s+cases", a.details)
            if m:
                cases_obs = float(m.group(1))

        base_mean = round(cases_obs / max(1.0 + (a.ears_c1_score or 0.0), 0.5), 1) if cases_obs is not None else None

        alert_items.append(AlertItem(
            id=a.id,
            district_pcode=a.district_pcode,
            district_name=d_name,
            division=d_div,
            disease=a.disease,
            year=a.year,
            epi_week=a.epi_week,
            alert_level=a.alert_level,
            composite_score=a.composite_score,
            ears_c1_score=a.ears_c1_score,
            ears_c2_score=a.ears_c2_score,
            ears_c3_score=a.ears_c3_score,
            forecast_breach=a.forecast_breach,
            incidence_per_100k=a.incidence_per_100k,
            headline=a.headline,
            details=a.details,
            acknowledged=a.acknowledged,
            acknowledged_by=a.acknowledged_by,
            acknowledged_at=a.acknowledged_at,
            review_notes=a.review_notes,
            created_at=a.created_at or datetime.utcnow(),
            cases_observed=cases_obs,
            baseline_mean=base_mean
        ))

    return AlertQueueResponse(
        total_active_warnings=active_warnings,
        priority_review_count=priority_count,
        watch_count=watch_count,
        acknowledged_count=ack_count,
        alerts=alert_items
    )


@router.post("/{alert_id}/acknowledge", response_model=AcknowledgeAlertResponse)
def acknowledge_alert(
    alert_id: int,
    request: AcknowledgeAlertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["district_health_officer"]))
):
    """
    District Health Officer (DHO) Alert Acknowledgment Workflow.
    Restricted to 'district_health_officer' role. Records audit trail.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert ID {alert_id} not found."
        )

    alert.acknowledged = True
    alert.acknowledged_by = current_user.username
    alert.acknowledged_at = datetime.utcnow()
    alert.review_notes = request.review_notes

    db.commit()
    db.refresh(alert)

    return AcknowledgeAlertResponse(
        status="ACKNOWLEDGED",
        alert_id=alert.id,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        message=f"Alert #{alert.id} ({alert.disease} in {alert.district_pcode}) successfully reviewed by {current_user.username}."
    )


@router.get("/backtest")
def get_alert_backtest_metrics():
    """
    Returns historical alert backtesting performance metrics (Precision, Recall,
    False Alert Frequency, Lead Time) disaggregated for Malaria and Typhoid.
    """
    import json
    from backend.config import PROCESSED_DIR
    backtest_file = PROCESSED_DIR / "backtest_results.json"
    if backtest_file.exists():
        with open(backtest_file, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Backtest evaluation results not yet generated. Please run alert evaluation pipeline."
    )
