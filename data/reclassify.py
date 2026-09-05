#!/usr/bin/env python3
"""
Move activities from one sport to another, in bulk.

Health Connect reports an exercise type, and some apps report a useless one:
Nothing X records its "Free training" as a generic workout whatever it was, so
an indoor run arrives indistinguishable from a circuit session and is stored as
gym work. Only the athlete knows which was which, and correcting a winter of
them one at a time in the app is not a reasonable ask.

    # look first -- nothing is written without --apply
    reclassify.py --user peraa --from gym --to treadmill --between 2026-01-01 2026-02-28
    reclassify.py --user peraa --from gym --to treadmill --between 2026-01-01 2026-02-28 --apply

    # narrow further where a duration tells them apart
    reclassify.py --user peraa --from gym --to treadmill --min-minutes 20

Changing the sport changes what an activity counts towards: running load,
records and the fitness curve. It does not recompute anything already stored --
best efforts are found during ingestion and a session that was never a run has
none, so a reclassified run will show splits and records only after a re-sync.
"""
import sys
from datetime import datetime

sys.path.append("/app")

from backend.app.core.database import SessionLocal      # noqa: E402
from backend.app.core.sports import (                   # noqa: E402
    CROSS_TRAINING_SPORTS, RUNNING_SPORTS,
)
from backend.app.models.models import Activity, User    # noqa: E402

KNOWN = sorted(set(RUNNING_SPORTS) | set(CROSS_TRAINING_SPORTS))


def _option(argv, name, count=1):
    if name not in argv:
        return None
    i = argv.index(name)
    values = argv[i + 1:i + 1 + count]
    return values if count > 1 else (values[0] if values else None)


def main(argv) -> int:
    apply = "--apply" in argv
    username = _option(argv, "--user")
    source = _option(argv, "--from")
    target = _option(argv, "--to")
    between = _option(argv, "--between", 2)
    min_minutes = _option(argv, "--min-minutes")
    max_minutes = _option(argv, "--max-minutes")

    if not username or not source or not target:
        print(__doc__.strip())
        return 2
    if target not in KNOWN:
        print(f"Unknown sport {target!r}. Known: {', '.join(KNOWN)}")
        return 2

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            print(f"No account called {username!r}.")
            return 1

        query = db.query(Activity).filter(
            Activity.user_id == user.id,
            Activity.sport_type == source,
        )
        if between and len(between) == 2:
            start = datetime.fromisoformat(between[0])
            # Inclusive of the end date, which is what a date range means to
            # everyone who is not a programmer.
            end = datetime.fromisoformat(between[1]).replace(hour=23, minute=59, second=59)
            query = query.filter(Activity.start_time >= start, Activity.start_time <= end)
        if min_minutes:
            query = query.filter(Activity.moving_time_sec >= float(min_minutes) * 60)
        if max_minutes:
            query = query.filter(Activity.moving_time_sec <= float(max_minutes) * 60)

        activities = query.order_by(Activity.start_time.asc()).all()
        if not activities:
            print("Nothing matches.")
            return 0

        print(f"{len(activities)} activity(ies) would become {target}:\n")
        for a in activities:
            km = (a.distance_meters or 0) / 1000
            print(f"  {a.start_time:%Y-%m-%d %H:%M}  {int((a.moving_time_sec or 0)//60):>3} min  "
                  f"{km:5.2f} km  hr {a.avg_hr or '—':>4}  {(a.name or '')[:28]}")
            if apply:
                a.sport_type = target

        if apply:
            db.commit()
            print(f"\nMoved {len(activities)} to {target}.")
            print("Their names are unchanged; edit any that now read oddly.")
            print("Best efforts and splits are not created retroactively — re-sync")
            print("those sessions if you want records from them.")
        else:
            print(f"\nNothing written. Re-run with --apply to move them.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
