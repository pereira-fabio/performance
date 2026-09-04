import os

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.models import UserProfile, Activity, User
from backend.app.api.auth import current_user
from backend.app.models.schemas import UserProfileSchema
from backend.app.services.activity_processor import ActivityProcessor
from backend.app.physiology.body import composition
from backend.app.services.avatars import (
    MAX_AVATAR_BYTES, avatar_path, media_type_of, remove_avatar, sniff, store,
)

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
    out = UserProfileSchema.model_validate(profile)
    out.has_avatar = avatar_path(user.id) is not None
    out.composition = composition(profile)
    return out

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
    profile.height_cm = payload.height_cm
    profile.neck_cm = payload.neck_cm
    profile.waist_cm = payload.waist_cm
    profile.hip_cm = payload.hip_cm
    profile.birth_date = payload.birth_date
    # These belong to the profile, not the account. Assigned to the account they
    # went nowhere: SQLAlchemy lets you set any attribute on an instance, so
    # custom zones were silently discarded on every save.
    if payload.hr_zones:
        profile.hr_zones = payload.hr_zones
    if payload.pace_zones:
        profile.pace_zones = payload.pace_zones

    db.commit()
    db.refresh(profile)
    out = UserProfileSchema.model_validate(profile)
    out.has_avatar = avatar_path(user.id) is not None
    out.composition = composition(profile)
    return out

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


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
):
    """
    Store a picture for the athlete.

    The browser scales it to a small square before it gets here, so this only
    has to reject what should never have been sent: something that is not an
    image, or something far larger than a scaled one could be.
    """
    data = await file.read(MAX_AVATAR_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is empty.")
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            "That picture is too large.")
    kind = sniff(data)
    if kind is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "That is not a PNG, JPEG or WebP image.")
    extension, _ = kind

    store(user.id, data, extension)
    return {"stored": True, "bytes": len(data)}


@router.get("/avatar")
def read_avatar(user: User = Depends(current_user)):
    """The athlete's own picture. Behind the session like everything else."""
    path = avatar_path(user.id)
    if not path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No picture set.")
    with open(path, "rb") as handle:
        data = handle.read()
    return Response(content=data, media_type=media_type_of(path),
                    headers={"Cache-Control": "no-cache"})


@router.delete("/avatar")
def delete_avatar(user: User = Depends(current_user)):
    remove_avatar(user.id)
    return {"stored": False}
