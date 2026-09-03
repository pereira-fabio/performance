#!/usr/bin/env python3
"""
Report which terrain tiles this athlete's routes need.

Devices that record no altitude leave grade undefined, so PeakPace recovers
elevation from local SRTM tiles. This lists exactly which 1-degree tiles the
stored routes fall into, and which are already present.

    docker exec -it peakpace-backend python backend/dem_tiles.py
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings          # noqa: E402
from backend.app.core.database import SessionLocal    # noqa: E402
from backend.app.models.models import ActivityStream  # noqa: E402
from backend.app.physiology.dem import tile_name, _find_tile_file  # noqa: E402

SOURCES = """
Where to get tiles (1-degree .hgt or .hgt.zip, 1 or 3 arc-second):

  * https://dwtkns.com/srtm30m/    click-a-tile downloader for SRTM 1 arc-second
                                   (30 m); needs a free NASA Earthdata login
  * https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003
                                   the authoritative NASA SRTMGL1 v003 dataset
  * https://www.opentopodata.org/datasets/srtm/
                                   notes on SRTM resolutions and coverage

1 arc-second (30 m, 3601x3601, ~25 MB/tile) resolves grade noticeably better
than 3 arc-second (90 m, 1201x1201, ~2.8 MB/tile). Both are supported; the
resolution actually used is recorded on each activity.

Drop the files in DEM_DIR unzipped as NxxEyyy.hgt, or leave them as the
downloaded NxxEyyy.hgt.zip -- both are read directly.
"""


def main() -> int:
    dem_dir = settings.DEM_DIR
    db = SessionLocal()
    try:
        streams = db.query(ActivityStream).all()
        needed = set()
        points = 0
        for stream in streams:
            for p in (stream.stream_data or {}).get("points", []):
                lat, lng = p.get("lat"), p.get("lng")
                if lat is None or lng is None:
                    continue
                needed.add(tile_name(float(lat), float(lng)))
                points += 1
    finally:
        db.close()

    print(f"DEM_DIR            : {dem_dir}")
    print(f"directory exists   : {os.path.isdir(dem_dir)}")
    print(f"activities scanned : {len(streams)} ({points} located points)\n")

    if not needed:
        print("No GPS points stored yet, so no tiles can be determined.")
        print("Sync at least one outdoor activity first.")
        return 0

    present, missing = [], []
    for name in sorted(needed):
        path = _find_tile_file(dem_dir, name) if os.path.isdir(dem_dir) else None
        (present if path else missing).append((name, path))

    print(f"Tiles required: {len(needed)}")
    for name, path in present:
        size_mb = os.path.getsize(path) / 1e6
        print(f"  [ok]      {name}  {os.path.basename(path)} ({size_mb:.1f} MB)")
    for name, _ in missing:
        print(f"  [MISSING] {name}")

    if missing:
        print(SOURCES)
        print(f"Needed but absent: {', '.join(n for n, _ in missing)}")
        print("\nUntil these are present, grade-adjusted pace and elevation stay")
        print("unavailable for the affected activities, and each one records why.")
        return 1

    print("\nAll required tiles present. Re-sync or re-import activities to")
    print("populate elevation and grade-adjusted pace for existing records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
