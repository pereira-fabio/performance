from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, date
import numpy as np

from backend.app.core.database import get_db
from backend.app.models.models import DailyHealth, BestEffort, Activity
from backend.app.core.sports import RUNNING_SPORTS, is_running
from backend.app.models.schemas import PMCPointOut, BestEffortOut

router = APIRouter(prefix="/metrics", tags=["Metrics & Physiology Trends"])

@router.get("/pmc", response_model=List[PMCPointOut])
def get_pmc_chart(
    days: int = Query(90, ge=7, le=730),
    db: Session = Depends(get_db)
):
    """
    Returns Performance Management Chart (PMC) time series data:
    CTL (Fitness), ATL (Fatigue), TSB (Form), Daily TSS, HRV RMSSD, Readiness Score.
    """
    start_date = datetime.utcnow().date() - timedelta(days=days)
    records = (
        db.query(DailyHealth)
        .filter(DailyHealth.date >= start_date)
        .order_by(DailyHealth.date.asc())
        .all()
    )
    return records

@router.get("/records", response_model=List[BestEffortOut])
def get_personal_records(db: Session = Depends(get_db)):
    """Returns all-time personal records across standard running distances."""
    # Join to the activity so efforts recorded before sport filtering existed,
    # or on a walk, cannot appear as running records.
    all_efforts = (
        db.query(BestEffort)
        .join(Activity, Activity.id == BestEffort.activity_id)
        .filter(Activity.sport_type.in_(RUNNING_SPORTS))
        .order_by(BestEffort.time_seconds.asc())
        .all()
    )
    
    # Keep best time per label
    seen = {}
    records = []
    for eff in all_efforts:
        if eff.label not in seen:
            seen[eff.label] = True
            eff.is_personal_record = True
            records.append(eff)
            
    # Sort by distance
    records.sort(key=lambda x: x.distance_meters)
    return records

@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Returns high-level training metrics:
    - 7-day volume & TSS
    - 28-day volume & TSS
    - Current CTL (Fitness), ATL (Fatigue), TSB (Form)
    - Latest Readiness Score
    - Average Aerobic Decoupling across recent aerobic runs
    """
    today = datetime.utcnow().date()
    d7 = today - timedelta(days=7)
    d28 = today - timedelta(days=28)
    
    all_7d = db.query(Activity).filter(Activity.start_time >= datetime.combine(d7, datetime.min.time())).all()
    all_28d = db.query(Activity).filter(Activity.start_time >= datetime.combine(d28, datetime.min.time())).all()

    # Headline volume is running volume; other sports are reported separately
    # rather than silently inflating the weekly total.
    acts_7d = [a for a in all_7d if is_running(a.sport_type)]
    acts_28d = [a for a in all_28d if is_running(a.sport_type)]

    dist_7d = sum(a.distance_meters for a in acts_7d) / 1000.0
    tss_7d = sum(a.r_tss or 0 for a in acts_7d)
    time_7d = sum(a.moving_time_sec for a in acts_7d)

    dist_28d = sum(a.distance_meters for a in acts_28d) / 1000.0
    tss_28d = sum(a.r_tss or 0 for a in acts_28d)

    other_7d = {}
    for a in all_7d:
        if is_running(a.sport_type):
            continue
        entry = other_7d.setdefault(a.sport_type, {"count": 0, "km": 0.0, "tss": 0.0})
        entry["count"] += 1
        entry["km"] += (a.distance_meters or 0.0) / 1000.0
        entry["tss"] += a.r_tss or 0.0
    for entry in other_7d.values():
        entry["km"] = round(entry["km"], 2)
        entry["tss"] = round(entry["tss"], 1)
    
    latest_health = db.query(DailyHealth).order_by(DailyHealth.date.desc()).first()
    
    # Decoupling trend
    decoupling_values = [a.aerobic_decoupling_pct for a in acts_28d if a.aerobic_decoupling_pct is not None]
    avg_decoupling = float(np.mean(decoupling_values)) if decoupling_values else None
    
    return {
        "volume_7d_km": round(dist_7d, 2),
        "tss_7d": round(tss_7d, 1),
        "time_7d_sec": time_7d,
        "runs_7d_count": len(acts_7d),
        "volume_28d_km": round(dist_28d, 2),
        "tss_28d": round(tss_28d, 1),
        "ctl": latest_health.ctl if latest_health else 0.0,
        "atl": latest_health.atl if latest_health else 0.0,
        "tsb": latest_health.tsb if latest_health else 0.0,
        "acwr": latest_health.acwr if latest_health else 0.0,
        "readiness_score": latest_health.readiness_score if latest_health else None,
        "avg_decoupling_28d": round(avg_decoupling, 2) if avg_decoupling else None,
        # Non-running activity in the last 7 days, keyed by sport.
        "other_sports_7d": other_7d,
    }
