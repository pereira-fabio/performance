"""
Ingestion pipeline: irregular device series in, physiology out.

The guiding rule here is that a metric is only produced when the data actually
supports it. Where a channel is missing or too sparse, the corresponding field
is left null and the reason is recorded in `Activity.data_quality`, rather than
being filled with a default that would look like a measurement.
"""
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Activity, ActivityStream, ActivitySplit, BestEffort, DailyHealth, UserProfile, User,
)
from backend.app.models.schemas import HealthConnectSessionPayload
from backend.app.physiology.resample import build_timeline, Timeline
from backend.app.physiology.dem import (
    sample_elevation, smooth_elevation, elevation_gain_loss,
)
from backend.app.physiology.zones import (
    get_default_hr_zones, get_default_pace_zones,
    calculate_hr_time_in_zones, calculate_pace_time_in_zones,
)
from backend.app.physiology.decoupling import calculate_aerobic_decoupling
from backend.app.physiology.trimp import (
    calculate_banister_trimp, calculate_edwards_trimp, calculate_rtss,
)
from backend.app.physiology.best_efforts import calculate_best_efforts
from backend.app.physiology.pmc import calculate_pmc_series
from backend.app.physiology.recovery import calculate_recovery_readiness
from backend.app.physiology.effect import (
    aerobic_training_effect, anaerobic_training_effect, recovery_hours,
)
from backend.app.physiology.progress import activity_xp
from backend.app.core.config import settings
from backend.app.core.sports import is_running

# Persisted stream resolution. The analysis grid is 1 Hz; storing every second
# of a long run is wasteful for a map and a couple of charts.
MAX_STORED_STREAM_POINTS = 2000

# A trailing split shorter than this is dropped rather than shown as a split.
MIN_TRAILING_SPLIT_M = 50.0

# Rolling window for recovery baselines.
BASELINE_DAYS = 7

# "Fastest pace" means the best sustained effort, not a one-sample spike.
FASTEST_WINDOW_SEC = 30.0

# How many prior sessions define what "typical" means for this athlete.
TYPICAL_SESSION_WINDOW = 20

# Intensity above this is not sustainable over a session, so it indicates bad
# pace data rather than a heroic effort.
MAX_PLAUSIBLE_IF = 1.35

# How far a device's reported distance may differ from the measured GPS track
# before the device figure is treated as broken rather than authoritative.
# Real devices agree with summed GPS to within a couple of percent.
MAX_DISTANCE_DIVERGENCE = 0.25


def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _clean(value) -> Optional[float]:
    """NaN and infinities are absences, not numbers."""
    if value is None:
        return None
    v = float(value)
    return None if (math.isnan(v) or math.isinf(v)) else v


