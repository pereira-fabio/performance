#!/usr/bin/env python3
"""
Scheduled database backups.

A thin wrapper: the logic lives in backend/app/core/backup.py so this and the
admin console cannot drift apart.

    python /data/backup.py            # one snapshot
    python /data/backup.py --force    # even if nothing changed
    python /data/backup.py --loop     # keep going, BACKUP_INTERVAL_SEC apart

Restoring:

    gunzip -c /data/backups/peakpace_<stamp>.db.gz > /tmp/restore.db
    docker cp /tmp/restore.db performance-backend:/db/peakpace.db
"""
import os
import sys
import time
from datetime import datetime

sys.path.append("/app")

from backend.app.core.backup import run_once, prune  # noqa: E402

INTERVAL_SEC = int(os.getenv("BACKUP_INTERVAL_SEC", "86400"))


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def main() -> int:
    force = "--force" in sys.argv
    if "--loop" not in sys.argv:
        try:
            run_once(force=force, log=log)
            return 0
        except Exception:
            return 1

    log(f"Backup loop started; every {INTERVAL_SEC}s "
        f"(retention {os.getenv('BACKUP_RETENTION_DAYS', '7')} days)")
    while True:
        try:
            run_once(force=force, log=log)
        except Exception:
            pass  # Already reported; a failed run must not stop the schedule.
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
