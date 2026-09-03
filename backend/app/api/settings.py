from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.models import UserProfile, Activity, User
from backend.app.api.auth import current_user
from backend.app.models.schemas import UserProfileSchema
from backend.app.services.activity_processor import ActivityProcessor

router = APIRouter(prefix="/settings", tags=["User Settings"])

@router.get("/profile", response_model=UserProfileSchema)
def get_user_profile(db: Session = Depends(get_db), user: User = Depends(current_user)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        profile = UserProfile(
            user_id=user.id,
            name=user.display_name or "Runner",
            max_hr=190,
            resting_hr=50,
            lthr=168,
            threshold_pace_sec=240.0,
            weight_kg=70.0
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

@router.put("/profile", response_model=UserProfileSchema)
def update_user_profile(payload: UserProfileSchema, db: Session = Depends(get_db), user: User = Depends(current_user)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    profile.name = payload.name
    profile.gender = payload.gender
    profile.max_hr = payload.max_hr
    profile.resting_hr = payload.resting_hr
    profile.lthr = payload.lthr
    profile.threshold_pace_sec = payload.threshold_pace_sec
    profile.weight_kg = payload.weight_kg
    if payload.hr_zones:
        user.hr_zones = payload.hr_zones
    if payload.pace_zones:
        user.pace_zones = payload.pace_zones
        
    db.commit()
    db.refresh(profile)
    return profile

@router.post("/recalculate")
def recalculate_all_metrics(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """
    Rebuilds the Performance Management Chart from the stored per-activity rTSS.

    Per-activity zones, TRIMP and rTSS are NOT recomputed here: doing that means
    replaying each stored stream through the ingestion pipeline, which is not
    implemented yet. Changing heart rate or pace thresholds therefore affects
    new activities and the PMC, but leaves the stored per-activity training load
    untouched.
    """
    processor = ActivityProcessor(db, user)
    activity_count = db.query(Activity).filter(Activity.user_id == user.id).count()
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
