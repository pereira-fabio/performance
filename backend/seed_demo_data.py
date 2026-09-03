import sys
import os
import math
import random
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import SessionLocal, Base, engine
from backend.app.models.models import UserProfile, DailyHealth
from backend.app.models.schemas import HealthConnectSessionPayload, LocationPoint, HeartRateSample, SpeedSample, CadenceSample
from backend.app.services.activity_processor import ActivityProcessor

def generate_mock_run(
    session_id: str,
    title: str,
    start_time: datetime,
    target_dist_m: float,
    base_speed_mps: float, # e.g. 3.33 m/s = 5:00/km
    base_hr: int,          # e.g. 145 bpm
    hr_drift_slope: float, # cardiac drift multiplier
    elev_variation: float  # elevation variation
) -> HealthConnectSessionPayload:
    duration_sec = target_dist_m / base_speed_mps
    num_points = int(duration_sec)
    
    # Starting coordinates (Central Park, NY)
    start_lat = 40.785091
    start_lng = -73.968285
    
    route_points = []
    hr_samples = []
    speed_samples = []
    cadence_samples = []
    
    curr_time = start_time
    for i in range(0, num_points, 2): # sample every 2 sec
        t = start_time + timedelta(seconds=i)
        progress = i / num_points
        
        # Circular route around park
        angle = progress * 2 * math.pi
        lat = start_lat + 0.015 * math.sin(angle)
        lng = start_lng + 0.012 * math.cos(angle)
        altitude = 35.0 + elev_variation * math.sin(angle * 3)
        
        # Speed with micro-variations
        speed = base_speed_mps + random.uniform(-0.15, 0.15)
        
        # HR with physiological cardiac drift & elevation response
        hr = int(base_hr + (progress * hr_drift_slope) + (elev_variation * 0.4 * math.sin(angle * 3)) + random.randint(-2, 2))
        
        # Cadence (spm)
        cadence = 172.0 + random.uniform(-3, 3)
        
        route_points.append(LocationPoint(time=t, lat=lat, lng=lng, altitude=altitude, speed=speed))
        hr_samples.append(HeartRateSample(time=t, bpm=hr))
        speed_samples.append(SpeedSample(time=t, speed_mps=speed))
        cadence_samples.append(CadenceSample(time=t, spm=cadence))
        
    return HealthConnectSessionPayload(
        session_id=session_id,
        title=title,
        sport_type="running",
        start_time=start_time,
        end_time=start_time + timedelta(seconds=duration_sec),
        distance_meters=target_dist_m,
        duration_sec=duration_sec,
        elevation_gain_m=elev_variation * 4,
        elevation_loss_m=elev_variation * 4,
        route_points=route_points,
        heart_rate_series=hr_samples,
        speed_series=speed_samples,
        cadence_series=cadence_samples
    )

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    processor = ActivityProcessor(db)

    print("🌱 Seeding User Profile...")
    user = processor._get_or_create_user_profile()
    user.name = "Alex Runner"
    user.max_hr = 192
    user.resting_hr = 48
    user.lthr = 170
    user.threshold_pace_sec = 230.0 # 3:50/km
    db.commit()

    print("🌱 Seeding 60 Days of Daily Health (HRV, Resting HR, Sleep)...")
    today = datetime.utcnow().date()
    for day_offset in range(60, 0, -1):
        d = today - timedelta(days=day_offset)
        rhr = int(48 + random.randint(-3, 4))
        hrv = round(65.0 + random.uniform(-10, 12), 1)
        sleep_sec = 7.5 * 3600 + random.uniform(-3600, 3600)
        
        dh = db.query(DailyHealth).filter(DailyHealth.date == d).first()
        if not dh:
            dh = DailyHealth(date=d)
            db.add(dh)
        dh.resting_hr = rhr
        dh.hrv_rmssd = hrv
        dh.sleep_duration_sec = sleep_sec
        dh.steps = random.randint(8000, 16000)
    db.commit()

    print("🌱 Generating Realistic Workouts with Sports Science Dynamics...")
    
    # 1. Aerobic Base Run (Low Decoupling)
    run1 = generate_mock_run(
        session_id="mock_run_base_1",
        title="Aerobic Base Easy Run",
        start_time=datetime.utcnow() - timedelta(days=6, hours=15),
        target_dist_m=10200.0,
        base_speed_mps=3.33, # 5:00/km
        base_hr=142,
        hr_drift_slope=3.0,  # ~1.5% decoupling
        elev_variation=15.0
    )
    processor.process_health_connect_session(run1)

    # 2. Fast Tempo Interval Run
    run2 = generate_mock_run(
        session_id="mock_run_tempo_2",
        title="Threshold Tempo Session",
        start_time=datetime.utcnow() - timedelta(days=4, hours=14),
        target_dist_m=8000.0,
        base_speed_mps=4.15, # 4:01/km
        base_hr=164,
        hr_drift_slope=8.0,
        elev_variation=10.0
    )
    processor.process_health_connect_session(run2)

    # 3. 5k PR Effort
    run3 = generate_mock_run(
        session_id="mock_run_pr_3",
        title="5K All-Out Time Trial",
        start_time=datetime.utcnow() - timedelta(days=2, hours=16),
        target_dist_m=5000.0,
        base_speed_mps=4.45, # 3:45/km
        base_hr=172,
        hr_drift_slope=12.0,
        elev_variation=5.0
    )
    processor.process_health_connect_session(run3)

    # 4. Long Sunday Run (Cardiovascular Drift Demonstration)
    run4 = generate_mock_run(
        session_id="mock_run_long_4",
        title="Sunday Long Endurance Run",
        start_time=datetime.utcnow() - timedelta(hours=6),
        target_dist_m=16500.0,
        base_speed_mps=3.20, # 5:12/km
        base_hr=144,
        hr_drift_slope=14.0, # High drift > 5%
        elev_variation=25.0
    )
    processor.process_health_connect_session(run4)

    print("✅ Seed complete! 4 workouts and 60 days of PMC trends populated.")
    db.close()

if __name__ == "__main__":
    seed_database()
