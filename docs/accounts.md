# Accounts and privacy

## Accounts

Several people can share one server with completely separate data. Every activity, health record, profile and setting belongs to exactly one account, and no endpoint serves data to an unauthenticated caller.

- **The first account registered becomes the administrator** and claims any activities already in the database — which is what an existing single-athlete install upgrading to accounts should do.
- Passwords are hashed with **scrypt** from the standard library. Sessions are opaque server-side tokens, not JWTs: they can be revoked, and there is no signing key to leak.
- Each account picks a **data source** at registration (Android or Garmin/file import). It only decides what the interface offers.

### Profile

**Menu → Profile.** Name, date of birth, sex, height, weight, and your training thresholds — max, resting and threshold heart rate, and threshold pace.

Not all of these do the same amount of work, and the form says which is which:

| Field | What it affects |
| :-- | :-- |
| Sex | The Banister TRIMP exponent, so it changes your training load |
| Max / resting / threshold HR | Heart-rate zones and TRIMP |
| Threshold pace | rTSS and intensity factor |
| Date of birth | Offers a max-HR estimate. Never applied on its own |
| Height, weight | Recorded only. Nothing computes from them yet |

Date of birth rather than age, so it does not go stale. The max-HR estimate uses Nes et al. (2013), which tracks measured maxima better than 220 − age across a wide range — offered as a button, never applied automatically, because a measured maximum from a hard effort beats any formula.

Changing thresholds affects new activities and the fitness curve. **Load already stored on past activities is not recalculated** — that needs replaying every stored stream, which is not implemented.

### Profile picture

Upload one and it replaces the number in the home page level badge; "Level 7" still appears beside it.

The browser crops it square and scales it to 256 px before upload, so the server needs no image library. Uploads are identified by their magic bytes rather than filename or declared type, capped at 1 MB. Pictures are files in `AVATAR_DIR`, **not in the database — so they are not in the backup.**

---

## Admin console

For administrators, under **Menu → Admin**.

- **Overview** — accounts, activities, database size, backup count and total size
- **Users** — grant or revoke administrator, activate or deactivate, delete
- **Backups** — list with age and size, create one now, prune old ones

Deleting an account removes its activities, streams, splits, best efforts, daily health, profile, cycle entries, sessions and picture.

That deletion is written out explicitly, row by row, rather than left to the foreign keys. **SQLite does not enforce `ON DELETE CASCADE` unless the pragma is set**, so relying on the constraint would leave orphaned rows behind — including the most personal ones.

---

## Backups

The scheduler writes a dated snapshot to `BACKUP_DIR` daily and prunes anything older than seven days, never dropping below three files however old they are.

Age-based rather than count-based on purpose: a week of history is what is actually wanted, and a count means something different whenever the schedule changes.

Each snapshot is taken with SQLite's own backup API, verified before it is kept, and gzipped. Several things had to be handled to make that reliable:

- Copying the file while the database is in use produces `database is locked` or a corrupt snapshot, so it goes through the backup API.
- A snapshot is verified and only then moved into place. A failed one is cleaned up rather than left as a 0-byte file that looks like a backup.
- `shutil.copy2` fails on SMB, which cannot set timestamps. Plain `copyfile` is used.

```bash
docker exec -it performance-backend python /data/backup.py        # one now
ls -la /opt/peakpace/data/backups
```

Restoring is copying a snapshot back over the database with the stack stopped:

```bash
# The volume is prefixed with the Compose project name, so find its real name:
docker volume ls | grep peakpace_db          # e.g. peakpace_peakpace_db

docker compose stop backend scheduler
gunzip -c /opt/peakpace/data/backups/peakpace-2026-09-04.db.gz > /tmp/restore.db

docker run --rm -v <volume-name>:/db -v /tmp:/in alpine sh -c \
  'cp /in/restore.db /db/peakpace.db && rm -f /db/peakpace.db-wal /db/peakpace.db-shm'

docker compose start backend scheduler
```

Removing the `-wal` and `-shm` files matters: the database runs in WAL mode, and a
write-ahead log left over from the old database alongside a restored one is a good
way to get back something that is neither.

**Backups contain the database only.** Profile pictures, terrain tiles and Garmin session tokens live under `/data` and are not in them — which is fine, because all three are replaceable.

---

## Export and deletion

**Settings → Your data.**

- **Export everything** — activities with GPS and heart-rate traces, splits, best efforts, daily health, profile and cycle entries, as JSON.
- **Summary only** — the same without the streams, which is much smaller.
- **Delete my account** — permanent, password-confirmed.

The export includes cycle entries because "export everything" has to mean everything; one that quietly omitted the most personal thing stored would not be one.

Deletion cannot reach into existing backups. The confirmation says so rather than implying an erasure it cannot perform.

---

## Cycle tracking

Optional menstrual cycle tracking, per account, **off by default**. Turn it on under **Settings → Cycle tracking**.

Cycle phase moves resting heart rate, perceived effort and how a hard session feels, so it belongs beside the training rather than in a separate app — and self-hosted, it stays on the machine it was entered on.

When enabled, the home page gains a cycle section and a calendar for logging period days.

### Design

**Days are logged individually, not as ranges.** That is what someone actually records, it survives a flow that pauses and resumes, and a mistake is corrected by untapping a day. Periods and cycle lengths are derived, so they stay right when the days change.

**Prediction is the median of recent cycles, not the mean.** With four or five cycles, one odd month is a quarter of the evidence. Cycles outside 15–60 days stay in the history but out of the average. Nothing is predicted from fewer than two cycles — the card says what is missing instead.

**Ovulation is estimated backwards from the expected period**, not forwards from the last one. The luteal phase is the consistent half; going forwards puts it wrong by the whole variation in cycle length.

The card states its confidence and shows the observed range.

### What it is not

Arithmetic on the dates you entered. **Not contraception, not a fertility test, not a diagnosis.** Cycles vary for many ordinary reasons, training load among them.

### Boundaries

- **The coach never receives any of it.** No cycle figure enters a recap or a PDF.
- Switching it off **hides it and keeps what you logged**. A switch is not a delete.
- It is offered to every account rather than gated on the profile's sex field, which many accounts will never have filled in.
- Deleting an account deletes it.

---

## What is stored where

| Data | Location | In backups |
| :-- | :-- | :-- |
| Activities, streams, health, profiles, cycle entries | SQLite on the `peakpace_db` volume | Yes |
| Backups | `$DATA_DIR/backups` | — |
| Profile pictures | `$DATA_DIR/avatars` | No |
| Garmin session tokens | `$DATA_DIR/connections` | No |
| Terrain tiles | `$DEM_DIR` | No |

Nothing is sent anywhere except an outbound connection to Garmin if you link an account, and OpenStreetMap tiles for the map — your route is drawn in your browser, and the coordinates are not sent to them.
