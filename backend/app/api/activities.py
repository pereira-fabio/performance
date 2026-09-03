from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.core.database import get_db
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
