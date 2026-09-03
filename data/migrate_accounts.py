#!/usr/bin/env python3
"""
Move an existing single-athlete database onto accounts.

Three changes cannot be made with ALTER TABLE in SQLite, so the affected tables
are rebuilt in the documented way -- create, copy, drop, rename -- inside one
transaction:

  activities     external_id was globally unique; it must now be unique only
                 per athlete, since two people can sync the same workout
  daily_health   keyed on date alone; must be keyed on athlete and date
  user_profile   keyed on a fixed id of 1; one row per athlete now

Existing rows are left with no owner on purpose. The first account registered
claims them, so the athlete who has been using this install keeps their year of
history rather than starting empty.

A verified backup is taken first and the migration refuses to run without one.

    docker exec -it performance-backend python /data/migrate_accounts.py
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB = os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", "")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/data/backups")


def backup() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    tmp = f"/tmp/pre_accounts_{stamp}.db"
    final = os.path.join(BACKUP_DIR, f"peakpace_pre_accounts_{stamp}.db")

    src, dst = sqlite3.connect(DB), sqlite3.connect(tmp)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    check = sqlite3.connect(tmp)
    if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("backup failed its integrity check")
    check.close()

    shutil.copyfile(tmp, final)
    os.remove(tmp)
    return final


def columns(c, table):
    return [r[1] for r in c.execute(f"PRAGMA table_info({table})")]


def main() -> int:
    if not os.path.exists(DB):
        print(f"No database at {DB}")
        return 1

    con = sqlite3.connect(DB)
    c = con.cursor()

    if "user_id" in columns(c, "daily_health") and "user_id" in columns(c, "activities"):
        print("Already migrated; nothing to do.")
        return 0

    path = backup()
    print(f"Backup written: {path} ({os.path.getsize(path)/1024:.0f} KB)\n")

    c.execute("PRAGMA foreign_keys=OFF")
    try:
        c.execute("BEGIN")

        # --- activities: owner column, and per-athlete uniqueness -----------
        if "user_id" not in columns(c, "activities"):
            c.execute("ALTER TABLE activities ADD COLUMN user_id VARCHAR(64)")
        for (name,) in c.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='activities'"
        ).fetchall():
            if name and "external_id" in name:
                c.execute(f"DROP INDEX IF EXISTS {name}")
        c.execute("CREATE INDEX IF NOT EXISTS ix_activities_external_id ON activities(external_id)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_activities_user_id ON activities(user_id)")
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_activity_user_external "
            "ON activities(user_id, external_id)"
        )
        print("activities: owner column added, uniqueness now per athlete")

        # --- daily_health: rebuild with a composite key ---------------------
        health_cols = columns(c, "daily_health")
        keep = [x for x in health_cols if x != "user_id"]
        c.execute("ALTER TABLE daily_health RENAME TO daily_health_old")
        c.execute(f"""
            CREATE TABLE daily_health (
                user_id VARCHAR(64) NOT NULL DEFAULT '',
                date DATE NOT NULL,
                {', '.join(f'{k} {"FLOAT" if k not in ("resting_hr","steps") else "INTEGER"}'
                           for k in keep if k != 'date' and k != 'updated_at')},
                updated_at DATETIME,
                PRIMARY KEY (user_id, date)
            )
        """)
        copy_cols = [k for k in keep]
        c.execute(
            f"INSERT INTO daily_health (user_id, {', '.join(copy_cols)}) "
            f"SELECT '', {', '.join(copy_cols)} FROM daily_health_old"
        )
        moved = c.execute("SELECT COUNT(*) FROM daily_health").fetchone()[0]
        c.execute("DROP TABLE daily_health_old")
        c.execute("CREATE INDEX IF NOT EXISTS ix_daily_health_user_id ON daily_health(user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_daily_health_date ON daily_health(date)")
        print(f"daily_health: rebuilt on (athlete, date), {moved} rows carried over")

        # --- user_profile: one row per athlete ------------------------------
        prof_cols = [x for x in columns(c, "user_profile") if x not in ("id", "user_id")]
        c.execute("ALTER TABLE user_profile RENAME TO user_profile_old")
        c.execute(f"""
            CREATE TABLE user_profile (
                id VARCHAR(64) NOT NULL PRIMARY KEY,
                user_id VARCHAR(64),
                {', '.join(f'{k} {"VARCHAR(128)" if k in ("name","gender") else "FLOAT"}'
                           for k in prof_cols if k not in ('hr_zones','pace_zones','updated_at'))},
                hr_zones JSON, pace_zones JSON, updated_at DATETIME
            )
        """)
        carry = [k for k in prof_cols]
        c.execute(
            f"INSERT INTO user_profile (id, user_id, {', '.join(carry)}) "
            f"SELECT lower(hex(randomblob(16))), NULL, {', '.join(carry)} FROM user_profile_old"
        )
        c.execute("DROP TABLE user_profile_old")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profile_user_id ON user_profile(user_id)")
        print("user_profile: rebuilt, one row per athlete")

        con.commit()
    except Exception as exc:
        con.rollback()
        print(f"\nMigration FAILED and was rolled back: {exc}")
        print(f"The database is unchanged. Backup remains at {path}")
        return 1
    finally:
        c.execute("PRAGMA foreign_keys=ON")

    unowned = c.execute("SELECT COUNT(*) FROM activities WHERE user_id IS NULL OR user_id=''").fetchone()[0]
    con.close()
    print(f"\nDone. {unowned} activities are waiting for an owner.")
    print("Register the first account in the web app and they will be claimed by it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
