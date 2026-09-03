#!/bin/sh
# PeakPace — Smart Incremental Database Backup
# Runs as a cron job inside the LXC container.
# Only backs up if the database has changed since the last backup.

DB_PATH="/db/peakpace.db"
BACKUP_DIR="/data/backups"
LAST_BACKUP_STAMP="/db/.last_backup_mtime"
MAX_BACKUPS=30  # Keep last 30 backups (~1 month of daily backups)

mkdir -p "$BACKUP_DIR"

# If database doesn't exist yet, skip
if [ ! -f "$DB_PATH" ]; then
    echo "[$(date)] No database found at $DB_PATH, skipping."
    exit 0
fi

# Get current modification time of database
CURRENT_MTIME=$(stat -c "%Y" "$DB_PATH")

# Get modification time of last backup (0 if never backed up)
LAST_MTIME=0
if [ -f "$LAST_BACKUP_STAMP" ]; then
    LAST_MTIME=$(cat "$LAST_BACKUP_STAMP")
fi

# Only proceed if database has been modified since last backup
if [ "$CURRENT_MTIME" -le "$LAST_MTIME" ]; then
    echo "[$(date)] No new data since last backup. Skipping."
    exit 0
fi

# Create a timestamped backup using SQLite's safe online backup
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
BACKUP_FILE="$BACKUP_DIR/peakpace_${TIMESTAMP}.db"

# Use sqlite3 .backup command for a crash-safe, consistent snapshot
# (works even while the backend is actively writing — WAL mode safe)
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

if [ $? -eq 0 ]; then
    echo "[$(date)] ✅ Backup saved: $BACKUP_FILE ($(du -sh "$BACKUP_FILE" | cut -f1))"
    # Save new modification timestamp
    echo "$CURRENT_MTIME" > "$LAST_BACKUP_STAMP"
    
    # Clean up old backups — keep only the last MAX_BACKUPS files
    BACKUP_COUNT=$(ls "$BACKUP_DIR"/peakpace_*.db 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
        ls -t "$BACKUP_DIR"/peakpace_*.db | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f
        echo "[$(date)] 🧹 Cleaned up old backups. Keeping last $MAX_BACKUPS."
    fi
else
    echo "[$(date)] ❌ Backup failed!"
    exit 1
fi
