from datetime import date, timedelta
from typing import List, Dict, Tuple
import numpy as np

def calculate_pmc_series(
    daily_tss_records: List[Dict[str, any]], # list of {"date": date, "tss": float}
    ctl_time_constant: float = 42.0, # Fitness decay constant (days)
    atl_time_constant: float = 7.0,  # Fatigue decay constant (days)
    end_date: date = None            # fill forward to here, default last activity day
) -> List[Dict[str, any]]:
    """
    Computes Performance Management Chart (PMC) time series:
    - CTL (Chronic Training Load / Fitness)
    - ATL (Acute Training Load / Fatigue)
    - TSB (Training Stress Balance / Form = CTL - ATL)
    - ACWR (Acute-Chronic Workload Ratio = ATL / CTL)
    
    Using Banister EWMA:
    CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) * (1 - exp(-1 / 42))
    ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) * (1 - exp(-1 / 7))
    """
    if not daily_tss_records:
        return []
        
    # Sort by date
    sorted_records = sorted(daily_tss_records, key=lambda x: x["date"])
    start_date = sorted_records[0]["date"]
    # Rest days still decay fitness and fatigue, so the series has to run to the
    # requested end date and not stop at the last day that happened to have a
    # workout -- otherwise CTL/ATL/TSB freeze at their last-run values.
    last_record_date = sorted_records[-1]["date"]
    end_date = max(end_date, last_record_date) if end_date else last_record_date
    
    # Map of date -> tss
    tss_map = {r["date"]: r.get("tss", 0.0) for r in sorted_records}
    
    ctl_decay = 1.0 - np.exp(-1.0 / ctl_time_constant)
    atl_decay = 1.0 - np.exp(-1.0 / atl_time_constant)
    
    current_ctl = 0.0
    current_atl = 0.0
    
    results = []
    curr = start_date
    while curr <= end_date:
        tss = tss_map.get(curr, 0.0)
        
        current_ctl = current_ctl + (tss - current_ctl) * ctl_decay
        current_atl = current_atl + (tss - current_atl) * atl_decay
        tsb = current_ctl - current_atl
        acwr = (current_atl / current_ctl) if current_ctl > 1.0 else 0.0
        
        results.append({
            "date": curr,
            "tss": float(np.round(tss, 1)),
            "ctl": float(np.round(current_ctl, 1)),
            "atl": float(np.round(current_atl, 1)),
            "tsb": float(np.round(tsb, 1)),
            "acwr": float(np.round(acwr, 2))
        })
        curr += timedelta(days=1)
        
    return results
