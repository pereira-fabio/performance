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
from backend.app.core.security import (
    hash_password, verify_password, new_token, password_problem,
)
from sqlalchemy import or_

from backend.app.models.models import User, AuthToken, Activity, DailyHealth, UserProfile


def _unowned(column):
    """
    Rows predating accounts.

    Two shapes exist: a nullable column left NULL, and a NOT NULL column the
    migration filled with an empty string. Both mean the same thing.
    """
    return or_(column.is_(None), column == "")

router = APIRouter(prefix="/auth", tags=["Accounts"])


class Credentials(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    display_name: Optional[str] = Field(default=None, max_length=128)


class Session_(BaseModel):
    token: str
    username: str
    display_name: Optional[str]
    user_id: str
    claimed_existing_data: bool = False


class Me(BaseModel):
    user_id: str
    username: str
    display_name: Optional[str]


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
        claimed_existing_data=claimed,
    )


@router.post("/login", response_model=Session_)
def login(body: Credentials, db: Session = Depends(get_db)):
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
    )


@router.post("/logout")
def logout(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        db.query(AuthToken).filter(AuthToken.token == raw).delete()
        db.commit()
    return {"status": "signed out"}


@router.get("/me", response_model=Me)
def me(user: User = Depends(current_user)):
    return Me(user_id=user.id, username=user.username, display_name=user.display_name)
