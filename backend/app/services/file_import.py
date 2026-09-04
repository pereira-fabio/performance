"""
Import activities from files a watch platform can export.

The Android companion reads Health Connect directly, which is the best path
when it exists -- but it exists only on Android. A Garmin owner on an iPhone
has no companion app and no Health Connect, so the way in has to be files.

Garmin Connect exports TCX or GPX per activity, and a zip of FIT files for
"Export All Data". Polar, Coros, Suunto and Wahoo all export at least one of
the three. None of it needs an API key, a developer account, or anything that
could stop working when a vendor changes their terms.

Every parser produces the same payload the phone sends, so a file and a live
sync go through exactly one physiology pipeline.
"""
import io
import zipfile
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from xml.etree import ElementTree

from backend.app.models.schemas import (
    HealthConnectSessionPayload, LocationPoint, HeartRateSample,
    SpeedSample, CadenceSample,
)

# FIT stores coordinates as semicircles over a signed 32-bit range.
SEMICIRCLE_TO_DEGREES = 180.0 / (2 ** 31)

SUPPORTED = (".gpx", ".tcx", ".fit", ".zip")

# Sport names as the exporters write them, mapped to ours. Garmin's activity
# type keys are the richest source and are included verbatim.
SPORT_ALIASES = {
    "running": "running", "run": "running", "trail_running": "running",
    "street_running": "running", "track_running": "running",
    "ultra_run": "running", "obstacle_run": "running",
    "treadmill_running": "treadmill", "indoor_running": "treadmill",
    "virtual_run": "treadmill",
    "walking": "walking", "walk": "walking", "casual_walking": "walking",
    "speed_walking": "walking", "indoor_walking": "walking",
    "hiking": "hiking", "hike": "hiking", "mountaineering": "hiking",
    "cycling": "cycling", "biking": "cycling", "road_biking": "cycling",
    "mountain_biking": "cycling", "gravel_cycling": "cycling",
    "indoor_cycling": "cycling", "virtual_ride": "cycling",
    "swimming": "swimming", "lap_swimming": "swimming",
    "open_water_swimming": "swimming",
    "rowing": "rowing", "indoor_rowing": "rowing",
    "training": "gym", "strength_training": "gym", "fitness_equipment": "gym",
    "cardio_training": "gym", "indoor_cardio": "gym", "yoga": "gym",
    "pilates": "gym", "elliptical": "gym", "stair_climbing": "gym",
    "indoor_climbing": "gym", "bouldering": "gym", "hiit": "gym",
    "generic": "other", "other": "other", "multi_sport": "other",
}

# Garmin has well over a hundred activity type keys and adds more. Matching a
# fragment catches the ones the table has not been told about -- a new
# "beach_running" should count as a run, not fall into the catch-all.
SPORT_FRAGMENTS = (
    ("treadmill", "treadmill"),
    ("run", "running"),
    ("jog", "running"),
    ("walk", "walking"),
    ("hik", "hiking"),
    ("trek", "hiking"),
    ("cycl", "cycling"),
    ("bik", "cycling"),
    ("ride", "cycling"),
    ("swim", "swimming"),
    ("row", "rowing"),
    ("strength", "gym"),
    ("cardio", "gym"),
    ("training", "gym"),
)


def normalise_sport(raw: Optional[str]) -> str:
    if not raw:
        return "running"
    key = str(raw).strip().lower().replace(" ", "_")
    if key in SPORT_ALIASES:
        return SPORT_ALIASES[key]
    for fragment, sport in SPORT_FRAGMENTS:
        if fragment in key:
            return sport
    return "other"


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


