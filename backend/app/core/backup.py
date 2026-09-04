"""
Database snapshots.

Lives in the package rather than beside the data so the scheduled container and
the admin console run exactly the same code; two implementations of a backup is
one more than anyone can verify.

Three faults in earlier versions shaped this:
  * writing the snapshot straight to an SMB share, where SQLite cannot take the
    locks it needs, so every run died with "database is locked"
  * leaving the half-written file behind on failure, which looked like a backup
  * shutil.copy2, whose utime() call CIFS refuses even after the data is safely
    written

So: snapshot locally, verify, compress, copy the bytes only, and clean up after
any failure.
"""
import glob
import gzip
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

MIN_PLAUSIBLE_BYTES = 1024


def _settings():
    return {
        "db": os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", ""),
        "dir": os.getenv("BACKUP_DIR", "/data/backups"),
        "stamp": os.getenv("BACKUP_STAMP", "/db/.last_backup_mtime"),
        "retention_days": int(os.getenv("BACKUP_RETENTION_DAYS", "7")),
        # Never prune below this, so a server that stops taking backups is not
        # left with none at all a week later.
        "keep_minimum": int(os.getenv("BACKUP_KEEP_MINIMUM", "3")),
        "compress": os.getenv("BACKUP_COMPRESS", "1") not in ("0", "false", "no"),
    }


@dataclass
class BackupFile:
    name: str
    path: str
    size: int
    created: datetime
    compressed: bool

    def as_dict(self):
        return {
            "name": self.name,
            "size_bytes": self.size,
            "size_mb": round(self.size / 1048576, 2),
            "created": self.created.isoformat(),
            "age_days": round((datetime.now() - self.created).total_seconds() / 86400, 1),
            "compressed": self.compressed,
        }


def list_backups() -> List[BackupFile]:
    cfg = _settings()
    found = []
    for path in sorted(
        glob.glob(os.path.join(cfg["dir"], "peakpace_*.db"))
        + glob.glob(os.path.join(cfg["dir"], "peakpace_*.db.gz"))
    ):
        try:
            stat = os.stat(path)
        except OSError:
            continue
        found.append(BackupFile(
            name=os.path.basename(path), path=path, size=stat.st_size,
            created=datetime.fromtimestamp(stat.st_mtime),
            compressed=path.endswith(".gz"),
        ))
    return sorted(found, key=lambda b: b.created, reverse=True)


def prune(log=print) -> int:
    """
    Drop snapshots older than the retention window.

    Age, not count: a week of history is what someone actually wants, and a
    count silently means something different whenever the schedule changes.
    """
    cfg = _settings()
    backups = list_backups()

    # Empty files from the era when failures left their artefacts behind.
    removed = 0
    for b in list(backups):
        if b.size < MIN_PLAUSIBLE_BYTES:
            try:
                os.remove(b.path)
                backups.remove(b)
                removed += 1
            except OSError:
                pass
    if removed:
        log(f"Removed {removed} empty file(s) from earlier failed runs.")

    cutoff = datetime.now() - timedelta(days=cfg["retention_days"])
    expired = [b for b in backups if b.created < cutoff]
    # Newest first, so the floor keeps the most recent.
    keepable = len(backups) - len(expired)
    for b in expired:
        if keepable >= cfg["keep_minimum"]:
            try:
                os.remove(b.path)
                removed += 1
            except OSError:
                continue
        else:
            keepable += 1
    if expired:
        log(f"Pruned {len(expired)} snapshot(s) older than {cfg['retention_days']} days.")
    return removed


def source_changed() -> bool:
    cfg = _settings()
    try:
        current = os.path.getmtime(cfg["db"])
    except OSError:
        return False
    last = 0.0
    if os.path.exists(cfg["stamp"]):
        try:
            last = float(open(cfg["stamp"]).read().strip())
        except (ValueError, OSError):
            last = 0.0
    return current > last


def run_once(force: bool = False, log=print) -> Optional[dict]:
    """Take one snapshot. Returns a summary, or None when skipped."""
    cfg = _settings()
    if not os.path.exists(cfg["db"]):
        log(f"No database at {cfg['db']}; nothing to back up.")
        return None
    if not force and not source_changed():
        log("No new data since the last backup; skipping.")
        return None

    os.makedirs(cfg["dir"], exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    final = os.path.join(cfg["dir"], f"peakpace_{stamp}.db" + (".gz" if cfg["compress"] else ""))

    fd, tmp = tempfile.mkstemp(prefix="backup_", suffix=".db", dir="/tmp")
    os.close(fd)
    os.remove(tmp)

    try:
        # The online backup API reads a live WAL-mode database safely, but it
        # needs a destination that supports locking -- hence local disk.
        src = sqlite3.connect(f"file:{cfg['db']}?mode=ro", uri=True)
        dst = sqlite3.connect(tmp)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

        check = sqlite3.connect(tmp)
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("snapshot failed its integrity check")
        activities = check.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        try:
            accounts = check.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        except sqlite3.Error:
            accounts = 0
        check.close()

        raw_size = os.path.getsize(tmp)
        if raw_size < MIN_PLAUSIBLE_BYTES:
            raise RuntimeError(f"snapshot is only {raw_size} bytes")

        if cfg["compress"]:
            with open(tmp, "rb") as raw, gzip.open(final, "wb", compresslevel=6) as out:
                shutil.copyfileobj(raw, out, length=1024 * 1024)
        else:
            shutil.copyfile(tmp, final)

        written = os.path.getsize(final)
        ratio = f", {raw_size / written:.1f}x smaller" if cfg["compress"] and written else ""
        log(f"Backup OK: {os.path.basename(final)} ({written / 1048576:.1f} MB{ratio}, "
            f"{activities} activities across {accounts} account(s))")

        try:
            with open(cfg["stamp"], "w") as fh:
                fh.write(str(os.path.getmtime(cfg["db"])))
        except OSError as exc:
            log(f"Could not write stamp file: {exc}")

        prune(log)
        return {
            "name": os.path.basename(final), "size_bytes": written,
            "activities": activities, "accounts": accounts,
        }

    except Exception as exc:
        log(f"Backup FAILED: {exc}")
        # Never leave a partial file pretending to be a backup.
        if os.path.exists(final):
            try:
                os.remove(final)
                log(f"Removed incomplete {os.path.basename(final)}")
            except OSError:
                pass
        raise
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
