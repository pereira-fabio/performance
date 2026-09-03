#!/usr/bin/env python3
"""
Report where GPS stands for recent activities.

Distinguishes three different problems that look identical in the interface:
the phone never sent a route, the route was sent but stored empty, or the route
is stored and only the display is wrong.

    docker exec -it performance-backend python /data/check_gps.py
"""
import json
import os
import sqlite3

DB = os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", "")
con = sqlite3.connect(DB)
c1, c2 = con.cursor(), con.cursor()

total = c1.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
with_gps = c1.execute(
    "SELECT COUNT(*) FROM activities WHERE json_extract(data_quality, '$.gps.available') = 1"
).fetchone()[0]
print(f"{total} activities, {with_gps} report a GPS route\n")

print("Most recent 10:")
print(f"  {'start':17s} {'sport':9s} {'gps':>4s} {'pts':>6s} {'stream lat/lng':>14s}  altitude")
for aid, st, sport, q in c1.execute(
    "SELECT id, start_time, sport_type, data_quality FROM activities "
    "ORDER BY start_time DESC LIMIT 10"
).fetchall():
    dq = json.loads(q) if q else {}
    gps = (dq.get("gps") or {})
    alt = (dq.get("altitude") or {})

    row = c2.execute(
        "SELECT stream_data FROM activity_streams WHERE activity_id = ?", (aid,)
    ).fetchone()
    located = 0
    if row and row[0]:
        pts = (json.loads(row[0]) or {}).get("points") or []
        located = sum(1 for p in pts if p.get("lat") is not None and p.get("lng") is not None)

    print(f"  {str(st)[:16]:17s} {sport:9s} {str(gps.get('available')):>4s} "
          f"{str(gps.get('sample_count') or '-'):>6s} {located:>14d}  {alt.get('source')}")

print("\nReasons recorded on activities without GPS:")
seen = {}
for (q,) in c1.execute("SELECT data_quality FROM activities WHERE data_quality IS NOT NULL"):
    dq = json.loads(q)
    if (dq.get("gps") or {}).get("available"):
        continue
    for note in dq.get("notes", []):
        seen[note] = seen.get(note, 0) + 1
    for key in ("distance", "gap_pace"):
        r = (dq.get("unavailable") or {}).get(key)
        if r:
            seen[r] = seen.get(r, 0) + 1
for note, n in sorted(seen.items(), key=lambda x: -x[1])[:6]:
    print(f"  {n:4d}x  {note}")
if not seen:
    print("  (none — every activity has a route)")
