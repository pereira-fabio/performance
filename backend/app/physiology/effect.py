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

# A session of typical size costs about a day of recovery.
RECOVERY_HOURS_PER_TYPICAL_SESSION = 24.0
RECOVERY_MIN_HOURS, RECOVERY_MAX_HOURS = 3.0, 72.0

# Below this the ratio becomes noise, so a floor stands in.
MIN_REFERENCE_LOAD = 12.0

# ln(2), which places a typical session at exactly 3.0 on the scale.
_TE_K = 0.6931


def aerobic_training_effect(
    r_tss: Optional[float], reference_load: float
) -> Tuple[Optional[float], str]:
    """
    How much this session moved aerobic fitness, against the athlete's own norm.

    The reference is the athlete's *typical session*, not their chronic daily
    load. Chronic load is an average across every day including rest days, so
    for someone training three times a week each session is inherently three or
    four times that average -- scoring against it marked every ordinary run as
    overreaching. A typical session now reads 3.0, half of one reads about 2.2,
    and double reads 4.0.
    """
    if not r_tss or r_tss <= 0:
        return None, "no training load recorded"

    reference = max(reference_load, MIN_REFERENCE_LOAD)
    ratio = r_tss / reference
    te = 1.0 + 4.0 * (1.0 - math.exp(-_TE_K * ratio))
    return round(min(max(te, TE_MIN), TE_MAX), 1), ""


def anaerobic_training_effect(
    hr_zone_seconds: Optional[Dict[str, float]], reference_load: float
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

    # Twenty minutes above threshold is a hard anaerobic session for anyone.
    minutes = hard_sec / 60.0
    te = 1.0 + 4.0 * (1.0 - math.exp(-minutes / 12.0))
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
    reference_load: float,
    tsb: float = 0.0,
    readiness: Optional[float] = None,
) -> Tuple[Optional[int], str]:
    """
    Hours until this session is absorbed.

    Scaled against a typical session for this athlete, then adjusted for how
    fresh they already were: arriving fatigued lengthens recovery, arriving
    fresh shortens it slightly.
    """
    if not r_tss or r_tss <= 0:
        return None, "no training load recorded"

    reference = max(reference_load, MIN_REFERENCE_LOAD)
    hours = RECOVERY_HOURS_PER_TYPICAL_SESSION * (r_tss / reference)

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
