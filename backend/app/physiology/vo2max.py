"""
Estimating VO2 max from a running performance.

Some watches report a VO2 max and some do not -- Garmin withholds it on several
models, and a phone reading Health Connect gets whatever the vendor chose to
write. An athlete without one is not less trainable, so it is estimated from
what every running record already contains: a distance and the time it took.

The method is Daniels and Gilbert's VDOT, from *Oxygen Power* (1979), which is
the same arithmetic behind the training tables generations of runners have used.
It asks how much oxygen a runner would consume at the speed they held, and what
fraction of their maximum they could sustain for that long, and divides one by
the other.

It is an estimate of running economy and aerobic capacity together, so it is
honest only for a genuine effort. A 5 km jog says nothing about a ceiling that
was never approached, which is why only hard efforts are used and why the
result is always labelled as estimated.
"""
import math
from typing import Iterable, Optional, Tuple

# Below this the effort is anaerobic enough that the model overestimates, and
# above it the athlete is fading for reasons the curve does not describe.
MIN_EFFORT_MINUTES = 3.0
MAX_EFFORT_MINUTES = 90.0

# Shorter than this and a few seconds of GPS error moves the answer more than
# the running does.
MIN_EFFORT_METRES = 1200.0

# An estimate from an effort older than this describes a fitness that has since
# moved on.
DEFAULT_WINDOW_DAYS = 120

# Sanity rails. Outside these the input was wrong, not the athlete remarkable:
# the untrained sit near 25 and the world's best are under 100.
MIN_PLAUSIBLE = 20.0
MAX_PLAUSIBLE = 90.0


def vdot(distance_m: float, time_seconds: float) -> Optional[float]:
    """
    Daniels-Gilbert VDOT for one effort, or None if it cannot be trusted.

    Returns millilitres of oxygen per kilogram per minute.
    """
    if not distance_m or not time_seconds or distance_m <= 0 or time_seconds <= 0:
        return None
    if distance_m < MIN_EFFORT_METRES:
        return None

    minutes = time_seconds / 60.0
    if not (MIN_EFFORT_MINUTES <= minutes <= MAX_EFFORT_MINUTES):
        return None

    velocity = distance_m / minutes  # metres per minute

    # Oxygen cost of running at that velocity.
    oxygen_cost = -4.60 + 0.182258 * velocity + 0.000104 * velocity ** 2

    # The fraction of maximum a runner can hold for that duration. It falls
    # from nearly all of it over a few minutes to a little over 80% across an
    # hour and a half, which is why a marathon and a 5k give the same VDOT for
    # an evenly trained runner.
    fraction = (0.8
                + 0.1894393 * math.exp(-0.012778 * minutes)
                + 0.2989558 * math.exp(-0.1932605 * minutes))
    if fraction <= 0:
        return None

    estimate = oxygen_cost / fraction
    if not (MIN_PLAUSIBLE <= estimate <= MAX_PLAUSIBLE):
        return None
    return round(estimate, 1)


def best_estimate(efforts: Iterable[Tuple[float, float]]) -> Optional[float]:
    """
    The best VDOT among several efforts.

    The maximum rather than the average: every effort that was not all-out
    understates the ceiling, so a slow day drags a mean down while telling you
    nothing. The best effort is the one that came closest to the truth.
    """
    values = [v for v in (vdot(d, t) for d, t in efforts) if v is not None]
    return max(values) if values else None


# Threshold is run at roughly this share of maximum oxygen uptake. Daniels puts
# it at 86-88% for most runners; the upper end is used because the figure it
# feeds -- threshold pace -- is a target, and a target set slightly ambitious is
# corrected by the athlete, while one set slow is simply believed.
THRESHOLD_FRACTION = 0.88

# An hour is the classic definition of threshold: the pace you could hold for
# one. Runs in this band are close enough to stand in for it.
HOUR_EFFORT_MIN_SEC = 50 * 60
HOUR_EFFORT_MAX_SEC = 75 * 60

# A steady hour that is far slower than the VDOT estimate was not a threshold
# effort, it was an easy long run. Believing it would set the threshold far too
# slow, which then inflates every training-load figure computed against it.
MAX_HOUR_EFFORT_SLOWDOWN = 1.20


def threshold_pace_from_vdot(value: Optional[float]) -> Optional[float]:
    """
    Threshold pace in seconds per kilometre, from a VDOT.

    Solves the oxygen-cost curve backwards: the velocity whose cost equals the
    share of maximum sustainable at threshold. The same quadratic used to get
    VDOT from a performance, read the other way.
    """
    if value is None or not (MIN_PLAUSIBLE <= value <= MAX_PLAUSIBLE):
        return None

    target = THRESHOLD_FRACTION * value
    # 0.000104 v^2 + 0.182258 v - (4.60 + target) = 0
    a, b, c = 0.000104, 0.182258, -(4.60 + target)
    discriminant = b * b - 4 * a * c
    if discriminant <= 0:
        return None
    velocity = (-b + math.sqrt(discriminant)) / (2 * a)   # metres per minute
    if velocity <= 0:
        return None
    return round(60000.0 / velocity, 1)
