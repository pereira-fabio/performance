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
    # None rather than a default: a default here is filled in before the
    # processor can choose a name that suits the sport.
    title: Optional[str] = None
    sport_type: Optional[str] = "running"
    start_time: datetime
    end_time: datetime
    distance_meters: Optional[float] = None
    duration_sec: Optional[float] = None
    calories_kcal: Optional[float] = None
    elevation_gain_m: Optional[float] = None
    elevation_loss_m: Optional[float] = None
    steps: Optional[int] = None
    vo2_max: Optional[float] = None

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
    # Where this effort stands against every other at the same distance: 1, 2,
    # 3, or None for one that is not in the top three. Null rather than 1 by
    # default, because these are also serialised as part of an activity, where
    # nothing has ranked them -- and a default of 1 there would have every
    # effort in every run claiming to be a record.
    rank: Optional[int] = None
    # Which run it happened in, so a record can be opened rather than just read.
    activity_id: Optional[str] = None
    activity_name: Optional[str] = None
    achieved_at: Optional[datetime] = None

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
    training_effect_aerobic: Optional[float] = None
    training_effect_anaerobic: Optional[float] = None
    recovery_hours: Optional[int] = None
    xp: Optional[int] = None
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
    steps: Optional[int] = None
    max_speed_mps: Optional[float] = None
    notes: Optional[str] = None
    splits: List[SplitOut] = []
    best_efforts: List[BestEffortOut] = []
    stream_data: Optional[Dict[str, Any]] = None

class UserProfileSchema(BaseModel):
    # Profile ids became UUID strings when accounts were introduced. Declaring
    # this an int made every read of the profile fail validation, which took
    # the whole profile screen down: the row was created and then could not be
    # serialised back out.
    id: Optional[str] = None
    name: str
    gender: str = "unspecified"
    max_hr: int
    resting_hr: int
    lthr: int
    threshold_pace_sec: float
    weight_kg: float
    height_cm: Optional[float] = None
    neck_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None
    birth_date: Optional[date] = None
    hr_zones: Optional[Dict[str, List[int]]] = None
    pace_zones: Optional[Dict[str, List[float]]] = None
    # Set by the API from the filesystem, not stored on the row: the picture
    # lives as a file, and duplicating its existence in the database would be
    # one more thing to keep in step.
    has_avatar: bool = False
    # Derived from the measurements above, never stored: recomputing is free,
    # and a stored figure would go stale the moment a measurement changed.
    composition: Optional[Dict[str, Any]] = None

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
