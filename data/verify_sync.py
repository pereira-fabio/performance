#!/usr/bin/env python3
"""
Check a freshly synced database against everything we fixed.

Each check corresponds to a real defect found along the way, so a pass here
means that specific bug is genuinely gone rather than merely untested.

    docker exec -it peakpace-backend python /data/verify_sync.py
"""
import json
import os
import sqlite3
from collections import Counter

DB = os.getenv("DATABASE_URL", "sqlite:////db/peakpace.db").replace("sqlite:///", "")
RUNNING = ("running", "treadmill")

results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"\n         {detail}" if detail else ""))


def main() -> int:
    con = sqlite3.connect(DB)
    c = con.cursor()

    n = c.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    print(f"\n=== {n} activities ===\n")
    if n == 0:
        print("Nothing synced yet - run Sync Now on the phone first.")
        return 1

    print("Sport breakdown:")
    for sport, cnt, pace in c.execute(
        "SELECT sport_type, COUNT(*), AVG(avg_pace_sec_km) FROM activities GROUP BY sport_type ORDER BY 2 DESC"
    ):
        p = f"{int((pace or 0)//60)}:{int((pace or 0)%60):02d}/km" if pace else "n/a"
        print(f"  {sport:12s} {cnt:4d}   avg {p}")
    print()

    # 1. Duplicates: one workout must not appear twice.
    dupes = c.execute(
        "SELECT start_time, COUNT(*) FROM activities GROUP BY start_time HAVING COUNT(*) > 1"
    ).fetchall()
    check("No duplicate activities at the same start time", not dupes,
          f"{len(dupes)} duplicated start time(s)" if dupes else "")

    # 2. Zero-distance runs: the signature of the Strava twin.
    # A treadmill or indoor run genuinely has no distance. What would be wrong
    # is an activity that recorded a GPS track yet stored no distance.
    contradictory = 0
    indoor = 0
    for dist, q in c.execute(
        f"SELECT distance_meters, data_quality FROM activities "
        f"WHERE sport_type IN {RUNNING} AND distance_meters <= 0 AND data_quality IS NOT NULL"
    ):
        if (json.loads(q).get("gps") or {}).get("available"):
            contradictory += 1
        else:
            indoor += 1
    check("No run has GPS but zero distance", contradictory == 0,
          (f"{contradictory} contradictory" if contradictory else
           f"{indoor} indoor run(s) with no distance, which is expected" if indoor else ""))

    # 3. Doubled distance. A pace threshold is useless here: doubling a
    #    7:12/km run yields 3:36/km, which looks merely fast. The reliable test
    #    is the stored distance against the GPS track it was derived from.
    diverged = []
    for aid, dist, q in c.execute(
        "SELECT a.id, a.distance_meters, s.stream_data FROM activities a "
        "JOIN activity_streams s ON s.activity_id = a.id WHERE a.distance_meters > 0"
    ).fetchall():
        pts = (json.loads(q) or {}).get("points") or []
        gps = next((p.get("distance") for p in reversed(pts) if p.get("distance")), None)
        if gps and abs(gps - dist) / dist > 0.10:
            diverged.append((aid[:8], round(dist), round(gps)))
    check("Stored distance agrees with the GPS track", not diverged,
          "; ".join(f"{a}: stored {d} m vs GPS {g} m" for a, d, g in diverged[:4]) if diverged else "")

    # 3b. Any device total the server had to reject outright.
    # The device total disagreeing with GPS is not itself a fault: on walks the
    # device figure is contaminated by step-derived distance and GPS is right.
    # What would matter is the guard failing to act, or runs being affected.
    conflicts, run_conflicts, doubled = 0, 0, 0
    for sport, q in c.execute(
        "SELECT sport_type, data_quality FROM activities WHERE data_quality IS NOT NULL"
    ):
        d = (json.loads(q) or {}).get("distance_conflict")
        if not d:
            continue
        conflicts += 1
        if sport in RUNNING:
            run_conflicts += 1
            # Only meaningful for runs. Walk distance is contaminated by
            # step-derived totals across a broad range of factors (0.7x to 5.9x
            # observed), so a walk landing near 2.0x is coincidence, not the
            # double-counting signature this is looking for.
            if 1.9 <= d["factor"] <= 2.1:
                doubled += 1
    check("No distance conflicts on runs", run_conflicts == 0,
          f"{run_conflicts} run(s) affected" if run_conflicts else
          f"{conflicts} on non-running activities, GPS kept (expected)")
    check("No run at ~2.0x device distance (double-counting signature)", doubled == 0,
          f"{doubled} run(s) at ~2.0x" if doubled else "")

    # 4. Walks must not be labelled as runs.
    slow = c.execute(
        f"SELECT COUNT(*) FROM activities WHERE sport_type IN {RUNNING} AND avg_pace_sec_km > 600"
    ).fetchone()[0]
    check("No 'runs' slower than 10:00/km (mislabelled walk signature)", slow == 0,
          f"{slow} suspiciously slow" if slow else "")

    # 5. Personal records must come only from runs.
    bad_pr = c.execute(
        f"SELECT COUNT(*) FROM best_efforts b JOIN activities a ON a.id=b.activity_id "
        f"WHERE a.sport_type NOT IN {RUNNING}"
    ).fetchone()[0]
    check("Best efforts derived only from runs", bad_pr == 0,
          f"{bad_pr} from non-running activities" if bad_pr else "")

    # 6. PMC must reflect running load only.
    run_tss = c.execute(
        f"SELECT COALESCE(SUM(r_tss),0) FROM activities WHERE sport_type IN {RUNNING}"
    ).fetchone()[0]
    other_tss = c.execute(
        f"SELECT COALESCE(SUM(r_tss),0) FROM activities WHERE sport_type NOT IN {RUNNING}"
    ).fetchone()[0]
    pmc_tss = c.execute("SELECT COALESCE(SUM(daily_tss),0) FROM daily_health").fetchone()[0]
    check("PMC load matches running only", abs(pmc_tss - run_tss) < 1.0,
          f"running {run_tss:.1f} | other {other_tss:.1f} | PMC {pmc_tss:.1f}")

    # 7. Heart rate must actually be joined, not lost to timestamp mismatch.
    cov = c.execute(
        "SELECT AVG(hr_coverage), MIN(hr_coverage) FROM activities WHERE hr_coverage > 0"
    ).fetchone()
    check("Heart rate coverage healthy (avg > 80%)", (cov[0] or 0) > 0.8,
          f"avg {(cov[0] or 0)*100:.0f}%, worst {(cov[1] or 0)*100:.0f}%")

    # 8. Splits must sum to roughly the stored distance.
    mismatch = 0
    for aid, dist in c.execute(
        f"SELECT id, distance_meters FROM activities WHERE sport_type IN {RUNNING} AND distance_meters > 0"
    ).fetchall():
        s = c.execute("SELECT COALESCE(SUM(distance_meters),0) FROM activity_splits WHERE activity_id=?",
                      (aid,)).fetchone()[0]
        if s > 0 and abs(s - dist) / dist > 0.05:
            mismatch += 1
    check("Split distances agree with activity distance", mismatch == 0,
          f"{mismatch} activity(ies) disagree by >5%" if mismatch else "")

    # 9. Nothing fabricated: absent metrics must carry a reason.
    silent = 0
    for (q,) in c.execute("SELECT data_quality FROM activities WHERE data_quality IS NOT NULL"):
        dq = json.loads(q)
        if dq.get("gps", {}).get("available") is False and not dq.get("unavailable"):
            silent += 1
    check("Missing metrics always carry an explanation", silent == 0,
          f"{silent} activity(ies) missing data with no reason recorded" if silent else "")

    # 10. Elevation source, for information.
    src = Counter()
    for (q,) in c.execute("SELECT data_quality FROM activities WHERE data_quality IS NOT NULL"):
        src[(json.loads(q).get("altitude") or {}).get("source")] += 1
    print(f"\n  Elevation sources: {dict(src)}")
    if src.get(None):
        print("  (null = no device altitude and no DEM tile; GAP unavailable for those)")

    failed = [r for r in results if not r[0]]
    print(f"\n=== {len(results) - len(failed)}/{len(results)} checks passed ===")
    if failed:
        print("Failed:")
        for _, name, detail in failed:
            print(f"  - {name}: {detail}")
    con.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
