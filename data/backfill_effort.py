#!/usr/bin/env python3
"""
Fill in training effect, recovery and XP for activities already stored.

These are computed from training load, which is already in the database, so
they never needed a re-sync -- they were simply only written at ingest. This
recomputes them in place for every activity, using the chronic load standing
before each one, exactly as the ingestion path does.

Safe to run repeatedly.

    docker exec -it performance-backend python /data/backfill_effort.py
"""
import os
import sys

sys.path.append("/app")

from backend.app.core.database import SessionLocal          # noqa: E402
from backend.app.models.models import Activity, DailyHealth  # noqa: E402
from backend.app.physiology.effect import (                  # noqa: E402
    aerobic_training_effect, anaerobic_training_effect, recovery_hours,
)
from backend.app.physiology.progress import activity_xp      # noqa: E402
from backend.app.services.activity_processor import MAX_PLAUSIBLE_IF  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        activities = db.query(Activity).order_by(Activity.start_time.asc()).all()
        if not activities:
            print("No activities.")
            return 0

        # Daily health is read once and indexed, rather than queried per
        # activity: a year of sessions would otherwise be a year of queries.
        health = {h.date: h for h in db.query(DailyHealth).all()}
        dates = sorted(health)

        # Effort is judged against the athlete's typical session for that
        # sport, matching how ingestion does it.
        import statistics
        history: dict = {}

        def typical(sport, own):
            past = history.get(sport, [])
            return statistics.median(past[-20:]) if len(past) >= 3 else float(own or 0.0)

        def fitness_before(day):
            """CTL, TSB and readiness standing on or before a date."""
            prior = [d for d in dates if d <= day]
            if not prior:
                return 0.0, 0.0, None
            h = health[prior[-1]]
            return float(h.ctl or 0.0), float(h.tsb or 0.0), h.readiness_score

        changed = 0
        capped = 0
        for a in activities:
            # Correct implausible load first, so everything derived from it is
            # computed against the corrected figure.
            if a.intensity_factor and a.intensity_factor > MAX_PLAUSIBLE_IF and a.moving_time_sec:
                a.r_tss = round((a.moving_time_sec * MAX_PLAUSIBLE_IF ** 2) / 36.0, 1)
                a.intensity_factor = MAX_PLAUSIBLE_IF
                quality = dict(a.data_quality or {})
                quality["intensity_capped"] = {
                    "capped_to": MAX_PLAUSIBLE_IF,
                    "reason": "pace implies an intensity that cannot be sustained",
                    "corrected_by": "backfill",
                }
                a.data_quality = quality
                capped += 1

            ctl, tsb, readiness = fitness_before(a.start_time.date())
            reference = typical(a.sport_type, a.r_tss)
            te_a, _ = aerobic_training_effect(a.r_tss, reference)
            te_an, _ = anaerobic_training_effect(a.hr_zone_seconds, reference)
            rec, _ = recovery_hours(a.r_tss, reference, tsb, readiness)
            if a.r_tss and a.r_tss > 0:
                history.setdefault(a.sport_type, []).append(float(a.r_tss))
            xp = activity_xp(a.r_tss, a.distance_meters, a.moving_time_sec)

            if (a.training_effect_aerobic, a.training_effect_anaerobic,
                    a.recovery_hours, a.xp) != (te_a, te_an, rec, xp):
                a.training_effect_aerobic = te_a
                a.training_effect_anaerobic = te_an
                a.recovery_hours = rec
                a.xp = xp
                changed += 1

        db.commit()
        total_xp = sum(a.xp or 0 for a in activities)
        with_te = sum(1 for a in activities if a.training_effect_aerobic is not None)
        if capped:
            print(f"Corrected implausible training load on {capped} activity(ies).")
        print(f"Updated {changed} of {len(activities)} activities.")
        print(f"Training effect now present on {with_te}/{len(activities)}.")
        print(f"Total experience: {total_xp:,} XP")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
