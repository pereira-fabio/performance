"""
Schema changes that ALTER TABLE cannot express.

SQLite cannot change a primary key or drop a unique constraint in place, so the
affected tables are rebuilt: create, copy, drop, rename, inside one
transaction. Running this at startup rather than leaving it to an operator is
deliberate -- a backend serving a database it has outgrown fails with opaque
500s, which is worse than a few seconds of work on boot.

Every step is idempotent, so a container restart costs nothing.
"""
import os
import shutil
import sqlite3
from datetime import datetime
from typing import List


def _columns(cur, table: str) -> List[str]:
    return [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]


def _table_exists(cur, table: str) -> bool:
    return cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _safety_copy(db_path: str) -> str:
    """Snapshot beside the database before restructuring it."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target_dir = os.getenv("BACKUP_DIR", "/data/backups")
    tmp = f"/tmp/pre_migration_{stamp}.db"

    src, dst = sqlite3.connect(db_path), sqlite3.connect(tmp)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    try:
        os.makedirs(target_dir, exist_ok=True)
        final = os.path.join(target_dir, f"peakpace_pre_migration_{stamp}.db")
        shutil.copyfile(tmp, final)
        os.remove(tmp)
        return final
    except OSError:
        # The backup directory may not be mounted; the local copy still stands.
        return tmp


def migrate_to_accounts(db_path: str) -> bool:
    """Give every table an owner. Returns True when it did work."""
    if not os.path.exists(db_path):
        return False

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        if not _table_exists(cur, "activities"):
            return False  # A fresh database; SQLAlchemy creates it correctly.
        if "user_id" in _columns(cur, "activities") and "user_id" in _columns(cur, "daily_health"):
            return False  # Already done.

        backup = _safety_copy(db_path)
        print(f"🔄 Migrating to accounts. Safety copy: {backup}", flush=True)

        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("BEGIN")

        if "user_id" not in _columns(cur, "activities"):
            cur.execute("ALTER TABLE activities ADD COLUMN user_id VARCHAR(64)")
        # external_id was globally unique; two athletes may hold the same
        # workout, so uniqueness moves to the pair.
        for (name,) in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='activities'"
        ).fetchall():
            if name and "external_id" in name:
                cur.execute(f"DROP INDEX IF EXISTS {name}")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_activities_external_id ON activities(external_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_activities_user_id ON activities(user_id)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_activity_user_external "
                    "ON activities(user_id, external_id)")

        if "user_id" not in _columns(cur, "daily_health"):
            keep = [c for c in _columns(cur, "daily_health") if c not in ("user_id",)]
            body = ", ".join(
                f"{c} " + ("INTEGER" if c in ("resting_hr", "steps") else
                           "DATETIME" if c == "updated_at" else "FLOAT")
                for c in keep if c != "date"
            )
            cur.execute("ALTER TABLE daily_health RENAME TO daily_health_old")
            cur.execute(
                f"CREATE TABLE daily_health (user_id VARCHAR(64) NOT NULL DEFAULT '', "
                f"date DATE NOT NULL, {body}, PRIMARY KEY (user_id, date))"
            )
            cur.execute(
                f"INSERT INTO daily_health (user_id, {', '.join(keep)}) "
                f"SELECT '', {', '.join(keep)} FROM daily_health_old"
            )
            cur.execute("DROP TABLE daily_health_old")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_daily_health_user_id ON daily_health(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_daily_health_date ON daily_health(date)")

        if _table_exists(cur, "user_profile") and "user_id" not in _columns(cur, "user_profile"):
            carry = [c for c in _columns(cur, "user_profile") if c not in ("id", "user_id")]
            body = ", ".join(
                f"{c} " + ("VARCHAR(128)" if c in ("name", "gender") else
                           "JSON" if c in ("hr_zones", "pace_zones") else
                           "DATETIME" if c == "updated_at" else "FLOAT")
                for c in carry
            )
            cur.execute("ALTER TABLE user_profile RENAME TO user_profile_old")
            cur.execute(
                f"CREATE TABLE user_profile (id VARCHAR(64) NOT NULL PRIMARY KEY, "
                f"user_id VARCHAR(64), {body})"
            )
            cur.execute(
                f"INSERT INTO user_profile (id, user_id, {', '.join(carry)}) "
                f"SELECT lower(hex(randomblob(16))), NULL, {', '.join(carry)} FROM user_profile_old"
            )
            cur.execute("DROP TABLE user_profile_old")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profile_user_id "
                        "ON user_profile(user_id)")

        con.commit()
        waiting = cur.execute(
            "SELECT COUNT(*) FROM activities WHERE user_id IS NULL OR user_id=''"
        ).fetchone()[0]
        print(f"✅ Migration complete. {waiting} activities await their first account.", flush=True)
        return True

    except Exception as exc:
        con.rollback()
        print(f"❌ Migration failed and was rolled back: {exc}", flush=True)
        raise
    finally:
        cur.execute("PRAGMA foreign_keys=ON")
        con.close()