# ---------------------------------------------------------------- TCX -----
def parse_tcx(data: bytes, name: str) -> List[HealthConnectSessionPayload]:
    """
    Garmin's per-activity export.

    Namespaces are stripped rather than matched: exporters disagree about which
    schema URL they use, and matching on them rejects files that are otherwise
    perfectly readable.
    """
    root = ElementTree.fromstring(data.decode("utf-8", errors="ignore"))
    sessions: List[HealthConnectSessionPayload] = []

    for activity in root.iter():
        if _strip_ns(activity.tag) != "Activity":
            continue

        sport = normalise_sport(activity.get("Sport"))
        activity_id = None
        route, hr, speed, cadence = [], [], [], []
        total_distance = 0.0
        calories = 0.0

        for node in activity.iter():
            tag = _strip_ns(node.tag)
            if tag == "Id" and activity_id is None:
                activity_id = (node.text or "").strip()
            elif tag == "Calories":
                calories += float(node.text or 0)
            elif tag == "DistanceMeters" and _strip_ns(
                    next(iter(activity.iter()), node).tag) and node.text:
                # Lap totals and trackpoint distances share a tag name; the
                # running maximum is the reliable figure either way.
                total_distance = max(total_distance, float(node.text or 0))
            elif tag == "Trackpoint":
                point_time = None
                lat = lng = alt = None
                for child in node.iter():
                    ctag = _strip_ns(child.tag)
                    text = (child.text or "").strip()
                    if ctag == "Time" and text:
                        point_time = _aware(datetime.fromisoformat(text.replace("Z", "+00:00")))
                    elif ctag == "LatitudeDegrees" and text:
                        lat = float(text)
                    elif ctag == "LongitudeDegrees" and text:
                        lng = float(text)
                    elif ctag == "AltitudeMeters" and text:
                        alt = float(text)
                    elif ctag == "Value" and text and _strip_ns(
                            child.tag) == "Value" and "HeartRate" in _strip_ns(node.tag or ""):
                        pass  # handled below
                    elif ctag == "HeartRateBpm":
                        for v in child.iter():
                            if _strip_ns(v.tag) == "Value" and (v.text or "").strip():
                                hr.append((point_time, int(float(v.text))))
                    elif ctag == "Speed" and text:
                        speed.append((point_time, float(text)))
                    elif ctag == "RunCadence" and text:
                        # TCX reports one foot; runners count both.
                        cadence.append((point_time, float(text) * 2))
                if point_time and lat is not None and lng is not None:
                    route.append(LocationPoint(time=point_time, lat=lat, lng=lng, altitude=alt))

        times = [p.time for p in route] + [t for t, _ in hr if t]
        if not times:
            continue
        start, end = min(times), max(times)

        sessions.append(HealthConnectSessionPayload(
            session_id=f"tcx:{activity_id or name}:{int(start.timestamp())}",
            title=f"{sport.capitalize()} activity",
            sport_type=sport, start_time=start, end_time=end,
            distance_meters=total_distance or None,
            calories_kcal=calories or None,
            route_points=route,
            heart_rate_series=[HeartRateSample(time=t, bpm=b) for t, b in hr if t],
            speed_series=[SpeedSample(time=t, speed_mps=s) for t, s in speed if t],
            cadence_series=[CadenceSample(time=t, spm=c) for t, c in cadence if t],
        ))
    return sessions


