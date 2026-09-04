#!/usr/bin/env python3
"""
Relabel Garmin activities that were imported with the wrong sport.

Garmin activities were downloaded as TCX, and TCX cannot say what the activity
was: its schema allows exactly three values for the Sport attribute -- Running,
Biking and Other -- so every walk, hike, swim and gym session arrived as
"Other" and landed in the catch-all tab. Runs were unaffected.

Garmin's own type key ("walking", "strength_training") is in the activity
listing, so this reads the listing and corrects the stored sport. It downloads
nothing: one listing call covers a year, which keeps it well clear of the rate
limit that a full re-sync would risk.

    docker exec -it performance-backend python /data/fix_garmin_sports.py <username>

Add --apply to write the changes; without it nothing is modified.
"""
import sys
from datetime import date, timedelta

sys.path.append("/app")

from backend.app.core.database import SessionLocal                 # noqa: E402
from backend.app.models.models import Activity, User               # noqa: E402
from backend.app.services import garmin_connector                  # noqa: E402
from backend.app.services.activity_processor import _default_name  # noqa: E402
from backend.app.services.file_import import normalise_sport       # noqa: E402

LOOKBACK_DAYS = 400

# Names a previous version generated. Only these are re-derived; anything
# Garmin named, or the athlete renamed, is left alone.
GENERIC = {"running session", "walking session", "gym session", "activity", "run", ""}


def main(argv) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    apply = "--apply" in argv[1:]
    if not args:
        print("Usage: fix_garmin_sports.py <username> [--apply]")
        return 2
    username = args[0]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            print(f"No account called {username!r}.")
            return 1

        stored = {
            a.external_id.split(":", 1)[1]: a
            for a in db.query(Activity)
            .filter(Activity.user_id == user.id,
                    Activity.external_id.like("garmin:%"))
            .all()
        }
        if not stored:
            print(f"{username} has no Garmin activities.")
            return 0
        print(f"{len(stored)} Garmin activities stored for {username}.")

        try:
            api = garmin_connector._client(user.id)
            listing = api.get_activities_by_date(
                (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat(),
                date.today().isoformat(),
            )
        except Exception as exc:
            print(f"Could not read the Garmin listing: {exc}")
            print("Reconnect the account in Settings and run this again.")
            return 1

        changed = 0
        unmatched = 0
        for entry in listing or []:
            activity = stored.pop(str(entry.get("activityId") or ""), None)
            if activity is None:
                continue
            sport = garmin_connector._sport_of(entry)
            if not sport or sport == activity.sport_type:
                continue
            old = activity.sport_type
            print(f"  {activity.start_time:%Y-%m-%d}  {activity.name[:34]:34} "
                  f"{old} -> {sport}")
            if apply:
                activity.sport_type = sport
                if (activity.name or "").strip().lower() in GENERIC:
                    activity.name = _default_name(sport)
            changed += 1

        unmatched = len(stored)
        if apply and changed:
            db.commit()
            print(f"\nUpdated {changed} activity(ies).")
        elif changed:
            print(f"\n{changed} activity(ies) would change. Re-run with --apply.")
        else:
            print("\nEverything is already labelled correctly.")
        if unmatched:
            print(f"{unmatched} stored activity(ies) were older than "
                  f"{LOOKBACK_DAYS} days and were not checked.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
