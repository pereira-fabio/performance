"""
Timeline resampling for workout ingestion.

Health Connect delivers every channel as an independent series with its own
timestamps: GPS route points at ~5 s, heart rate at ~1 Hz with gaps, and speed
or cadence frequently as a single aggregate sample for the whole session.
Joining those on exact timestamp equality keeps only the points that happen to
coincide -- measured against real Nothing X exports, that is between 2% and 63%
of route points depending on the session.

Every channel is therefore resampled onto a uniform 1 Hz grid using a nearest
sample within an explicit tolerance, and the fraction of the grid actually
backed by a real sample is recorded next to it. Nothing here substitutes a
value it does not have: a channel with no usable source is reported unavailable
so callers can decline to compute metrics that depend on it.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
import math

import numpy as np

# Join tolerances, in seconds, either side of a grid point.
HR_TOLERANCE_SEC = 5.0
SPEED_TOLERANCE_SEC = 5.0
CADENCE_TOLERANCE_SEC = 10.0

# A channel needs at least this many samples to be treated as a time series
# rather than a single session-level aggregate.
MIN_SERIES_SAMPLES = 10

# GPS points implying a speed above this are treated as position glitches.
MAX_PLAUSIBLE_SPEED_MPS = 12.0

# Speed is differentiated from GPS distance, so it is smoothed over this window
# to suppress jitter without flattening genuine pace changes.
SPEED_SMOOTHING_SEC = 15

# Half-width of the window used to differentiate altitude against distance.
GRADE_HALF_WINDOW_SEC = 5
GRADE_MIN_RUN_M = 5.0
GRADE_CLIP = 0.40

# Altitude varying by less than this across a whole session is treated as
# absent rather than flat ground -- devices that do not record elevation write
# a constant, and a constant would silently make every grade exactly zero.
MIN_ALTITUDE_RANGE_M = 1.0

# A grid is only built if the session is at least this long.
MIN_SESSION_SEC = 30.0
# Guard against a malformed payload producing a multi-million point grid.
MAX_GRID_POINTS = 12 * 3600


@dataclass
class Channel:
    """One resampled data channel plus how much of it is real."""

    values: np.ndarray                      # float array over the grid, NaN where unknown
    available: bool = False                 # usable as a time series
    coverage: float = 0.0                   # 0..1 of grid points backed by a sample
    sample_count: int = 0
    median_interval_sec: Optional[float] = None
    max_gap_sec: Optional[float] = None
    scalar: Optional[float] = None          # session-level aggregate, when not a series

    def as_quality(self) -> Dict[str, object]:
        return {
            "available": self.available,
            "coverage": round(self.coverage, 4),
            "sample_count": self.sample_count,
            "median_interval_sec": self.median_interval_sec,
            "max_gap_sec": self.max_gap_sec,
        }


@dataclass
class Timeline:
    """A uniform 1 Hz view of a session."""

    t: np.ndarray                           # epoch seconds
    offset: np.ndarray                      # seconds since session start
    dt: float = 1.0

    lat: Optional[np.ndarray] = None
    lng: Optional[np.ndarray] = None
    altitude: Optional[np.ndarray] = None
    distance: Optional[np.ndarray] = None   # cumulative metres
    speed: Optional[np.ndarray] = None      # m/s
    grade: Optional[np.ndarray] = None      # rise/run, decimal
    gap_speed: Optional[np.ndarray] = None  # grade-adjusted m/s

    channels: Dict[str, Channel] = field(default_factory=dict)
    has_gps: bool = False
    has_altitude: bool = False
    altitude_source: Optional[str] = None   # "device" or "dem"
    dem_info: Optional[Dict[str, object]] = None
    notes: List[str] = field(default_factory=list)

    def __len__(self) -> int:
        return int(len(self.t))

    @property
    def heart_rate(self) -> Optional[np.ndarray]:
        ch = self.channels.get("heart_rate")
        return ch.values if ch and ch.available else None

    @property
    def cadence(self) -> Optional[np.ndarray]:
        ch = self.channels.get("cadence")
        return ch.values if ch and ch.available else None

    def moving_mask(self, threshold_mps: float = 0.5) -> np.ndarray:
        if self.speed is None:
            return np.zeros(len(self), dtype=bool)
        return np.nan_to_num(self.speed, nan=0.0) >= threshold_mps

    def moving_seconds(self, threshold_mps: float = 0.5) -> float:
        return float(np.count_nonzero(self.moving_mask(threshold_mps)) * self.dt)

    def quality_report(self) -> Dict[str, object]:
        report: Dict[str, object] = {name: ch.as_quality() for name, ch in self.channels.items()}
        report["gps"] = {"available": self.has_gps}
        report["altitude"] = {
            "available": self.has_altitude,
            "source": self.altitude_source,
        }
        if self.dem_info:
            report["altitude"]["dem"] = self.dem_info
        report["grid_seconds"] = len(self)
        if self.notes:
            report["notes"] = list(self.notes)
        return report


def to_epoch_seconds(value) -> Optional[float]:
    """Accepts a datetime (naive treated as UTC) or a numeric epoch."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Millisecond epochs are common in health exports.
        return float(value) / 1000.0 if float(value) > 1e11 else float(value)
    tz = getattr(value, "tzinfo", None)
    if tz is None:
        from datetime import timezone

        value = value.replace(tzinfo=timezone.utc)
    return float(value.timestamp())