class ActivityProcessor:
    """
    Processes one athlete's sessions.

    The account is required rather than optional: every read and write below is
    scoped to it, and defaulting to whoever happens to be first in the table is
    how one athlete's run lands on another's dashboard.
    """

    def __init__(self, db: Session, account: User):
        self.db = db
        self.account = account
        self.user = self._get_or_create_user_profile()

    def _typical_session_load(self, sport_type: str, before, fallback) -> float:
        """
        The athlete's usual session, used as the yardstick for effort.

        Median rather than mean, so one very long run does not raise the bar
        for every session after it. Restricted to the same sport, because an
        hour in the gym and an hour running are not comparable efforts.
        """
        rows = (
            self.db.query(Activity.r_tss)
            .filter(
                Activity.user_id == self.account.id,
                Activity.sport_type == sport_type,
                Activity.r_tss.isnot(None),
                Activity.r_tss > 0,
                Activity.start_time < before,
            )
            .order_by(Activity.start_time.desc())
            .limit(TYPICAL_SESSION_WINDOW)
            .all()
        )
        loads = [float(r[0]) for r in rows]
        if len(loads) >= 3:
            return float(np.median(loads))
        # Too little history to have a norm yet: treat this session as typical,
        # which puts it mid-scale rather than at an arbitrary extreme.
        return float(fallback or 0.0)

    @staticmethod
    def _dem_elevation(lats, lngs):
        """Terrain elevation for a track, used when the device recorded none."""
        dem_dir = getattr(settings, "DEM_DIR", "") or ""
        result = sample_elevation(lats, lngs, dem_dir)
        info = {
            "coverage": round(result.coverage, 4),
            "tiles_used": result.tiles_used,
            "tiles_missing": result.tiles_missing,
            "resolution_m": result.resolution_m,
        }
        if result.coverage <= 0.0:
            if result.tiles_missing:
                info["reason"] = (
                    "no terrain tile covering this route: missing "
                    + ", ".join(result.tiles_missing)
                )
            elif not dem_dir or not os.path.isdir(dem_dir):
                info["reason"] = f"no terrain tile directory at {dem_dir or '(unset)'}"
            return None, info
        return result.elevation, info

    def _get_or_create_user_profile(self) -> UserProfile:
        profile = (
            self.db.query(UserProfile)
            .filter(UserProfile.user_id == self.account.id)
            .first()
        )
        if not profile:
            profile = UserProfile(
                user_id=self.account.id,
                name=self.account.display_name or "Runner",
                max_hr=190, resting_hr=50,
                lthr=168, threshold_pace_sec=240.0, weight_kg=70.0,
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def process_health_connect_session(self, payload: HealthConnectSessionPayload) -> Activity:
        start_time = to_naive_utc(payload.start_time)
        end_time = to_naive_utc(payload.end_time)

        tl = build_timeline(
            start_time=payload.start_time,
            end_time=payload.end_time,
            route_points=payload.route_points,
            heart_rate_series=payload.heart_rate_series,
            speed_series=payload.speed_series,
            cadence_series=payload.cadence_series,
            elevation_provider=self._dem_elevation,
        )
        if tl is None:
            raise ValueError(
                "Session carries no usable data: needs either a GPS route, a "
                "speed series, or a heart rate series of at least 30 seconds."
            )

        quality: Dict[str, Any] = tl.quality_report()
        unavailable: Dict[str, str] = {}

        # The device's own distance total is generally more accurate than summed
        # haversine over raw GPS, which over-measures. Rescale the whole distance
        # track to that total rather than using one source for average pace and
        # another for splits, GAP and best efforts -- mixing them makes the
        # displayed pace disagree with the splits it is supposedly derived from.
        declared = payload.distance_meters
        if declared and declared > 0 and tl.distance is not None:
            measured = float(tl.distance[-1])
            if measured > 0:
                scale = declared / measured
                if abs(scale - 1.0) > MAX_DISTANCE_DIVERGENCE:
                    # GPS is a direct measurement and rarely wrong by this much.
                    # A device total this far off means the reported distance is
                    # broken -- a source writing duplicate DistanceRecords, for
                    # instance -- so keep GPS and record the conflict rather
                    # than propagating the bad figure into pace and every
                    # derived metric.
                    quality["distance_conflict"] = {
                        "gps_meters": round(measured, 1),
                        "device_meters": round(declared, 1),
                        "factor": round(scale, 4),
                        "resolution": "kept GPS distance; device total rejected",
                    }
                    unavailable["device_distance"] = (
                        f"device reported {declared / 1000:.2f} km against "
                        f"{measured / 1000:.2f} km of GPS track "
                        f"({scale:.2f}x); device total ignored"
                    )
                else:
                    tl.distance = tl.distance * scale
                    if tl.speed is not None:
                        tl.speed = tl.speed * scale
                    if tl.gap_speed is not None:
                        tl.gap_speed = tl.gap_speed * scale
                    # Only worth surfacing when the two disagree materially.
                    if abs(scale - 1.0) > 0.02:
                        quality["distance_rescaled"] = {
                            "gps_meters": round(measured, 1),
                            "device_meters": round(declared, 1),
                            "factor": round(scale, 4),
                        }

        elapsed_sec = (end_time - start_time).total_seconds()
        if elapsed_sec <= 0:
            elapsed_sec = float(payload.duration_sec or len(tl))
        moving_sec = tl.moving_seconds()
        if moving_sec <= 0:
            # No speed channel at all -- an indoor session recorded as heart
            # rate only. Moving time cannot be distinguished from stopped time,
            # so the recorded duration is the honest figure. Reporting zero
            # makes a 45-minute gym session look like it never happened.
            moving_sec = elapsed_sec
            unavailable["moving_time"] = (
                "no speed data, so moving time cannot be separated from "
                "elapsed time; elapsed duration reported instead"
            )

        # --- distance and pace ----------------------------------------
        total_dist = float(tl.distance[-1]) if tl.distance is not None else None

        avg_speed = avg_pace_sec = max_speed = None
        if total_dist and moving_sec > 0:
            avg_speed = total_dist / moving_sec
            avg_pace_sec = 1000.0 / avg_speed if avg_speed > 0 else None
        if tl.speed is not None:
            moving = tl.moving_mask()
            if np.any(moving):
                # The fastest *sustained* speed, over half a minute. A single
                # GPS spike would otherwise be reported as a sprint: a 7:19/km
                # run should not claim a 3:24/km best.
                window = int(min(FASTEST_WINDOW_SEC / tl.dt, np.count_nonzero(moving)))
                if window >= 3:
                    rolled = np.convolve(tl.speed[moving], np.ones(window) / window, mode="valid")
                    max_speed = float(np.max(rolled)) if len(rolled) else None
                else:
                    max_speed = float(np.max(tl.speed[moving]))
        if total_dist is None:
            unavailable["distance"] = "no GPS route and no usable speed series"

        # --- grade-adjusted pace --------------------------------------
        gap_pace_sec = None
        if tl.gap_speed is not None:
            moving = tl.moving_mask()
            if np.any(moving):
                mean_gap = float(np.nanmean(tl.gap_speed[moving]))
                gap_pace_sec = 1000.0 / mean_gap if mean_gap > 0 else None
        else:
            dem_reason = (tl.dem_info or {}).get("reason")
            unavailable["gap_pace"] = (
                f"no elevation data ({dem_reason}), so grade cannot be determined "
                "and pace cannot be grade-adjusted"
                if dem_reason else
                "no elevation data, so grade cannot be determined and pace "
                "cannot be grade-adjusted"
            )

        # --- elevation -------------------------------------------------
        if tl.altitude_source == "dem" and tl.distance is not None:
            # Raw terrain samples under GPS lateral error saw-tooth badly and
            # would inflate total ascent, so smooth before anything reads it.
            tl.altitude = smooth_elevation(tl.distance, tl.altitude)
            self._recompute_grade(tl)

        elev_gain = elev_loss = None
        if tl.has_altitude:
            # Threshold hysteresis, so profile noise is not counted as climbing.
            elev_gain, elev_loss = elevation_gain_loss(tl.altitude)
        elif payload.elevation_gain_m is not None:
            elev_gain = float(payload.elevation_gain_m)
            elev_loss = float(payload.elevation_loss_m or 0.0)
        else:
            unavailable["elevation"] = "device did not record altitude"

        # --- heart rate ------------------------------------------------
        hr_channel = tl.channels.get("heart_rate")
        hr_values = tl.heart_rate
        avg_hr = max_hr = min_hr = None
        if hr_values is not None:
            measured = hr_values[~np.isnan(hr_values) & (hr_values > 30)]
            if len(measured):
                avg_hr, max_hr, min_hr = (
                    int(np.mean(measured)), int(np.max(measured)), int(np.min(measured)),
                )
        if avg_hr is None:
            unavailable["heart_rate"] = "no usable heart rate samples in this session"

        # --- cadence and stride ---------------------------------------
        cad_channel = tl.channels.get("cadence")
        avg_cad = max_cad = avg_stride = None
        if cad_channel is not None:
            if cad_channel.available:
                measured = cad_channel.values[~np.isnan(cad_channel.values)]
                measured = measured[measured > 0]
                if len(measured):
                    avg_cad, max_cad = float(np.mean(measured)), float(np.max(measured))
            elif cad_channel.scalar:
                # A single aggregate sample is a session average, not a series.
                avg_cad = float(cad_channel.scalar)
                unavailable["cadence_series"] = (
                    f"only {cad_channel.sample_count} cadence sample(s); session "
                    "average available but no per-point cadence"
                )
        if avg_speed and avg_cad and avg_cad > 50:
            avg_stride = round(avg_speed / (avg_cad / 60.0), 2)

        # --- decoupling and efficiency --------------------------------
        decoupling_pct = aerobic_ef = None
        if tl.speed is not None and hr_values is not None:
            decoupling_pct, aerobic_ef, reason = calculate_aerobic_decoupling(
                speeds_mps=tl.speed, heart_rates=hr_values, dt=tl.dt,
            )
            if reason:
                unavailable["aerobic_decoupling"] = reason
        else:
            unavailable["aerobic_decoupling"] = "needs both speed and heart rate"

        # --- zones and training load ----------------------------------
        hr_zone_seconds = pace_zone_seconds = None
        banister = edwards = None
        if hr_values is not None:
            hr_zones = get_default_hr_zones(self.user.max_hr, self.user.resting_hr, self.user.lthr)
            hr_zone_seconds = calculate_hr_time_in_zones(hr_values, tl.dt, hr_zones)
            banister, reason = calculate_banister_trimp(
                heart_rates=hr_values, dt=tl.dt, max_hr=self.user.max_hr,
                resting_hr=self.user.resting_hr, gender=self.user.gender,
            )
            if reason:
                unavailable["trimp"] = reason
            else:
                edwards = calculate_edwards_trimp(hr_zone_seconds)

        if tl.speed is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                pace_series = np.where(tl.speed > 0.1, 1000.0 / np.maximum(tl.speed, 1e-9), np.nan)
            pace_zones = get_default_pace_zones(self.user.threshold_pace_sec)
            pace_zone_seconds = calculate_pace_time_in_zones(pace_series, tl.dt, pace_zones)

        # rTSS is defined on grade-adjusted pace. Without elevation the honest
        # fallback is raw pace, which is recorded as such rather than presented
        # as if the grade adjustment had been applied.
        r_tss = intensity_factor = None
        rtss_basis = None
        speed_for_rtss = tl.gap_speed if tl.gap_speed is not None else tl.speed
        if speed_for_rtss is not None:
            r_tss, intensity_factor, _ngp, reason = calculate_rtss(
                gap_speeds_mps=speed_for_rtss, dt=tl.dt,
                threshold_pace_sec=self.user.threshold_pace_sec,
            )
            # Sustaining much above threshold pace for a whole session is not
            # physically plausible; an intensity that high means the pace is
            # wrong, usually from glitched GPS over a very short session. Load
            # grows with the square of intensity, so left alone a 100-second
            # walk can outweigh a real run and carry that error into training
            # effect, recovery and experience.
            if intensity_factor and intensity_factor > MAX_PLAUSIBLE_IF:
                capped = MAX_PLAUSIBLE_IF
                moving = float(np.count_nonzero(tl.moving_mask()) * tl.dt)
                quality["intensity_capped"] = {
                    "measured": intensity_factor,
                    "capped_to": capped,
                    "reason": "pace implies an intensity that cannot be sustained",
                }
                r_tss = round((moving * capped ** 2) / 36.0, 1)
                intensity_factor = capped
            rtss_basis = "grade_adjusted" if tl.gap_speed is not None else "raw_pace_no_elevation"
            if reason:
                unavailable["r_tss"] = reason
        if r_tss is None and banister is not None:
            # Heart-rate-only sessions still carry real load.
            r_tss = banister
            rtss_basis = "banister_trimp_fallback"
        if r_tss is None:
            unavailable.setdefault("r_tss", "no pace or heart rate basis for training load")

        latest_health = (
            self.db.query(DailyHealth)
            .filter(DailyHealth.user_id == self.account.id,
                    DailyHealth.date <= start_time.date())
            .order_by(DailyHealth.date.desc())
            .first()
        )
        ctl = float(latest_health.ctl) if latest_health else 0.0
        tsb = float(latest_health.tsb) if latest_health else 0.0
        readiness = latest_health.readiness_score if latest_health else None

        reference_load = self._typical_session_load(
            payload.sport_type or "running", start_time, r_tss
        )
        te_aerobic, te_reason = aerobic_training_effect(r_tss, reference_load)
        te_anaerobic, _ = anaerobic_training_effect(hr_zone_seconds, reference_load)
        recovery, rec_reason = recovery_hours(r_tss, reference_load, tsb, readiness)
        if te_reason:
            unavailable["training_effect"] = te_reason
        if rec_reason:
            unavailable["recovery"] = rec_reason

        quality["unavailable"] = unavailable
        quality["rtss_basis"] = rtss_basis
        quality["estimates"] = {
            # Stated plainly: these are modelled from load, not measured.
            "training_effect": "estimated from training load relative to fitness",
            "recovery_hours": "estimated from training load, form and readiness",
            "reference_session_load": round(reference_load, 1),
        }

        # --- persist ---------------------------------------------------
        existing = (
            self.db.query(Activity)
            .filter(Activity.user_id == self.account.id,
                    Activity.external_id == payload.session_id)
            .first()
        )

        # Never let a re-sync downgrade an activity. A client that has lost
        # access to a channel -- exercise routes are unreadable from a
        # background context on some devices -- would otherwise replace a run
        # that has GPS with the same run stripped of it.
        if existing is not None and existing.data_quality:
            had_gps = bool((existing.data_quality.get("gps") or {}).get("available"))
            had_hr = float(existing.hr_coverage or 0.0)
            new_hr = float(quality.get("heart_rate", {}).get("coverage") or 0.0)
            if (had_gps and not tl.has_gps) or (had_hr > 0.5 and new_hr < had_hr / 2):
                lost = []
                if had_gps and not tl.has_gps:
                    lost.append("GPS route")
                if had_hr > 0.5 and new_hr < had_hr / 2:
                    lost.append(f"heart rate ({had_hr:.0%} -> {new_hr:.0%})")
                print(
                    f"↩️  Keeping existing route/heart-rate for {existing.id}: "
                    f"incoming sync is missing {', '.join(lost)}"
                )
                # Refusing the downgrade must not throw away the rest of the
                # sync. Values that do not depend on the missing channel are
                # still the freshest available, so they are applied; the stream
                # and everything derived from it are left untouched.
                if payload.calories_kcal is not None:
                    existing.calories_kcal = payload.calories_kcal
                if payload.steps is not None:
                    existing.steps = payload.steps
                if payload.vo2_max is not None:
                    existing.vo2_max = payload.vo2_max
                existing.training_effect_aerobic = te_aerobic
                existing.training_effect_anaerobic = te_anaerobic
                existing.recovery_hours = recovery
                existing.xp = activity_xp(
                    existing.r_tss, existing.distance_meters, existing.moving_time_sec
                )
                self.db.commit()
                self.db.refresh(existing)
                return existing

        activity = existing or Activity(external_id=payload.session_id, user_id=self.account.id)
        if existing:
            # Re-sync updates in place. Recreating the row would mint a new id
            # every hour and break any link to the activity.
            for child in list(existing.splits):
                self.db.delete(child)
            for child in list(existing.best_efforts):
                self.db.delete(child)
            if existing.streams:
                self.db.delete(existing.streams)
            self.db.flush()

        activity.name = payload.title or "Running Session"
        activity.sport_type = payload.sport_type or "running"
        activity.start_time = start_time
        activity.end_time = end_time
        activity.elapsed_time_sec = elapsed_sec
        activity.moving_time_sec = moving_sec
        activity.distance_meters = total_dist or 0.0
        activity.avg_speed_mps = _clean(avg_speed)
        activity.max_speed_mps = _clean(max_speed)
        activity.avg_pace_sec_km = _clean(avg_pace_sec)
        activity.gap_pace_sec_km = _clean(gap_pace_sec)
        activity.elevation_gain_m = _clean(elev_gain)
        activity.elevation_loss_m = _clean(elev_loss)
        activity.avg_altitude_m = (
            _clean(float(np.mean(tl.altitude))) if tl.has_altitude else None
        )
        activity.avg_hr = avg_hr
        activity.max_hr = max_hr
        activity.min_hr = min_hr
        activity.avg_cadence = _clean(avg_cad)
        activity.max_cadence = _clean(max_cad)
        activity.avg_stride_length_m = _clean(avg_stride)
        activity.aerobic_decoupling_pct = _clean(decoupling_pct)
        activity.aerobic_efficiency_factor = _clean(aerobic_ef)
        activity.trimp_banister = _clean(banister)
        activity.trimp_edwards = _clean(edwards)
        activity.r_tss = _clean(r_tss)
        activity.intensity_factor = _clean(intensity_factor)
        activity.hr_zone_seconds = hr_zone_seconds
        activity.pace_zone_seconds = pace_zone_seconds
        activity.calories_kcal = payload.calories_kcal
        activity.steps = payload.steps
        activity.vo2_max = payload.vo2_max
        activity.training_effect_aerobic = te_aerobic
        activity.training_effect_anaerobic = te_anaerobic
        activity.recovery_hours = recovery
        activity.xp = activity_xp(r_tss, total_dist, moving_sec)
        activity.source = "health_connect"
        activity.notes = payload.notes
        activity.hr_coverage = round(hr_channel.coverage, 4) if hr_channel else 0.0
        activity.data_quality = quality

        if not existing:
            self.db.add(activity)
        self.db.flush()

        self.db.add(ActivityStream(
            activity_id=activity.id,
            stream_data={"points": self._serialise_stream(tl)},
        ))

        for split in self._compute_splits(tl):
            split.activity_id = activity.id
            self.db.add(split)

        # A walk covering 5 km is not a 5k personal record, so best efforts are
        # only derived for sports whose pace is comparable to a run.
        if tl.distance is not None and is_running(activity.sport_type):
            for be in calculate_best_efforts(
                list(tl.distance), list(tl.offset), start_time
            ):
                existing_pr = (
                    self.db.query(BestEffort)
                    .filter(BestEffort.label == be["label"])
                    .order_by(BestEffort.time_seconds.asc())
                    .first()
                )
                self.db.add(BestEffort(
                    activity_id=activity.id,
                    distance_meters=be["distance_meters"],
                    label=be["label"],
                    time_seconds=be["time_seconds"],
                    pace_sec_km=be["pace_sec_km"],
                    start_time_offset_sec=be["start_time_offset_sec"],
                    achieved_at=be["achieved_at"],
                    is_personal_record=(
                        existing_pr is None or be["time_seconds"] < existing_pr.time_seconds
                    ),
                ))

        self.db.commit()
        self._update_daily_pmc(activity.start_time.date())
        self.db.refresh(activity)
        return activity

    # ------------------------------------------------------------------
    @staticmethod
    def _recompute_grade(tl: Timeline) -> None:
        """Re-derive grade and grade-adjusted speed after altitude changes."""
        from backend.app.physiology.gap import grade_cost_ratio
        from backend.app.physiology.resample import (
            GRADE_HALF_WINDOW_SEC, GRADE_MIN_RUN_M, GRADE_CLIP,
        )

        if tl.altitude is None or tl.distance is None or tl.speed is None:
            return
        w = GRADE_HALF_WINDOW_SEC
        n = len(tl)
        if n <= 2 * w:
            return
        rise = np.zeros(n)
        run = np.zeros(n)
        rise[w:-w] = tl.altitude[2 * w:] - tl.altitude[:-2 * w]
        run[w:-w] = tl.distance[2 * w:] - tl.distance[:-2 * w]
        grade = np.where(run >= GRADE_MIN_RUN_M, rise / np.maximum(run, 1e-9), 0.0)
        tl.grade = np.clip(grade, -GRADE_CLIP, GRADE_CLIP)
        tl.gap_speed = tl.speed * np.array([grade_cost_ratio(float(g)) for g in tl.grade])

    def _serialise_stream(self, tl: Timeline) -> List[Dict[str, Any]]:
        step = max(1, len(tl) // MAX_STORED_STREAM_POINTS)
        idx = range(0, len(tl), step)

        def at(arr, i):
            return None if arr is None else _clean(arr[i])

        return [{
            "timestamp_offset": float(tl.offset[i]),
            "lat": at(tl.lat, i),
            "lng": at(tl.lng, i),
            "altitude": at(tl.altitude, i),
            "distance": at(tl.distance, i),
            "speed": at(tl.speed, i),
            "grade": at(tl.grade, i),
            "gap_speed": at(tl.gap_speed, i),
            "heart_rate": at(tl.heart_rate, i),
            "cadence": at(tl.cadence, i),
        } for i in idx]

    def _compute_splits(self, tl: Timeline) -> List[ActivitySplit]:
        if tl.distance is None or len(tl) < 2:
            return []

        splits: List[ActivitySplit] = []
        total = float(tl.distance[-1])
        boundaries = np.arange(1000.0, total + 1000.0, 1000.0)
        start_idx = 0

        for n, target in enumerate(boundaries, start=1):
            crossing = np.searchsorted(tl.distance, target)
            end_idx = int(min(crossing, len(tl) - 1))
            if end_idx <= start_idx:
                continue

            sl = slice(start_idx, end_idx + 1)
            seg_dist = float(tl.distance[end_idx] - tl.distance[start_idx])
            seg_time = float(tl.offset[end_idx] - tl.offset[start_idx])
            is_partial = seg_dist < 950.0

            if is_partial and seg_dist < MIN_TRAILING_SPLIT_M:
                break
            if seg_time <= 0:
                continue

            seg_speed = seg_dist / seg_time
            seg_hr = None
            if tl.heart_rate is not None:
                hrs = tl.heart_rate[sl]
                hrs = hrs[~np.isnan(hrs) & (hrs > 30)]
                if len(hrs):
                    seg_hr = int(np.mean(hrs))
            seg_cad = None
            if tl.cadence is not None:
                cads = tl.cadence[sl]
                cads = cads[~np.isnan(cads) & (cads > 0)]
                if len(cads):
                    seg_cad = float(np.mean(cads))

            gap_pace = None
            if tl.gap_speed is not None:
                gaps = tl.gap_speed[sl]
                gaps = gaps[~np.isnan(gaps) & (gaps > 0)]
                if len(gaps):
                    gap_pace = round(1000.0 / float(np.mean(gaps)), 1)

            elev_diff = None
            if tl.has_altitude:
                elev_diff = round(float(tl.altitude[end_idx] - tl.altitude[start_idx]), 1)

            splits.append(ActivitySplit(
                split_number=n,
                distance_meters=round(seg_dist, 1),
                elapsed_time_sec=round(seg_time, 1),
                pace_sec_km=round(1000.0 / seg_speed, 1) if seg_speed > 0 else 0.0,
                gap_sec_km=gap_pace,
                avg_hr=seg_hr,
                avg_cadence=seg_cad,
                elevation_diff_m=elev_diff,
                aerobic_efficiency=(
                    round((seg_speed * 60.0) / seg_hr, 3) if seg_hr and seg_speed > 0 else None
                ),
                is_partial=is_partial,
            ))
            start_idx = end_idx

        return splits

    # ------------------------------------------------------------------
    def _update_daily_pmc(self, target_date=None):
        earliest = (self.db.query(Activity)
                    .filter(Activity.user_id == self.account.id)
                    .order_by(Activity.start_time.asc()).first())
        if not earliest:
            return

        today = datetime.utcnow().date()
        end_date = max(today, target_date) if target_date else today

        activities = self.db.query(Activity).filter(Activity.user_id == self.account.id).all()
        daily_tss: Dict[Any, float] = {}
        for a in activities:
            # CTL and ATL describe running fitness and fatigue. Folding walks
            # and gym sessions in makes the curve describe nothing in
            # particular; their load is kept on the activity itself.
            if not is_running(a.sport_type):
                continue
            d = a.start_time.date()
            daily_tss[d] = daily_tss.get(d, 0.0) + (a.r_tss or 0.0)

        if not daily_tss:
            return

        pmc_points = calculate_pmc_series(
            [{"date": d, "tss": tss} for d, tss in daily_tss.items()],
            end_date=end_date,
        )

        existing = {
            dh.date: dh
            for dh in self.db.query(DailyHealth).filter(DailyHealth.user_id == self.account.id).all()
        }
        # Baselines are rolling means over the preceding days, so the recovery
        # score can compare today against the athlete's own recent normal.
        hrv_history: List[float] = []
        rhr_history: List[float] = []

        for pt in pmc_points:
            d = pt["date"]
            dh = existing.get(d)
            if not dh:
                dh = DailyHealth(user_id=self.account.id, date=d)
                self.db.add(dh)
                existing[d] = dh

            dh.daily_tss, dh.ctl, dh.atl = pt["tss"], pt["ctl"], pt["atl"]
            dh.tsb, dh.acwr = pt["tsb"], pt["acwr"]

            baseline_hrv = float(np.mean(hrv_history[-BASELINE_DAYS:])) if hrv_history else None
            baseline_rhr = float(np.mean(rhr_history[-BASELINE_DAYS:])) if rhr_history else None

            dh.readiness_score, _ = calculate_recovery_readiness(
                hrv_rmssd=dh.hrv_rmssd,
                resting_hr=dh.resting_hr,
                sleep_duration_sec=dh.sleep_duration_sec,
                tsb=dh.tsb,
                baseline_hrv_7d=baseline_hrv,
                baseline_rhr_7d=baseline_rhr,
            )

            if dh.hrv_rmssd:
                hrv_history.append(float(dh.hrv_rmssd))
            if dh.resting_hr:
                rhr_history.append(float(dh.resting_hr))

        self.db.commit()
