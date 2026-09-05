import os

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.sports import RUNNING_SPORTS
from backend.app.models.models import UserProfile, Activity, BestEffort, User
from backend.app.api.auth import current_user
from backend.app.models.schemas import UserProfileSchema
from backend.app.services.activity_processor import ActivityProcessor
from backend.app.physiology.body import composition
from backend.app.physiology.vo2max import (
    HOUR_EFFORT_MAX_SEC, HOUR_EFFORT_MIN_SEC, MAX_HOUR_EFFORT_SLOWDOWN,
    best_estimate, threshold_pace_from_vdot,
)
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


@router.get("/threshold-suggestion")
def threshold_suggestion(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """
    A threshold pace worked out from the athlete's own running.

    Threshold pace is the one figure in the profile nobody can simply read off
    a device, and left at its default every zone and every load figure is wrong.
    So it is derived two ways, in order of preference:

      1. The fastest run of about an hour. That is the definition of threshold
         -- the pace you could hold for one -- so a real one beats any model.
      2. Otherwise from VO2 max, measured or estimated, through the same
         oxygen-cost curve that produced it.

    Offered, never applied. An athlete who has measured their threshold in a
    test knows better than either of these, and overwriting that would make the
    zones worse.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()

    # VO2 max: whatever a device reported, else derived from a best effort.
    measured = (
        db.query(Activity.vo2_max)
        .filter(Activity.user_id == user.id, Activity.vo2_max.isnot(None))
        .order_by(Activity.start_time.desc()).first()
    )
    vo2 = measured[0] if measured else None
    vo2_estimated = False
    if vo2 is None:
        efforts = (
            db.query(BestEffort.distance_meters, BestEffort.time_seconds)
            .join(Activity, Activity.id == BestEffort.activity_id)
            .filter(Activity.user_id == user.id,
                    Activity.sport_type.in_(RUNNING_SPORTS))
            .all()
        )
        vo2 = best_estimate([(d, t) for d, t in efforts])
        vo2_estimated = vo2 is not None

    from_vo2 = threshold_pace_from_vdot(vo2)

    # The fastest sustained hour, which is the definition rather than a model of
    # it. Quickest rather than most recent: a steady hour understates threshold,
    # and the quickest one came closest to being the effort this describes.
    hour = (
        db.query(Activity)
        .filter(Activity.user_id == user.id,
                Activity.sport_type.in_(RUNNING_SPORTS),
                Activity.moving_time_sec >= HOUR_EFFORT_MIN_SEC,
                Activity.moving_time_sec <= HOUR_EFFORT_MAX_SEC,
                Activity.avg_pace_sec_km.isnot(None))
        .order_by(Activity.avg_pace_sec_km.asc())
        .first()
    )

    suggestion = None
    basis = None
    detail = None

    if hour is not None:
        pace = round(float(hour.avg_pace_sec_km), 1)
        # A steady hour far slower than the model says was an easy long run,
        # not a threshold effort. Taking it would set the threshold too slow,
        # and every load figure computed against it too high.
        plausible = from_vo2 is None or pace <= from_vo2 * MAX_HOUR_EFFORT_SLOWDOWN
        if plausible:
            suggestion, basis = pace, "hour_effort"
            detail = (f"your quickest hour-long run, "
                      f"{hour.start_time:%-d %B %Y}")

    if suggestion is None and from_vo2 is not None:
        suggestion, basis = from_vo2, "vo2max"
        detail = (f"a VO\u2082 max of {round(vo2)}"
                  + (", itself estimated from your best effort" if vo2_estimated else ""))

    return {
        "pace_sec_km": suggestion,
        "basis": basis,
        "detail": detail,
        "current_pace_sec_km": float(profile.threshold_pace_sec) if profile else None,
        "vo2_max": round(vo2, 1) if vo2 is not None else None,
        "vo2_max_estimated": vo2_estimated,
        "reason": None if suggestion else
                  "Not enough running yet — a hard effort of 5 km or longer is what this needs.",
    }
