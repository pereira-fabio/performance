from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import traceback
import gpxpy

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.models.schemas import HealthConnectSessionPayload, DailyHealthPayload, ActivityDetailOut
from backend.app.models.models import DailyHealth, Activity
from backend.app.services.activity_processor import ActivityProcessor

router = APIRouter(prefix="/sync", tags=["Sync & Ingestion"])

def verify_token(authorization: Optional[str] = Header(None)):
    # An empty token leaves sync open, which is the default for an isolated
    # home network. Setting API_AUTH_TOKEN to anything enforces it.
    if settings.API_AUTH_TOKEN:
        if not authorization or authorization.replace("Bearer ", "") != settings.API_AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid sync authentication token")
    return True

@router.post("/session", response_model=ActivityDetailOut)
def sync_session(
    payload: HealthConnectSessionPayload,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_token)
):
    """
    Primary ingestion endpoint for the Android Health Connect companion app.
    Ingests exercise session with GPS route, HR series, cadence series, and speed series.
    """
    try:
        processor = ActivityProcessor(db)
        activity = processor.process_health_connect_session(payload)
        return activity
    except ValueError as e:
        # The session parsed but carries nothing usable. This is a property of
        # the data, not a server fault, so say exactly what was missing.
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        db.rollback()
        print(f"❌ Error syncing workout {payload.session_id}:")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to process workout session: {str(e)}")

@router.post("/daily-health")
def sync_daily_health(
    payload: DailyHealthPayload,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_token)
):
    """
    Syncs daily wellness metrics from Health Connect (Resting HR, HRV RMSSD, Sleep, VO2 Max).
    """
    try:
        record = db.query(DailyHealth).filter(DailyHealth.date == payload.date).first()
        if not record:
            record = DailyHealth(date=payload.date)
            db.add(record)
            
        if payload.resting_hr is not None:
            record.resting_hr = payload.resting_hr
        if payload.hrv_rmssd is not None:
            record.hrv_rmssd = payload.hrv_rmssd
        if payload.sleep_duration_sec is not None:
            record.sleep_duration_sec = payload.sleep_duration_sec
        if payload.sleep_score is not None:
            record.sleep_score = payload.sleep_score
        if payload.vo2_max is not None:
            record.vo2_max = payload.vo2_max
        if payload.steps is not None:
            record.steps = payload.steps
            
        db.commit()
        
        processor = ActivityProcessor(db)
        processor._update_daily_pmc(payload.date)
        
        return {"status": "success", "date": str(payload.date)}
    except Exception as e:
        db.rollback()
        print(f"❌ Error syncing daily health for {payload.date}:")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to process daily health: {str(e)}")

@router.post("/upload-gpx", response_model=ActivityDetailOut)
async def upload_gpx(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    gpx = gpxpy.parse(contents.decode("utf-8", errors="ignore"))
    
    route_points = []
    hr_series = []
    
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                route_points.append({
                    "time": pt.time,
                    "lat": pt.latitude,
                    "lng": pt.longitude,
                    "altitude": pt.elevation,
                    "speed": pt.speed
                })
                for ext in pt.extensions:
                    for child in ext:
                        if "hr" in child.tag.lower() or "heartrate" in child.tag.lower():
                            try:
                                hr_series.append({"time": pt.time, "bpm": int(child.text)})
                            except ValueError:
                                pass
                                
    if not route_points:
        raise HTTPException(status_code=400, detail="No GPS track points found in GPX file")

    route_points = [p for p in route_points if p["time"] is not None]
    if not route_points:
        raise HTTPException(
            status_code=422,
            detail="GPX track points carry no timestamps, so no timeline can be built.",
        )

    session_id = f"gpx_{file.filename}_{int(route_points[0]['time'].timestamp())}"
    payload = HealthConnectSessionPayload(
        session_id=session_id,
        title=gpx.name or file.filename.replace(".gpx", ""),
        sport_type="running",
        start_time=route_points[0]["time"],
        end_time=route_points[-1]["time"],
        route_points=route_points,
        heart_rate_series=hr_series
    )
    
    try:
        processor = ActivityProcessor(db)
        return processor.process_health_connect_session(payload)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
