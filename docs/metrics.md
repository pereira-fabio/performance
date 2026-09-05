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

## VO2 max

Reported by the device where it reports one. Several watches do not — Garmin
withholds it on some models, and a phone gets whatever the vendor wrote — so
where nothing measured it, it is **estimated** from the best running effort of
the last 120 days and labelled as an estimate.

The method is Daniels and Gilbert's VDOT (*Oxygen Power*, 1979): the oxygen
cost of the speed held, divided by the fraction of maximum sustainable for that
long. Only efforts between 3 and 90 minutes and over 1200 m are used — shorter
is anaerobic enough that the model overestimates, longer and the athlete is
fading for reasons the curve does not describe, and below 1200 m a few seconds
of GPS error moves the answer more than the running does.

The best effort is taken rather than the average: every effort that was not
all-out understates the ceiling, so a mean is dragged down by easy days. A
measured reading always wins over an estimate.

## Body composition

BMI is weight over height squared and knows nothing else. It cannot tell muscle
from fat, which is why it reads a lean, heavily trained runner as overweight. It
is shown because it is the figure everyone recognises, beside something that
answers the question BMI is usually being asked.

That is the **US Navy circumference method** (Hodgdon and Beckett, 1984), which
estimates body fat from girths: neck and waist against height for men, with hips
as well for women. The two formulas are not interchangeable, so an athlete who
has not recorded their sex gets no estimate rather than the wrong one, and a
woman without a hip measurement gets none either.

It is not a DEXA scan. It is repeatable with a tape measure at home, which makes
it useful for watching a direction of travel rather than chasing an absolute.
Lean mass is shown alongside because it is the figure worth watching across a
training block: it should hold steady while weight moves.

Implausible measurements produce nothing rather than a figure — a waist entered
in inches, or a height in metres, would otherwise give an answer that looks
right. Neither figure is a diagnosis.

## Threshold pace

The one figure in the profile no device reports, and the one everything else is
measured against: pace zones, rTSS and intensity all come from it. Left at its
default of 4:00/km, a 6:00/km runner has every session land in the slowest zone
and every load figure overstated.

The profile therefore offers one, worked out from the athlete's own running, in
order of preference:

1. **The quickest run of about an hour** (50–75 minutes). That is the definition
   of threshold — the pace you could hold for one — so a real effort beats any
   model. The quickest rather than the most recent, because a steady hour
   understates it.
2. **Otherwise from VO2 max**, by solving the same oxygen-cost curve backwards
   for the velocity at 88% of maximum, which is where Daniels puts threshold.
   Checked against his published T-pace tables from VDOT 30 to 60.

An hour more than 20% slower than the model says was an easy long run, not a
threshold effort, and is ignored — believing it would set the threshold far too
slow and inflate every load figure computed against it.

It is offered as a button and never applied on its own. An athlete who has
measured their threshold in a test knows better than either estimate.

## What you can change afterwards

An activity can be renamed, moved to a different sport, tagged with the kind of
session it was — recovery, easy, long, tempo, intervals, race — annotated, and
given a calorie or step count the device never wrote.

**Distance, duration and heart rate are not editable.** Pace, load, zones,
records and the fitness curve are all computed from them, and changing one
without replaying the session through the physiology engine leaves an activity
whose own figures disagree. A wrong distance is a re-sync, not a correction.

The tag is the athlete's, not the watch's: a device records what happened, and
only the runner knows whether an easy pace was a recovery jog or all they had
left. Runs arrive with a suggested one, and **a tag you set is never
overwritten**, including by a re-sync.

### How a run is tagged automatically

Two decisions shape it.

**Sessions are judged against the athlete's own runs, not against absolutes.**
Intensity is measured relative to threshold pace, which people set once and
often not at all — and left at its default every run of a slower athlete looks
like a recovery jog. Comparing a session with the median of their recent ones
asks "was this harder than usual *for you*", which is the real question and
stays right even when the threshold is wrong. Below five previous runs there is
no median worth having, so it falls back to the textbook fractions of threshold
speed.

**It never guesses "race".** A race and a hard tempo are identical in the data,
and the two mistakes do not cost the same: an untagged race takes a moment to
label, while a training run recorded as a race quietly becomes part of a
history that never happened.

| Tag | When |
| :-- | :-- |
| `interval` | The pace swings far more than a hill would explain |
| `long` | Over 90 minutes, or over an hour and much longer than usual |
| `tempo` | Meaningfully harder than the athlete's usual run |
| `recovery` | Meaningfully easier |
| `easy` | Everything else with a usable intensity |
| *none* | Not a run, or nothing to go on — better than a word nobody chose |

Intervals are detected from the smoothed speed trace rather than from splits,
because repetitions shorter than a kilometre average out inside one and leave a
session of them looking perfectly even. A steady run varies by well under a
percent on that measure and a hilly one by around nine; repetitions are past
twenty. Splits are used as a fallback for a device that recorded no usable
speed.

## Zones, splits and best efforts

- **Heart-rate zones** from your max, resting and threshold heart rates, and **pace zones** from your threshold pace. Every zone is shown, including those with no time in them: an empty zone says the effort never reached it, and hiding it makes the chart look like it is missing rows. Where almost everything lands in one zone, the thresholds it is measured against are usually still the defaults, and the activity page says so.
- **Splits** per kilometre, with pace, GAP, heart rate and elevation change. A trailing partial kilometre is marked and excluded from comparisons.
- **Best efforts** at 400 m, 1 km, 1 mile, 5 km, 10 km, half and full marathon, found as the fastest window anywhere in the activity.
- **Personal records** keep the best *three* at each distance, ranked. A record alone does not say whether it was a step or a leap; the two behind it do, and beating your second-fastest 5k is a real result on a day the record is out of reach. Only one entry per run, since a single session holds several efforts at a distance and three rows from one morning is a list of one run. Each opens the run it happened in.
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
