"""
Cycle tracking, per account and off by default.

Kept behind an explicit switch because this is the most personal data in the
application: nobody should have to look at a feature about their body that they
did not ask for, and on a shared server the switch is per account rather than
per install.

Turning it off hides it and stops nothing being collected; it does not delete
what was logged, because a switch is not a delete and treating it as one would
lose data on a mis-tap. Deleting an account still removes all of it.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.auth import current_user
from backend.app.core.database import get_db
from backend.app.models.models import CycleEntry, User
from backend.app.services import cycle as cycle_service

router = APIRouter(prefix="/cycle", tags=["Cycle"])


class DayIn(BaseModel):
    date: date
    flow: Optional[str] = Field(default=None, max_length=16)
    notes: Optional[str] = None


class Enabled(BaseModel):
    enabled: bool


def _logged_days(db: Session, user_id: str) -> List[date]:
    return [
        row[0] for row in
        db.query(CycleEntry.date).filter(CycleEntry.user_id == user_id)
        .order_by(CycleEntry.date.asc()).all()
    ]


@router.get("")
def cycle_summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Where the athlete is in their cycle, and when the next one is expected."""
    days = _logged_days(db, user.id)
    summary = cycle_service.summarise(days)
    summary["enabled"] = bool(user.cycle_tracking)
    return summary


@router.put("/enabled")
def set_enabled(body: Enabled, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    user.cycle_tracking = bool(body.enabled)
    db.commit()
    return {"enabled": bool(user.cycle_tracking)}


@router.get("/calendar")
def cycle_calendar(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    """A month of logged days, with the expected ones marked separately."""
    if month:
        year, _, mon = month.partition("-")
        try:
            first = date(int(year), int(mon), 1)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                detail=f"{month!r} is not a valid month.")
    else:
        first = date.today().replace(day=1)
    last = (first + timedelta(days=32)).replace(day=1)

    entries = (
        db.query(CycleEntry)
        .filter(CycleEntry.user_id == user.id,
                CycleEntry.date >= first, CycleEntry.date < last)
        .all()
    )
    summary = cycle_service.summarise(_logged_days(db, user.id))
    # Predicted days never overwrite logged ones: what happened outranks what
    # was expected, and showing both on one day would be a contradiction.
    logged = {e.date.isoformat() for e in entries}
    expected = [
        d for d in cycle_service.predicted_days(summary)
        if first.isoformat() <= d < last.isoformat() and d not in logged
    ]
    return {
        "month": f"{first:%Y-%m}",
        "days": {e.date.isoformat(): {"flow": e.flow, "notes": e.notes} for e in entries},
        "predicted": expected,
        "today": date.today().isoformat(),
    }


@router.put("/day")
def log_day(body: DayIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Log a day, or change what was recorded for it."""
    if body.date > date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="A day in the future cannot be logged.")
    if body.flow and body.flow not in cycle_service.FLOW_LEVELS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Flow must be one of {', '.join(cycle_service.FLOW_LEVELS)}.")

    entry = (
        db.query(CycleEntry)
        .filter(CycleEntry.user_id == user.id, CycleEntry.date == body.date)
        .first()
    )
    if entry is None:
        entry = CycleEntry(user_id=user.id, date=body.date)
        db.add(entry)
    entry.flow = body.flow
    entry.notes = body.notes
    db.commit()
    return {"date": body.date.isoformat(), "flow": entry.flow}


@router.delete("/day")
def unlog_day(day: date = Query(..., alias="date"),
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    deleted = (
        db.query(CycleEntry)
        .filter(CycleEntry.user_id == user.id, CycleEntry.date == day)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"date": day.isoformat(), "removed": bool(deleted)}
