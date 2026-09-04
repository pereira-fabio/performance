#!/usr/bin/env python3
"""
PeakPace database backup.

Replaces both earlier attempts (data/backup_db.sh and backend/backup.py), which
between them failed every scheduled run and left a trail of 0-byte files. Three
separate faults caused that:

  1. `sqlite3 .backup` wrote its snapshot straight to the SMB share. SQLite
     needs POSIX locks on the destination and CIFS generally cannot provide
     them, so every run died with "database is locked".
  2. The failure branch exited without deleting the file it had already
     created, so each failure left an empty backup behind that looked real.
  3. shutil.copy2 copies timestamps, and CIFS refuses utime() -- so even a
     successful copy raised PermissionError afterwards.

The fix: snapshot to local disk where locking works, verify it, then copy the
bytes only (copyfile, not copy2) to the share. Anything that goes wrong cleans
up after itself rather than leaving a misleading artefact.

    python /data/backup.py            # one backup
    python /data/backup.py --loop     # run forever, BACKUP_INTERVAL_SEC apart

Restoring:

    gunzip -c /data/backups/peakpace_<stamp>.db.gz > /tmp/restore.db
    docker cp /tmp/restore.db performance-backend:/db/peakpace.db
"""
import glob
import gzip
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import datetime

DB = os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", "")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/data/backups")
STAMP_FILE = os.getenv("BACKUP_STAMP", "/db/.last_backup_mtime")
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "30"))
# Daily. Hourly was writing a full copy of the whole database every hour for
# data that changes a few times a week.
INTERVAL_SEC = int(os.getenv("BACKUP_INTERVAL_SEC", "86400"))
MIN_PLAUSIBLE_BYTES = 1024

# Snapshots are compressed rather than made incremental. A SQLite file of
# mostly JSON compresses about five to one, and every snapshot stays
# independently restorable -- an incremental chain is worthless if one link in
# it is lost, which is exactly the situation a backup exists for.
COMPRESS = os.getenv("BACKUP_COMPRESS", "1") not in ("0", "false", "no")


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def source_changed() -> bool:
    """Skip work when nothing has been written since the last backup."""
    try:
        current = os.path.getmtime(DB)
    except OSError:
        return False
    last = 0.0
    if os.path.exists(STAMP_FILE):
        try:
            last = float(open(STAMP_FILE).read().strip())
        except (ValueError, OSError):
            last = 0.0
    return current > last


def record_stamp():
    try:
        with open(STAMP_FILE, "w") as fh:
            fh.write(str(os.path.getmtime(DB)))
    except OSError as exc:
        log(f"Could not write stamp file: {exc}")


def _all_backups():
    """Every snapshot, compressed or not, oldest first."""
    return sorted(
        glob.glob(os.path.join(BACKUP_DIR, "peakpace_*.db"))
        + glob.glob(os.path.join(BACKUP_DIR, "peakpace_*.db.gz"))
    )


def clear_empty():
    """Remove worthless 0-byte files left by the previous implementations.

    They sort as recent, so pruning by age would keep them and discard real
    backups instead.
    """
    removed = 0
    for path in _all_backups():
        try:
            if os.path.getsize(path) < MIN_PLAUSIBLE_BYTES:
                os.remove(path)
                removed += 1
        except OSError:
            pass
    if removed:
        log(f"Removed {removed} empty backup file(s) from earlier failed runs.")


def prune():
    clear_empty()
    backups = _all_backups()
    excess = len(backups) - MAX_BACKUPS
    if excess > 0:
        for path in backups[:excess]:
            try:
                os.remove(path)
            except OSError:
                pass
        log(f"Pruned {excess} old backup(s), keeping {MAX_BACKUPS}.")


def run_once(force: bool = False) -> bool:
    if not os.path.exists(DB):
        log(f"No database at {DB}; nothing to back up.")
        return True
    if not force and not source_changed():
        log("No new data since the last backup; skipping.")
        return True

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    final = os.path.join(BACKUP_DIR, f"peakpace_{stamp}.db" + (".gz" if COMPRESS else ""))

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="peakpace_backup_", suffix=".db", dir="/tmp")
    os.close(tmp_fd)
    os.remove(tmp_path)

    try:
        # Snapshot locally. The online backup API reads a live WAL-mode
        # database safely, but it needs a destination that supports locking.
        src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        dst = sqlite3.connect(tmp_path)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

        # Prove the snapshot is usable before it replaces anything.
        check = sqlite3.connect(tmp_path)
        status = check.execute("PRAGMA integrity_check").fetchone()[0]
        activities = check.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        # Report the accounts covered. The snapshot is deliberately whole-system
        # rather than per athlete: a backup has to restore atomically, and one
        # athlete's rows put back into a live database is a merge, not a
        # restore. Individual athletes export their own data instead.
        try:
            accounts = check.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        except sqlite3.Error:
            accounts = 0
        check.close()
        if status != "ok":
            raise RuntimeError(f"integrity_check returned {status!r}")

        size = os.path.getsize(tmp_path)
        if size < MIN_PLAUSIBLE_BYTES:
            raise RuntimeError(f"snapshot is only {size} bytes")

        # copyfile, not copy2: CIFS refuses the utime() that copy2 performs
        # after writing, which would fail the run despite the data being fine.
        if COMPRESS:
            with open(tmp_path, "rb") as raw, gzip.open(final, "wb", compresslevel=6) as out:
                shutil.copyfileobj(raw, out, length=1024 * 1024)
        else:
            shutil.copyfile(tmp_path, final)
            if os.path.getsize(final) != size:
                raise RuntimeError("copied file size does not match the snapshot")

        written = os.path.getsize(final)
        ratio = f", {size / written:.1f}x smaller" if COMPRESS and written else ""
        log(f"Backup OK: {os.path.basename(final)} ({written / 1024 / 1024:.1f} MB{ratio}, "
            f"{activities} activities across {accounts} account(s))")
        record_stamp()
        prune()
        return True

    except Exception as exc:
        log(f"Backup FAILED: {exc}")
        # Never leave a partial file behind pretending to be a backup.
        if os.path.exists(final):
            try:
                os.remove(final)
                log(f"Removed incomplete {final}")
            except OSError:
                pass
        return False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main() -> int:
    loop = "--loop" in sys.argv
    force = "--force" in sys.argv
    if not loop:
        return 0 if run_once(force) else 1

    log(f"Backup loop started; every {INTERVAL_SEC}s into {BACKUP_DIR}")
    while True:
        run_once(force)
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
