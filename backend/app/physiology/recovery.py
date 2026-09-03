from typing import List, Dict, Optional, Tuple
import numpy as np

def calculate_recovery_readiness(
    hrv_rmssd: Optional[float],
    resting_hr: Optional[int],
    sleep_duration_sec: Optional[float],
    tsb: float,
    baseline_hrv_7d: Optional[float] = None,
    baseline_rhr_7d: Optional[float] = None
) -> Tuple[float, str]:
    """
    Computes a comprehensive Training Readiness Score (0 - 100) and recommendation
    combining:
    1. HRV RMSSD vs 7-day rolling baseline
    2. Resting HR vs baseline
    3. Sleep duration / quality
    4. TSB (Form / Training Stress Balance)
    """
    score = 70.0 # baseline neutral
    
    # 1. HRV component
    if hrv_rmssd and baseline_hrv_7d and baseline_hrv_7d > 0:
        hrv_ratio = hrv_rmssd / baseline_hrv_7d
        if hrv_ratio >= 1.05:
            score += 15.0 # Parasympathetic recovery strong
        elif hrv_ratio < 0.90:
            score -= 15.0 # Sympathetic stress / under-recovered
            
    # 2. Resting HR component
    if resting_hr and baseline_rhr_7d and baseline_rhr_7d > 0:
        rhr_diff = resting_hr - baseline_rhr_7d
        if rhr_diff > 3:
            score -= 10.0 # elevated RHR indicates systemic fatigue or infection
        elif rhr_diff < -2:
            score += 5.0
            
    # 3. Sleep component
    if sleep_duration_sec:
        hours = sleep_duration_sec / 3600.0
        if hours >= 7.5:
            score += 10.0
        elif hours < 6.0:
            score -= 15.0
            
    # 4. TSB component
    if tsb < -20: # High acute fatigue
        score -= 15.0
    elif tsb > 10: # Fresh/Peaked
        score += 10.0
        
    final_score = float(np.clip(score, 0.0, 100.0))
    
    if final_score >= 80:
        recommendation = "Optimal: Body is primed for high-intensity workouts, intervals, or race efforts."
    elif final_score >= 60:
        recommendation = "Good: Ready for moderate aerobic base or steady tempo runs."
    elif final_score >= 40:
        recommendation = "Fatigued: Stick to easy Zone 1-2 recovery running or active recovery."
    else:
        recommendation = "High Strain: Rest day strongly recommended to prevent overtraining or injury."
        
    return final_score, recommendation
