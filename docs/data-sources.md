# Data sources

Three ways in, one pipeline. Whatever the source, every activity is turned into the same payload and goes through the same physiology engine, so a file import and a live sync produce identical figures.

| Source | For | Automatic |
| :-- | :-- | :-- |
| [Health Connect](#android-health-connect) | Android phones | Yes, hourly |
| [Garmin Connect](#garmin-connect) | Garmin watches, including on iPhone | Yes, every 30 minutes |
| [File import](#file-import) | Polar, Coros, Suunto, Wahoo, anything that exports | No |

Each account picks its source at registration, which only decides what the interface offers. Nothing stops you using more than one.

---

## Android Health Connect

The companion app in `android-companion/` reads Health Connect directly. This is the best path when it exists, because Health Connect holds more than most vendors' own cloud exports do.

### Records read

`ExerciseSessionRecord` · `HeartRateRecord` · `SpeedRecord` · `DistanceRecord` · `StepsRecord` · `StepsCadenceRecord` · `ElevationGainedRecord` · `TotalCaloriesBurnedRecord` · `ActiveCaloriesBurnedRecord` · `Vo2MaxRecord` · `HeartRateVariabilityRmssdRecord` · `RestingHeartRateRecord` · `SleepSessionRecord` · GPS from `ExerciseRoute`

### Building and installing

```bash
cd android-companion
ANDROID_HOME=/path/to/android-sdk ./gradlew assembleDebug
# app/build/outputs/apk/debug/app-debug.apk
```

Or open the folder in Android Studio and run it.

Then in the app: grant Health Connect permissions, set your server address (`http://<server>:8000`), and sync. It syncs hourly in the background via WorkManager, and the app doubles as a viewer — the dashboard is bundled into the APK and runs from local assets, so it works without loading a page from the server.

### Two permissions you must grant separately

Health Connect hides these under **App permissions → Performance Sync → Additional access**, and the app cannot request them in the main flow:

- **`READ_HEALTH_DATA_HISTORY`** — without it only the last **30 days** are readable, and a backfill silently stops there.
- **`READ_HEALTH_DATA_IN_BACKGROUND`** — without it the hourly sync reads *nothing at all*, because the app is backgrounded when it runs.

If a backfill mysteriously stops a month back, this is why.

### Duplicates from other apps

Health Connect is a shared store. Strava writes your runs back into it, so a run recorded by your watch can appear twice — once from the watch, once from Strava, often with a different distance.

The app filters by data origin and skips writers that are not the recording device, and the server independently refuses an activity that overlaps one it already has. You may still see this in the logs, which is the app working:

```
Skipped 7 duplicate sessions written back by another app
```

---

## Garmin Connect

For an athlete with a Garmin watch and no Health Connect — an iPhone, typically — the watch platform is polled for them.

**Settings → Automatic sync**, enter Garmin credentials, and the scheduler checks every 30 minutes.

**The first sync imports the whole account**, not a recent slice of it. It does not do so in one request: each run downloads at most `GARMIN_BATCH` activities (150 by default), **oldest first**, and records how far it reached, so a long history arrives over successive polls. A run that stops early does not mark the account as up to date — doing so would step over everything still queued and never come back for it.

Oldest first matters: a partial run then leaves a complete history behind it. Newest first would import the recent end and leave a hole that no later run would look in.

Later syncs re-check the last few days, because an activity can be uploaded from the watch long after it was recorded. The overlap re-offers a handful of activities the server already has, which are rejected as duplicates.

Set `GARMIN_INITIAL_DAYS` to a positive number to limit the first sync to that many days instead.

### How it works, and the honest caveat

This uses the same private endpoints the Garmin Connect website uses, through the `garminconnect` library. **It is not a supported API and Garmin can change it.**

The alternative is worse for something self-hosted: the official Garmin Developer API needs an application, approval, OAuth secrets, a publicly reachable callback, and a vendor relationship that can be withdrawn. This needs an outbound connection and nothing else. Everything fails softly — a broken sync records why and leaves existing data alone.

**Your password is used once to obtain session tokens and is never stored.** Only the tokens are kept, in `CONNECTION_TOKEN_DIR`, one directory per athlete. Changing your Garmin password invalidates them.

Two-factor accounts are supported: the code is requested on the sign-in form.

### Sport types

Garmin activities download as TCX, and **TCX cannot say what the activity was** — its schema allows exactly three values for the `Sport` attribute: `Running`, `Biking` and `Other`. Every walk, hike, swim and gym session exports as `Other`.

So the sport is taken from Garmin's own activity type key in the listing (`walking`, `strength_training`, `lap_swimming`) and the file is used only for the samples. Unknown type keys are matched on a fragment, so a `beach_running` nobody has heard of still counts as a run.

If activities imported before this fix are in the wrong tab, relabel them without re-downloading a year of files:

```bash
docker exec -it performance-backend python /data/fix_garmin_sports.py <username>
# add --apply to write the changes
```

---

## File import

**Menu → Settings → Import activities.** Accepts `.tcx`, `.gpx`, `.fit`, and `.zip` archives containing any of them — including Garmin's "Export All Data".

Every parser produces the same payload the phone sends. Notes on the formats:

- **TCX** — namespaces are stripped rather than matched, because exporters disagree about which schema URL they use and matching on it rejects files that are otherwise perfectly readable. Cadence is doubled: TCX reports one foot, runners count both.
- **FIT** — coordinates are semicircles over a signed 32-bit range.
- **GPX** — has no sport field, so imports are treated as runs. Re-label afterwards if that is wrong.

---

## What ingestion does to your data

The same pipeline for every source. This is where most of the correctness lives.

### 1. Resampling onto a common clock

Channels arrive on different clocks. Heart rate lands roughly every 5 seconds, sometimes with duplicate timestamps; GPS lands about every second; speed is somewhere between.

Joining these on exact timestamps drops **37–98%** of the heart-rate data, which was the original bug that made every derived figure wrong. Instead everything is resampled onto a uniform 1 Hz grid with a nearest-neighbour join and an explicit tolerance. Typical coverage after this is 95–99%, and the actual figure is recorded per channel.

Duplicate timestamps are collapsed, and a channel that is constant throughout — an altitude of exactly `0.0` at every point, which some devices write — is treated as absent rather than as a flat course.

### 2. Distance reconciliation

Pace comes from the device's total distance; grade-adjusted pace comes from the GPS track. If those disagree, the two figures are computed on different bases and cannot be compared.

The GPS track is therefore rescaled to the device total when they diverge by less than 25%. Beyond that the difference is not drift but a different activity, and the activity is flagged rather than reconciled. The applied factor is recorded in `data_quality`.

### 3. Duplicate and junk rejection

- An incoming activity that overlaps one already stored is rejected.
- A re-sync never downgrades an activity: if the stored version has GPS and the incoming one does not — exercise routes are unreadable from a background context on some devices — the route is kept, while values that do not depend on it are still updated.
- Implausible intensity is capped. A 2.5-minute walk should not carry the training load of a threshold session.

### 4. Data quality

Every activity stores what was measured, how well, and what was estimated, under `data_quality`. That is what lets the interface show a dash with a reason instead of a plausible number. See [Metrics](metrics.md#when-a-figure-is-missing).

---

## Checking a sync

```bash
docker exec -it performance-backend python /data/verify_sync.py    # end-to-end checks
docker exec -it performance-backend python /data/check_fields.py   # which fields are populated
docker exec -it performance-backend python /data/check_gps.py      # GPS and elevation coverage
```
