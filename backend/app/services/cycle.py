"""
Menstrual cycle tracking.

Cycle phase changes resting heart rate, perceived effort and how a hard session
feels, so an athlete keeping training data has a real reason to keep this
alongside it. That it lives on the same self-hosted server as everything else
is the point: this is the most personal data in the application and it never
leaves the machine it was entered on.

What this is not: it is not contraception, not a fertility test, and not a
diagnosis. Everything below is arithmetic on the dates that were entered.
Cycles vary for many ordinary reasons -- training load among them -- and the
figures say how confident they are rather than presenting a guess as a fact.

Design note: periods are derived from logged days rather than stored as ranges,
so correcting a mis-tap corrects the cycle history with it.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

# Two logged days closer together than this belong to the same period. Flow
# commonly pauses for a day, and treating that as a new cycle would halve every
# cycle length that followed it.
SAME_PERIOD_GAP_DAYS = 3

# A cycle outside this range is almost always a missed or mis-entered log
# rather than a real cycle, and averaging one in drags every prediction with
# it. They are kept in the history and left out of the average.
MIN_PLAUSIBLE_CYCLE = 15
MAX_PLAUSIBLE_CYCLE = 60

# Recent cycles describe the athlete now; a cycle from two years ago does not.
MAX_CYCLES_AVERAGED = 6

# Below this there is no average worth the name, only a coincidence.
MIN_CYCLES_FOR_PREDICTION = 2

# The luteal phase -- ovulation to the next period -- is far more consistent
# between people and between cycles than the follicular phase that precedes it.
# So ovulation is estimated backwards from the expected period, never forwards
# from the last one, which would put it wrong by the whole variation in cycle
# length.
LUTEAL_PHASE_DAYS = 14

DEFAULT_CYCLE_LENGTH = 28

FLOW_LEVELS = ("spotting", "light", "medium", "heavy")


@dataclass
class Period:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


def group_periods(days: Sequence[date]) -> List[Period]:
    """Turn logged days into periods, tolerating a flow that pauses."""
    ordered = sorted(set(days))
    if not ordered:
        return []
    periods: List[Period] = []
    start = previous = ordered[0]
    for day in ordered[1:]:
        if (day - previous).days >= SAME_PERIOD_GAP_DAYS:
            periods.append(Period(start, previous))
            start = day
        previous = day
    periods.append(Period(start, previous))
    return periods


def cycle_lengths(periods: Sequence[Period]) -> List[int]:
    """Days from the start of one period to the start of the next."""
    return [(b.start - a.start).days for a, b in zip(periods, periods[1:])]


def _plausible(lengths: Sequence[int]) -> List[int]:
    return [n for n in lengths if MIN_PLAUSIBLE_CYCLE <= n <= MAX_PLAUSIBLE_CYCLE]


def summarise(days: Sequence[date], today: Optional[date] = None) -> Dict[str, Any]:
    """
    Everything the cycle view shows, derived from the logged days alone.

    Returns `tracking: False` shapes rather than raising when there is not
    enough history: an athlete who has logged one day should be told what is
    missing, not shown a prediction built on nothing.
    """
    today = today or date.today()
    periods = group_periods(days)

    empty = {
        "logged_days": len(set(days)),
        "periods_recorded": len(periods),
        "has_prediction": False,
        "last_period_start": None,
        "last_period_days": None,
        "average_cycle_days": None,
        "average_period_days": None,
        "cycle_range": None,
        "cycle_day": None,
        "phase": None,
        "predicted_next_start": None,
        "predicted_window": None,
        "days_until_next": None,
        "confidence": "none",
        "reason": None,
    }
    if not periods:
        empty["reason"] = "Log the days of a period and this fills in."
        return empty

    last = periods[-1]
    # A period still running has no meaningful length yet.
    complete_periods = [p for p in periods if p.end < today]
    period_days = [p.days for p in complete_periods] or [last.days]

    raw_lengths = cycle_lengths(periods)
    usable = _plausible(raw_lengths)[-MAX_CYCLES_AVERAGED:]

    summary = dict(empty)
    summary.update({
        "last_period_start": last.start.isoformat(),
        "last_period_days": last.days if last.end < today else None,
        "average_period_days": round(median(period_days), 1) if period_days else None,
        "cycle_day": (today - last.start).days + 1 if today >= last.start else None,
    })
    if last.contains(today):
        summary["phase"] = "period"

    if len(usable) < MIN_CYCLES_FOR_PREDICTION:
        needed = MIN_CYCLES_FOR_PREDICTION + 1 - len(periods)
        summary["reason"] = (
            "Log one more period and a prediction appears." if needed <= 1
            else f"Log {needed} more periods and a prediction appears."
        )
        summary["confidence"] = "none"
        return summary

    # The median resists a single odd cycle in a way the mean does not, and
    # with four or five cycles to work from one odd cycle is a quarter of the
    # evidence.
    average = median(usable)
    shortest, longest = min(usable), max(usable)
    predicted = last.start + timedelta(days=int(round(average)))

    # The window is the observed spread, not a statistical interval: it says
    # "your cycles have run between these lengths", which is what it is.
    window_start = last.start + timedelta(days=shortest)
    window_end = last.start + timedelta(days=longest)

    summary.update({
        "has_prediction": True,
        "average_cycle_days": round(average, 1),
        "cycle_range": [shortest, longest],
        "predicted_next_start": predicted.isoformat(),
        "predicted_window": [window_start.isoformat(), window_end.isoformat()],
        "days_until_next": (predicted - today).days,
        "confidence": (
            "high" if len(usable) >= 4 and (longest - shortest) <= 4 else
            "moderate" if len(usable) >= 3 and (longest - shortest) <= 9 else
            "low"
        ),
    })

    if summary["phase"] != "period":
        summary["phase"] = _phase_on(today, predicted)
    return summary


def _phase_on(day: date, next_start: date) -> Optional[str]:
    """
    Which phase a day falls in, estimated backwards from the next period.

    Named for orientation, not for decisions: these boundaries are arithmetic
    on dates, and the body does not read a calendar.
    """
    ovulation = next_start - timedelta(days=LUTEAL_PHASE_DAYS)
    if day > next_start:
        return None  # the prediction has passed; nothing honest to say
    if abs((day - ovulation).days) <= 1:
        return "ovulation"
    if day < ovulation:
        return "follicular"
    return "luteal"


def predicted_days(summary: Dict[str, Any], months_ahead: int = 3) -> List[str]:
    """
    Which future days are expected to be period days, for shading a calendar.

    Only cycles ahead of today are projected, and only while the prediction is
    worth showing. Drawing them for the past would overwrite what was actually
    logged with what was merely expected.
    """
    if not summary.get("has_prediction") or not summary.get("predicted_next_start"):
        return []
    average = int(round(summary["average_cycle_days"] or DEFAULT_CYCLE_LENGTH))
    length = int(round(summary.get("average_period_days") or 5))
    start = date.fromisoformat(summary["predicted_next_start"])

    out: List[str] = []
    horizon = date.today() + timedelta(days=31 * months_ahead)
    cursor = start
    # Guarded by the horizon and a cycle count: a corrupt average must not spin.
    for _ in range(months_ahead + 2):
        if cursor > horizon:
            break
        for offset in range(max(1, length)):
            out.append((cursor + timedelta(days=offset)).isoformat())
        cursor += timedelta(days=max(MIN_PLAUSIBLE_CYCLE, average))
    return out
