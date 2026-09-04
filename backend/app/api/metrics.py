from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, timedelta, date
import numpy as np

from backend.app.core.database import get_db
from backend.app.models.models import DailyHealth, BestEffort, Activity, UserProfile, User
from backend.app.api.auth import current_user
from backend.app.core.sports import RUNNING_SPORTS, is_running
from backend.app.physiology.progress import (
    level_for_xp, evaluate_achievements, attribute_scores, _streak_weeks,
)
from backend.app.models.schemas import PMCPointOut, BestEffortOut

router = APIRouter(prefix="/metrics", tags=["Metrics & Physiology Trends"])

@router.get("/pmc", response_model=List[PMCPointOut])
def get_pmc_chart(
    days: int = Query(90, ge=7, le=730),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """
    Returns Performance Management Chart (PMC) time series data:
    CTL (Fitness), ATL (Fatigue), TSB (Form), Daily TSS, HRV RMSSD, Readiness Score.
    """
    start_date = datetime.utcnow().date() - timedelta(days=days)
    records = (
        db.query(DailyHealth)
        .filter(DailyHealth.user_id == user.id, DailyHealth.date >= start_date)
        .order_by(DailyHealth.date.asc())
        .all()
    )
    return records

# How many efforts to keep per distance. Three because a personal best on its
# own does not say whether it was a step or a leap; the two behind it do.
RECORDS_PER_DISTANCE = 3


@router.get("/records", response_model=List[BestEffortOut])
def get_personal_records(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """The best three efforts at each standard running distance."""
    # Joined to the activity so efforts recorded before sport filtering existed,
    # or on a walk, cannot appear as running records.
    rows = (
        db.query(BestEffort, Activity.name)
        .join(Activity, Activity.id == BestEffort.activity_id)
        .filter(Activity.user_id == user.id, Activity.sport_type.in_(RUNNING_SPORTS))
        .order_by(BestEffort.time_seconds.asc())
        .all()
    )

    kept: dict = {}
    for effort, activity_name in rows:
        bucket = kept.setdefault(effort.label, [])
        if len(bucket) >= RECORDS_PER_DISTANCE:
            continue
        # One entry per run. A single session can hold several efforts at a
        # distance, and three rows from the same morning is a list of one run,
        # not a top three.
        if any(e["activity_id"] == effort.activity_id for e in bucket):
            continue
        bucket.append({
            "label": effort.label,
            "distance_meters": effort.distance_meters,
            "time_seconds": effort.time_seconds,
            "pace_sec_km": effort.pace_sec_km,
            # Derived from the ranking rather than read from the row: the
            # stored flag is set at ingestion and can be stale, and the query
            # above has just established the real order.
            "is_personal_record": len(bucket) == 0,
            "rank": len(bucket) + 1,
            "activity_id": effort.activity_id,
            "activity_name": activity_name,
            "achieved_at": effort.achieved_at,
        })

    records = [e for bucket in kept.values() for e in bucket]
    records.sort(key=lambda e: (e["distance_meters"], e["rank"]))
    return records

@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
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
    
    all_7d = db.query(Activity).filter(Activity.user_id == user.id, Activity.start_time >= datetime.combine(d7, datetime.min.time())).all()
    all_28d = db.query(Activity).filter(Activity.user_id == user.id, Activity.start_time >= datetime.combine(d28, datetime.min.time())).all()

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
    
    latest_health = db.query(DailyHealth).filter(DailyHealth.user_id == user.id).order_by(DailyHealth.date.desc()).first()
    
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
        # Per-sport totals so each tab can show its own figures without the
        # sports being mixed into one meaningless aggregate.
        "by_sport": _by_sport(all_7d, all_28d),
    }


def _by_sport(acts_7d, acts_28d):
    """Volume, time and load for every sport present, over 7 and 28 days."""
    sports = {a.sport_type for a in acts_28d} | {a.sport_type for a in acts_7d}
    out = {}
    for sport in sports:
        w = [a for a in acts_7d if a.sport_type == sport]
        m = [a for a in acts_28d if a.sport_type == sport]
        out[sport] = {
            "count_7d": len(w),
            "km_7d": round(sum(a.distance_meters or 0 for a in w) / 1000.0, 2),
            "time_7d_sec": round(sum(a.moving_time_sec or 0 for a in w)),
            "load_7d": round(sum(a.r_tss or 0 for a in w), 1),
            "count_28d": len(m),
            "km_28d": round(sum(a.distance_meters or 0 for a in m) / 1000.0, 2),
            "time_28d_sec": round(sum(a.moving_time_sec or 0 for a in m)),
            "load_28d": round(sum(a.r_tss or 0 for a in m), 1),
        }
    return out


@router.get("/home")
def get_home(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """
    The overview: progression, balance across sports, and standing milestones.

    Everything here is derived from figures already computed per activity. The
    levels and attribute axes are a presentation layer over that, not new
    measurements.
    """
    activities = db.query(Activity).filter(Activity.user_id == user.id).order_by(Activity.start_time.asc()).all()
    if not activities:
        return {"empty": True}

    runs = [a for a in activities if is_running(a.sport_type)]
    total_xp = sum(a.xp or 0 for a in activities)
    progression = level_for_xp(total_xp)

    # Share of effort by sport, for the donut. Time is the fairest common unit:
    # kilometres would erase gym work entirely.
    split: Dict[str, Dict[str, float]] = {}
    for a in activities:
        e = split.setdefault(a.sport_type, {"count": 0, "seconds": 0.0, "km": 0.0, "xp": 0})
        e["count"] += 1
        e["seconds"] += a.moving_time_sec or 0.0
        e["km"] += (a.distance_meters or 0.0) / 1000.0
        e["xp"] += a.xp or 0
    for e in split.values():
        e["km"] = round(e["km"], 1)
        e["hours"] = round(e["seconds"] / 3600.0, 1)

    latest = db.query(DailyHealth).filter(DailyHealth.user_id == user.id).order_by(DailyHealth.date.desc()).first()
    ctl = float(latest.ctl) if latest else 0.0
    tsb = float(latest.tsb) if latest else 0.0

    today = datetime.utcnow().date()
    d7 = today - timedelta(days=7)
    weekly_km = sum(
        (a.distance_meters or 0) / 1000.0 for a in runs if a.start_time.date() >= d7
    )

    # Sessions per week over the last eight, so a single big week does not
    # masquerade as consistency.
    d56 = today - timedelta(days=56)
    recent = [a for a in activities if a.start_time.date() >= d56]
    sessions_per_week = round(len(recent) / 8.0, 2)

    best_effort_rows = (
        db.query(BestEffort)
        .join(Activity, Activity.id == BestEffort.activity_id)
        .filter(Activity.user_id == user.id, Activity.sport_type.in_(RUNNING_SPORTS))
        .all()
    )
    best_by_label: Dict[str, float] = {}
    for be in best_effort_rows:
        if be.label not in best_by_label or be.time_seconds < best_by_label[be.label]:
            best_by_label[be.label] = be.time_seconds

    best_pace = min((be.pace_sec_km for be in best_effort_rows), default=None)
    decoupling = [a.aerobic_decoupling_pct for a in runs if a.aerobic_decoupling_pct is not None]
    avg_decoupling = float(np.mean(decoupling[-10:])) if decoupling else None

    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    threshold = float(profile.threshold_pace_sec) if profile else 300.0

    attributes = attribute_scores(
        ctl=ctl, weekly_km=weekly_km, sessions_per_week=sessions_per_week,
        best_pace_sec=best_pace, threshold_pace_sec=threshold,
        avg_decoupling=avg_decoupling,
        readiness=latest.readiness_score if latest else None,
    )

    total_km = sum((a.distance_meters or 0) / 1000.0 for a in runs)
    achievements = evaluate_achievements(
        activities=[{"date": a.start_time.date(), "km": (a.distance_meters or 0) / 1000.0} for a in runs],
        best_efforts=best_by_label,
        total_km=total_km,
        longest_km=max(((a.distance_meters or 0) / 1000.0 for a in runs), default=0.0),
    )

    vo2 = next((a.vo2_max for a in reversed(activities) if a.vo2_max), None)
    if vo2 is None:
        vo2_row = (
            db.query(DailyHealth).filter(DailyHealth.user_id == user.id, DailyHealth.vo2_max.isnot(None))
            .order_by(DailyHealth.date.desc()).first()
        )
        vo2 = vo2_row.vo2_max if vo2_row else None

    return {
        "empty": False,
        "progression": progression,
        "attributes": attributes,
        "split": split,
        "streak_weeks": _streak_weeks([a.start_time.date() for a in activities]),
        "totals": {
            "activities": len(activities),
            "runs": len(runs),
            "km": round(total_km, 1),
            "hours": round(sum(a.moving_time_sec or 0 for a in activities) / 3600.0, 1),
        },
        "form": {"ctl": round(ctl, 1), "tsb": round(tsb, 1),
                 "readiness": latest.readiness_score if latest else None},
        "vo2_max": vo2,
        "resting_hr": latest.resting_hr if latest else None,
        "achievements": [a.__dict__ for a in achievements],
    }
