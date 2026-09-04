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
