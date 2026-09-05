from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.core.database import get_db
from backend.app.core.sports import WORKOUT_TAGS, is_valid_tag
from backend.app.models.models import Activity, ActivityStream
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

    for field, value in sent.items():
        if field in ("name", "notes", "workout_tag") and isinstance(value, str):
            value = value.strip() or None
        setattr(activity, field, value)

    # A name is not optional: emptying it would leave a row with nothing to
    # call it in any list it appears in.
    if not (activity.name or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A name is required.")

    db.commit()
    db.refresh(activity)
    return activity
