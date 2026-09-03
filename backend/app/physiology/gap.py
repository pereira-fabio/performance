import numpy as np

def minetti_cost(gradient: float) -> float:
    """
    Calculates the energy cost of running at a given gradient i (slope in decimal).
    Based on Minetti et al. (2002):
    C_r(i) = 155.4*i^5 - 30.4*i^4 - 43.3*i^3 + 46.3*i^2 + 19.5*i + 3.6 (J / kg * m)
    """
    i = np.clip(gradient, -0.45, 0.45)
    cost = (
        155.4 * (i ** 5)
        - 30.4 * (i ** 4)
        - 43.3 * (i ** 3)
        + 46.3 * (i ** 2)
        + 19.5 * i
        + 3.6
    )
    return float(cost)

FLAT_COST = minetti_cost(0.0) # 3.6 J / (kg * m)

def grade_cost_ratio(gradient: float) -> float:
    """Ratio of energy cost on slope compared to flat surface."""
    cost = minetti_cost(gradient)
    return cost / FLAT_COST

def calculate_gap_speed(speed_mps: float, gradient: float) -> float:
    """
    Converts actual speed on a slope to equivalent flat-ground speed (Grade-Adjusted Speed).
    Higher uphill cost -> higher equivalent flat speed.
    """
    if speed_mps <= 0.1:
        return 0.0
    ratio = grade_cost_ratio(gradient)
    return float(speed_mps * ratio)

def calculate_gap_pace(pace_sec_km: float, gradient: float) -> float:
    """
    Converts actual pace (sec/km) on a slope to Grade-Adjusted Pace (sec/km).
    Uphill (gradient > 0) -> equivalent flat pace is faster (smaller sec/km).
    Downhill (gradient < 0) -> adjusted for downhill braking cost.
    """
    if pace_sec_km <= 0 or np.isnan(pace_sec_km):
        return pace_sec_km
    ratio = grade_cost_ratio(gradient)
    if ratio <= 0.01:
        return pace_sec_km
    return float(pace_sec_km / ratio)
