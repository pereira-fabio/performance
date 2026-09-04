# Metrics

Every figure the app computes, how it is computed, and when it refuses to compute one.

The rule throughout: **a measurement and an estimate are different things, and both are different from a guess.** Measurements come from the device. Estimates are derived and labelled as derived. Guesses are not shown at all.

---

## Aerobic decoupling (Pa:HR)

How much your cardiovascular efficiency drifted across the session. Efficiency is speed over heart rate; decoupling compares the first half with the second:

```
decoupling (%) = (1 − EF₂ / EF₁) × 100
```

| Value | Reading |
| :-- | :-- |
| under 3% | Negligible drift, strong aerobic efficiency |
| 3–5% | Well-trained aerobic base |
| over 5% | Meaningful drift — fatigue, dehydration, heat, or running above aerobic threshold |

Requires at least **20 minutes** of continuous data (`DECOUPLING_WINDOW_MIN_DURATION_SEC`). Below that the two halves are too short for the comparison to mean anything, and it is left unavailable.

---

## Grade-adjusted pace (GAP)

What your pace on a slope would have been on the flat, using the fifth-order energy-cost polynomial from **Minetti et al. (2002)**:

```
Cr(i) = 155.4i⁵ − 30.4i⁴ − 43.3i³ + 46.3i² + 19.5i + 3.6    (J/kg·m)
```

where `i` is the gradient. Needs a grade, so it needs elevation.

---

## Elevation recovery

Many wearables write **no usable altitude at all** to Health Connect. Nothing X, for example, records a constant `0.0` for every route point and writes no `ElevationGainedRecord`. No elevation means no grade, and no grade means no GAP.

Elevation is therefore recovered from the GPS track against a local **SRTM digital elevation model**.

- **Bilinear interpolation** between DEM posts. Nearest-neighbour stair-steps, and the steps manufacture false grade spikes.
- The profile is smoothed over roughly 60 m of track, then ascent is accumulated with a **3 m threshold**. This matters more than it sounds: summing raw differences counts measurement noise as climbing, and on a profile carrying 2 m of jitter it turned a real 39 m climb into **1866 m**. With smoothing and hysteresis the same run reports 34 m.
- **A device that reports real altitude always wins.** The terrain model is consulted only when it does not.
- Tiles are read from local storage, so **GPS traces are never sent to a remote elevation service**.
- Each activity records the source, the tiles used and the resolution under `data_quality.altitude`.

### Setting it up

```bash
# 1. Which tiles do your routes need?
docker exec -it performance-backend python backend/dem_tiles.py

# 2. Download them into DEM_DIR (/data/dem), as NxxEyyy.hgt
#    or the downloaded NxxEyyy.hgt.zip — both are read directly.

# 3. Re-sync to populate elevation and GAP on existing activities.
```

1 arc-second (30 m) tiles resolve grade noticeably better than 3 arc-second (90 m). Both work. If no tile covers a route, elevation and GAP stay unavailable and the activity records exactly why.

> **Naming trap:** in the common SRTM archives the letter prefix is a 4° band counted from the equator, not the latitude. Central Europe is `M31`/`M32`, not `U31`/`U32`.

---

## Training load

### rTSS — running training stress score

A 30-second rolling mean of grade-adjusted speed is raised to the fourth power, averaged and rooted to give **normalised graded pace**. Intensity factor is NGP over threshold speed, and:

```
rTSS = moving_time × IF² / 36
```

An hour at exactly threshold scores 100. Only moving samples contribute and the duration used is moving duration, so stopped time neither inflates nor deflates the score.

Intensity is capped at a plausible ceiling. Without it a 2.5-minute walk scored 41 — arithmetically defensible, physiologically nonsense.

Where pace is unusable but heart rate is not, load falls back to Banister TRIMP and the activity records `rtss_basis: banister_trimp_fallback`, which the interface shows as "from heart rate".

### TRIMP

**Banister** TRIMP weights time by heart-rate reserve on an exponential curve, with a different exponent by sex — which is why the profile's sex field changes your load figures.

**Edwards** TRIMP sums time in each heart-rate zone with fixed weights.

---

## Fitness, fatigue and form (PMC)

The Banister performance management chart, over daily training load:

| Figure | Meaning | How |
| :-- | :-- | :-- |
| **CTL** — Fitness | What you have built | 42-day exponentially weighted average |
| **ATL** — Fatigue | What you are carrying | 7-day exponentially weighted average |
| **TSB** — Form | Freshness | CTL − ATL |
| **ACWR** | Injury-risk proxy | ATL ÷ CTL, with 0.8–1.3 the usual safe range |

**Only running drives this curve.** Walks and gym sessions carry their own load and are reported separately.

---

## Training effect and recovery

Aerobic training effect on the familiar 1–5 scale:

```
TE = 1 + 4 × (1 − e^(−k · ratio))
```

where `ratio` is the session's load against a **typical session load for that sport**.

The reference matters. It was originally CTL, which is a *daily average* — measuring one session against it made almost everything score 4.1–5.0, because a real session is naturally several times an average day. Against a typical session of the same sport, an easy run scores easy.

Recovery hours are estimated from the same load, adjusted for current form. Both are estimates from load, not measurements, and the interface says so under every one.

---

## Zones, splits and best efforts

- **Heart-rate zones** from your max, resting and threshold heart rates.
- **Splits** per kilometre, with pace, GAP, heart rate and elevation change. A trailing partial kilometre is marked and excluded from comparisons.
- **Best efforts** at 400 m, 1 km, 1 mile, 5 km, 10 km, half and full marathon, found as the fastest window anywhere in the activity.
- **Fastest pace** is the best 30-second window, not an instantaneous GPS spike.

**Only running sets records.** A walk cannot set a 5 km personal record.

---

## Progress: XP, levels and achievements

XP per activity:

```
xp = training_load × 1.0  +  km × 6.0  +  active_hours × 40.0
```

Levels follow `600 × level^1.45`, so each one costs more than the last. Achievements cover single-run distances, cumulative distance, session counts, weekly consistency and best times. Unearned ones show progress rather than hiding.

This is the one part of the app that is deliberately a game. It is computed from real figures and affects nothing else.

---

## Attributes

The radar chart under **Stats** scores five attributes out of 100 — endurance, speed, volume, consistency and recovery — from your recent training. It is a summary for orientation, not a measurement of anything physiological.

---

## When a figure is missing

Every activity carries a `data_quality` record: which channels were present, what fraction of the session each covered, what was estimated, and why anything absent is absent.

The interface uses it directly. A dash is hoverable and explains itself — "not written by the device for this session", "no tile covers this route", "heart rate covers 41% of this session". Where coverage is below 80%, the activity page says so before showing anything derived from it.

This is deliberate and it is the point. A plausible wrong number is worse than an honest gap, because you cannot tell it is wrong.
