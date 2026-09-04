#!/usr/bin/env python3
"""
Rename activities that were stored with the wrong sport in their name.

Everything synced before this fix took its name from a default of "Running
Session", so walks and gym sessions are all called runs. Only names that came
from that default are touched -- anything the device actually named, or that
you renamed yourself, is left alone.

    docker exec -it performance-backend python /data/rename_activities.py
"""
import os
import sys

sys.path.append("/app")

from backend.app.core.database import SessionLocal              # noqa: E402
from backend.app.models.models import Activity                  # noqa: E402
from backend.app.services.activity_processor import _default_name  # noqa: E402

# The defaults previous versions used. Only these are replaced.
GENERIC = {"running session", "activity", "run", ""}


def main() -> int:
    db = SessionLocal()
    try:
        activities = db.query(Activity).all()
        changed = {}
        for a in activities:
            current = (a.name or "").strip()
            if current.lower() not in GENERIC:
                continue  # A real name from the device, or one you chose.
            proper = _default_name(a.sport_type)
            if proper != current:
                a.name = proper
                changed[a.sport_type] = changed.get(a.sport_type, 0) + 1
        db.commit()

        if not changed:
            print("Nothing to rename.")
        else:
            total = sum(changed.values())
            print(f"Renamed {total} of {len(activities)} activities:")
            for sport, n in sorted(changed.items(), key=lambda kv: -kv[1]):
                print(f"  {n:4d}  {sport} -> {_default_name(sport)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
