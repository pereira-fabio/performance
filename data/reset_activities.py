#!/usr/bin/env python3
"""
Wipe stored activities so they can be re-synced from scratch.

Takes a real backup first -- using the snapshot-locally-then-copy method the
scheduled backup should have been using all along -- and deliberately keeps the
things that cannot be re-synced:

  * user_profile: your max HR, LTHR and threshold pace
  * daily_health wellness columns: resting HR, HRV, sleep, steps
    (the phone only re-sends the last 30 days of these)

Everything derived from activities is cleared and will be rebuilt on sync.

    docker exec -it peakpace-backend python /data/reset_activities.py
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB = os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", "")
BACKUP_DIR = "/data/backups"


def main() -> int:
    if not os.path.exists(DB):
        print(f"No database at {DB}")
        return 1

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    local_tmp = f"/tmp/peakpace_pre_reset_{stamp}.db"
    final = os.path.join(BACKUP_DIR, f"peakpace_pre_reset_{stamp}.db")

    # Snapshot to local disk. SQLite needs locks the destination must support,
    # and a CIFS/SMB share generally cannot provide them -- which is why every
    # scheduled backup so far produced a 0-byte file.
    src = sqlite3.connect(DB)
    dst = sqlite3.connect(local_tmp)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    # copyfile, not copy2: an SMB/CIFS share will not allow utime() on the
    # destination, and copy2 would fail on that after the data was already
    # written. Only the contents matter here.
    shutil.copyfile(local_tmp, final)
    os.remove(local_tmp)
    size = os.path.getsize(final) / 1024
    if size < 1:
        print(f"Backup looks empty ({size:.1f} KB) - aborting rather than risk data.")
        return 1
    print(f"Backup written: {final} ({size:.1f} KB)")

    con = sqlite3.connect(DB)
    c = con.cursor()
    before = {
        t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("activities", "activity_streams", "activity_splits",
                  "best_efforts", "daily_health", "user_profile")
    }
    print("before:", before)

    c.execute("DELETE FROM best_efforts")
    c.execute("DELETE FROM activity_splits")
    c.execute("DELETE FROM activity_streams")
    c.execute("DELETE FROM activities")
    # Wellness stays; only the activity-derived training load is cleared.
    c.execute("UPDATE daily_health SET daily_tss=0, ctl=0, atl=0, tsb=0, acwr=0, readiness_score=NULL")
    con.commit()
    c.execute("VACUUM")
    con.commit()

    after = {
        t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("activities", "activity_streams", "activity_splits",
                  "best_efforts", "daily_health", "user_profile")
    }
    con.close()
    print("after: ", after)
    print("\nCleared. Kept user profile and daily wellness.")
    print("Now open the app and tap Sync Now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
