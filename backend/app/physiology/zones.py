from typing import Dict, List, Tuple
import numpy as np

def get_default_hr_zones(max_hr: int, resting_hr: int, lthr: int = None) -> Dict[str, Tuple[int, int]]:
    """
    Calculate 5 heart rate zones using Karvonen (Heart Rate Reserve) formula or LTHR.
    Z1: Recovery (50-60% HRR)
    Z2: Aerobic / Endurance (60-70% HRR)
    Z3: Tempo (70-80% HRR)
    Z4: Threshold (80-90% HRR)
    Z5: Anaerobic / VO2 Max (90-100% HRR)
    """
    hrr = max_hr - resting_hr
    if hrr <= 0:
        hrr = max_hr * 0.7 # fallback
    
    z1_max = int(resting_hr + 0.60 * hrr)
    z2_max = int(resting_hr + 0.70 * hrr)
    z3_max = int(resting_hr + 0.80 * hrr)
    z4_max = int(resting_hr + 0.90 * hrr)
    
    return {
        "z1": (0, z1_max),
        "z2": (z1_max + 1, z2_max),
        "z3": (z2_max + 1, z3_max),
        "z4": (z3_max + 1, z4_max),
        "z5": (z4_max + 1, max_hr + 25)
    }

def get_default_pace_zones(threshold_pace_sec: float) -> Dict[str, Tuple[float, float]]:
    """
    Calculate 6 standard running pace zones based on Lactate Threshold Pace (FTP pace).
    Z1: Recovery (> 129% TP)
    Z2: Aerobic Endurance (114% - 129% TP)
    Z3: Tempo (106% - 113% TP)
    Z4: Threshold (99% - 105% TP)
    Z5: VO2 Max (90% - 98% TP)
    Z6: Anaerobic (< 90% TP)
    """
    tp = threshold_pace_sec
    return {
        "z1": (tp * 1.29, 9999.0),
        "z2": (tp * 1.14, tp * 1.29),
        "z3": (tp * 1.06, tp * 1.14),
        "z4": (tp * 0.99, tp * 1.06),
        "z5": (tp * 0.90, tp * 0.99),
        "z6": (0.0, tp * 0.90)
    }

def calculate_hr_time_in_zones(
    hr_series: List[float],
    dt: float,
    zones: Dict[str, Tuple[int, int]]
) -> Dict[str, float]:
    """Seconds spent in each HR zone over a uniform grid of `dt` seconds.

    NaN entries are samples with no measurement and contribute to no zone, so
    zone totals sum to measured time rather than elapsed time.
    """
    zone_times = {k: 0.0 for k in zones}
    for hr in hr_series:
        if hr is None or np.isnan(hr) or hr <= 30:
            continue
        for zone_name, (low, high) in zones.items():
            if low <= hr <= high:
                zone_times[zone_name] += dt
                break
    return zone_times

def calculate_pace_time_in_zones(
    pace_series: List[float],
    dt: float,
    zones: Dict[str, Tuple[float, float]]
) -> Dict[str, float]:
    """Seconds spent in each pace zone over a uniform grid of `dt` seconds."""
    zone_times = {k: 0.0 for k in zones}
    for pace in pace_series:
        if pace is None or np.isnan(pace) or pace <= 0:
            continue
        for zone_name, (low, high) in zones.items():
            if low <= pace < high or (zone_name == "z1" and pace >= low):
                zone_times[zone_name] += dt
                break
    return zone_times
