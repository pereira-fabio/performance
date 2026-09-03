#!/usr/bin/env python3
"""Show the activities the verifier flagged, with enough context to judge them."""
import json, os, sqlite3

DB = os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", "")
c = sqlite3.connect(DB).cursor()

print("=== distance conflicts (device total rejected) ===")
rows = []
for name, sport, st, dist, dur, cov, q in c.execute(
    "SELECT name, sport_type, start_time, distance_meters, moving_time_sec, hr_coverage, data_quality "
    "FROM activities WHERE data_quality IS NOT NULL ORDER BY start_time"
):
    dq = json.loads(q)
    conflict = dq.get("distance_conflict")
    if not conflict:
        continue
    gps, dev, f = conflict["gps_meters"], conflict["device_meters"], conflict["factor"]
    gpsq = dq.get("gps", {})
    rows.append(f)
    pace_gps = (dur / (gps / 1000.0)) if gps > 0 else 0
    pace_dev = (dur / (dev / 1000.0)) if dev > 0 else 0
    fmt = lambda p: f"{int(p//60)}:{int(p%60):02d}" if p else "n/a"
    print(f"\n  {str(st)[:16]}  {sport:8s}  {dur/60:5.1f} min  HRcov {(cov or 0)*100:3.0f}%")
    print(f"     GPS    {gps/1000:6.2f} km -> {fmt(pace_gps)}/km   (kept)")
    print(f"     device {dev/1000:6.2f} km -> {fmt(pace_dev)}/km   factor {f}")
    print(f"     gps samples={gpsq.get('sample_count')} median_interval={gpsq.get('median_interval_sec')}s "
          f"max_gap={gpsq.get('max_gap_sec')}s")
    if dq.get("notes"):
        for n in dq["notes"]:
            if "gps" in n.lower() or "dropped" in n.lower():
                print(f"     note: {n}")

if rows:
    over = [f for f in rows if f > 1]
    under = [f for f in rows if f < 1]
    print(f"\n  {len(rows)} conflict(s): {len(over)} with device HIGHER than GPS "
          f"(factors {sorted(over)}), {len(under)} LOWER (factors {sorted(under)})")

print("\n\n=== zero-distance running activities ===")
for name, st, dur, cov, q in c.execute(
    "SELECT name, start_time, moving_time_sec, hr_coverage, data_quality FROM activities "
    "WHERE sport_type IN ('running','treadmill') AND distance_meters <= 0"
):
    dq = json.loads(q)
    print(f"  {str(st)[:16]}  {dur/60:.1f} min  HRcov {(cov or 0)*100:.0f}%")
    print(f"     gps={dq.get('gps')}")
    print(f"     unavailable={dq.get('unavailable')}")
    print(f"     notes={dq.get('notes')}")

print("\n\n=== worst heart-rate coverage ===")
for name, sport, st, cov in c.execute(
    "SELECT name, sport_type, start_time, hr_coverage FROM activities "
    "WHERE hr_coverage IS NOT NULL ORDER BY hr_coverage ASC LIMIT 5"
):
    print(f"  {(cov or 0)*100:5.1f}%  {str(st)[:16]}  {sport}")
