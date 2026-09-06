#!/usr/bin/env python3
"""
Find best efforts at distances that were not in the list when a run was stored.

Best efforts are searched for during ingestion, so adding a distance does
nothing for runs already in the database. This searches the stored streams
instead of re-downloading a history that has not changed.

    docker exec -it performance-backend python /data/backfill_best_efforts.py
    docker exec -it performance-backend python /data/backfill_best_efforts.py --apply

Only distances an activity has no effort for are added. The stream is thinned
on the way into the database, so a time found here is a little coarser than one
found at ingestion -- accurate to the spacing of the stored points, a few
seconds on a long run. Overwriting the precise ones with those would be a step
backwards, so it never does.
"""
import sys
from collections import Counter

sys.path.append("/app")

from backend.app.core.database import SessionLocal              # noqa: E402
from backend.app.core.sports import RUNNING_SPORTS              # noqa: E402
from backend.app.models.models import (                         # noqa: E402
    Activity, ActivityStream, BestEffort, User,
)
from backend.app.physiology.best_efforts import calculate_best_efforts  # noqa: E402


def _clock(seconds: float) -> str:
    """A race time. Hours where there are hours: 1:29:22, never 89:22."""
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def backfill(db, user, apply: bool) -> Counter:
    counts = Counter()
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user.id,
                Activity.sport_type.in_(RUNNING_SPORTS))
        .order_by(Activity.start_time.asc())
        .all()
    )

    for activity in activities:
        row = (
            db.query(ActivityStream.stream_data)
            .filter(ActivityStream.activity_id == activity.id).first()
        )
        points = ((row[0] if row else None) or {}).get("points") or []
        distances, offsets = [], []
        for point in points:
            d, t = point.get("distance"), point.get("timestamp_offset")
            if d is None or t is None:
                continue
            distances.append(float(d))
            offsets.append(float(t))
        if len(distances) < 10:
            counts["no usable stream"] += 1
            continue

        held = {
            label for (label,) in
            db.query(BestEffort.label).filter(BestEffort.activity_id == activity.id).all()
        }

        for effort in calculate_best_efforts(distances, offsets, activity.start_time):
            if effort["label"] in held:
                continue
            best_so_far = (
                db.query(BestEffort)
                .join(Activity, Activity.id == BestEffort.activity_id)
                .filter(Activity.user_id == user.id,
                        BestEffort.label == effort["label"])
                .order_by(BestEffort.time_seconds.asc())
                .first()
            )
            print(f"  {activity.start_time:%Y-%m-%d}  {effort['label']:14} "
                  f"{_clock(effort['time_seconds']):>9}   {(activity.name or '')[:26]}")
            counts[effort["label"]] += 1
            if apply:
                db.add(BestEffort(
                    activity_id=activity.id,
                    distance_meters=effort["distance_meters"],
                    label=effort["label"],
                    time_seconds=effort["time_seconds"],
                    pace_sec_km=effort["pace_sec_km"],
                    start_time_offset_sec=effort["start_time_offset_sec"],
                    achieved_at=effort["achieved_at"],
                    is_personal_record=(
                        best_so_far is None
                        or effort["time_seconds"] < best_so_far.time_seconds
                    ),
                ))
                # Flushed so the next activity compares against it, exactly as
                # it would have during a sync.
                db.flush()
    return counts


def main(argv) -> int:
    apply = "--apply" in argv[1:]
    names = [a for a in argv[1:] if not a.startswith("--")]

    db = SessionLocal()
    try:
        query = db.query(User)
        if names:
            query = query.filter(User.username.in_(names))
        users = query.order_by(User.created_at.asc()).all()
        if not users:
            print("No matching accounts.")
            return 1

        total = Counter()
        for user in users:
            print(f"\n{user.username}:")
            counts = backfill(db, user, apply)
            total.update(counts)
            if not counts:
                print("  nothing to add")

        if apply:
            db.commit()

        found = sum(v for k, v in total.items() if k != "no usable stream")
        print("\n" + "-" * 46)
        for label, n in sorted(total.items(), key=lambda kv: -kv[1]):
            print(f"  {label:16} {n}")
        print(f"\n{found} effort(s) {'added' if apply else 'would be added'}.")
        if not apply and found:
            print("Re-run with --apply to keep them.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
