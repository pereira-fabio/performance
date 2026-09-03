#!/usr/bin/env python3
"""
PeakPace Smart Database Backup
Runs inside the backend container via LXC cron.
Uses Python's sqlite3 online backup API — safe with WAL mode and no locking issues.
"""
import sqlite3
import os
import sys
import glob
from datetime import datetime

DB_PATH = os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", "")
BACKUP_DIR = "/data/backups"
STAMP_FILE = "/db/.last_backup_mtime"
MAX_BACKUPS = 30

os.makedirs(BACKUP_DIR, exist_ok=True)

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

if not os.path.exists(DB_PATH):
    log(f"No database found at {DB_PATH}. Skipping.")
    sys.exit(0)

current_mtime = os.path.getmtime(DB_PATH)
last_mtime = 0.0

if os.path.exists(STAMP_FILE):
    try:
        last_mtime = float(open(STAMP_FILE).read().strip())
    except Exception:
        last_mtime = 0.0

if current_mtime <= last_mtime:
    log("No new data since last backup. Skipping.")
    sys.exit(0)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
backup_file = os.path.join(BACKUP_DIR, f"peakpace_{timestamp}.db")

try:
    # Python sqlite3 backup API: reads safely from live WAL-mode DB without locking
    source = sqlite3.connect(DB_PATH)
    dest = sqlite3.connect(backup_file)
    with dest:
        source.backup(dest, pages=100)
    source.close()
    dest.close()

    size_kb = os.path.getsize(backup_file) / 1024
    log(f"✅ Backup saved: {backup_file} ({size_kb:.1f} KB)")

    # Save new mtime stamp
    with open(STAMP_FILE, "w") as f:
        f.write(str(current_mtime))

    # Prune old backups — keep only the last MAX_BACKUPS
    all_backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "peakpace_*.db")))
    if len(all_backups) > MAX_BACKUPS:
        to_delete = all_backups[:len(all_backups) - MAX_BACKUPS]
        for old in to_delete:
            os.remove(old)
        log(f"🧹 Pruned {len(to_delete)} old backup(s). Keeping last {MAX_BACKUPS}.")

except Exception as e:
    log(f"❌ Backup failed: {e}")
    sys.exit(1)
