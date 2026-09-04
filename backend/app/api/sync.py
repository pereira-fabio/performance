from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import traceback

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.models.schemas import HealthConnectSessionPayload, DailyHealthPayload, ActivityDetailOut
from backend.app.models.models import DailyHealth, Activity, User
from backend.app.api.auth import current_user
from backend.app.services.activity_processor import ActivityProcessor
from backend.app.services.file_import import parse_any

router = APIRouter(prefix="/sync", tags=["Sync & Ingestion"])


@router.post("/session", response_model=ActivityDetailOut)
def sync_session(
    payload: HealthConnectSessionPayload,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """
    Primary ingestion endpoint for the Android Health Connect companion app.
    Ingests exercise session with GPS route, HR series, cadence series, and speed series.
    """
    try:
        processor = ActivityProcessor(db, user)
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
    user: User = Depends(current_user),
):
    """
    Syncs daily wellness metrics from Health Connect (Resting HR, HRV RMSSD, Sleep, VO2 Max).
    """
    try:
        record = (db.query(DailyHealth)
                  .filter(DailyHealth.user_id == user.id, DailyHealth.date == payload.date).first())
        if not record:
            record = DailyHealth(user_id=user.id, date=payload.date)
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
        
        processor = ActivityProcessor(db, user)
        processor._update_daily_pmc(payload.date)
        
        return {"status": "success", "date": str(payload.date)}
    except Exception as e:
        db.rollback()
        print(f"❌ Error syncing daily health for {payload.date}:")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to process daily health: {str(e)}")

@router.post("/import")
async def import_files(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """
    Import activities from exported files.

    Accepts GPX, TCX, FIT, and zip archives of them -- which is what Garmin's
    "Export All Data" produces. This is the path for anyone without Health
    Connect: a Garmin, Polar or Coros owner, or anyone on an iPhone.

    Files are processed independently so one unreadable activity in a bulk
    archive does not lose the rest of it.
    """
    processor = ActivityProcessor(db, user)
    imported, skipped, problems = 0, 0, []

    for upload in files:
        payloads, errors = parse_any(upload.filename or "upload", await upload.read())
        problems.extend(errors)
        for payload in payloads:
            try:
                processor.process_health_connect_session(payload)
                imported += 1
            except ValueError as exc:
                # Nothing usable in it; recorded rather than failing the batch.
                skipped += 1
                problems.append(f"{payload.session_id}: {exc}")
            except Exception as exc:
                db.rollback()
                skipped += 1
                problems.append(f"{payload.session_id}: {exc}")

    return {
        "imported": imported,
        "skipped": skipped,
        "problems": problems[:50],
        "problem_count": len(problems),
    }
