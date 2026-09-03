from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.models import UserProfile, Activity
from backend.app.models.schemas import UserProfileSchema
from backend.app.services.activity_processor import ActivityProcessor

router = APIRouter(prefix="/settings", tags=["User Settings"])

@router.get("/profile", response_model=UserProfileSchema)
def get_user_profile(db: Session = Depends(get_db)):
    user = db.query(UserProfile).first()
    if not user:
        user = UserProfile(
            id=1,
            name="Runner",
            max_hr=190,
            resting_hr=50,
            lthr=168,
            threshold_pace_sec=240.0,
            weight_kg=70.0
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@router.put("/profile", response_model=UserProfileSchema)
def update_user_profile(payload: UserProfileSchema, db: Session = Depends(get_db)):
    user = db.query(UserProfile).first()
    if not user:
        user = UserProfile(id=1)
        db.add(user)
        
    user.name = payload.name
    user.gender = payload.gender
    user.max_hr = payload.max_hr
    user.resting_hr = payload.resting_hr
    user.lthr = payload.lthr
    user.threshold_pace_sec = payload.threshold_pace_sec
    user.weight_kg = payload.weight_kg
    if payload.hr_zones:
        user.hr_zones = payload.hr_zones
    if payload.pace_zones:
        user.pace_zones = payload.pace_zones
        
    db.commit()
    db.refresh(user)
    return user

@router.post("/recalculate")
def recalculate_all_metrics(db: Session = Depends(get_db)):
    """
    Rebuilds the Performance Management Chart from the stored per-activity rTSS.

    Per-activity zones, TRIMP and rTSS are NOT recomputed here: doing that means
    replaying each stored stream through the ingestion pipeline, which is not
    implemented yet. Changing heart rate or pace thresholds therefore affects
    new activities and the PMC, but leaves the stored per-activity training load
    untouched.
    """
    processor = ActivityProcessor(db)
    activity_count = db.query(Activity).count()
    processor._update_daily_pmc()

    return {
        "status": "success",
        "pmc_rebuilt": True,
        "activities_recomputed": 0,
        "activities_total": activity_count,
        "detail": (
            "PMC rebuilt from stored activity training loads. Per-activity zones "
            "and training load are not yet recomputed against new thresholds."
        ),
    }
