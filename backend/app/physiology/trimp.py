"""Training load: Banister TRIMP, Edwards TRIMP and running TSS."""
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

# Training load integrates heart rate over time, so a session with large
# unmeasured stretches would under-report. Below this coverage no figure is
# reported rather than a systematic undercount.
MIN_HR_COVERAGE = 0.50

# rTSS needs enough moving samples for a 30 s rolling window to mean anything.
MIN_RTSS_SAMPLES = 60
NGP_WINDOW_SEC = 30


def calculate_banister_trimp(
    heart_rates: Sequence[float],
    dt: float,
    max_hr: int,
    resting_hr: int,
    gender: str = "male",
    min_coverage: float = MIN_HR_COVERAGE,
) -> Tuple[Optional[float], Optional[str]]:
    """
    Banister Training Impulse over a uniform grid of `dt` seconds.

        TRIMP = sum( dt_min * hr_ratio * 0.64 * exp(y * hr_ratio) )
        hr_ratio = (HR - HR_rest) / (HR_max - HR_rest),  y = 1.92 male / 1.67 female

    Returns (trimp, unavailable_reason). NaN entries are unmeasured samples.
    """
    hrs = np.asarray(heart_rates, dtype=float)
    if len(hrs) == 0:
        return None, "no heart rate data"

    hrr = float(max_hr - resting_hr)
    if hrr <= 0:
        return None, "max heart rate is not above resting heart rate"

    measured = ~np.isnan(hrs)
    coverage = float(np.count_nonzero(measured)) / len(hrs)
    if coverage < min_coverage:
        return None, f"heart rate covers only {coverage * 100:.0f}% of the session"

    valid = hrs[measured]
    above_rest = valid > resting_hr
    if not np.any(above_rest):
        return 0.0, None

    y = 1.92 if str(gender).lower() == "male" else 1.67
    ratio = (np.minimum(valid[above_rest], max_hr) - resting_hr) / hrr
    contributions = (dt / 60.0) * ratio * 0.64 * np.exp(y * ratio)
    return float(np.round(float(np.sum(contributions)), 1)), None


def calculate_edwards_trimp(hr_zone_times_sec: Dict[str, float]) -> float:
    """Edwards TRIMP: minutes in each of five heart rate zones, weighted 1-5."""
    weights = {"z1": 1.0, "z2": 2.0, "z3": 3.0, "z4": 4.0, "z5": 5.0}
    total = sum((hr_zone_times_sec.get(z, 0.0) / 60.0) * w for z, w in weights.items())
    return float(np.round(total, 1))


def calculate_rtss(
    gap_speeds_mps: Sequence[float],
    dt: float,
    threshold_pace_sec: float,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
    """
    Running Training Stress Score from Normalised Graded Pace.

    A 30 s rolling mean of grade-adjusted speed is raised to the fourth power,
    averaged and rooted to give NGP. Intensity Factor is NGP over threshold
    speed, and rTSS is moving_time * IF^2 / 36.

    Only moving samples contribute, and the duration used is the moving
    duration, so stopped time neither inflates nor deflates the score.

    Returns (rtss, intensity_factor, ngp_pace_sec_km, unavailable_reason).
    """
    if threshold_pace_sec <= 0:
        return None, None, None, "no threshold pace configured"

    speeds = np.asarray(gap_speeds_mps, dtype=float)
    if len(speeds) == 0:
        return None, None, None, "no grade-adjusted speed data"

    moving = np.nan_to_num(speeds, nan=0.0) >= 0.5
    moving_speeds = speeds[moving]
    if len(moving_speeds) < MIN_RTSS_SAMPLES:
        return None, None, None, "not enough moving samples for a 30 s rolling window"

    window = int(min(max(1, round(NGP_WINDOW_SEC / dt)), len(moving_speeds)))
    rolling = np.convolve(moving_speeds, np.ones(window) / window, mode="valid")

    ngp_speed = float(np.mean(rolling**4) ** 0.25)
    threshold_speed = 1000.0 / threshold_pace_sec
    if ngp_speed <= 0 or threshold_speed <= 0:
        return None, None, None, "degenerate normalised graded pace"

    intensity_factor = ngp_speed / threshold_speed
    moving_time_sec = float(len(moving_speeds) * dt)
    r_tss = (moving_time_sec * (intensity_factor**2)) / 36.0

    return (
        float(np.round(r_tss, 1)),
        float(np.round(intensity_factor, 2)),
        float(np.round(1000.0 / ngp_speed, 1)),
        None,
    )
