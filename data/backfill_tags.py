#!/usr/bin/env python3
"""
Tag runs that were stored before tagging existed.

Tags are assigned during ingestion, so a history synced earlier has none. The
alternative to this is re-syncing everything, which re-downloads every activity
from the phone or from Garmin to arrive at exactly the same answer; this reads
what is already in the database.

It reproduces what ingestion does rather than approximating it: the same
suggestion function, the same measure of how a session compares with the
athlete's usual ones, and the stored stream for the speed trace.

    docker exec -it performance-backend python /data/backfill_tags.py
    docker exec -it performance-backend python /data/backfill_tags.py --apply

Without --apply nothing is written. Add a username to limit it to one account.
An activity that already has a tag is never touched, whether it was set by hand
or by an earlier run of this.
"""
import sys
from collections import Counter
from statistics import median

sys.path.append("/app")

from backend.app.core.database import SessionLocal                    # noqa: E402
from backend.app.core.sports import RUNNING_SPORTS                    # noqa: E402
from backend.app.models.models import (                               # noqa: E402
    Activity, ActivitySplit, ActivityStream, User,
)
from backend.app.physiology.tagging import speed_variation, suggest_tag  # noqa: E402
from backend.app.services.activity_processor import (                     # noqa: E402
    ActivityProcessor, MIN_RUNS_FOR_RELATIVE_TAGS,
)


def _trace(db, activity_id):
    """
    The stored speed trace, and how far apart its samples are.

    Streams are thinned on the way into the database, so the spacing has to
    come from the timestamps rather than be assumed to be one a second --
    smoothing a four-second sample as though it were one flattens a session
    past the point where repetitions are still visible.
    """
    row = (
        db.query(ActivityStream.stream_data)
        .filter(ActivityStream.activity_id == activity_id)
        .first()
    )
    if not row or not row[0]:
        return None, None

    points = (row[0] or {}).get("points") or []
    speeds = [p.get("speed") for p in points]
    if not any(s for s in speeds):
        return None, None

    offsets = [p.get("timestamp_offset") for p in points if p.get("timestamp_offset") is not None]
    interval = None
    if len(offsets) > 1:
        span = offsets[-1] - offsets[0]
        if span > 0:
            interval = span / (len(offsets) - 1)
    return speeds, (interval or 1.0)


def _splits(db, activity_id):
    rows = (
        db.query(ActivitySplit.pace_sec_km, ActivitySplit.gap_sec_km, ActivitySplit.is_partial)
        .filter(ActivitySplit.activity_id == activity_id)
        .order_by(ActivitySplit.split_number.asc())
        .all()
    )
    return [{"pace_sec_km": p, "gap_sec_km": g, "is_partial": bool(part)}
            for p, g, part in rows]


def _overall(activities):
    """
    The athlete's usual intensity and duration across their whole history.

    Ingestion cannot use this -- when a run arrives, the runs after it do not
    exist -- so the first few sessions of an account are judged against absolute
    fractions of threshold pace instead. That is fine live and wrong here: a
    backfill can see the whole history, and without it the earliest runs get
    measured against a threshold pace that is very often still the default,
    which labels every one of them a recovery jog while identical runs later in
    the same history come out as easy.
    """
    intensities = [float(a.intensity_factor) for a in activities
                   if a.intensity_factor and a.intensity_factor > 0]
    durations = [float(a.moving_time_sec) for a in activities
                 if a.moving_time_sec and a.moving_time_sec > 0]
    enough = MIN_RUNS_FOR_RELATIVE_TAGS
    return (
        median(intensities) if len(intensities) >= enough else None,
        median(durations) if len(durations) >= enough else None,
    )


def backfill(db, user, apply: bool) -> Counter:
    # Oldest first, so each activity is judged against the runs that came
    # before it -- which is what ingestion did, and what makes "harder than
    # usual" mean the same thing here as it did then.
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user.id,
                Activity.sport_type.in_(RUNNING_SPORTS))
        .order_by(Activity.start_time.asc())
        .all()
    )
    processor = ActivityProcessor(db, user)
    overall_if, overall_duration = _overall(activities)
    counts = Counter()

    for activity in activities:
        if activity.workout_tag:
            counts["kept"] += 1
            continue

        speeds, interval = _trace(db, activity.id)
        # What ingestion would have used, falling back to the whole history for
        # the earliest runs rather than to a threshold pace that may never have
        # been set.
        typical_if, typical_duration = processor._typical_running(activity.start_time)
        typical_if = typical_if or overall_if
        typical_duration = typical_duration or overall_duration

        tag = suggest_tag(
            sport_type=activity.sport_type,
            moving_time_sec=activity.moving_time_sec,
            intensity_factor=activity.intensity_factor,
            splits=_splits(db, activity.id),
            typical_intensity=typical_if,
            typical_duration_sec=typical_duration,
            speed_variation=(
                speed_variation(speeds, sample_interval_sec=interval) if speeds else None
            ),
        )
        if not tag:
            counts["no signal"] += 1
            continue

        print(f"  {activity.start_time:%Y-%m-%d}  {(activity.name or '')[:34]:34} -> {tag}")
        counts[tag] += 1
        if apply:
            activity.workout_tag = tag

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
                print("  no runs")

        if apply:
            db.commit()

        print("\n" + "-" * 46)
        tagged = sum(v for k, v in total.items() if k not in ("kept", "no signal"))
        for tag, n in sorted(total.items(), key=lambda kv: -kv[1]):
            print(f"  {tag:12} {n}")
        if apply:
            print(f"\nTagged {tagged} activity(ies).")
        else:
            print(f"\n{tagged} activity(ies) would be tagged. Re-run with --apply.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
