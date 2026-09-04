# API reference

Base path `/api/v1`. Interactive docs at `http://<server>:8000/docs`.

## Authentication

Every endpoint except `/auth/status`, `/auth/register` and `/auth/login` needs a bearer token:

```
Authorization: Bearer <token>
```

Tokens are opaque server-side session identifiers returned by register and login. They can be revoked and carry no signed payload.

`API_AUTH_TOKEN`, if set, is a separate shared secret the phone sends on sync endpoints. It is not a session.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"you","password":"..."}' | jq -r .token)

curl -s http://localhost:8000/api/v1/metrics/summary -H "Authorization: Bearer $TOKEN"
```

---

## Accounts

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/auth/status` | Whether any account exists. Drives first-run registration |
| `POST` | `/auth/register` | Create an account. The first becomes administrator |
| `POST` | `/auth/login` | Exchange credentials for a token |
| `POST` | `/auth/logout` | Revoke the current token |
| `GET` | `/auth/me` | Current account, including flags a stored session may predate |
| `PATCH` | `/auth/me/source` | Change data source |
| `DELETE` | `/auth/me` | Delete the account. Body `{password, confirm: "DELETE"}` |
| `GET` | `/auth/export` | Everything, as JSON. `?include_streams=false` for the small version |

## Activities

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/activities` | List, newest first |
| `GET` | `/activities/{id}` | One activity with streams, splits and best efforts |
| `DELETE` | `/activities/{id}` | Remove one |

## Sync

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `POST` | `/sync/session` | Ingest one activity. What the phone posts |
| `POST` | `/sync/daily-health` | Resting HR, HRV, sleep, VO₂ max, steps |
| `POST` | `/sync/import` | Upload TCX, GPX, FIT or zip files |

## Metrics

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/metrics/summary` | 7- and 28-day volume and load, CTL/ATL/TSB/ACWR, per sport |
| `GET` | `/metrics/pmc` | Fitness curve. `?days=180` |
| `GET` | `/metrics/records` | Personal records by distance |
| `GET` | `/metrics/home` | Home page: level, XP, attributes, sport split, achievements |

## Reports

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/reports/week` | A finished week. `?offset=0` is the last complete one; `?key=2026-W35` for a specific one |
| `GET` | `/reports/period` | `?kind=week\|month\|year` with `key` or `offset` |
| `GET` | `/reports/periods` | Months or years that actually contain training |
| `GET` | `/reports/calendar` | Training days in a month, for the week picker. `?month=2026-09` |
| `GET` | `/reports/pdf` | A printable report. `?kind=month&key=2026-08&include_note=true` |

## Coach

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/coach/status` | Whether a model is configured and reachable, and which are available |
| `GET` | `/coach/activity/{id}` | A note on one activity. `?refresh=true` to rewrite |
| `GET` | `/coach/week` | The current rolling week |
| `GET` | `/coach/period` | A review of a finished period. `?kind=week&key=2026-W35` |

## Connections

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/connections` | The linked account, if any, with last sync and status |
| `POST` | `/connections/garmin` | Link. Body `{email, password, mfa_code?}`. The password is not stored |
| `POST` | `/connections/sync` | Pull now rather than waiting for the scheduler |
| `DELETE` | `/connections` | Unlink and discard the tokens |

## Settings

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/settings/profile` | Physiology and body metrics |
| `PUT` | `/settings/profile` | Update them |
| `POST` | `/settings/recalculate` | Rebuild the fitness curve from stored load |
| `POST` | `/settings/avatar` | Upload a picture, multipart. PNG, JPEG or WebP, 1 MB |
| `GET` | `/settings/avatar` | The picture. 404 if none |
| `DELETE` | `/settings/avatar` | Remove it |

## Cycle

Off by default. Data from these endpoints is never given to the coach.

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/cycle` | Phase, cycle day, prediction and confidence |
| `PUT` | `/cycle/enabled` | Body `{enabled}`. Off hides it, it does not delete |
| `GET` | `/cycle/calendar` | Logged and expected days. `?month=2026-09` |
| `PUT` | `/cycle/day` | Log or amend. Body `{date, flow?, notes?}` |
| `DELETE` | `/cycle/day` | Unlog. `?date=2026-09-01` |

## Admin

Administrators only.

| Method | Path | Purpose |
| :-- | :-- | :-- |
| `GET` | `/admin/overview` | Accounts, activities, database and backup sizes |
| `GET` | `/admin/users` | All accounts with activity counts |
| `PATCH` | `/admin/users/{id}` | Grant or revoke administrator, activate or deactivate |
| `DELETE` | `/admin/users/{id}` | Delete an account and everything belonging to it |
| `GET` | `/admin/backups` | List with age and size |
| `POST` | `/admin/backups` | Create one now |
| `DELETE` | `/admin/backups` | Prune by the retention policy |

---

## Errors

Standard status codes. `400` invalid input, `401` bad or missing session, `403` not permitted, `404` absent, `413` too large, `422` failed validation.

FastAPI returns validation errors as a list under `detail`; the frontend's `describeError` handles all three shapes the API can produce, so a message is never rendered as `[object Object]`.
