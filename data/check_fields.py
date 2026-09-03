#!/usr/bin/env python3
"""
Show which per-activity fields are populated, and where a gap comes from.

The fields fall into two groups that fail for different reasons:

  server-side   training effect, recovery, XP -- computed from training load,
                so they appear on any re-sync once the backend is rebuilt
  device-side   calories, steps, VO2 max, cadence -- read from Health Connect,
                so they need the permission granted and a fresh sync

Which group is empty tells you which half to look at.

    docker exec -it performance-backend python /data/check_fields.py
"""
import os
import sqlite3

DB = os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", "")
con = sqlite3.connect(DB)
c = con.cursor()

existing = {r[1] for r in c.execute("PRAGMA table_info(activities)")}
SERVER = ["training_effect_aerobic", "training_effect_anaerobic", "recovery_hours", "xp"]
DEVICE = ["calories_kcal", "steps", "vo2_max", "avg_cadence", "avg_stride_length_m", "max_speed_mps"]

missing_cols = [c_ for c_ in SERVER + DEVICE if c_ not in existing]
if missing_cols:
    print("COLUMNS MISSING from the database:", ", ".join(missing_cols))
    print("-> the backend was not rebuilt, or it started before the code was updated.")
    print("   Run: docker-compose up -d --build\n")

total = c.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
print(f"{total} activities\n")

def report(title, cols, note):
    print(f"{title}")
    for col in cols:
        if col not in existing:
            print(f"  {col:24s}  column does not exist")
            continue
        n = c.execute(f"SELECT COUNT(*) FROM activities WHERE {col} IS NOT NULL AND {col} != 0").fetchone()[0]
        sample = c.execute(
            f"SELECT {col} FROM activities WHERE {col} IS NOT NULL AND {col} != 0 "
            "ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
        mark = "ok " if n else "-- "
        print(f"  {mark}{col:24s} {n:4d}/{total}   {('e.g. ' + str(round(sample[0], 2))) if sample else ''}")
    print(f"  {note}\n")

report("Computed on the server (need only a rebuild + re-sync):", SERVER,
       "If these are empty, the backend is stale or nothing has been re-synced.")
report("Read from the device (need the permission and a fresh sync):", DEVICE,
       "If these are empty but the group above is filled, it is the phone side.")

print("Five most recent, newest first:")
print(f"  {'start':17s} {'sport':9s} {'kcal':>6s} {'steps':>7s} {'vo2':>5s} {'TE':>4s} {'rec':>5s} {'xp':>5s}")
for st, sport, kcal, steps, vo2, te, rec, xp in c.execute(
    "SELECT start_time, sport_type, calories_kcal, steps, vo2_max, "
    "training_effect_aerobic, recovery_hours, xp FROM activities "
    "ORDER BY start_time DESC LIMIT 5"
):
    f = lambda v, w: (f"{v:>{w}.0f}" if isinstance(v, (int, float)) else f"{'-':>{w}}")
    print(f"  {str(st)[:16]:17s} {sport:9s} {f(kcal,6)} {f(steps,7)} {f(vo2,5)} "
          f"{(f'{te:>4.1f}' if te else '   -')} {f(rec,5)} {f(xp,5)}")