def _series_stats(times: np.ndarray) -> Tuple[Optional[float], Optional[float]]:
    if len(times) < 2:
        return None, None
    gaps = np.diff(times)
    gaps = gaps[gaps > 0]
    if len(gaps) == 0:
        return None, None
    return float(np.median(gaps)), float(np.max(gaps))


def nearest_join(
    grid: np.ndarray,
    times: Sequence[float],
    values: Sequence[float],
    tolerance_sec: float,
) -> np.ndarray:
    """Nearest sample to each grid point, NaN beyond `tolerance_sec`."""
    out = np.full(len(grid), np.nan)
    if len(times) == 0:
        return out

    times = np.asarray(times, dtype=float)
    values = np.asarray(values, dtype=float)
    order = np.argsort(times)
    times, values = times[order], values[order]

    if len(times) == 1:
        within = np.abs(grid - times[0]) <= tolerance_sec
        out[within] = values[0]
        return out

    idx = np.searchsorted(times, grid)
    left = np.clip(idx - 1, 0, len(times) - 1)
    right = np.clip(idx, 0, len(times) - 1)
    d_left = np.abs(grid - times[left])
    d_right = np.abs(grid - times[right])
    take_right = d_right < d_left
    best = np.where(take_right, right, left)
    best_dist = np.where(take_right, d_right, d_left)

    out = values[best]
    out[best_dist > tolerance_sec] = np.nan
    return out


