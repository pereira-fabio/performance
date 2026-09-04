# Installation

Performance is a three-container Docker Compose stack. Nothing about it is specific to Proxmox or TrueNAS — those are just where this instance runs — so if you already have Docker somewhere, skip to [Deploying](#deploying).

---

## What the stack contains

| Container | Purpose | Port |
| :-- | :-- | :-- |
| `performance-backend` | API and physiology engine | 8000 |
| `performance-frontend` | The dashboard, served by nginx | 3000 |
| `performance-scheduler` | Backups and Garmin polling. Reuses the backend image | — |

The scheduler runs from `/data/scheduler.py` on the mounted volume rather than from inside the image, so changing what it does needs no rebuild.

---

## Storage layout

Two volumes, and the split matters.

| Path | Backed by | Holds |
| :-- | :-- | :-- |
| `/db` | Docker named volume `peakpace_db` | The SQLite database |
| `/data` | Bind mount from the host, typically your NAS share | Backups, terrain tiles, avatars, Garmin session tokens, maintenance scripts |

**The database lives on a Docker volume, not on the NAS share.** SQLite over SMB or NFS is a good way to corrupt a database: network filesystems implement locking loosely, and WAL mode assumes real locks. Backups are written to `/data`, so the NAS still holds a durable copy — it just is not the live file.

The named volume is called `peakpace_db` and stays that way. Renaming a Docker volume does not move the data into the new one, so a rename would bring the stack up against an empty database.

---

## Proxmox LXC

### 1. Create the container

Debian 12 or Ubuntu 22.04/24.04. Allocate **2 vCPU, 2 GB RAM, 10 GB disk** — comfortable for years of activities.

Under **Options → Features**, enable **Nesting** and **keyctl**. Docker will not start inside an LXC without them.

### 2. Mount the TrueNAS share

Either from the Proxmox host, by adding this to `/etc/pve/lxc/<CTID>.conf`:

```ini
mp0: /mnt/pve/truenas_share,mp=/opt/peakpace/data
```

Or inside the container:

```bash
mkdir -p /opt/peakpace/data
mount -t cifs //truenas.local/bigboy/App/data /opt/peakpace/data \
  -o username=<USER>,password=<PASS>,uid=1000,gid=1000
```

Add it to `/etc/fstab` so it survives a reboot. A missing mount at boot means the stack starts with an empty `/data`: backups go nowhere and terrain tiles disappear.

### 3. Install Docker

```bash
apt update && apt install -y docker.io docker-compose-plugin
```

---

## Deploying

```bash
git clone git@github.com:pereira-fabio/performance.git /opt/peakpace
cd /opt/peakpace
docker compose up -d --build
```

Then open `http://<server>:3000` and register. **The first account becomes the administrator.**

The schema is created and migrated on startup, so an upgrade is only ever:

```bash
cd /opt/peakpace && docker compose up -d --build
```

Missing columns are added and missing tables created automatically. Existing rows are never rewritten.

---

## Configuration

Everything is environment variables in `docker-compose.yml`. None are required to start.

### Backend

| Variable | Default | What it does |
| :-- | :-- | :-- |
| `DATABASE_URL` | `sqlite:////db/peakpace.db` | Where the database lives. Keep it off a network share |
| `DATA_DIR` | `/data` | Root for everything that is not the database |
| `API_AUTH_TOKEN` | *empty* | A shared secret the phone must send. Empty leaves sync open, which is fine on an isolated home network. If you set it, enter the same value in the app under **API Sync Token** |
| `SECRET_KEY` | `change-me-in-production` | Change it |
| `DEM_DIR` | `/data/dem` | Terrain tiles for elevation recovery. Empty disables it. See [Metrics](metrics.md#elevation-recovery) |
| `CONNECTION_TOKEN_DIR` | `/data/connections` | Garmin session tokens, one directory per athlete |
| `AVATAR_DIR` | `$DATA_DIR/avatars` | Profile pictures |
| `OLLAMA_URL` | *empty* | Your language model. Empty turns the coach off entirely |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Which model to ask |
| `GARMIN_INITIAL_DAYS` | `365` | How far back the first Garmin sync reaches |

`OLLAMA_URL` ships pointing at the address this instance uses. **Change it to your own, or empty it.** An unreachable model costs nothing but a timeout — the coach fails softly and no training data depends on it.

### Scheduler

| Variable | Default | What it does |
| :-- | :-- | :-- |
| `BACKUP_DIR` | `/data/backups` | Where backups are written |
| `BACKUP_INTERVAL_SEC` | `86400` | Daily. The database changes a few times a week, not hourly |
| `BACKUP_RETENTION_DAYS` | `7` | Age-based, not count-based: a week of history is what is wanted, and a count means something different whenever the schedule changes |
| `BACKUP_KEEP_MINIMUM` | `3` | Never prune below this, however old they are |
| `BACKUP_COMPRESS` | `1` | gzip the snapshot |
| `CONNECTION_POLL_SEC` | `1800` | How often linked Garmin accounts are checked |

---

## Verifying it came up

```bash
docker compose ps
curl -s http://localhost:8000/api/v1/auth/status
docker logs performance-backend  | tail -20
docker logs performance-scheduler | tail -20
```

The backend prints every schema change it makes on startup (`schema: added activities.xp`), which is the quickest way to confirm an upgrade actually applied.

---

## Networking

Nothing here reaches the public internet except:

- **Garmin Connect**, if an account is linked, outbound only.
- **OpenStreetMap tiles**, for the map on an activity page. Your route is drawn client-side; the coordinates are not sent anywhere.

Terrain tiles are read from local storage precisely so GPS traces are never sent to a remote elevation service.

If you expose this beyond your LAN, put it behind a reverse proxy with TLS. `usesCleartextTraffic` is enabled in the Android app for plain-HTTP LAN use, and sessions are bearer tokens — fine on a home network, not fine on the open internet.
