from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date

# --- Stream & Point Schemas ---
class LocationPoint(BaseModel):
    time: datetime
    lat: float
    lng: float
    altitude: Optional[float] = None
    speed: Optional[float] = None

class HeartRateSample(BaseModel):
    time: datetime
    bpm: int

class SpeedSample(BaseModel):
    time: datetime
    speed_mps: float

class CadenceSample(BaseModel):
    time: datetime
    spm: float

# Health Connect Ingestion Payload
class HealthConnectSessionPayload(BaseModel):
    session_id: str
    title: Optional[str] = "Running Session"
    sport_type: Optional[str] = "running"
    start_time: datetime
    end_time: datetime
    distance_meters: Optional[float] = None
    duration_sec: Optional[float] = None
    calories_kcal: Optional[float] = None
    elevation_gain_m: Optional[float] = None
    elevation_loss_m: Optional[float] = None
    
    # Time-series streams
    route_points: Optional[List[LocationPoint]] = []
    heart_rate_series: Optional[List[HeartRateSample]] = []
    speed_series: Optional[List[SpeedSample]] = []
    cadence_series: Optional[List[CadenceSample]] = []
    notes: Optional[str] = None

class DailyHealthPayload(BaseModel):
    date: date
    resting_hr: Optional[int] = None
    hrv_rmssd: Optional[float] = None
    sleep_duration_sec: Optional[float] = None
    sleep_score: Optional[float] = None
    vo2_max: Optional[float] = None
    steps: Optional[int] = None

# --- Output Schemas ---
class SplitOut(BaseModel):
    split_number: int
    distance_meters: float
    elapsed_time_sec: float
    pace_sec_km: float
    gap_sec_km: Optional[float] = None
    avg_hr: Optional[int] = None
    avg_cadence: Optional[float] = None
    elevation_diff_m: Optional[float] = None
    aerobic_efficiency: Optional[float] = None
    is_partial: bool = False

    class Config:
        from_attributes = True

class BestEffortOut(BaseModel):
    label: str
    distance_meters: float
    time_seconds: float
    pace_sec_km: float
    is_personal_record: bool

    class Config:
        from_attributes = True

class ActivitySummaryOut(BaseModel):
    id: str
    external_id: Optional[str] = None
    name: str
    sport_type: str
    start_time: datetime
    end_time: datetime
    elapsed_time_sec: float
    moving_time_sec: float
    distance_meters: float
    avg_pace_sec_km: Optional[float] = None
    gap_pace_sec_km: Optional[float] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_cadence: Optional[float] = None
    elevation_gain_m: Optional[float] = None
    aerobic_decoupling_pct: Optional[float] = None
    r_tss: Optional[float] = None
    intensity_factor: Optional[float] = None
    hr_coverage: Optional[float] = None
    # Per-channel coverage plus an `unavailable` map explaining any metric the
    # data did not support. Clients should show absence, not substitute zero.
    data_quality: Optional[Dict[str, Any]] = None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True

class ActivityDetailOut(ActivitySummaryOut):
    min_hr: Optional[int] = None
    avg_speed_mps: Optional[float] = None
    max_speed_mps: Optional[float] = None
    avg_altitude_m: Optional[float] = None
    avg_stride_length_m: Optional[float] = None
    elevation_loss_m: Optional[float] = None
    aerobic_efficiency_factor: Optional[float] = None
    trimp_banister: Optional[float] = None
    trimp_edwards: Optional[float] = None
    hr_zone_seconds: Optional[Dict[str, float]] = None
    pace_zone_seconds: Optional[Dict[str, float]] = None
    calories_kcal: Optional[float] = None
    vo2_max: Optional[float] = None
    notes: Optional[str] = None
    splits: List[SplitOut] = []
    best_efforts: List[BestEffortOut] = []
    stream_data: Optional[Dict[str, Any]] = None

class UserProfileSchema(BaseModel):
    id: int = 1
    name: str
    gender: str
    max_hr: int
    resting_hr: int
    lthr: int
    threshold_pace_sec: float
    weight_kg: float
    hr_zones: Optional[Dict[str, List[int]]] = None
    pace_zones: Optional[Dict[str, List[float]]] = None

    class Config:
        from_attributes = True

class PMCPointOut(BaseModel):
    date: date
    daily_tss: float
    ctl: float
    atl: float
    tsb: float
    resting_hr: Optional[int] = None
    hrv_rmssd: Optional[float] = None
    readiness_score: Optional[float] = None