def _build_channel(
    grid: np.ndarray,
    samples: Sequence[Tuple[float, float]],
    tolerance_sec: float,
    name: str,
    notes: List[str],
) -> Channel:
    """Resample one irregular series, or fall back to a session-level scalar."""
    clean = [(t, v) for t, v in samples if t is not None and v is not None and not math.isnan(v)]
    if not clean:
        return Channel(values=np.full(len(grid), np.nan), sample_count=0)

    clean.sort(key=lambda p: p[0])

    # Devices commonly write each reading twice at the same instant. Collapse
    # duplicate timestamps so the sample count and interval statistics describe
    # the real measurement rate rather than the write rate.
    collapsed: Dict[float, List[float]] = {}
    for t, v in clean:
        collapsed.setdefault(t, []).append(v)
    duplicates = len(clean) - len(collapsed)
    if duplicates:
        notes.append(f"{name}: collapsed {duplicates} duplicate-timestamp sample(s)")

    times = np.array(sorted(collapsed), dtype=float)
    values = np.array([float(np.mean(collapsed[t])) for t in times], dtype=float)
    clean = list(zip(times, values))
    median_iv, max_gap = _series_stats(times)

    # Too sparse to be a series: keep the mean as an aggregate and say so.
    if len(clean) < MIN_SERIES_SAMPLES:
        notes.append(
            f"{name}: {len(clean)} sample(s) for the whole session, kept as a session average only"
        )
        return Channel(
            values=np.full(len(grid), np.nan),
            available=False,
            coverage=0.0,
            sample_count=len(clean),
            median_interval_sec=median_iv,
            max_gap_sec=max_gap,
            scalar=float(np.mean(values)),
        )

    joined = nearest_join(grid, times, values, tolerance_sec)
    coverage = float(np.count_nonzero(~np.isnan(joined))) / max(len(grid), 1)
    return Channel(
        values=joined,
        available=coverage > 0.0,
        coverage=coverage,
        sample_count=len(clean),
        median_interval_sec=median_iv,
        max_gap_sec=max_gap,
        scalar=float(np.mean(values)),
    )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _cumulative_route(
    points: List[Tuple[float, float, float, Optional[float]]],
    notes: List[str],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """(times, cumulative distance, lat, lng, altitude) with glitch points dropped."""
    times, dists, lats, lngs, alts = [], [], [], [], []
    cum = 0.0
    dropped = 0
    prev = None

    for t, lat, lng, alt in points:
        if prev is not None:
            dt = t - prev[0]
            if dt <= 0:
                continue
            step = _haversine(prev[1], prev[2], lat, lng)
            if step / dt > MAX_PLAUSIBLE_SPEED_MPS:
                dropped += 1
                continue
            cum += step
        times.append(t)
        dists.append(cum)
        lats.append(lat)
        lngs.append(lng)
        alts.append(alt if alt is not None else np.nan)
        prev = (t, lat, lng)

    if dropped:
        notes.append(f"gps: dropped {dropped} point(s) implying over {MAX_PLAUSIBLE_SPEED_MPS} m/s")

    alt_arr = np.array(alts, dtype=float)
    return (
        np.array(times, dtype=float),
        np.array(dists, dtype=float),
        np.array(lats, dtype=float),
        np.array(lngs, dtype=float),
        None if np.all(np.isnan(alt_arr)) else alt_arr,
    )


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or len(values) < window:
        return values
    kernel = np.ones(window) / window
    padded = np.pad(values, (window // 2, window - 1 - window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def build_timeline(
    start_time,
    end_time,
    route_points: Optional[Sequence] = None,
    heart_rate_series: Optional[Sequence] = None,
    speed_series: Optional[Sequence] = None,
    cadence_series: Optional[Sequence] = None,
    elevation_provider=None,
) -> Optional[Timeline]:
    """
    Resample a session onto a uniform 1 Hz grid.

    `elevation_provider` is an optional callable taking (lat, lng) arrays and
    returning (elevation_array, info_dict). It is consulted only when the device
    recorded no usable altitude of its own, so a device that reports real
    elevation is always preferred over a terrain model.

    Returns None when the session is too short or carries no usable channel at
    all. Callers must consult `Timeline.channels` and `has_gps` / `has_altitude`
    before computing any derived metric.
    """
    notes: List[str] = []

    t_start = to_epoch_seconds(start_time)
    t_end = to_epoch_seconds(end_time)

    route = []
    for p in route_points or []:
        pt = to_epoch_seconds(getattr(p, "time", None))
        lat, lng = getattr(p, "lat", None), getattr(p, "lng", None)
        if pt is None or lat is None or lng is None:
            continue
        route.append((pt, float(lat), float(lng), getattr(p, "altitude", None)))
    route.sort(key=lambda x: x[0])

    hr_samples = [
        (to_epoch_seconds(getattr(s, "time", None)), getattr(s, "bpm", None))
        for s in (heart_rate_series or [])
    ]
    speed_samples = [
        (to_epoch_seconds(getattr(s, "time", None)), getattr(s, "speed_mps", None))
        for s in (speed_series or [])
    ]
    cadence_samples = [
        (to_epoch_seconds(getattr(s, "time", None)), getattr(s, "spm", None))
        for s in (cadence_series or [])
    ]

    # Bound the grid by whatever data actually exists, not just the declared window.
    candidates = [t for t, _ in hr_samples + speed_samples + cadence_samples if t is not None]
    if route:
        candidates += [route[0][0], route[-1][0]]
    if t_start is not None:
        candidates.append(t_start)
    if t_end is not None:
        candidates.append(t_end)
    if not candidates:
        return None

    grid_start = min(candidates)
    grid_end = max(candidates)
    span = grid_end - grid_start
    if span < MIN_SESSION_SEC:
        return None
    if span > MAX_GRID_POINTS:
        notes.append(f"session span {span:.0f}s truncated to {MAX_GRID_POINTS}s")
        grid_end = grid_start + MAX_GRID_POINTS

    grid = np.arange(grid_start, grid_end + 1.0, 1.0)
    tl = Timeline(t=grid, offset=grid - grid_start, dt=1.0, notes=notes)

    # --- GPS: position, cumulative distance, altitude -----------------------
    if len(route) >= 2:
        r_t, r_dist, r_lat, r_lng, r_alt = _cumulative_route(route, notes)
        if len(r_t) >= 2:
            tl.has_gps = True
            tl.distance = np.interp(grid, r_t, r_dist, left=r_dist[0], right=r_dist[-1])
            tl.lat = np.interp(grid, r_t, r_lat, left=np.nan, right=np.nan)
            tl.lng = np.interp(grid, r_t, r_lng, left=np.nan, right=np.nan)

            gps_iv, gps_gap = _series_stats(r_t)
            tl.channels["gps"] = Channel(
                values=tl.distance,
                available=True,
                coverage=1.0,
                sample_count=len(r_t),
                median_interval_sec=gps_iv,
                max_gap_sec=gps_gap,
            )

            if r_alt is not None:
                finite = r_alt[~np.isnan(r_alt)]
                if len(finite) >= 2 and float(np.max(finite) - np.min(finite)) >= MIN_ALTITUDE_RANGE_M:
                    valid = ~np.isnan(r_alt)
                    tl.altitude = np.interp(grid, r_t[valid], r_alt[valid])
                    tl.has_altitude = True
                    tl.altitude_source = "device"
                else:
                    notes.append(
                        "altitude: present but constant, treated as unavailable "
                        "(device does not record elevation)"
                    )

            # Fall back to a terrain model only where the device gave nothing.
            if not tl.has_altitude and elevation_provider is not None:
                try:
                    dem_elev, dem_info = elevation_provider(tl.lat, tl.lng)
                except Exception as exc:
                    dem_elev, dem_info = None, {"error": str(exc)}
                if dem_elev is not None and np.count_nonzero(~np.isnan(dem_elev)) > 0:
                    tl.altitude = dem_elev
                    tl.has_altitude = True
                    tl.altitude_source = "dem"
                    tl.dem_info = dem_info
                    notes.append(
                        "altitude: recovered from terrain model, device recorded none"
                    )
                elif dem_info:
                    tl.dem_info = dem_info

    # --- Speed --------------------------------------------------------------
    if tl.distance is not None:
        # Differentiate GPS distance; this is the only dense speed source most
        # devices provide, since SpeedRecord is often one sample per session.
        raw = np.gradient(tl.distance, tl.dt)
        raw = np.clip(raw, 0.0, MAX_PLAUSIBLE_SPEED_MPS)
        tl.speed = _rolling_mean(raw, SPEED_SMOOTHING_SEC)
    else:
        speed_ch = _build_channel(grid, speed_samples, SPEED_TOLERANCE_SEC, "speed", notes)
        tl.channels["speed"] = speed_ch
        if speed_ch.available:
            filled = np.nan_to_num(speed_ch.values, nan=0.0)
            tl.speed = _rolling_mean(filled, SPEED_SMOOTHING_SEC)
            tl.distance = np.cumsum(tl.speed) * tl.dt
            notes.append("distance derived from speed samples; no GPS route present")
        else:
            notes.append(
                "no GPS route and no usable speed series: pace, distance and "
                "grade-adjusted metrics are unavailable for this session"
            )

    # --- Grade and grade-adjusted speed ------------------------------------
    if tl.has_altitude and tl.distance is not None and tl.speed is not None:
        from backend.app.physiology.gap import grade_cost_ratio

        w = GRADE_HALF_WINDOW_SEC
        rise = np.zeros(len(grid))
        run = np.zeros(len(grid))
        rise[w:-w] = tl.altitude[2 * w :] - tl.altitude[: -2 * w]
        run[w:-w] = tl.distance[2 * w :] - tl.distance[: -2 * w]
        grade = np.where(run >= GRADE_MIN_RUN_M, rise / np.maximum(run, 1e-9), 0.0)
        tl.grade = np.clip(grade, -GRADE_CLIP, GRADE_CLIP)
        ratios = np.array([grade_cost_ratio(float(g)) for g in tl.grade])
        tl.gap_speed = tl.speed * ratios
    elif tl.speed is not None:
        # No elevation means no grade adjustment is possible. GAP is left unset
        # rather than silently equal to raw speed.
        tl.grade = None
        tl.gap_speed = None

    # --- Heart rate and cadence --------------------------------------------
    tl.channels["heart_rate"] = _build_channel(
        grid, hr_samples, HR_TOLERANCE_SEC, "heart_rate", notes
    )
    tl.channels["cadence"] = _build_channel(
        grid, cadence_samples, CADENCE_TOLERANCE_SEC, "cadence", notes
    )
    if tl.distance is not None and "speed" not in tl.channels:
        tl.channels["speed"] = Channel(
            values=tl.speed,
            available=True,
            coverage=1.0,
            sample_count=len(route),
            median_interval_sec=tl.channels.get("gps").median_interval_sec if tl.channels.get("gps") else None,
        )

    if tl.speed is None and not tl.channels["heart_rate"].available:
        return None

    return tl
