"""
Server administration.

Everything here is deliberately narrow: managing accounts and inspecting
backups. It gives no route into another athlete's training data -- an
administrator can see that an account exists and how much it holds, and can
remove it, but not read it. Someone with database access can of course read
everything; that is a different level of trust and not one this API grants.
"""
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.auth import current_user
from backend.app.core.backup import list_backups, run_once, prune, _settings
from backend.app.core.database import get_db
from backend.app.models.models import (
    User, AuthToken, Activity, DailyHealth, UserProfile, BestEffort,
    ActivitySplit, ActivityStream, CycleEntry,
)

router = APIRouter(prefix="/admin", tags=["Administration"])


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


class AccountOut(BaseModel):
    id: str
    username: str
    display_name: Optional[str]
    is_admin: bool
    is_active: bool
    created_at: datetime
    activities: int
    last_activity: Optional[datetime]
    sessions: int


class AccountPatch(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


def _admin_count(db: Session) -> int:
    return db.query(User).filter(User.is_admin.is_(True), User.is_active.is_(True)).count()


@router.get("/users", response_model=List[AccountOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    out = []
    for u in db.query(User).order_by(User.created_at.asc()).all():
        acts = db.query(Activity).filter(Activity.user_id == u.id)
        last = acts.order_by(Activity.start_time.desc()).first()
        out.append(AccountOut(
            id=u.id, username=u.username, display_name=u.display_name,
            is_admin=bool(u.is_admin), is_active=bool(u.is_active),
            created_at=u.created_at, activities=acts.count(),
            last_activity=last.start_time if last else None,
            sessions=db.query(AuthToken).filter(AuthToken.user_id == u.id).count(),
        ))
    return out


@router.patch("/users/{user_id}", response_model=AccountOut)
def update_user(
    user_id: str, body: AccountPatch,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account")

    # Locking every administrator out of the console would leave no way back
    # in short of editing the database by hand.
    losing_admin = (body.is_admin is False or body.is_active is False) and target.is_admin
    if losing_admin and _admin_count(db) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This is the only administrator; promote another account first",
        )

    if body.is_active is not None:
        target.is_active = body.is_active
        if not body.is_active:
            # Disabling an account should end its sessions immediately, not
            # whenever its token happens to be checked next.
            db.query(AuthToken).filter(AuthToken.user_id == target.id).delete(
                synchronize_session=False)
    if body.is_admin is not None:
        target.is_admin = body.is_admin
    db.commit()

    db.refresh(target)
    acts = db.query(Activity).filter(Activity.user_id == target.id)
    last = acts.order_by(Activity.start_time.desc()).first()
    return AccountOut(
        id=target.id, username=target.username, display_name=target.display_name,
        is_admin=bool(target.is_admin), is_active=bool(target.is_active),
        created_at=target.created_at, activities=acts.count(),
        last_activity=last.start_time if last else None,
        sessions=db.query(AuthToken).filter(AuthToken.user_id == target.id).count(),
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account")
    if target.id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Use Settings to delete your own account, where it asks for your password",
        )
    if target.is_admin and _admin_count(db) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot remove the only administrator")

    # Read what the response needs before the row goes: afterwards SQLAlchemy
    # expires the instance and touching an attribute raises.
    username = target.username
    target_id = target.id

    ids = [a.id for a in db.query(Activity.id).filter(Activity.user_id == target.id).all()]
    if ids:
        for model in (BestEffort, ActivitySplit, ActivityStream):
            db.query(model).filter(model.activity_id.in_(ids)).delete(synchronize_session=False)
        db.query(Activity).filter(Activity.user_id == target.id).delete(synchronize_session=False)
    db.query(DailyHealth).filter(DailyHealth.user_id == target.id).delete(synchronize_session=False)
    db.query(UserProfile).filter(UserProfile.user_id == target.id).delete(synchronize_session=False)
    # Deleted explicitly rather than left to the foreign key: SQLite does not
    # enforce ON DELETE CASCADE unless the pragma is set, so these rows would
    # otherwise outlive the account that owned them.
    db.query(CycleEntry).filter(CycleEntry.user_id == target.id).delete(synchronize_session=False)
    db.query(AuthToken).filter(AuthToken.user_id == target.id).delete(synchronize_session=False)
    db.query(User).filter(User.id == target.id).delete(synchronize_session=False)
    db.commit()

    return {"status": "deleted", "username": username, "user_id": target_id,
            "activities_removed": len(ids)}


@router.get("/backups")
def backups(_: User = Depends(require_admin)):
    cfg = _settings()
    files = list_backups()
    total = sum(b.size for b in files)
    return {
        "directory": cfg["dir"],
        "retention_days": cfg["retention_days"],
        "keep_minimum": cfg["keep_minimum"],
        "compressed": cfg["compress"],
        "count": len(files),
        "total_mb": round(total / 1048576, 1),
        "backups": [b.as_dict() for b in files],
    }


@router.post("/backups")
def create_backup(_: User = Depends(require_admin)):
    try:
        result = run_once(force=True)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Backup failed: {exc}")
    if not result:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No database to back up")
    return result


@router.delete("/backups")
def prune_backups(_: User = Depends(require_admin)):
    removed = prune()
    return {"status": "pruned", "removed": removed}


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    files = list_backups()
    newest = files[0] if files else None
    db_path = _settings()["db"]
    return {
        "accounts": db.query(User).count(),
        "active_accounts": db.query(User).filter(User.is_active.is_(True)).count(),
        "activities": db.query(Activity).count(),
        "unowned_activities": db.query(Activity).filter(Activity.user_id.is_(None)).count(),
        "database_mb": round(os.path.getsize(db_path) / 1048576, 1)
        if os.path.exists(db_path) else None,
        "backups": len(files),
        "backup_total_mb": round(sum(b.size for b in files) / 1048576, 1),
        "newest_backup": newest.as_dict() if newest else None,
    }
