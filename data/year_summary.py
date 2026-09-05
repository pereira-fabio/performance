#!/usr/bin/env python3
"""
What the server holds for a year, by sport and by month.

For answering one question: when a phone says 62 runs and the app shows 56,
did six never arrive, or did they arrive filed as something else? Nothing X
records some sessions as a generic workout, which is stored as gym work rather
than as a run, so a missing run is often a present one under another heading.

    docker exec -it performance-backend python /data/year_summary.py
    docker exec -it performance-backend python /data/year_summary.py 2025 --user peraa
"""
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.path.append("/app")

from backend.app.core.database import SessionLocal          # noqa: E402
from backend.app.core.sports import is_running              # noqa: E402
from backend.app.models.models import Activity, User        # noqa: E402


def main(argv) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    username = None
    if "--user" in argv[1:]:
        i = argv.index("--user")
        username = argv[i + 1] if i + 1 < len(argv) else None
        if username in args:
            args.remove(username)

    year = int(args[0]) if args else datetime.utcnow().year

    db = SessionLocal()
    try:
        query = db.query(Activity).filter(
            Activity.start_time >= datetime(year, 1, 1),
            Activity.start_time < datetime(year + 1, 1, 1),
        )
        if username:
            user = db.query(User).filter(User.username == username).first()
            if user is None:
                print(f"No account called {username!r}.")
                return 1
            query = query.filter(Activity.user_id == user.id)

        activities = query.order_by(Activity.start_time.asc()).all()
        if not activities:
            print(f"Nothing stored for {year}.")
            return 0

        by_sport = Counter(a.sport_type for a in activities)
        by_month = defaultdict(Counter)
        for a in activities:
            by_month[a.start_time.month][a.sport_type] += 1

        runs = sum(1 for a in activities if is_running(a.sport_type))
        print(f"{year}: {len(activities)} activities, {runs} of them runs\n")

        print("BY SPORT")
        for sport, n in by_sport.most_common():
            mark = "  <- counts as running" if is_running(sport) else ""
            print(f"  {sport:14} {n:>4}{mark}")

        print("\nBY MONTH")
        sports = [s for s, _ in by_sport.most_common()]
        header = "      " + "".join(f"{s[:6]:>8}" for s in sports) + f"{'total':>8}"
        print(header)
        for month in range(1, 13):
            counts = by_month.get(month)
            if not counts:
                continue
            row = f"  {datetime(year, month, 1):%b}  "
            row += "".join(f"{counts.get(s, 0):>8}" for s in sports)
            row += f"{sum(counts.values()):>8}"
            print(row)

        # Sessions with no distance are the ones a phone may not think of as
        # runs at all, and the likeliest place a count disagrees.
        vague = [a for a in activities if not a.distance_meters]
        if vague:
            print(f"\n{len(vague)} activity(ies) stored with no distance:")
            for a in vague[:20]:
                print(f"  {a.start_time:%Y-%m-%d %H:%M}  {a.sport_type:10} "
                      f"{int((a.moving_time_sec or 0) // 60):>3} min  {(a.name or '')[:30]}")
            if len(vague) > 20:
                print(f"  ... and {len(vague) - 20} more")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
