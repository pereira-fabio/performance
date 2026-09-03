"""
Elevation from a local Digital Elevation Model.

Many wearables write no altitude at all -- Nothing X writes a constant 0.0 for
every route point -- which leaves grade undefined and makes grade-adjusted pace
impossible. Terrain height is a function of position, so it can be recovered
from the GPS track against a DEM.

This reads SRTM `.hgt` tiles directly: raw big-endian int16, square, one file
per 1 degree cell, north row first. That format needs no GDAL or rasterio, so
the container stays slim, and the tiles sit on local storage -- GPS traces are
never sent to a remote elevation service.

Sampled elevation is smoothed along the track before use. Raw DEM samples under
GPS lateral error produce a saw-toothed profile that inflates total ascent
dramatically; smoothing is what makes the resulting climb figure meaningful.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple
import math
import os
import zipfile

import numpy as np

# SRTM marks missing data with this sentinel.
SRTM_VOID = -32768

# Recognised tile side lengths, in posts: SRTM3 (~90 m) and SRTM1 (~30 m).
TILE_SIZES = {1201 * 1201 * 2: 1201, 3601 * 3601 * 2: 3601}

# Elevation is averaged over roughly this much track before grade and ascent
# are derived from it.
SMOOTHING_DISTANCE_M = 60.0

# Ascent is only credited once the profile has moved this far from the last
# committed point. Smoothing alone leaves enough residual wander to accumulate
# hundreds of false metres over a long run.
ASCENT_THRESHOLD_M = 3.0

# Ignore a tile whose values are entirely void.
MIN_VALID_FRACTION = 0.05


@dataclass
class DEMResult:
    elevation: np.ndarray          # metres, NaN where unavailable
    coverage: float                # 0..1 of points resolved
    tiles_used: List[str]
    tiles_missing: List[str]
    resolution_m: Optional[int]    # nominal post spacing


def tile_name(lat: float, lng: float) -> str:
    """SRTM tile covering a coordinate, e.g. 49.51,5.88 -> 'N49E005'."""
    lat_i = math.floor(lat)
    lng_i = math.floor(lng)
    ns = "N" if lat_i >= 0 else "S"
    ew = "E" if lng_i >= 0 else "W"
    return f"{ns}{abs(lat_i):02d}{ew}{abs(lng_i):03d}"


def required_tiles(lats, lngs) -> List[str]:
    """Distinct tiles needed to cover a set of coordinates."""
    seen = set()
    for la, lo in zip(lats, lngs):
        if la is None or lo is None or np.isnan(la) or np.isnan(lo):
            continue
        seen.add(tile_name(float(la), float(lo)))
    return sorted(seen)


def _find_tile_file(dem_dir: str, name: str) -> Optional[str]:
    for candidate in (f"{name}.hgt", f"{name}.HGT", f"{name}.hgt.zip", f"{name}.zip"):
        path = os.path.join(dem_dir, candidate)
        if os.path.exists(path):
            return path
    return None


@lru_cache(maxsize=16)
def _load_tile(path: str) -> Optional[Tuple[np.ndarray, int]]:
    """Load one tile as a (size, size) float array with voids as NaN."""
    try:
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".hgt")]
                if not names:
                    return None
                raw = zf.read(names[0])
            size = TILE_SIZES.get(len(raw))
            if size is None:
                return None
            data = np.frombuffer(raw, dtype=">i2").reshape(size, size)
        else:
            size = TILE_SIZES.get(os.path.getsize(path))
            if size is None:
                return None
            data = np.memmap(path, dtype=">i2", mode="r", shape=(size, size))

        arr = np.asarray(data, dtype=np.float64)
        arr[arr == SRTM_VOID] = np.nan
        if np.count_nonzero(~np.isnan(arr)) / arr.size < MIN_VALID_FRACTION:
            return None
        return arr, size
    except Exception:
        return None


def _sample_tile(arr: np.ndarray, size: int, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    """Bilinear sample. Nearest-neighbour would stair-step and fake grade spikes."""
    lat0 = np.floor(lats)
    lng0 = np.floor(lngs)
    n = size - 1

    # Row 0 is the northern edge, so latitude runs backwards down the array.
    row_f = (1.0 - (lats - lat0)) * n
    col_f = (lngs - lng0) * n
    row_f = np.clip(row_f, 0, n)
    col_f = np.clip(col_f, 0, n)

    r0 = np.floor(row_f).astype(int)
    c0 = np.floor(col_f).astype(int)
    r1 = np.minimum(r0 + 1, n)
    c1 = np.minimum(c0 + 1, n)
    dr = row_f - r0
    dc = col_f - c0

    v00, v01 = arr[r0, c0], arr[r0, c1]
    v10, v11 = arr[r1, c0], arr[r1, c1]

    out = (
        v00 * (1 - dr) * (1 - dc)
        + v01 * (1 - dr) * dc
        + v10 * dr * (1 - dc)
        + v11 * dr * dc
    )
    # A void in any corner poisons the interpolation; fall back to the nearest
    # valid corner rather than returning a number derived from a sentinel.
    bad = np.isnan(out)
    if np.any(bad):
        stack = np.stack([v00[bad], v01[bad], v10[bad], v11[bad]])
        all_void = np.all(np.isnan(stack), axis=0)
        with np.errstate(invalid="ignore"):
            filled = np.where(all_void, np.nan, np.nanmean(np.nan_to_num(stack, nan=0.0), axis=0))
        # Recompute the mean over only the valid corners.
        valid_count = np.count_nonzero(~np.isnan(stack), axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            summed = np.nansum(stack, axis=0)
            filled = np.where(valid_count > 0, summed / np.maximum(valid_count, 1), np.nan)
        out[bad] = filled
    return out


def sample_elevation(lats, lngs, dem_dir: str) -> DEMResult:
    """Elevation for each coordinate, NaN where no tile covers it."""
    lats = np.asarray(lats, dtype=float)
    lngs = np.asarray(lngs, dtype=float)
    out = np.full(len(lats), np.nan)

    if not dem_dir or not os.path.isdir(dem_dir):
        return DEMResult(out, 0.0, [], [], None)

    valid = ~np.isnan(lats) & ~np.isnan(lngs)
    if not np.any(valid):
        return DEMResult(out, 0.0, [], [], None)

    used: List[str] = []
    missing: List[str] = []
    resolution: Optional[int] = None

    names = np.array(
        [tile_name(la, lo) if v else "" for la, lo, v in zip(lats, lngs, valid)]
    )
    for name in sorted(set(names[names != ""])):
        mask = names == name
        path = _find_tile_file(dem_dir, name)
        if not path:
            missing.append(str(name))
            continue
        loaded = _load_tile(path)
        if loaded is None:
            missing.append(str(name))
            continue
        arr, size = loaded
        out[mask] = _sample_tile(arr, size, lats[mask], lngs[mask])
        used.append(str(name))
        resolution = 30 if size == 3601 else 90

    coverage = float(np.count_nonzero(~np.isnan(out))) / max(len(out), 1)
    return DEMResult(out, coverage, used, missing, resolution)


def smooth_elevation(
    distance_m: np.ndarray,
    elevation_m: np.ndarray,
    window_m: float = SMOOTHING_DISTANCE_M,
) -> np.ndarray:
    """
    Average elevation over a fixed length of track.

    The samples are on a uniform time grid, so the window is converted from
    metres to samples using the median step. Without this the profile carries
    GPS jitter straight into grade and total ascent.
    """
    n = len(elevation_m)
    if n < 5:
        return elevation_m

    steps = np.diff(distance_m)
    steps = steps[steps > 0]
    if len(steps) == 0:
        return elevation_m

    per_sample = float(np.median(steps))
    if per_sample <= 0:
        return elevation_m

    window = int(round(window_m / per_sample))
    window = max(3, min(window, n if n % 2 else n - 1))
    if window % 2 == 0:
        window += 1
    if window >= n:
        window = n if n % 2 else n - 1
    if window < 3:
        return elevation_m

    filled = elevation_m.copy()
    bad = np.isnan(filled)
    if np.all(bad):
        return elevation_m
    if np.any(bad):
        idx = np.arange(n)
        filled[bad] = np.interp(idx[bad], idx[~bad], filled[~bad])

    pad = window // 2
    padded = np.pad(filled, (pad, pad), mode="edge")
    kernel = np.ones(window) / window
    return np.convolve(padded, kernel, mode="valid")


def elevation_gain_loss(
    elevation_m: np.ndarray,
    threshold_m: float = ASCENT_THRESHOLD_M,
) -> Tuple[float, float]:
    """
    Total ascent and descent, ignoring wander below `threshold_m`.

    Summing every positive difference counts measurement noise as climbing: on a
    profile carrying only 2 m of jitter that inflates a 39 m climb to over 1800 m.
    Movement is credited only once it exceeds the threshold from the last
    committed point, which then becomes the new reference.
    """
    values = np.asarray(elevation_m, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return 0.0, 0.0

    gain = loss = 0.0
    anchor = float(values[0])
    for x in values[1:]:
        delta = float(x) - anchor
        if delta >= threshold_m:
            gain += delta
            anchor = float(x)
        elif delta <= -threshold_m:
            loss += -delta
            anchor = float(x)
    return round(gain, 1), round(loss, 1)
