#!/usr/bin/env python3
"""
Scheduled work: backups, and polling linked watch accounts.

One container rather than two. The tasks share nothing but a clock, and a
single loop makes their cadences visible together instead of buried in two
compose services.

    python /data/scheduler.py
"""
import os
import sys
import time
import traceback
from datetime import datetime, timedelta

sys.path.append("/app")

from backend.app.core.backup import run_once as run_backup          # noqa: E402
from backend.app.core.database import SessionLocal                  # noqa: E402
from backend.app.models.models import DeviceConnection, User        # noqa: E402

BACKUP_INTERVAL = int(os.getenv("BACKUP_INTERVAL_SEC", "86400"))
CONNECTION_INTERVAL = int(os.getenv("CONNECTION_POLL_SEC", "1800"))
TICK = 60


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def poll_connections():
    """Pull new activities for every linked account."""
    from backend.app.api.connections import run_sync

    db = SessionLocal()
    try:
        links = (
            db.query(DeviceConnection)
            .filter(DeviceConnection.enabled.is_(True))
            .all()
        )
        for link in links:
            user = db.query(User).filter(User.id == link.user_id).first()
            if not user or not user.is_active:
                continue
            try:
                outcome = run_sync(db, user, link)
                if outcome.imported or not outcome.ok:
                    log(f"{user.username} · {link.provider}: {outcome.message}")
            except Exception as exc:
                # One athlete's broken link must not stop everyone else's.
                db.rollback()
                log(f"{user.username} · {link.provider} failed: {exc}")
    finally:
        db.close()


def main() -> int:
    log(f"Scheduler started · backup every {BACKUP_INTERVAL}s · "
        f"connections every {CONNECTION_INTERVAL}s")

    next_backup = datetime.now()
    next_poll = datetime.now()

    while True:
        now = datetime.now()
        if now >= next_backup:
            try:
                run_backup(log=log)
            except Exception:
                traceback.print_exc()
            next_backup = now + timedelta(seconds=BACKUP_INTERVAL)
        if now >= next_poll:
            try:
                poll_connections()
            except Exception:
                traceback.print_exc()
            next_poll = now + timedelta(seconds=CONNECTION_INTERVAL)
        time.sleep(TICK)


if __name__ == "__main__":
    raise SystemExit(main())
