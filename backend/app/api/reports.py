"""
Weekly, monthly and yearly recaps.

The recap is deliberately a separate endpoint from the dashboard rather than a
filter on it. A dashboard is a live thing that changes under you; a recap is a
finished period that does not, which is what makes it worth reading on a Monday
and worth printing at the end of a month.
"""
from datetime import date, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.api.auth import current_user
from backend.app.core.database import get_db
from backend.app.models.models import User
from backend.app.services import reports

router = APIRouter(prefix="/reports", tags=["Reports"])

KINDS = ("week", "month", "year")


def _period(kind: str, key: Optional[str], offset: int) -> reports.Period:
    if kind not in KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail=f"Unknown report period {kind!r}.")
    if key:
        try:
            return reports.parse_key(kind, key)
        except (ValueError, TypeError):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                detail=f"{key!r} is not a valid {kind}.")
    if kind == "week":
        return reports.last_complete_week(offset)
    today = date.today()
    # Offset counts backwards from the current period for months and years,
    # which are browsed from where you are rather than from the last finished
    # one -- a month is worth reading while it is still running.
    if kind == "month":
        cursor = today.replace(day=1)
        for _ in range(offset):
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        return reports.month_of(cursor)
    return reports.year_of(date(today.year - offset, 1, 1))


@router.get("/week")
def week_report(
    offset: int = Query(0, ge=0, le=520),
    key: Optional[str] = None,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    """
    The last completed week, or an earlier one.

    Offset 0 is the week that has finished, not the seven days ending today:
    read on Monday morning it covers Monday to Sunday just gone.
    """
    period = _period("week", key, offset)
    report = reports.build_report(db, user.id, period)
    # Enough to page through weeks without the client doing calendar maths.
    # The next week is only offered once it has finished, so paging forward
    # can never land on a half-written week presented as a recap.
    following = reports.week_of(period.end.date())
    report["offset"] = offset
    report["previous_key"] = reports.preceding(period).key
    report["next_key"] = following.key if following.complete else None
    return report


@router.get("/period")
def period_report(
    kind: str = Query(..., pattern="^(week|month|year)$"),
    key: Optional[str] = None,
    offset: int = Query(0, ge=0, le=520),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    return reports.build_report(db, user.id, _period(kind, key, offset))


@router.get("/periods")
def periods(
    kind: str = Query("month", pattern="^(month|year)$"),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    """Which months or years this athlete actually trained in."""
    return reports.available_periods(db, user.id, kind)


@router.get("/pdf")
def report_pdf(
    kind: str = Query("month", pattern="^(week|month|year)$"),
    key: Optional[str] = None,
    offset: int = Query(0, ge=0, le=520),
    include_note: bool = True,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    """A printable recap."""
    try:
        from backend.app.services import report_pdf
    except ImportError:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF support is not installed on this server. Rebuild the "
                   "backend image to pick it up.",
        )

    period = _period(kind, key, offset)
    report = reports.build_report(db, user.id, period)

    note = model = None
    if include_note and not report.get("empty"):
        # A slow or missing model must not cost the athlete their report, so
        # this is best-effort: the PDF is complete without it.
        try:
            from backend.app.api.coach import _cached_or_generate
            from backend.app.services import coach
            brief = coach.build_period_brief(report)
            result = _cached_or_generate(
                db, user, f"report-{kind}", period.key, brief, False,
                system=coach.REVIEW_SYSTEM_PROMPT, max_tokens=400)
            if result.available:
                note, model = result.text, result.model
        except Exception:
            note = model = None

    data = report_pdf.render(
        report, athlete=(user.display_name or user.username), note=note, note_model=model)

    filename = f"performance-{period.key}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}",
            "Content-Length": str(len(data)),
        },
    )
