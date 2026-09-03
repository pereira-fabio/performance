"""
Progression: experience, levels, achievements and attribute scores.

This layer is openly a game. It invents nothing about the body -- every input
is a figure already measured or computed elsewhere -- but the scoring curves,
level thresholds and attribute axes are design choices, not physiology. They
are kept here, apart from the measurement code, so the two are never confused.
"""
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional

# Experience rewards time spent and effort made, in roughly equal measure, so a
# long easy run and a short hard one both count for something.
XP_PER_TRAINING_LOAD = 1.0
XP_PER_KM = 6.0
XP_PER_ACTIVE_HOUR = 40.0

# Levels get further apart as they rise: level n needs BASE * n^EXPONENT total.
LEVEL_BASE_XP = 600.0
LEVEL_EXPONENT = 1.45
MAX_LEVEL = 99


def activity_xp(r_tss: Optional[float], distance_m: Optional[float], moving_sec: Optional[float]) -> int:
    """Experience for one session."""
    xp = (r_tss or 0.0) * XP_PER_TRAINING_LOAD
    xp += ((distance_m or 0.0) / 1000.0) * XP_PER_KM
    xp += ((moving_sec or 0.0) / 3600.0) * XP_PER_ACTIVE_HOUR
    return int(round(xp))


def level_for_xp(total_xp: int) -> Dict[str, int]:
    """Current level, plus how far through it the athlete is."""
    level = 1
    while level < MAX_LEVEL and total_xp >= int(LEVEL_BASE_XP * (level ** LEVEL_EXPONENT)):
        level += 1

    current_floor = 0 if level == 1 else int(LEVEL_BASE_XP * ((level - 1) ** LEVEL_EXPONENT))
    next_at = int(LEVEL_BASE_XP * (level ** LEVEL_EXPONENT)) if level < MAX_LEVEL else total_xp
    span = max(next_at - current_floor, 1)

    return {
        "level": level,
        "xp": total_xp,
        "xp_into_level": total_xp - current_floor,
        "xp_for_next": next_at - current_floor,
        "progress_pct": int(round(min(max((total_xp - current_floor) / span, 0.0), 1.0) * 100)),
    }


@dataclass
class Achievement:
    key: str
    name: str
    detail: str
    earned: bool
    progress: float          # 0..1 toward earning it
    value: Optional[str] = None


def _streak_weeks(dates: Iterable[date]) -> int:
    """Consecutive weeks, counting back from this week, with any activity."""
    weeks = {d - timedelta(days=d.weekday()) for d in dates}
    if not weeks:
        return 0
    cursor = date.today() - timedelta(days=date.today().weekday())
    streak = 0
    # This week not being done yet should not break a run of weeks.
    if cursor not in weeks:
        cursor -= timedelta(days=7)
    while cursor in weeks:
        streak += 1
        cursor -= timedelta(days=7)
    return streak


def evaluate_achievements(
    activities: List[dict],
    best_efforts: Dict[str, float],
    total_km: float,
    longest_km: float,
) -> List[Achievement]:
    """
    Milestones worth noticing. Each carries its progress so an unearned one is
    still informative rather than a locked grey box.
    """
    run_dates = [a["date"] for a in activities]
    streak = _streak_weeks(run_dates)
    count = len(activities)
    month_ago = date.today() - timedelta(days=30)
    km_30d = sum(a["km"] for a in activities if a["date"] >= month_ago)

    def milestone(key, name, detail, value, target, unit="", fmt="{:.0f}"):
        return Achievement(
            key=key, name=name, detail=detail,
            earned=value >= target, progress=min(value / target, 1.0) if target else 0.0,
            value=f"{fmt.format(value)}{unit} / {fmt.format(target)}{unit}",
        )

    out = [
        milestone("first_10k", "Ten kilometres", "Cover 10 km in a single run", longest_km, 10, " km", "{:.1f}"),
        milestone("half", "Half marathon", "Cover 21.1 km in a single run", longest_km, 21.1, " km", "{:.1f}"),
        milestone("century", "Century", "100 km in a single month", km_30d, 100, " km", "{:.0f}"),
        milestone("thousand", "Thousand club", "1000 km all time", total_km, 1000, " km", "{:.0f}"),
        milestone("fifty", "Fifty sessions", "Record 50 activities", count, 50),
        milestone("consistency", "Consistency", "Train every week for 8 weeks", streak, 8, " wks"),
    ]

    # Pace milestones only make sense once the distance has been covered.
    for label, target_sec, name in (
        ("5k", 30 * 60, "5k under 30:00"),
        ("5k", 25 * 60, "5k under 25:00"),
        ("10k", 60 * 60, "10k under 1:00:00"),
    ):
        best = best_efforts.get(label)
        if best:
            out.append(Achievement(
                key=f"{label}_{target_sec}", name=name,
                detail=f"Best {label}: {int(best // 60)}:{int(best % 60):02d}",
                earned=best <= target_sec,
                progress=min(target_sec / best, 1.0),
                value=f"{int(best // 60)}:{int(best % 60):02d}",
            ))
    return out


def attribute_scores(
    ctl: float,
    weekly_km: float,
    sessions_per_week: float,
    best_pace_sec: Optional[float],
    threshold_pace_sec: float,
    avg_decoupling: Optional[float],
    readiness: Optional[float],
) -> Dict[str, int]:
    """
    Five axes, each 0-100, for the profile chart.

    The scales are deliberately generous at the low end and hard to max out, so
    the shape says something about the balance of an athlete's training rather
    than everyone sitting at the edge.
    """
    def clamp(v: float) -> int:
        return int(round(min(max(v, 0.0), 100.0)))

    endurance = clamp(100 * (1 - math.exp(-ctl / 45.0)))
    volume = clamp(100 * (1 - math.exp(-weekly_km / 45.0)))
    consistency = clamp(100 * min(sessions_per_week / 5.0, 1.0))

    if best_pace_sec and threshold_pace_sec > 0:
        # Matching threshold pace sits at 65, and the top of the scale needs a
        # margin well beyond it, so the axis stays informative for years.
        speed = clamp(65 * (threshold_pace_sec / best_pace_sec) ** 1.8)
    else:
        speed = 0

    # Low cardiac drift and high readiness both indicate a body absorbing work.
    if avg_decoupling is not None:
        recovery = clamp(100 - avg_decoupling * 9)
    elif readiness is not None:
        recovery = clamp(readiness)
    else:
        recovery = 0

    return {
        "endurance": endurance,
        "speed": speed,
        "volume": volume,
        "consistency": consistency,
        "recovery": recovery,
    }
