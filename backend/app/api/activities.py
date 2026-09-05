from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.core.database import get_db
from backend.app.core.sports import WORKOUT_TAGS, is_valid_tag
from backend.app.models.models import Activity, ActivitySplit, ActivityStream
from backend.app.physiology.progress import activity_xp
from backend.app.models.schemas import ActivitySummaryOut, ActivityDetailOut
from backend.app.api.auth import current_user
from backend.app.models.models import User

router = APIRouter(prefix="/activities", tags=["Activities"])

@router.get("", response_model=List[ActivitySummaryOut])
def list_activities(
    skip: int = 0,
    limit: int = Query(500, ge=1, le=2000),
    sport_type: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """List running activities ordered by start time descending."""
    query = db.query(Activity).filter(Activity.user_id == user.id)
    if sport_type:
        query = query.filter(Activity.sport_type == sport_type)
    return query.order_by(Activity.start_time.desc()).offset(skip).limit(limit).all()

# Declared before /{activity_id}: routes match in the order they are defined,
# and a literal path registered after a parameterised one is never reached --
# "tags" would simply be looked up as an activity id.
@router.get("/tags")
def workout_tags(_: User = Depends(current_user)):
    """The tag vocabulary, so the client never invents one the server rejects."""
    return {"tags": list(WORKOUT_TAGS)}


@router.get("/{activity_id}", response_model=ActivityDetailOut)
def get_activity_detail(
    activity_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Get rich activity detail with splits, best efforts, zones, and GPS stream."""
    activity = (db.query(Activity)
                .filter(Activity.id == activity_id, Activity.user_id == user.id).first())
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
        
    stream = db.query(ActivityStream).filter(ActivityStream.activity_id == activity_id).first()
    stream_payload = stream.stream_data if stream else None
    
    # Construct response
    res = ActivityDetailOut.model_validate(activity)
    res.stream_data = stream_payload
    return res

@router.delete("/{activity_id}")
def delete_activity(
    activity_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Delete an activity and recalculate PMC."""
    activity = (db.query(Activity)
                .filter(Activity.id == activity_id, Activity.user_id == user.id).first())
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
        
    date_to_update = activity.start_time.date()
    db.delete(activity)
    db.commit()
    
    from backend.app.services.activity_processor import ActivityProcessor
    processor = ActivityProcessor(db, user)
    processor._update_daily_pmc(date_to_update)
    
    return {"status": "success", "deleted_id": activity_id}


class ActivityEdit(BaseModel):
    """
    What an athlete may change about a recorded activity.

    Deliberately not the measurements. Distance, duration and heart rate are
    what everything else is computed from -- pace, load, zones, records, the
    fitness curve -- and editing one without replaying the session through the
    physiology engine leaves an activity whose figures disagree with each other.
    A wrong distance is a re-sync, not a correction.

    What is here is either descriptive, or a value the device simply never
    wrote and nothing downstream derives anything from.
    """
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    sport_type: Optional[str] = Field(default=None, max_length=64)
    workout_tag: Optional[str] = Field(default=None, max_length=32)
    notes: Optional[str] = None
    calories_kcal: Optional[float] = Field(default=None, ge=0, le=30000)
    steps: Optional[int] = Field(default=None, ge=0, le=500000)
    # Accepted only where the activity has no distance series behind it. See
    # the check in the handler for why that line is drawn there.
    distance_meters: Optional[float] = Field(default=None, ge=0, le=1_000_000)


@router.patch("/{activity_id}", response_model=ActivityDetailOut)
def edit_activity(
    activity_id: str,
    body: ActivityEdit,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """
    Correct or annotate one activity.

    Only the fields present in the request are touched, so clearing a value and
    leaving it alone are different requests rather than the same one.
    """
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id, Activity.user_id == user.id)
        .first()
    )
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such activity")

    sent = body.model_dump(exclude_unset=True)

    if "workout_tag" in sent and not is_valid_tag(sent["workout_tag"]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Tag must be one of {', '.join(WORKOUT_TAGS)}.",
        )
    if "sport_type" in sent:
        value = (sent["sport_type"] or "").strip().lower()
        if not value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A sport is required.")
        sent["sport_type"] = value

    # Distance is the one measurement that can be corrected, and only when
    # nothing was derived from a distance series. Splits exist exactly when
    # there was one, so they are the test: with splits, an edited total would
    # contradict the kilometres it is supposed to be the sum of. Without them
    # the distance and the duration are the whole activity, and a distance the
    # athlete knows is better than none -- a watch whose GPS failed still leaves
    # a runner who knows how far they went.
    if "distance_meters" in sent:
        has_series = (
            db.query(ActivitySplit)
            .filter(ActivitySplit.activity_id == activity.id).first() is not None
        )
        if has_series:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "This activity was recorded with a distance trace, so its total "
                "cannot be edited on its own — pace, splits and training load "
                "are all derived from it. Re-sync the activity instead.",
            )

    for field, value in sent.items():
        if field in ("name", "notes", "workout_tag") and isinstance(value, str):
            value = value.strip() or None
        setattr(activity, field, value)

    if "distance_meters" in sent:
        _apply_entered_distance(activity, sent["distance_meters"])

    # A name is not optional: emptying it would leave a row with nothing to
    # call it in any list it appears in.
    if not (activity.name or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A name is required.")

    db.commit()
    db.refresh(activity)
    return activity


def _apply_entered_distance(activity, distance) -> None:
    """
    Recompute what a hand-entered distance actually determines.

    Pace and speed follow from it directly. Training load does not: rTSS needs
    a pace series and there is none, so it stays as it was -- from heart rate,
    or absent. Nothing here fabricates the figures a distance trace would have
    given.

    The entry is recorded in data_quality, so a figure the athlete typed is
    never mistaken later for one a device measured.
    """
    quality = dict(activity.data_quality or {})
    unavailable = dict(quality.get("unavailable") or {})

    if distance and distance > 0 and activity.moving_time_sec:
        activity.distance_meters = float(distance)
        activity.avg_speed_mps = float(distance) / activity.moving_time_sec
        activity.avg_pace_sec_km = activity.moving_time_sec / (float(distance) / 1000.0)
        unavailable.pop("distance", None)
        unavailable.pop("pace", None)
        quality["distance_entered_by_hand"] = True
    else:
        activity.distance_meters = 0.0
        activity.avg_speed_mps = None
        activity.avg_pace_sec_km = None
        unavailable["distance"] = "the session recorded no distance"
        quality.pop("distance_entered_by_hand", None)

    quality["unavailable"] = unavailable
    activity.data_quality = quality
    activity.xp = activity_xp(
        activity.r_tss, activity.distance_meters, activity.moving_time_sec
    )
