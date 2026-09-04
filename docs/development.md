# Development

## Repository layout

```
backend/
  app/
    api/            FastAPI routers, one per area
    core/           config, database, security, migrations, backups, sport rules
    models/         SQLAlchemy models and Pydantic schemas
    physiology/     the science: gap, decoupling, trimp, pmc, zones,
                    best_efforts, dem, resample, effect, recovery, progress
    services/       ingestion and features: activity_processor, file_import,
                    garmin_connector, coach, reports, report_pdf, cycle, avatars
  dem_tiles.py      which terrain tiles your routes need
  seed_demo_data.py sample data
frontend/
  src/
    api/client.ts   every call to the backend
    components/     the interface
    lib/            formatting, theme, auth, errors, image
    types/          shared types
android-companion/
  app/src/main/java/com/performance/app/
    data/           HealthConnectManager, SyncApiClient
    ui/             DashboardScreen, SettingsScreen, WebDownloads, Theme
    worker/         SyncWorker
data/               maintenance scripts, on the mounted volume
docs/               this documentation
```

`physiology/` is deliberately separate from `services/`. Everything in it is a pure function of its inputs and testable without a database.

---

## The ingestion pipeline

`ActivityProcessor` is where a payload becomes an activity, in this order:

1. **Resample** every channel onto a uniform 1 Hz grid (`physiology/resample.py`), recording coverage per channel.
2. **Recover elevation** from the terrain model if the device wrote none (`physiology/dem.py`).
3. **Reconcile distance** between the device total and the GPS track.
4. **Derive** pace, GAP, decoupling, TRIMP, rTSS, zones, splits, best efforts.
5. **Estimate** training effect, recovery and XP from load.
6. **Persist**, refusing duplicates and refusing to downgrade an existing activity.
7. **Rebuild** the fitness curve.

Every step records what it could not do and why, which is what `data_quality` is.

---

## Running locally

### Backend

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
DATABASE_URL=sqlite:///./dev.db DATA_DIR=./devdata \
  uvicorn backend.app.main:app --reload --port 8000
```

**Use Python 3.12.** `garminconnect` requires it, and testing on one version while shipping another hides real failures — that exact mismatch has already caused one broken build here.

### Frontend

```bash
cd frontend
npm install
npm run dev        # proxies /api to localhost:8000
npm run build      # production bundle into dist/
npx tsc --noEmit   # typecheck alone
```

### Android

```bash
cd android-companion
ANDROID_HOME=/path/to/android-sdk ./gradlew assembleDebug
```

The SDK path must be passed explicitly, or set in `local.properties`, or gradle stops with *"SDK location not found"*.

**The APK bundles the dashboard.** Build the frontend and copy it in before building the app, or the viewer ships stale:

```bash
cd frontend && npm run build && cd ..
rm -rf android-companion/app/src/main/assets/www
cp -r frontend/dist android-companion/app/src/main/assets/www
cd android-companion && ANDROID_HOME=... ./gradlew assembleDebug
```

The debug key is stable, so a new debug APK installs over an older one without an uninstall. Check before replacing a distributed build:

```bash
$ANDROID_HOME/build-tools/*/apksigner verify --print-certs app-debug.apk
```

---

## Deploying

```bash
cd /opt/peakpace && docker compose up -d --build
```

`backend/Dockerfile` copies `app/` wholesale, so new modules need no change to it. Scripts under `data/` are on the mounted volume and take effect without a rebuild.

Schema changes are applied on startup by `Base.metadata.create_all` (new tables) and `ensure_schema` (new columns, from `_ADDED_COLUMNS` in `core/database.py`). **Adding a column to a model means adding it there too** — SQLAlchemy creates missing tables but never missing columns, so without it every query against the model fails.

---

## Maintenance scripts

Run with `docker exec -it performance-backend python /data/<script>.py`.

| Script | What it does |
| :-- | :-- |
| `verify_sync.py` | End-to-end checks against everything previously fixed |
| `check_fields.py` | Which per-activity fields are populated, and where gaps come from |
| `check_gps.py` | GPS and elevation coverage |
| `inspect_conflicts.py` | The activities the verifier flagged, with context |
| `backfill_effort.py` | Training effect, recovery and XP for activities stored before they existed |
| `rename_activities.py` | Fix names generated with the wrong sport |
| `fix_garmin_sports.py` | Relabel Garmin activities from the listing, without re-downloading |
| `reset_activities.py` | Wipe activities for a clean re-sync |
| `migrate_accounts.py` | Move a single-athlete database onto accounts |
| `backup.py` | One backup now |
| `scheduler.py` | The scheduler loop itself |

---

## Troubleshooting

**Activities appear twice, or one is 0 km**
Another app is writing your runs back into Health Connect. The companion filters by data origin, and the server refuses overlapping activities. Check the phone log for `Skipped N duplicate sessions`.

**Distance is roughly double**
Device total and GPS track disagreed. Look at `data_quality.distance` on the activity for the rescale factor.

**Elevation and GAP are missing**
No terrain tile covers the route. `python backend/dem_tiles.py` lists what is needed; the activity records the reason under `data_quality.altitude`.

**Health Connect backfill stops 30 days back**
`READ_HEALTH_DATA_HISTORY` is not granted. It is under **Additional access**, separate from the main permission flow.

**Nothing syncs in the background, but "Sync now" works**
`READ_HEALTH_DATA_IN_BACKGROUND` is not granted.

**Garmin sign-in fails**
The message carries the underlying reason. The same exception covers a wrong password, a rate limit and a changed login page — a `429` clears on its own.

**Walks show under Gym**
Imported before sports were read from the Garmin listing. `fix_garmin_sports.py` relabels them.

**The coach says nothing**
`OLLAMA_URL` is empty or unreachable. `GET /coach/status` says which. The feature fails softly by design.

**`database is locked`**
Something is copying the SQLite file directly. Backups go through the backup API for this reason; do not `cp` a live database.

---

## Conventions

- **Comments explain why, not what.** A comment that restates the code is noise; one that records why a threshold is 3 m and not 1 m is the reason the next person does not undo it.
- **Never invent a number.** If the data cannot support a figure, record why and show a dash. `data_quality` exists so the interface can explain itself.
- **Weighted averages, not means of means.** A total over a total, every time.
- **Sports stay separate.** `core/sports.py` decides what counts as running; nothing else should guess.
- **Fail softly at the edges.** A broken Garmin sync, an unreachable model or a missing terrain tile must leave stored data exactly as it was.
