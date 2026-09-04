"""
Generated commentary on training.

Every response says which model wrote it and when. That is not decoration: the
rest of this application is careful about the difference between a measurement
and an estimate, and text from a language model is a third thing again.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.auth import current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.sports import is_running
from backend.app.models.models import Activity, Insight, User
from backend.app.services import coach

router = APIRouter(prefix="/coach", tags=["Coach"])


class Note(BaseModel):
    available: bool
    text: Optional[str] = None
    model: Optional[str] = None
    created_at: Optional[datetime] = None
    generated: bool = False          # written now, rather than reused
    reason: Optional[str] = None


def _configured() -> Optional[str]:
    return settings.OLLAMA_URL.strip() or None


@router.get("/status")
def coach_status(_: User = Depends(current_user)):
    url = _configured()
    if not url:
        return {"enabled": False, "reason": "No language model is configured on this server."}
    models = coach.list_models(url)
    return {
        "enabled": True,
        "url": url,
        "model": settings.OLLAMA_MODEL,
        "reachable": bool(models),
        "available_models": models,
    }


def _cached_or_generate(
    db: Session, user: User, kind: str, subject_id: Optional[str], brief: str, refresh: bool,
    system: str = coach.SYSTEM_PROMPT, max_tokens: int = 200,
) -> Note:
    url = _configured()
    if not url:
        return Note(available=False, reason="No language model is configured on this server.")

    model = settings.OLLAMA_MODEL
    fingerprint = coach.brief_fingerprint(brief, model, system)

    existing = (
        db.query(Insight)
        .filter(Insight.user_id == user.id, Insight.kind == kind,
                Insight.subject_id == subject_id)
        .first()
    )
    if existing and existing.fingerprint == fingerprint and not refresh:
        return Note(available=True, text=existing.text, model=existing.model,
                    created_at=existing.created_at, generated=False)

    result = coach.generate(url, model, brief, system=system, max_tokens=max_tokens)
    if not result.ok:
        # Fall back to whatever was written last rather than showing nothing.
        if existing:
            return Note(available=True, text=existing.text, model=existing.model,
                        created_at=existing.created_at, generated=False,
                        reason=result.error)
        return Note(available=False, reason=result.error)

    if existing:
        existing.text, existing.model, existing.fingerprint = result.text, model, fingerprint
        existing.created_at = datetime.utcnow()
    else:
        existing = Insight(user_id=user.id, kind=kind, subject_id=subject_id,
                           fingerprint=fingerprint, text=result.text, model=model)
        db.add(existing)
    db.commit()

    return Note(available=True, text=result.text, model=model,
                created_at=existing.created_at, generated=True)


@router.get("/activity/{activity_id}", response_model=Note)
def activity_note(
    activity_id: str, refresh: bool = False,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id, Activity.user_id == user.id)
        .first()
    )
    if not activity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")

    from backend.app.services.activity_processor import ActivityProcessor
    from backend.app.models.models import DailyHealth

    health = (
        db.query(DailyHealth)
        .filter(DailyHealth.user_id == user.id, DailyHealth.date <= activity.start_time.date())
        .order_by(DailyHealth.date.desc()).first()
    )
    processor = ActivityProcessor(db, user)
    since = activity.start_time - timedelta(days=28)
    longest = (
        db.query(Activity)
        .filter(Activity.user_id == user.id, Activity.sport_type == activity.sport_type,
                Activity.start_time >= since, Activity.start_time <= activity.start_time)
        .order_by(Activity.distance_meters.desc()).first()
    )

    context = {
        "ctl": float(health.ctl) if health else None,
        "tsb": float(health.tsb) if health else None,
        "typical_load": processor._typical_session_load(
            activity.sport_type, activity.start_time, activity.r_tss),
        "longest_recent": bool(longest and longest.id == activity.id and is_running(activity.sport_type)),
    }
    brief = coach.build_activity_brief(activity, context)
    return _cached_or_generate(db, user, "activity", activity.id, brief, refresh)


@router.get("/period", response_model=Note)
def period_note(
    kind: str = "week",
    key: Optional[str] = None,
    offset: int = 0,
    refresh: bool = False,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    """
    A review of a finished period, to sit alongside its recap.

    Cached against the period key rather than regenerated per view: a finished
    week does not change, so neither should what was written about it.
    """
    from backend.app.api.reports import _period
    from backend.app.services import reports as reports_service

    period = _period(kind, key, offset)
    report = reports_service.build_report(db, user.id, period)
    if report.get("empty"):
        return Note(available=False, reason="Nothing was recorded in this period.")

    brief = coach.build_period_brief(report)
    # A review earns a longer leash than a per-run note: it has a comparison to
    # make, and cutting it off mid-sentence is worse than the extra seconds.
    return _cached_or_generate(db, user, f"report-{kind}", period.key, brief, refresh,
                               system=coach.REVIEW_SYSTEM_PROMPT, max_tokens=400)


@router.get("/week", response_model=Note)
def weekly_note(
    refresh: bool = False,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    from backend.app.api.metrics import get_dashboard_summary

    since = datetime.utcnow() - timedelta(days=7)
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user.id, Activity.start_time >= since)
        .order_by(Activity.start_time.asc()).all()
    )
    if not activities:
        return Note(available=False, reason="No training in the past week to comment on.")

    summary = get_dashboard_summary(db=db, user=user)
    brief = coach.build_weekly_brief(summary, activities)
    # Keyed by the week so a new week gets its own note.
    subject = datetime.utcnow().strftime("%G-W%V")
    return _cached_or_generate(db, user, "week", subject, brief, refresh)
