#!/usr/bin/env python3
"""
What one activity actually arrived with.

When a figure is missing the question is always the same: did the phone not
send it, or did the server not use it? Every activity already records the
answer -- this prints it.

    docker exec -it performance-backend python /data/inspect_activity.py
    docker exec -it performance-backend python /data/inspect_activity.py <activity-id>
    docker exec -it performance-backend python /data/inspect_activity.py --user ann

With no id it shows the most recently recorded activity, which is almost always
the one being asked about.
"""
import json
import sys

sys.path.append("/app")

from backend.app.core.database import SessionLocal              # noqa: E402
from backend.app.models.models import Activity, ActivityStream, User  # noqa: E402


def _fmt_pace(seconds):
    if not seconds or seconds <= 0:
        return "—"
    return f"{int(seconds // 60)}:{int(round(seconds % 60)):02d} /km"


def describe(db, activity, searched_all: bool) -> None:
    # Whose it is, always. On a server with more than one athlete the newest
    # activity is often not the one being asked about, and an answer about
    # somebody else's run looks exactly like an answer about yours.
    owner = db.query(User).filter(User.id == activity.user_id).first()
    who = owner.username if owner else "unowned"

    print(f"\n{activity.name}   {activity.start_time:%Y-%m-%d %H:%M}   {activity.sport_type}")
    print(f"account {who}   id {activity.id}")
    print(f"external {activity.external_id}   via {activity.source}")
    if searched_all:
        print(f"(newest across all accounts — use --user <name> to pick one)")
    print("-" * 68)

    km = (activity.distance_meters or 0) / 1000.0
    print("STORED")
    print(f"  distance        {km:.2f} km" if km else "  distance        — ")
    print(f"  moving time     {int((activity.moving_time_sec or 0) // 60)} min")
    print(f"  average pace    {_fmt_pace(activity.avg_pace_sec_km)}")
    print(f"  grade-adjusted  {_fmt_pace(activity.gap_pace_sec_km)}")
    print(f"  average HR      {activity.avg_hr or '—'}")
    print(f"  training load   {round(activity.r_tss) if activity.r_tss else '—'}")
    print(f"  tag             {activity.workout_tag or '—'}")

    quality = activity.data_quality or {}

    # What the phone sent, and how much of the session each channel covered.
    print("\nCHANNELS RECEIVED")
    channels = {k: v for k, v in quality.items() if isinstance(v, dict) and "coverage" in v}
    if not channels:
        print("  (nothing recorded — this activity predates channel reporting)")
    for name, info in sorted(channels.items()):
        coverage = info.get("coverage")
        samples = info.get("sample_count")
        bar = ""
        if isinstance(coverage, (int, float)):
            filled = int(round(coverage * 20))
            bar = "[" + "#" * filled + "." * (20 - filled) + f"] {coverage:.0%}"
        print(f"  {name:16} {bar}  {samples if samples is not None else ''} samples")

    gps = quality.get("gps") or {}
    if gps:
        print(f"  {'gps route':16} "
              f"{'present' if gps.get('available') else 'ABSENT'}"
              f"  {gps.get('points', '')} points")

    # The reason each absent figure is absent, which is the point of all this.
    missing = quality.get("unavailable") or {}
    print("\nWHY A FIGURE IS MISSING")
    if not missing:
        print("  nothing was reported as unavailable")
    for field, reason in sorted(missing.items()):
        print(f"  {field:16} {reason}")

    for key in ("distance", "altitude", "rtss_basis"):
        if key in quality and not isinstance(quality[key], dict):
            print(f"\n{key}: {quality[key]}")
        elif isinstance(quality.get(key), dict) and "coverage" not in quality[key]:
            print(f"\n{key}: {json.dumps(quality[key])}")

    stream = (
        db.query(ActivityStream.stream_data)
        .filter(ActivityStream.activity_id == activity.id).first()
    )
    points = ((stream[0] if stream else None) or {}).get("points") or []
    if points:
        print(f"\nSTORED STREAM: {len(points)} points")
        for field in ("lat", "speed", "heart_rate", "altitude", "distance", "cadence"):
            got = sum(1 for p in points if p.get(field) is not None)
            print(f"  {field:12} {got:>5} / {len(points)}")
    else:
        print("\nSTORED STREAM: none")


def main(argv) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    username = None
    if "--user" in argv[1:]:
        i = argv.index("--user")
        username = argv[i + 1] if i + 1 < len(argv) else None
        if username in args:
            args.remove(username)

    db = SessionLocal()
    try:
        query = db.query(Activity)
        if username:
            user = db.query(User).filter(User.username == username).first()
            if user is None:
                print(f"No account called {username!r}.")
                return 1
            query = query.filter(Activity.user_id == user.id)

        if args:
            activity = query.filter(Activity.id == args[0]).first()
            if activity is None:
                print(f"No activity {args[0]!r}.")
                return 1
        else:
            activity = query.order_by(Activity.start_time.desc()).first()
            if activity is None:
                print("No activities stored.")
                return 1

        describe(db, activity, searched_all=not username and not args)

        if not username and not args:
            # Which accounts exist, so the right one can be asked for without
            # having to go and look it up.
            others = [u.username for u in db.query(User).order_by(User.created_at.asc()).all()]
            if len(others) > 1:
                print(f"\nAccounts on this server: {', '.join(others)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
