"""
Weekly, monthly and yearly training reports.

A recap is a different question from the dashboard. The dashboard answers
"where am I now"; a recap answers "what did I just do, and was it more or less
than before". Comparison is therefore the whole point of this module: every
headline figure is paired with the same figure from the period before it,
because a 42 km week means nothing until you know the week before was 28.

Weeks are ISO weeks, Monday to Sunday, and the default recap is the week that
has *finished*. A rolling seven-day window would put Sunday's long run in two
different summaries and never settle on a verdict; a completed week is a fact
that stops changing, which is what makes it worth reading on Monday morning.

Runs lead, because that is what the athlete is training for. Everything else is
counted honestly and kept out of the running averages.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend.app.core.sports import is_running
from backend.app.models.models import Activity, BestEffort, DailyHealth

# A pace average is only meaningful where enough of the distance was measured.
MIN_DISTANCE_FOR_PACE_M = 400.0


@dataclass
class Period:
    """A closed date range with the identity needed to page through them."""
    kind: str        # "week" | "month" | "year"
    key: str         # "2026-W36", "2026-09", "2026"
    label: str       # "1 - 7 September 2026"
    start: datetime  # inclusive
    end: datetime    # exclusive
    complete: bool   # has the period finished

    @property
    def days(self) -> int:
        return max(1, (self.end - self.start).days)


def _midnight(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time())


def week_of(day: date, today: Optional[date] = None) -> Period:
    today = today or date.today()
    monday = day - timedelta(days=day.weekday())
    sunday = monday + timedelta(days=6)
    year, week, _ = monday.isocalendar()
    # A range spanning a month or year boundary needs both sides spelling out.
    if monday.month == sunday.month:
        label = f"{monday.day}-{sunday.day} {sunday:%B %Y}"
    elif monday.year == sunday.year:
        label = f"{monday.day} {monday:%b} - {sunday.day} {sunday:%b %Y}"
    else:
        label = f"{monday.day} {monday:%b %Y} - {sunday.day} {sunday:%b %Y}"
    return Period(
        kind="week", key=f"{year}-W{week:02d}", label=label,
        start=_midnight(monday), end=_midnight(monday + timedelta(days=7)),
        complete=sunday < today,
    )


def last_complete_week(offset: int = 0, today: Optional[date] = None) -> Period:
    """
    The most recently finished week, or one further back per offset.

    Offset 0 on a Monday is the seven days that ended yesterday, which is the
    recap someone opening the app on Monday morning is looking for.
    """
    today = today or date.today()
    return week_of(today - timedelta(days=today.weekday() + 7 * (offset + 1)), today)


def month_of(day: date, today: Optional[date] = None) -> Period:
    today = today or date.today()
    first = day.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return Period(
        kind="month", key=f"{first:%Y-%m}", label=f"{first:%B %Y}",
        start=_midnight(first), end=_midnight(nxt),
        complete=nxt <= today,
    )


def year_of(day: date, today: Optional[date] = None) -> Period:
    today = today or date.today()
    first = date(day.year, 1, 1)
    return Period(
        kind="year", key=f"{first:%Y}", label=f"{first:%Y}",
        start=_midnight(first), end=_midnight(date(day.year + 1, 1, 1)),
        complete=date(day.year + 1, 1, 1) <= today,
    )


def parse_key(kind: str, key: str) -> Period:
    """Turn a period key back into a period. Raises ValueError on nonsense."""
    if kind == "week":
        year, _, week = key.partition("-W")
        return week_of(date.fromisocalendar(int(year), int(week), 1))
    if kind == "month":
        year, _, month = key.partition("-")
        return month_of(date(int(year), int(month), 1))
    if kind == "year":
        return year_of(date(int(key), 1, 1))
    raise ValueError(f"unknown period kind {kind!r}")


def preceding(period: Period) -> Period:
    """The period immediately before this one, for comparison."""
    if period.kind == "week":
        return week_of((period.start - timedelta(days=1)).date())
    if period.kind == "month":
        return month_of((period.start - timedelta(days=1)).date())
    return year_of((period.start - timedelta(days=1)).date())


# ------------------------------------------------------------- figures -----
def _sum(values: Sequence[Optional[float]]) -> float:
    return float(sum(v or 0.0 for v in values))


def _weighted(pairs: Sequence[tuple]) -> Optional[float]:
    """Average of (value, weight), ignoring anything unmeasured."""
    kept = [(v, w) for v, w in pairs if v is not None and w and w > 0]
    if not kept:
        return None
    total = sum(w for _, w in kept)
    return sum(v * w for v, w in kept) / total if total else None


def _round(value: Optional[float], digits: int = 1) -> Optional[float]:
    return None if value is None else round(float(value), digits)


def summarise(activities: List[Activity]) -> Dict[str, Any]:
    """
    Headline figures for a set of activities.

    Averages are weighted, never a mean of means: a week's average pace is its
    total distance over its total time. Averaging the pace of a 20 km run with
    that of a 2 km jog and calling the result the week's pace would flatter or
    punish the athlete depending only on how many short sessions they did.
    """
    runs = [a for a in activities if is_running(a.sport_type)]
    run_distance = _sum([a.distance_meters for a in runs])
    run_moving = _sum([a.moving_time_sec for a in runs])

    paced = [a for a in runs if (a.distance_meters or 0) >= MIN_DISTANCE_FOR_PACE_M]
    fastest = min((a for a in paced if a.avg_pace_sec_km), key=lambda a: a.avg_pace_sec_km, default=None)
    longest = max(runs, key=lambda a: a.distance_meters or 0, default=None)

    zones: Dict[str, float] = {}
    for a in runs:
        for zone, seconds in (a.hr_zone_seconds or {}).items():
            zones[zone] = zones.get(zone, 0.0) + float(seconds or 0)

    return {
        "sessions": len(activities),
        "runs": len(runs),
        "km": _round(run_distance / 1000.0, 2),
        "moving_sec": round(run_moving),
        "elapsed_sec": round(_sum([a.elapsed_time_sec for a in runs])),
        "load": _round(_sum([a.r_tss for a in runs])),
        "elevation_gain_m": _round(_sum([a.elevation_gain_m for a in runs]), 0),
        "calories": _round(_sum([a.calories_kcal for a in activities]), 0),
        "xp": round(_sum([a.xp for a in activities])),
        "steps": round(_sum([a.steps for a in activities])) or None,
        # Distance over time, not a mean of paces.
        "avg_pace_sec_km": _round(run_moving / (run_distance / 1000.0)) if run_distance > 0 and run_moving else None,
        "avg_gap_sec_km": _round(_weighted([(a.gap_pace_sec_km, a.distance_meters) for a in runs])),
        "avg_hr": _round(_weighted([(a.avg_hr, a.moving_time_sec) for a in runs]), 0),
        "max_hr": max((a.max_hr for a in runs if a.max_hr), default=None),
        "avg_cadence": _round(_weighted([(a.avg_cadence, a.moving_time_sec) for a in runs])),
        "avg_stride_m": _round(_weighted([(a.avg_stride_length_m, a.distance_meters) for a in runs]), 2),
        "avg_decoupling_pct": _round(_weighted([(a.aerobic_decoupling_pct, a.moving_time_sec) for a in runs])),
        "avg_training_effect": _round(_weighted([(a.training_effect_aerobic, 1) for a in runs])),
        "longest_km": _round((longest.distance_meters or 0) / 1000.0, 2) if longest else None,
        "fastest_pace_sec_km": _round(fastest.avg_pace_sec_km) if fastest else None,
        "fastest_name": fastest.name if fastest else None,
        "days_trained": len({a.start_time.date() for a in activities}),
        "hr_zone_seconds": {k: round(v) for k, v in sorted(zones.items())} or None,
    }


def _delta(now: Optional[float], before: Optional[float]) -> Optional[Dict[str, Any]]:
    """
    How a figure moved, in absolute and relative terms.

    A percentage against zero is undefined rather than infinite: a first week
    back after none at all is "new", not "up 100%".
    """
    if now is None or before is None:
        return None
    change = now - before
    return {
        "change": _round(change, 2),
        "pct": _round((change / before) * 100.0) if before else None,
    }


COMPARED = (
    "km", "moving_sec", "load", "runs", "sessions", "elevation_gain_m",
    "avg_pace_sec_km", "avg_hr", "days_trained", "calories",
)


def _form_at(db: Session, user_id: str, moment: datetime) -> Optional[DailyHealth]:
    """The most recent fitness figures on or before a date."""
    return (
        db.query(DailyHealth)
        .filter(DailyHealth.user_id == user_id, DailyHealth.date <= moment.date())
        .order_by(DailyHealth.date.desc())
        .first()
    )


def _bucket(group: List[Activity], key: str, label: str) -> Dict[str, Any]:
    runs = [a for a in group if is_running(a.sport_type)]
    return {
        "date": key,
        "label": label,
        "km": _round(_sum([a.distance_meters for a in runs]) / 1000.0, 2),
        "load": _round(_sum([a.r_tss for a in runs])),
        "moving_sec": round(_sum([a.moving_time_sec for a in group])),
        "sessions": len(group),
    }


def breakdown(activities: List[Activity], period: Period) -> Dict[str, Any]:
    """
    The period cut into readable pieces, empty ones included.

    A week and a month are read day by day; a year is read month by month,
    because 365 bars is not a chart anyone can look at. Empty buckets are kept
    deliberately -- the gaps in a training week are as informative as the
    sessions, and dropping them would silently close them up.
    """
    if period.kind == "year":
        groups: Dict[str, List[Activity]] = {}
        for a in activities:
            groups.setdefault(f"{a.start_time:%Y-%m}", []).append(a)
        rows = []
        cursor = period.start.date()
        while cursor < period.end.date():
            key = f"{cursor:%Y-%m}"
            rows.append(_bucket(groups.get(key, []), key, cursor.strftime("%b")))
            cursor = (cursor + timedelta(days=32)).replace(day=1)
        return {"unit": "month", "rows": rows}

    groups_by_day: Dict[date, List[Activity]] = {}
    for a in activities:
        groups_by_day.setdefault(a.start_time.date(), []).append(a)
    rows = []
    day = period.start.date()
    fmt = "%a" if period.kind == "week" else "%-d"
    while day < period.end.date():
        rows.append(_bucket(groups_by_day.get(day, []), day.isoformat(), day.strftime(fmt)))
        day += timedelta(days=1)
    return {"unit": "day", "rows": rows}


def _session_rows(activities: List[Activity]) -> List[Dict[str, Any]]:
    return [{
        "id": a.id,
        "name": a.name,
        "sport_type": a.sport_type,
        "start_time": a.start_time.isoformat(),
        "km": _round((a.distance_meters or 0) / 1000.0, 2),
        "moving_sec": round(a.moving_time_sec or 0),
        "pace_sec_km": _round(a.avg_pace_sec_km),
        "gap_sec_km": _round(a.gap_pace_sec_km),
        "avg_hr": a.avg_hr,
        "load": _round(a.r_tss),
        "elevation_gain_m": _round(a.elevation_gain_m, 0),
        "training_effect": _round(a.training_effect_aerobic),
        "decoupling_pct": _round(a.aerobic_decoupling_pct),
        "is_run": is_running(a.sport_type),
    } for a in activities]


def _activities_in(db: Session, user_id: str, period: Period) -> List[Activity]:
    return (
        db.query(Activity)
        .filter(Activity.user_id == user_id,
                Activity.start_time >= period.start,
                Activity.start_time < period.end)
        .order_by(Activity.start_time.asc())
        .all()
    )


def build_report(db: Session, user_id: str, period: Period) -> Dict[str, Any]:
    """Everything a recap of this period needs, comparison included."""
    activities = _activities_in(db, user_id, period)
    previous_period = preceding(period)
    previous = _activities_in(db, user_id, previous_period)

    totals = summarise(activities)
    before = summarise(previous)
    deltas = {key: _delta(totals.get(key), before.get(key)) for key in COMPARED}

    # Non-running work is counted, never folded into the running averages.
    other: Dict[str, Dict[str, Any]] = {}
    for a in activities:
        if is_running(a.sport_type):
            continue
        entry = other.setdefault(a.sport_type, {"count": 0, "km": 0.0, "moving_sec": 0.0, "load": 0.0})
        entry["count"] += 1
        entry["km"] += (a.distance_meters or 0.0) / 1000.0
        entry["moving_sec"] += a.moving_time_sec or 0.0
        entry["load"] += a.r_tss or 0.0
    for entry in other.values():
        entry["km"] = round(entry["km"], 2)
        entry["moving_sec"] = round(entry["moving_sec"])
        entry["load"] = round(entry["load"], 1)

    efforts = (
        db.query(BestEffort)
        .join(Activity, BestEffort.activity_id == Activity.id)
        .filter(Activity.user_id == user_id,
                BestEffort.achieved_at >= period.start,
                BestEffort.achieved_at < period.end)
        .order_by(BestEffort.distance_meters.asc())
        .all()
    )
    # Only the quickest of each distance: a 5k split exists inside every 10k,
    # and listing them all would bury the one that matters.
    best_by_label: Dict[str, BestEffort] = {}
    for effort in efforts:
        current = best_by_label.get(effort.label)
        if current is None or effort.time_seconds < current.time_seconds:
            best_by_label[effort.label] = effort

    opening = _form_at(db, user_id, period.start - timedelta(days=1))
    closing = _form_at(db, user_id, period.end - timedelta(days=1))

    return {
        "kind": period.kind,
        "key": period.key,
        "label": period.label,
        "start": period.start.isoformat(),
        "end": (period.end - timedelta(seconds=1)).isoformat(),
        "complete": period.complete,
        "day_count": period.days,
        "empty": not activities,
        "totals": totals,
        "previous": {"key": previous_period.key, "label": previous_period.label, "totals": before},
        "deltas": deltas,
        "breakdown": breakdown(activities, period),
        "sessions": _session_rows(activities),
        "other_sports": other,
        "records": [{
            "label": e.label,
            "time_seconds": _round(e.time_seconds),
            "pace_sec_km": _round(e.pace_sec_km),
            "achieved_at": e.achieved_at.isoformat(),
            "is_personal_record": bool(e.is_personal_record),
        } for e in sorted(best_by_label.values(), key=lambda e: e.distance_meters)],
        "form": {
            "ctl_start": _round(opening.ctl) if opening else None,
            "ctl_end": _round(closing.ctl) if closing else None,
            "atl_end": _round(closing.atl) if closing else None,
            "tsb_end": _round(closing.tsb) if closing else None,
            "acwr_end": _round(closing.acwr, 2) if closing else None,
        },
    }


def training_calendar(db: Session, user_id: str, month: date) -> Dict[str, Any]:
    """
    Which days of a month were trained, for picking a week off a calendar.

    Deliberately small: a day, what was done on it, and how far. Paging a
    calendar should not drag a month of full activity records across the wire.
    """
    start = _midnight(month.replace(day=1))
    end = _midnight((start + timedelta(days=32)).date().replace(day=1))

    rows = (
        db.query(Activity.start_time, Activity.sport_type, Activity.distance_meters)
        .filter(Activity.user_id == user_id,
                Activity.start_time >= start, Activity.start_time < end)
        .all()
    )
    days: Dict[str, Dict[str, Any]] = {}
    for start_time, sport, distance in rows:
        entry = days.setdefault(start_time.date().isoformat(),
                                {"sessions": 0, "km": 0.0, "sports": []})
        entry["sessions"] += 1
        entry["km"] += (distance or 0.0) / 1000.0
        if sport not in entry["sports"]:
            entry["sports"].append(sport)
    for entry in days.values():
        entry["km"] = round(entry["km"], 2)

    # The bounds let the picker stop offering months that hold nothing.
    first = (
        db.query(Activity.start_time)
        .filter(Activity.user_id == user_id)
        .order_by(Activity.start_time.asc()).first()
    )
    return {
        "month": f"{start:%Y-%m}",
        "days": days,
        "earliest": first[0].date().isoformat() if first else None,
        "today": date.today().isoformat(),
    }


def available_periods(db: Session, user_id: str, kind: str) -> List[Dict[str, Any]]:
    """
    Which months or years the athlete actually has training in.

    Offering an empty January is a worse experience than not offering it, so
    the picker is built from the data rather than from the calendar.
    """
    first = (
        db.query(Activity.start_time)
        .filter(Activity.user_id == user_id)
        .order_by(Activity.start_time.asc())
        .first()
    )
    if not first:
        return []
    earliest, today = first[0].date(), date.today()

    seen: List[Period] = []
    if kind == "year":
        for year in range(today.year, earliest.year - 1, -1):
            seen.append(year_of(date(year, 1, 1)))
    else:
        cursor = today.replace(day=1)
        floor = earliest.replace(day=1)
        while cursor >= floor:
            seen.append(month_of(cursor))
            cursor = (cursor - timedelta(days=1)).replace(day=1)
    return [{"key": p.key, "label": p.label, "complete": p.complete} for p in seen]
