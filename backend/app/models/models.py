from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, ForeignKey, Date, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from backend.app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Activity(Base):
    __tablename__ = "activities"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    external_id = Column(String(128), unique=True, index=True, nullable=True) # Health Connect session ID
    name = Column(String(255), nullable=False, default="Running Session")
    sport_type = Column(String(64), default="running")
    
    # Timing
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    elapsed_time_sec = Column(Float, nullable=False)
    moving_time_sec = Column(Float, nullable=False)
    
    # Distance & Speed
    distance_meters = Column(Float, nullable=False)
    avg_speed_mps = Column(Float, nullable=True)
    max_speed_mps = Column(Float, nullable=True)
    avg_pace_sec_km = Column(Float, nullable=True) # in seconds per km (e.g. 300 = 5:00/km)
    gap_pace_sec_km = Column(Float, nullable=True) # Grade-Adjusted Pace
    
    # Elevation
    elevation_gain_m = Column(Float, nullable=True)
    elevation_loss_m = Column(Float, nullable=True)
    avg_altitude_m = Column(Float, nullable=True)
    
    # Heart Rate & Physiology
    avg_hr = Column(Integer, nullable=True)
    max_hr = Column(Integer, nullable=True)
    min_hr = Column(Integer, nullable=True)
    lthr_estimated = Column(Integer, nullable=True)
    
    # Cadence & Dynamics
    avg_cadence = Column(Float, nullable=True) # steps per minute (spm)
    max_cadence = Column(Float, nullable=True)
    avg_stride_length_m = Column(Float, nullable=True)
    
    # Advanced Sports Science Metrics
    aerobic_decoupling_pct = Column(Float, nullable=True) # Pa:HR drift % (> 5% = fatigue/drift)
    aerobic_efficiency_factor = Column(Float, nullable=True) # Speed (m/min) / HR
    trimp_banister = Column(Float, nullable=True)
    trimp_edwards = Column(Float, nullable=True)
    r_tss = Column(Float, nullable=True) # Running Training Stress Score
    intensity_factor = Column(Float, nullable=True) # IF = GAP / ThresholdPace
    
    # Zone Distributions (stored as JSON arrays/dicts)
    hr_zone_seconds = Column(JSON, nullable=True) # {"z1": 600, "z2": 1800, ...}
    pace_zone_seconds = Column(JSON, nullable=True)
    
    # Data quality: which channels the device actually provided, how much of
    # the session they covered, and why any metric was withheld.
    hr_coverage = Column(Float, default=0.0) # 0-1 fraction of session with a real HR sample
    data_quality = Column(JSON, nullable=True)

    # Metadata
    calories_kcal = Column(Float, nullable=True)
    vo2_max = Column(Float, nullable=True)
    source = Column(String(32), default="health_connect") # health_connect, gpx, fit, manual
    raw_payload_path = Column(String(512), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    splits = relationship("ActivitySplit", back_populates="activity", cascade="all, delete-orphan")
    streams = relationship("ActivityStream", back_populates="activity", uselist=False, cascade="all, delete-orphan")
    best_efforts = relationship("BestEffort", back_populates="activity", cascade="all, delete-orphan")


class ActivityStream(Base):
    __tablename__ = "activity_streams"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    activity_id = Column(String(64), ForeignKey("activities.id", ondelete="CASCADE"), unique=True, index=True)
    
    # Compressed / Structured JSON data containing arrays of:
    # time, lat, lng, altitude, distance, speed, heart_rate, cadence, grade, gap_speed
    stream_data = Column(JSON, nullable=False)
    
    activity = relationship("Activity", back_populates="streams")


class ActivitySplit(Base):
    __tablename__ = "activity_splits"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    activity_id = Column(String(64), ForeignKey("activities.id", ondelete="CASCADE"), index=True)
    split_number = Column(Integer, nullable=False) # 1, 2, 3...
    distance_meters = Column(Float, nullable=False) # usually 1000m
    elapsed_time_sec = Column(Float, nullable=False)
    pace_sec_km = Column(Float, nullable=False)
    gap_sec_km = Column(Float, nullable=True)
    avg_hr = Column(Integer, nullable=True)
    avg_cadence = Column(Float, nullable=True)
    elevation_diff_m = Column(Float, nullable=True)
    aerobic_efficiency = Column(Float, nullable=True)
    is_partial = Column(Boolean, default=False) # trailing sub-kilometre segment
    
    activity = relationship("Activity", back_populates="splits")


class BestEffort(Base):
    __tablename__ = "best_efforts"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    activity_id = Column(String(64), ForeignKey("activities.id", ondelete="CASCADE"), index=True)
    distance_meters = Column(Float, nullable=False) # 400, 800, 1000, 1609.34, 5000, 10000, 21097, 42195
    label = Column(String(32), nullable=False) # "400m", "1k", "1 Mile", "5k", "10k", "Half", "Marathon"
    time_seconds = Column(Float, nullable=False)
    pace_sec_km = Column(Float, nullable=False)
    start_time_offset_sec = Column(Float, nullable=False)
    achieved_at = Column(DateTime, nullable=False, index=True)
    is_personal_record = Column(Boolean, default=False)
    
    activity = relationship("Activity", back_populates="best_efforts")


class DailyHealth(Base):
    __tablename__ = "daily_health"
    
    date = Column(Date, primary_key=True, index=True)
    resting_hr = Column(Integer, nullable=True)
    hrv_rmssd = Column(Float, nullable=True) # Heart Rate Variability RMSSD in ms
    sleep_duration_sec = Column(Float, nullable=True)
    sleep_score = Column(Float, nullable=True)
    vo2_max = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)
    
    # Performance Management Chart (PMC) calculated metrics
    daily_tss = Column(Float, default=0.0)
    ctl = Column(Float, default=0.0) # Chronic Training Load ("Fitness" ~42-day EWMA)
    atl = Column(Float, default=0.0) # Acute Training Load ("Fatigue" ~7-day EWMA)
    tsb = Column(Float, default=0.0) # Training Stress Balance ("Form" = CTL - ATL)
    acwr = Column(Float, default=0.0) # Acute:Chronic Workload Ratio
    readiness_score = Column(Float, nullable=True) # 0 - 100 calculated recovery score
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserProfile(Base):
    __tablename__ = "user_profile"
    
    id = Column(Integer, primary_key=True, default=1)
    name = Column(String(128), default="Runner")
    gender = Column(String(16), default="male")
    max_hr = Column(Integer, default=190)
    resting_hr = Column(Integer, default=50)
    lthr = Column(Integer, default=168) # Lactate Threshold HR
    threshold_pace_sec = Column(Float, default=240.0) # 4:00/km
    weight_kg = Column(Float, default=70.0)
    
    # Custom zone configurations (JSON)
    hr_zones = Column(JSON, nullable=True) # {"z1": [0, 130], "z2": [131, 150], ...}
    pace_zones = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
