"""
Linking a watch platform so activities arrive on their own.

Health Connect is read by the companion app on the athlete's own phone. Anyone
outside that -- a Garmin owner, or anyone on an iPhone -- needs the server to
fetch on their behalf, which is what this manages.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.auth import current_user
from backend.app.core.database import get_db
from backend.app.models.models import DeviceConnection, User
from backend.app.services import garmin_connector
from backend.app.services.activity_processor import ActivityProcessor

router = APIRouter(prefix="/connections", tags=["Device connections"])


class GarminCredentials(BaseModel):
    email: str
    password: str
    mfa_code: Optional[str] = None


class ConnectionOut(BaseModel):
    provider: str
    account_label: Optional[str]
    enabled: bool
    last_synced_at: Optional[datetime]
    last_status: Optional[str]
    last_ok: bool


@router.get("", response_model=Optional[ConnectionOut])
def get_connection(db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.query(DeviceConnection).filter(DeviceConnection.user_id == user.id).first()
    if not row:
        return None
    return ConnectionOut(
        provider=row.provider, account_label=row.account_label, enabled=bool(row.enabled),
        last_synced_at=row.last_synced_at, last_status=row.last_status,
        last_ok=bool(row.last_ok),
    )


@router.post("/garmin", response_model=ConnectionOut)
def connect_garmin(
    body: GarminCredentials,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """
    Link a Garmin Connect account.

    The password is used once to obtain session tokens and is not stored.
    Changing the Garmin password invalidates the link, which is the intended
    way to revoke it.
    """
    ok, message = garmin_connector.connect(
        user.id, body.email.strip(), body.password, body.mfa_code
    )
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, message)

    row = db.query(DeviceConnection).filter(DeviceConnection.user_id == user.id).first()
    if not row:
        row = DeviceConnection(user_id=user.id)
        db.add(row)
    row.provider = "garmin"
    row.account_label = body.email.strip()
    row.enabled = True
    row.last_status = "Connected, waiting for the first sync."
    row.last_ok = True
    # Switching to a polled connection means files are no longer the way in.
    user.data_source = "garmin"
    db.commit()
    db.refresh(row)

    return ConnectionOut(
        provider=row.provider, account_label=row.account_label, enabled=True,
        last_synced_at=row.last_synced_at, last_status=row.last_status, last_ok=True,
    )


@router.delete("")
def disconnect(db: Session = Depends(get_db), user: User = Depends(current_user)):
    garmin_connector.disconnect(user.id)
    db.query(DeviceConnection).filter(DeviceConnection.user_id == user.id).delete(
        synchronize_session=False)
    if user.data_source == "garmin":
        user.data_source = "file_import"
    db.commit()
    return {"status": "disconnected"}


@router.post("/sync")
def sync_now(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Pull anything new straight away, rather than waiting for the schedule."""
    row = db.query(DeviceConnection).filter(DeviceConnection.user_id == user.id).first()
    if not row or not row.enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No connection is linked")

    outcome = run_sync(db, user, row)
    if not outcome.ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, outcome.message)
    return {
        "imported": outcome.imported, "skipped": outcome.skipped,
        "found": outcome.found, "message": outcome.message,
    }


def run_sync(db: Session, user: User, row: DeviceConnection):
    """
    Shared by the endpoint and the scheduler, so a manual sync and an automatic
    one cannot behave differently.
    """
    processor = ActivityProcessor(db, user)

    def handle(payload):
        processor.process_health_connect_session(payload)

    outcome = garmin_connector.fetch_since(user.id, row.last_synced_at, handle)

    row.last_ok = outcome.ok
    row.last_status = outcome.message
    if outcome.ok:
        # Only claim to be up to date when the whole listing was worked
        # through. A batch that stopped early has history behind it, and
        # stamping "synced to now" would step over everything still queued and
        # never come back for it. Recording where it reached lets the next poll
        # carry on from there; the overlap the connector applies means the
        # boundary activity is simply re-offered and rejected as a duplicate.
        row.last_synced_at = (
            datetime.utcnow() if outcome.complete
            else (outcome.reached or row.last_synced_at)
        )
    if outcome.needs_reauth:
        row.enabled = False
    db.commit()
    return outcome
