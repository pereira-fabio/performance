"""Aerobic decoupling (Pa:HR drift) and aerobic efficiency."""
from typing import List, Optional, Sequence, Tuple

import numpy as np

# Decoupling compares two halves of a run, so it needs a run long enough for
# each half to be meaningful.
DEFAULT_MIN_DURATION_SEC = 1200.0

# Below this fraction of the moving portion carrying a real heart rate sample,
# the two half-averages are not comparable and no figure is reported.
MIN_HR_COVERAGE = 0.70


def calculate_aerobic_decoupling(
    speeds_mps: Sequence[float],
    heart_rates: Sequence[float],
    dt: float = 1.0,
    min_duration_sec: float = DEFAULT_MIN_DURATION_SEC,
    min_hr_coverage: float = MIN_HR_COVERAGE,
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Aerobic Decoupling (Pa:HR drift) and Aerobic Efficiency Factor (EF).

    EF = speed (m/min) / heart rate (bpm), and decoupling compares EF across the
    first and second half of the moving portion:

        decoupling (%) = (1 - EF_2 / EF_1) * 100

    Interpretation: under 3% is a strong aerobic base, 3-5% is well trained, and
    above 5% indicates meaningful cardiac drift from fatigue, heat or running
    above aerobic threshold.

    Inputs are expected on a uniform grid of `dt` seconds, with NaN marking
    samples where no measurement was recorded. Returns
    (decoupling_pct, efficiency_factor, unavailable_reason); the reason is set
    whenever a figure is withheld, and is None on success.
    """
    speeds = np.asarray(speeds_mps, dtype=float)
    hrs = np.asarray(heart_rates, dtype=float)

    if len(speeds) == 0 or len(hrs) == 0:
        return None, None, "no speed or heart rate data"

    n = min(len(speeds), len(hrs))
    speeds, hrs = speeds[:n], hrs[:n]

    # Restrict to samples that are genuinely moving with a plausible heart rate.
    moving = np.nan_to_num(speeds, nan=0.0) >= 0.5
    moving_sec = float(np.count_nonzero(moving) * dt)
    if moving_sec <= 0:
        return None, None, "no moving time recorded"

    usable = moving & ~np.isnan(hrs) & (hrs > 40)
    coverage = float(np.count_nonzero(usable)) / max(float(np.count_nonzero(moving)), 1.0)

    if coverage < min_hr_coverage:
        return (
            None,
            None,
            f"heart rate covers only {coverage * 100:.0f}% of moving time "
            f"({min_hr_coverage * 100:.0f}% required)",
        )

    valid_speeds = speeds[usable]
    valid_hrs = hrs[usable]
    valid_sec = float(len(valid_speeds) * dt)

    avg_speed_mpm = float(np.mean(valid_speeds)) * 60.0
    avg_hr = float(np.mean(valid_hrs))
    overall_ef = float(np.round(avg_speed_mpm / avg_hr, 3)) if avg_hr > 0 else None

    # Efficiency is meaningful on any run; the drift split needs duration.
    if valid_sec < min_duration_sec:
        return (
            None,
            overall_ef,
            f"moving time {valid_sec / 60:.0f} min is below the "
            f"{min_duration_sec / 60:.0f} min needed for a stable split",
        )

    half = len(valid_speeds) // 2
    ef_1_speed = float(np.mean(valid_speeds[:half])) * 60.0
    ef_1_hr = float(np.mean(valid_hrs[:half]))
    ef_2_speed = float(np.mean(valid_speeds[half:])) * 60.0
    ef_2_hr = float(np.mean(valid_hrs[half:]))

    if ef_1_hr <= 0 or ef_2_hr <= 0 or ef_1_speed <= 0:
        return None, overall_ef, "degenerate heart rate or speed in one half"

    ef_1 = ef_1_speed / ef_1_hr
    ef_2 = ef_2_speed / ef_2_hr
    if ef_1 <= 0:
        return None, overall_ef, "degenerate first-half efficiency"

    drift_pct = (1.0 - (ef_2 / ef_1)) * 100.0
    return float(np.round(drift_pct, 2)), overall_ef, None
