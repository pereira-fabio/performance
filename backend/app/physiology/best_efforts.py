from typing import List, Dict, Tuple, Optional
from datetime import datetime
import numpy as np

STANDARD_INTERVALS = [
    {"label": "400m", "distance": 400.0},
    {"label": "800m", "distance": 800.0},
    {"label": "1k", "distance": 1000.0},
    {"label": "1 Mile", "distance": 1609.34},
    {"label": "2 Miles", "distance": 3218.68},
    {"label": "5k", "distance": 5000.0},
    {"label": "10k", "distance": 10000.0},
    {"label": "15k", "distance": 15000.0},
    {"label": "Half Marathon", "distance": 21097.5},
    {"label": "Marathon", "distance": 42195.0},
]

def calculate_best_efforts(
    cumulative_distances_m: List[float],
    cumulative_times_sec: List[float],
    start_time: datetime
) -> List[Dict[str, any]]:
    """
    Finds best/fastest time for standard running distances within an activity stream.
    Uses sliding window search over cumulative distance & time arrays.
    """
    if len(cumulative_distances_m) < 10:
        return []
        
    total_dist = cumulative_distances_m[-1]
    best_efforts = []
    
    for interval in STANDARD_INTERVALS:
        target_dist = interval["distance"]
        if total_dist < target_dist:
            continue
            
        best_time = float("inf")
        best_start_offset = 0.0
        
        # Sliding pointer algorithm
        right = 0
        n = len(cumulative_distances_m)
        for left in range(n):
            target = cumulative_distances_m[left] + target_dist
            # Advance right pointer until distance reached
            while right < n and cumulative_distances_m[right] < target:
                right += 1
            if right >= n:
                break
                
            dist_delta = cumulative_distances_m[right] - cumulative_distances_m[left]
            time_delta = cumulative_times_sec[right] - cumulative_times_sec[left]
            
            # Interpolate to exact distance
            if dist_delta > 0:
                exact_time = time_delta * (target_dist / dist_delta)
                if exact_time < best_time:
                    best_time = exact_time
                    best_start_offset = cumulative_times_sec[left]
                    
        if best_time < float("inf") and best_time > 0:
            pace_sec_km = (best_time / (target_dist / 1000.0))
            best_efforts.append({
                "label": interval["label"],
                "distance_meters": target_dist,
                "time_seconds": float(np.round(best_time, 1)),
                "pace_sec_km": float(np.round(pace_sec_km, 1)),
                "start_time_offset_sec": float(np.round(best_start_offset, 1)),
                "achieved_at": start_time,
                "is_personal_record": False # will be evaluated against user history
            })
            
    return best_efforts
