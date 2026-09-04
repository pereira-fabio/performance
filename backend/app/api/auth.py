"""
Accounts and sessions.

The first account created claims any data that predates accounts, so an
existing single-athlete install keeps its history instead of starting empty.
Every account after that starts clean and sees only its own.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.avatars import remove_avatar
from backend.app.services import garmin_connector
from backend.app.core.security import (
    hash_password, verify_password, new_token, password_problem,
)
from sqlalchemy import or_

from backend.app.models.models import (
    User, AuthToken, Activity, DailyHealth, UserProfile, BestEffort,
    CycleEntry, DeviceConnection, Insight,
)


def _unowned(column):
    """
    Rows predating accounts.

    Two shapes exist: a nullable column left NULL, and a NOT NULL column the
    migration filled with an empty string. Both mean the same thing.
    """
    return or_(column.is_(None), column == "")

router = APIRouter(prefix="/auth", tags=["Accounts"])


class Credentials(BaseModel):
    """Registration, where the constraints belong."""
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    display_name: Optional[str] = Field(default=None, max_length=128)
    # health_connect for Android, file_import for Garmin, Polar, Coros and the
    # rest -- anything that exports files but has no Health Connect.
    data_source: Optional[str] = Field(default="health_connect")


class Session_(BaseModel):
    token: str
    username: str
    display_name: Optional[str]
    user_id: str
    is_admin: bool = False
    data_source: str = "health_connect"
    cycle_tracking: bool = False
    claimed_existing_data: bool = False


class Me(BaseModel):
    user_id: str
    username: str
    display_name: Optional[str]
    is_admin: bool = False
    data_source: str = "health_connect"
    cycle_tracking: bool = False


def _issue(db: Session, user: User, label: Optional[str]) -> str:
    token = new_token()
    db.add(AuthToken(token=token, user_id=user.id, label=label))
    db.commit()
    return token


def current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the caller from their bearer token.

    Rejecting unauthenticated requests outright is deliberate: with several
    people on one network, serving anyone's data to an anonymous caller would
    defeat the point of having accounts at all.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")

    raw = authorization.split(" ", 1)[1].strip()
    row = db.query(AuthToken).filter(AuthToken.token == raw).first()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, sign in again")

    user = db.query(User).filter(User.id == row.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is no longer active")

    row.last_used_at = datetime.utcnow()
    db.commit()
    return user


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    """Whether anyone has registered yet, so clients can offer the right screen."""
    count = db.query(User).count()
    return {
        "has_accounts": count > 0,
        "accounts": count,
        # Data written before accounts existed, waiting to be claimed.
        "unclaimed_activities": db.query(Activity).filter(_unowned(Activity.user_id)).count(),
    }


@router.post("/register", response_model=Session_)
def register(body: Credentials, db: Session = Depends(get_db)):
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)

    username = body.username.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is taken")

    first_account = db.query(User).count() == 0
    user = User(
        username=username,
        display_name=(body.display_name or body.username).strip(),
        password_hash=hash_password(body.password),
        is_admin=first_account,
        data_source=(body.data_source or "health_connect"),
    )
    db.add(user)
    db.flush()

    claimed = False
    if first_account:
        # A single-athlete install upgrading to accounts: the history is theirs.
        moved_activities = (
            db.query(Activity).filter(_unowned(Activity.user_id))
            .update({"user_id": user.id}, synchronize_session=False)
        )
        db.query(DailyHealth).filter(_unowned(DailyHealth.user_id)).update(
            {"user_id": user.id}, synchronize_session=False
        )
        db.query(UserProfile).filter(_unowned(UserProfile.user_id)).update(
            {"user_id": user.id}, synchronize_session=False
        )
        claimed = moved_activities > 0

    db.commit()
    return Session_(
        token=_issue(db, user, "register"), username=user.username,
        display_name=user.display_name, user_id=user.id,
        is_admin=bool(user.is_admin), data_source=user.data_source or "health_connect",
        cycle_tracking=bool(user.cycle_tracking),
        claimed_existing_data=claimed,
    )


class LoginCredentials(BaseModel):
    """
    Signing in, where they do not.

    A rule tightened after an account was made would otherwise lock that
    account out permanently: the username is only a lookup key here, and
    validating it decides nothing.
    """
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


@router.post("/login", response_model=Session_)
def login(body: LoginCredentials, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip().lower()).first()
    # The same message either way: distinguishing them tells an attacker which
    # usernames exist.
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    return Session_(
        token=_issue(db, user, "login"), username=user.username,
        display_name=user.display_name, user_id=user.id,
        is_admin=bool(user.is_admin), data_source=user.data_source or "health_connect",
        cycle_tracking=bool(user.cycle_tracking),
    )


class SourcePatch(BaseModel):
    data_source: str


@router.patch("/me/source", response_model=Me)
def set_data_source(
    body: SourcePatch, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Switch between reading Health Connect and importing files."""
    if body.data_source not in ("health_connect", "file_import"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown data source")
    user.data_source = body.data_source
    db.commit()
    return Me(user_id=user.id, username=user.username, display_name=user.display_name,
              is_admin=bool(user.is_admin), data_source=user.data_source,
              cycle_tracking=bool(user.cycle_tracking))


@router.post("/logout")
def logout(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        db.query(AuthToken).filter(AuthToken.token == raw).delete()
        db.commit()
    return {"status": "signed out"}


class DeleteRequest(BaseModel):
    password: str
    # Typed out in full, so a stray click cannot destroy a year of training.
    confirm: str = Field(description='Must be the word DELETE')


@router.delete("/me")
def delete_account(
    body: DeleteRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Erase this account and everything belonging to it.

    Deletion is explicit rather than relying on foreign keys: SQLite only
    enforces ON DELETE CASCADE when the connection asks it to, and this is not
    an operation to leave depending on a pragma being set.

    Backups are untouched by design. Someone who deletes an account today
    should not silently un-delete it by restoring last week, so the operator
    prunes backups on their own schedule.
    """
    from backend.app.models.models import ActivityStream, ActivitySplit

    if body.confirm.strip().upper() != "DELETE":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Type DELETE to confirm')
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password")

    ids = [a.id for a in db.query(Activity.id).filter(Activity.user_id == user.id).all()]
    removed = {"activities": len(ids)}

    if ids:
        for model in (BestEffort, ActivitySplit, ActivityStream):
            db.query(model).filter(model.activity_id.in_(ids)).delete(synchronize_session=False)
        db.query(Activity).filter(Activity.user_id == user.id).delete(synchronize_session=False)

    removed["daily_health"] = (
        db.query(DailyHealth).filter(DailyHealth.user_id == user.id)
        .delete(synchronize_session=False)
    )
    db.query(UserProfile).filter(UserProfile.user_id == user.id).delete(synchronize_session=False)
    # Deleted explicitly rather than left to the foreign key: SQLite does not
    # enforce ON DELETE CASCADE unless the pragma is set, so these rows would
    # otherwise outlive the account that owned them.
    db.query(CycleEntry).filter(CycleEntry.user_id == user.id).delete(synchronize_session=False)
    # Written commentary about this athlete's training, and the link to their
    # watch account -- which holds the email it was linked with.
    db.query(Insight).filter(Insight.user_id == user.id).delete(synchronize_session=False)
    db.query(DeviceConnection).filter(
        DeviceConnection.user_id == user.id).delete(synchronize_session=False)
    remove_avatar(user.id)
    # The session tokens are files, not rows, so no cascade would ever have
    # reached them. They stay valid against Garmin until they expire.
    garmin_connector.disconnect(user.id)
    db.query(AuthToken).filter(AuthToken.user_id == user.id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
    db.commit()

    return {
        "status": "deleted",
        "removed": removed,
        "note": "Existing backups still contain this data until they are pruned.",
    }


@router.get("/export")
def export_my_data(
    include_streams: bool = True,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Everything belonging to the signed-in athlete, as portable JSON.

    This is not a backup. A backup restores the whole system atomically and is
    the operator's concern; this is one athlete's own data, in a form they can
    take elsewhere or keep independently of this server. Splitting the backup
    per athlete instead would leave no consistent restore point.

    Streams are the bulk of it -- a year of running is tens of megabytes -- so
    they can be left out for a summary that stays small.
    """
    from backend.app.models.models import ActivityStream, ActivitySplit

    activities = (
        db.query(Activity).filter(Activity.user_id == user.id)
        .order_by(Activity.start_time.asc()).all()
    )
    ids = [a.id for a in activities]

    streams = {}
    if include_streams and ids:
        for s in db.query(ActivityStream).filter(ActivityStream.activity_id.in_(ids)):
            streams[s.activity_id] = s.stream_data

    splits: dict = {}
    for sp in db.query(ActivitySplit).filter(ActivitySplit.activity_id.in_(ids or [""])):
        splits.setdefault(sp.activity_id, []).append({
            c.name: getattr(sp, c.name) for c in sp.__table__.columns
            if c.name not in ("id", "activity_id")
        })

    efforts: dict = {}
    for be in db.query(BestEffort).filter(BestEffort.activity_id.in_(ids or [""])):
        efforts.setdefault(be.activity_id, []).append({
            c.name: getattr(be, c.name) for c in be.__table__.columns
            if c.name not in ("id", "activity_id")
        })

    def row(obj, skip=()):
        return {
            c.name: getattr(obj, c.name)
            for c in obj.__table__.columns if c.name not in skip
        }

    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()

    return {
        "format": "performance.export.v1",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "account": {"username": user.username, "display_name": user.display_name},
        "profile": row(profile, skip=("id", "user_id")) if profile else None,
        "daily_health": [
            row(h, skip=("user_id",))
            for h in db.query(DailyHealth).filter(DailyHealth.user_id == user.id)
                       .order_by(DailyHealth.date.asc())
        ],
        # Included because "export everything" has to mean everything; an
        # export that quietly omits the most personal thing stored is not one.
        "cycle_entries": [
            row(c, skip=("user_id",))
            for c in db.query(CycleEntry).filter(CycleEntry.user_id == user.id)
                       .order_by(CycleEntry.date.asc())
        ],
        "activities": [
            {
                **row(a, skip=("user_id",)),
                "splits": splits.get(a.id, []),
                "best_efforts": efforts.get(a.id, []),
                **({"stream": streams.get(a.id)} if include_streams else {}),
            }
            for a in activities
        ],
    }


@router.get("/me", response_model=Me)
def me(user: User = Depends(current_user)):
    return Me(user_id=user.id, username=user.username,
              display_name=user.display_name, is_admin=bool(user.is_admin),
              data_source=user.data_source or "health_connect",
              cycle_tracking=bool(user.cycle_tracking))
