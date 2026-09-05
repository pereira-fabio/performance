from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.core.database import get_db
from backend.app.core.sports import WORKOUT_TAGS, is_valid_tag
from backend.app.models.models import Activity, ActivitySplit, ActivityStream, UserProfile
from backend.app.physiology.progress import activity_xp
from backend.app.physiology.trimp import calculate_banister_trimp
from backend.app.services.activity_processor import ActivityProcessor, to_naive_utc
from datetime import datetime, timedelta
import uuid
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
class ManualActivity(BaseModel):
    """
    An activity the athlete enters themselves.

    Only what a person can actually know: what it was, when, how long, how far,
    and what their watch showed them. Nothing derived is accepted -- pace comes
    from distance over duration, and grade-adjusted pace, decoupling, fitness
    and fatigue are not offered at all, because a figure typed into those boxes
    would be indistinguishable from one this server computed and would quietly
    corrupt every trend built on them.
    """
    name: str = Field(min_length=1, max_length=255)
    sport_type: str = Field(max_length=64)
    start_time: datetime
    duration_sec: float = Field(gt=0, le=60 * 60 * 24)
    distance_meters: Optional[float] = Field(default=None, ge=0, le=1_000_000)
    avg_hr: Optional[int] = Field(default=None, ge=25, le=250)
    max_hr: Optional[int] = Field(default=None, ge=25, le=260)
    elevation_gain_m: Optional[float] = Field(default=None, ge=0, le=30000)
    calories_kcal: Optional[float] = Field(default=None, ge=0, le=30000)
    steps: Optional[int] = Field(default=None, ge=0, le=500000)
    workout_tag: Optional[str] = Field(default=None, max_length=32)
    notes: Optional[str] = None


@router.post("", response_model=ActivityDetailOut, status_code=status.HTTP_201_CREATED)
def create_activity(
    body: ManualActivity,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """
    Record an activity by hand.

    For a session that never reached the phone at all: a watch that failed to
    export it, a run on someone else's device, a race with nothing but a result.
    It is marked as entered by hand and never pretends to be more than it is.
    """
    if not is_valid_tag(body.workout_tag):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Tag must be one of {', '.join(WORKOUT_TAGS)}.",
        )
    sport = (body.sport_type or "").strip().lower()
    if not sport:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A sport is required.")
    if body.max_hr and body.avg_hr and body.max_hr < body.avg_hr:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Maximum heart rate cannot be below the average.",
        )

    start = to_naive_utc(body.start_time)
    end = start + timedelta(seconds=body.duration_sec)
    distance = float(body.distance_meters or 0.0)

    activity = Activity(
        user_id=user.id,
        # Prefixed so it can never collide with a synced id, and so a manual
        # entry is recognisable in the database without reading its quality.
        external_id=f"manual:{uuid.uuid4()}",
        name=body.name.strip(),
        sport_type=sport,
        start_time=start,
        end_time=end,
        # Nothing distinguishes moving from stopped in a figure someone typed.
        elapsed_time_sec=body.duration_sec,
        moving_time_sec=body.duration_sec,
        distance_meters=distance,
        avg_hr=body.avg_hr,
        max_hr=body.max_hr,
        elevation_gain_m=body.elevation_gain_m,
        calories_kcal=body.calories_kcal,
        steps=body.steps,
        workout_tag=body.workout_tag or None,
        notes=(body.notes or "").strip() or None,
        source="manual",
        hr_coverage=0.0,
    )
    if distance > 0:
        activity.avg_speed_mps = distance / body.duration_sec
        activity.avg_pace_sec_km = body.duration_sec / (distance / 1000.0)

    unavailable = {
        "gap_pace": "grade-adjusted pace needs a route and a speed trace",
        "aerobic_decoupling": "decoupling needs pace and heart rate over time",
        "splits": "splits need a distance-over-time series",
        "best_efforts": "best efforts need a distance-over-time series",
        "hr_zones": "time in zones needs a heart-rate series, not an average",
    }
    if distance <= 0:
        unavailable["distance"] = "not entered"
        unavailable["pace"] = "no distance, so pace cannot be derived"

    # A single average heart rate over a known duration is exactly the session
    # form of Banister TRIMP, so it is a real figure rather than a stand-in --
    # the same function the ingestion path uses, given one sample and the whole
    # duration as its step.
    if body.avg_hr:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        trimp, reason = calculate_banister_trimp(
            heart_rates=[float(body.avg_hr)],
            dt=body.duration_sec,
            max_hr=(profile.max_hr if profile else 190),
            resting_hr=(profile.resting_hr if profile else 50),
            gender=(profile.gender if profile else "male"),
        )
        if trimp is not None:
            activity.trimp_banister = trimp
            activity.r_tss = trimp
        elif reason:
            unavailable["r_tss"] = reason
    else:
        unavailable["r_tss"] = (
            "training load needs a pace trace or a heart rate; neither was entered"
        )

    activity.data_quality = {"entered_by_hand": True, "unavailable": unavailable}
    activity.xp = activity_xp(activity.r_tss, distance, body.duration_sec)

    db.add(activity)
    db.commit()

    # The fitness curve reads stored load, so it has to be rebuilt for the day
    # this lands on -- which may be months ago.
    ActivityProcessor(db, user)._update_daily_pmc(start.date())
    db.refresh(activity)
    return activity


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
