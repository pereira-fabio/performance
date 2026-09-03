"""
Training effect and recovery time.

Both are estimates, and are labelled as such wherever they surface. The
commercial versions (Firstbeat's Training Effect, Garmin's recovery advisor)
model EPOC from beat-to-beat data that Health Connect does not expose, so what
follows is a transparent approximation from load and intensity rather than a
reproduction of those figures.

The reasoning is stated in each function so a number can be argued with rather
than taken on trust.
"""
import math
from typing import Dict, Optional, Tuple

# Training effect is conventionally read on a 1.0-5.0 scale.
TE_MIN, TE_MAX = 1.0, 5.0

# A session whose load equals current fitness is a normal hard day and is
# treated as costing about a day of recovery.
RECOVERY_HOURS_PER_CTL_MULTIPLE = 24.0
RECOVERY_MIN_HOURS, RECOVERY_MAX_HOURS = 3.0, 72.0

# Below this fitness the ratio becomes meaningless, so a floor stands in.
MIN_MEANINGFUL_CTL = 15.0


def aerobic_training_effect(r_tss: Optional[float], ctl: float) -> Tuple[Optional[float], str]:
    """
    How much this session moved aerobic fitness, relative to current fitness.

    The same hour costs a beginner far more than a trained athlete, so the
    session's load is scored against the athlete's own chronic load rather than
    against an absolute scale. Roughly: half your fitness is maintenance,
    matching it is a solid session, double is a hard overload.
    """
    if not r_tss or r_tss <= 0:
        return None, "no training load recorded"

    reference = max(ctl, MIN_MEANINGFUL_CTL)
    ratio = r_tss / reference

    # Calibrated so half your fitness reads as maintaining, parity as
    # improving, and roughly 2.5x as the top of the scale.
    te = 1.0 + 4.0 * (1.0 - math.exp(-0.75 * ratio))
    return round(min(max(te, TE_MIN), TE_MAX), 1), ""


def anaerobic_training_effect(
    hr_zone_seconds: Optional[Dict[str, float]], ctl: float
) -> Tuple[Optional[float], str]:
    """
    Anaerobic contribution, taken from time spent in the top two heart-rate
    zones. Without beat-to-beat data this is the closest honest proxy: work
    above threshold is what drives the anaerobic response.
    """
    if not hr_zone_seconds:
        return None, "no heart rate zone data"

    hard_sec = (hr_zone_seconds.get("z4") or 0.0) + (hr_zone_seconds.get("z5") or 0.0) * 2.0
    if hard_sec <= 0:
        return 0.0, ""

    reference = max(ctl, MIN_MEANINGFUL_CTL)
    minutes = hard_sec / 60.0
    te = 1.0 + 4.0 * (1.0 - math.exp(-0.05 * minutes * (25.0 / reference)))
    return round(min(max(te, TE_MIN), TE_MAX), 1), ""


def describe_training_effect(te: Optional[float]) -> str:
    if te is None:
        return "Unknown"
    if te < 1.5:
        return "Easy"
    if te < 2.5:
        return "Maintaining"
    if te < 3.5:
        return "Improving"
    if te < 4.5:
        return "Highly improving"
    return "Overreaching"


def recovery_hours(
    r_tss: Optional[float],
    ctl: float,
    tsb: float = 0.0,
    readiness: Optional[float] = None,
) -> Tuple[Optional[int], str]:
    """
    Hours until this session is absorbed.

    Scaled from the session's load against chronic load, then adjusted for how
    fresh the athlete already was: arriving fatigued lengthens recovery, and
    arriving fresh shortens it slightly.
    """
    if not r_tss or r_tss <= 0:
        return None, "no training load recorded"

    reference = max(ctl, MIN_MEANINGFUL_CTL)
    hours = RECOVERY_HOURS_PER_CTL_MULTIPLE * (r_tss / reference)

    # Accumulated fatigue slows absorption; freshness speeds it a little.
    if tsb < -20:
        hours *= 1.30
    elif tsb < -10:
        hours *= 1.15
    elif tsb > 10:
        hours *= 0.90

    if readiness is not None:
        if readiness < 40:
            hours *= 1.25
        elif readiness > 80:
            hours *= 0.90

    return int(round(min(max(hours, RECOVERY_MIN_HOURS), RECOVERY_MAX_HOURS))), ""