# ---------------------------------------------------------------- FIT -----
def parse_fit(data: bytes, name: str) -> List[HealthConnectSessionPayload]:
    """
    The format Garmin's bulk export produces.

    Records carry whatever the device recorded, so every channel is treated as
    optional; a treadmill FIT has heart rate and no position, and the pipeline
    already handles that shape.
    """
    import fitparse

    fit = fitparse.FitFile(io.BytesIO(data))

    route, hr, speed, cadence = [], [], [], []
    for record in fit.get_messages("record"):
        values = {d.name: d.value for d in record}
        ts = _aware(values.get("timestamp"))
        if ts is None:
            continue

        lat, lng = values.get("position_lat"), values.get("position_long")
        if lat is not None and lng is not None:
            route.append(LocationPoint(
                time=ts,
                lat=lat * SEMICIRCLE_TO_DEGREES,
                lng=lng * SEMICIRCLE_TO_DEGREES,
                altitude=values.get("enhanced_altitude", values.get("altitude")),
            ))
        if values.get("heart_rate") is not None:
            hr.append(HeartRateSample(time=ts, bpm=int(values["heart_rate"])))
        spd = values.get("enhanced_speed", values.get("speed"))
        if spd is not None:
            speed.append(SpeedSample(time=ts, speed_mps=float(spd)))
        if values.get("cadence") is not None:
            # FIT reports one foot per minute for running.
            cadence.append(CadenceSample(time=ts, spm=float(values["cadence"]) * 2))

    sport = "running"
    distance = calories = None
    start = end = None
    for session in fit.get_messages("session"):
        values = {d.name: d.value for d in session}
        sport = normalise_sport(values.get("sport"))
        distance = values.get("total_distance") or distance
        calories = values.get("total_calories") or calories
        start = _aware(values.get("start_time")) or start
        break

    times = [p.time for p in route] + [s.time for s in hr]
    if not times and start is None:
        return []
    start = start or min(times)
    end = max(times) if times else start

    return [HealthConnectSessionPayload(
        session_id=f"fit:{name}:{int(start.timestamp())}",
        title=f"{sport.capitalize()} activity",
        sport_type=sport, start_time=start, end_time=end,
        distance_meters=float(distance) if distance else None,
        calories_kcal=float(calories) if calories else None,
        route_points=route, heart_rate_series=hr,
        speed_series=speed, cadence_series=cadence,
    )]


# ---------------------------------------------------------------- GPX -----
def parse_gpx(data: bytes, name: str) -> List[HealthConnectSessionPayload]:
    import gpxpy

    gpx = gpxpy.parse(data.decode("utf-8", errors="ignore"))
    route, hr = [], []

    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.time is None:
                    continue
                t = _aware(pt.time)
                route.append(LocationPoint(time=t, lat=pt.latitude, lng=pt.longitude,
                                           altitude=pt.elevation))
                for ext in pt.extensions:
                    for child in ext.iter():
                        tag = _strip_ns(child.tag).lower()
                        if tag in ("hr", "heartrate") and (child.text or "").strip():
                            try:
                                hr.append(HeartRateSample(time=t, bpm=int(float(child.text))))
                            except ValueError:
                                pass

    if not route:
        return []
    start = route[0].time
    return [HealthConnectSessionPayload(
        session_id=f"gpx:{name}:{int(start.timestamp())}",
        title=gpx.name or name.rsplit(".", 1)[0],
        sport_type="running", start_time=start, end_time=route[-1].time,
        route_points=route, heart_rate_series=hr,
    )]


# -------------------------------------------------------------- dispatch --
def parse_any(name: str, data: bytes) -> Tuple[List[HealthConnectSessionPayload], List[str]]:
    """
    Read whatever was uploaded. Returns (sessions, problems).

    A zip is walked rather than rejected: Garmin's bulk export is a zip of
    hundreds of FIT files, and asking someone to unpack and upload them one at
    a time is not an import feature.
    """
    lower = name.lower()
    problems: List[str] = []

    if lower.endswith(".zip"):
        sessions: List[HealthConnectSessionPayload] = []
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return [], [f"{name}: not a readable zip archive"]

        for entry in archive.namelist():
            if entry.endswith("/") or entry.lower().endswith(".zip"):
                continue  # Nested archives are not followed.
            if not entry.lower().endswith((".gpx", ".tcx", ".fit")):
                continue
            try:
                found, errs = parse_any(entry, archive.read(entry))
                sessions.extend(found)
                problems.extend(errs)
            except Exception as exc:
                problems.append(f"{entry}: {exc}")
        if not sessions and not problems:
            problems.append(f"{name}: no GPX, TCX or FIT files inside")
        return sessions, problems

    try:
        if lower.endswith(".tcx"):
            return parse_tcx(data, name), problems
        if lower.endswith(".fit"):
            return parse_fit(data, name), problems
        if lower.endswith(".gpx"):
            return parse_gpx(data, name), problems
    except Exception as exc:
        return [], [f"{name}: {exc}"]

    return [], [f"{name}: unsupported file type (expected GPX, TCX, FIT or ZIP)"]
