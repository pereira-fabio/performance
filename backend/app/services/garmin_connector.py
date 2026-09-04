"""
Automatic sync from Garmin Connect.

Exporting a file after every run is not a workflow anyone keeps up, so an
athlete without Health Connect needs their watch platform polled for them.

This uses the same private endpoints the Garmin Connect website uses, through
the `garminconnect` library, because the alternatives are worse for something
self-hosted: the official Garmin Developer API needs an application, approval,
OAuth secrets and a publicly reachable callback, and a vendor relationship that
can be withdrawn. This needs an outbound connection and nothing else.

The trade is honest and worth stating plainly: it is not a supported API and
Garmin can change it. Everything here therefore fails softly -- a broken sync
records why and leaves existing data alone.

The athlete's password is used once to obtain session tokens and never stored.
"""
import io
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, List, Optional, Tuple

from backend.app.models.schemas import HealthConnectSessionPayload
from backend.app.services.file_import import normalise_sport, parse_any

# Where garth keeps its session tokens, one directory per athlete.
TOKEN_ROOT = os.getenv("CONNECTION_TOKEN_DIR", "/data/connections")

# How far back a first sync reaches, in days. Zero means the whole account,
# which is the default: an athlete linking their watch expects their history,
# not the part of it that happens to fall inside a year.
#
# It is not fetched in one go. A run imports at most GARMIN_BATCH activities,
# oldest first, and records how far it got, so a long history arrives over
# successive polls instead of one enormous request that trips a rate limit and
# leaves nothing behind.
INITIAL_LOOKBACK_DAYS = int(os.getenv("GARMIN_INITIAL_DAYS", "0"))

# The earliest date worth asking about. Garmin Connect did not exist before it,
# and an open-ended query still has to name a start.
EPOCH = date(2000, 1, 1)

# Activities downloaded per run. Each one is a separate request for its TCX, so
# this is the knob that decides how hard a backfill leans on Garmin.
BATCH = int(os.getenv("GARMIN_BATCH", "150"))

# Re-fetch a little before the last sync, since an activity can be uploaded
# from the watch well after it was recorded.
OVERLAP_DAYS = 3


@dataclass
class SyncOutcome:
    ok: bool
    imported: int = 0
    skipped: int = 0
    found: int = 0
    message: str = ""
    needs_reauth: bool = False
    # False when the batch limit stopped the run before the end of the listing.
    # The caller must not then mark the account as synced up to now, or
    # everything still queued behind the cut would be skipped forever.
    complete: bool = True
    # The start time of the newest activity actually dealt with, which is where
    # the next run resumes from.
    reached: Optional[datetime] = None


def token_dir(user_id: str) -> str:
    return os.path.join(TOKEN_ROOT, user_id)


def _client(user_id: str):
    """A logged-in client resumed from stored tokens."""
    import garminconnect

    api = garminconnect.Garmin()
    # With no credentials this restores the stored session; it raises if the
    # tokens are gone or no longer accepted.
    api.login(tokenstore=token_dir(user_id))
    return api


def connect(user_id: str, email: str, password: str,
            mfa_code: Optional[str] = None) -> Tuple[bool, str]:
    """
    Exchange credentials for session tokens.

    Returns (ok, message). The password is not retained: only the tokens garth
    writes are kept, and changing the Garmin password invalidates them.
    """
    import garminconnect

    path = token_dir(user_id)
    os.makedirs(path, exist_ok=True)

    try:
        if mfa_code:
            # Supplying the code through the callback lets the library finish
            # the login in one pass, and it persists the tokens itself. The
            # early-return route hands back a status, not the client state that
            # resume_login needs, so there is nothing to resume from.
            api = garminconnect.Garmin(email, password, prompt_mfa=lambda: mfa_code)
            api.login(tokenstore=path)
        else:
            api = garminconnect.Garmin(email, password, return_on_mfa=True)
            status, _ = api.login(tokenstore=path)
            if status == "needs_mfa":
                return False, "This account uses two-factor authentication; enter the code."
        return True, "Connected."
    except garminconnect.GarminConnectTooManyRequestsError:
        return False, ("Garmin is rate-limiting requests from this server. "
                       "Wait a few minutes and try again.")
    except garminconnect.GarminConnectAuthenticationError as exc:
        # The library raises this for several distinct situations, and telling
        # someone their password is wrong when Garmin is simply throttling
        # sends them chasing a problem that does not exist.
        detail = str(exc).lower()
        if "429" in detail or "rate" in detail or "too many" in detail:
            return False, ("Garmin is rate-limiting requests from this server. "
                           "Wait a few minutes and try again.")
        if "mfa" in detail or "code" in detail:
            return False, "This account needs a two-factor code."
        # The underlying reason is carried through: this exception covers
        # several situations, and without the detail a rate limit or a changed
        # login page is indistinguishable from a wrong password.
        detail = str(exc).strip()
        if detail and detail.lower() not in ("", "none"):
            return False, f"Garmin did not accept the sign-in ({detail[:160]})."
        return False, "Garmin did not accept that email and password."
    except garminconnect.GarminConnectConnectionError as exc:
        return False, f"Could not reach Garmin Connect: {exc}"
    except Exception as exc:
        return False, f"Unexpected problem contacting Garmin: {exc}"


def disconnect(user_id: str) -> None:
    shutil.rmtree(token_dir(user_id), ignore_errors=True)


def _sport_of(entry: dict) -> Optional[str]:
    """
    The activity's real sport, from the listing rather than the file.

    TCX cannot express it. Its schema allows exactly three values for the Sport
    attribute -- Running, Biking and Other -- so Garmin exports every walk,
    hike, swim and gym session as "Other", and a walk would land in whatever
    bucket catches everything that is not a run. The listing entry carries
    Garmin's own type key ("walking", "strength_training", "lap_swimming"),
    which is what the athlete actually chose on the watch.
    """
    kind = entry.get("activityType")
    key = kind.get("typeKey") if isinstance(kind, dict) else kind
    return normalise_sport(key) if key else None


def _payloads_from_download(raw: bytes, activity_id: str, fmt: str) -> List[HealthConnectSessionPayload]:
    """Turn a downloaded activity into payloads, whatever Garmin sent."""
    name = f"garmin_{activity_id}.{fmt}"
    if fmt == "original":
        # ORIGINAL is a zip holding the FIT file.
        try:
            zipfile.ZipFile(io.BytesIO(raw))
            name = f"garmin_{activity_id}.zip"
        except zipfile.BadZipFile:
            name = f"garmin_{activity_id}.fit"
    sessions, _problems = parse_any(name, raw)
    return sessions


def _started_at(entry: dict) -> Optional[datetime]:
    """When an activity began, from whichever field the listing carries."""
    for key in ("startTimeGMT", "startTimeLocal"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "").strip())
        except ValueError:
            continue
    return None


def fetch_since(
    user_id: str,
    since: Optional[datetime],
    process: Callable[[HealthConnectSessionPayload], None],
    limit: int = BATCH,
) -> SyncOutcome:
    """
    Import activities recorded since a date, oldest first.

    Oldest first so a partial run is resumable: whatever it reaches, everything
    before that point is now stored, and the caller can record how far it got.
    Newest first would import the recent end and leave a hole behind it that no
    later run would ever look in.

    Each activity is handled independently: one that fails to download or parse
    is counted and passed over rather than abandoning the rest of the sync.
    """
    import garminconnect

    try:
        api = _client(user_id)
    except Exception as exc:
        return SyncOutcome(
            ok=False, needs_reauth=True,
            message=f"Garmin session is no longer valid, sign in again ({exc}).",
        )

    if since:
        start = (since - timedelta(days=OVERLAP_DAYS)).date()
    elif INITIAL_LOOKBACK_DAYS > 0:
        start = date.today() - timedelta(days=INITIAL_LOOKBACK_DAYS)
    else:
        # The whole account. The library pages the listing itself, so this is
        # one call however many years it covers; only the downloads are batched.
        start = EPOCH

    try:
        listing = api.get_activities_by_date(start.isoformat(), date.today().isoformat())
    except garminconnect.GarminConnectTooManyRequestsError:
        return SyncOutcome(ok=False, message="Garmin is rate-limiting; will retry later.")
    except Exception as exc:
        return SyncOutcome(ok=False, message=f"Could not list activities: {exc}")

    entries = list(listing or [])
    # Garmin returns newest first. Sorting the other way makes the batch below
    # a prefix of the history rather than a window floating in the middle of it.
    # Entries with no readable date go last so they cannot claim to be oldest.
    entries.sort(key=lambda e: _started_at(e) or datetime.max)

    batch = entries[:limit]
    complete = len(batch) == len(entries)
    reached: Optional[datetime] = None

    imported = skipped = 0
    for entry in batch:
        started = _started_at(entry)
        if started and (reached is None or started > reached):
            reached = started
        activity_id = str(entry.get("activityId") or "")
        if not activity_id:
            continue
        try:
            raw = api.download_activity(
                activity_id, dl_fmt=garminconnect.Garmin.ActivityDownloadFormat.TCX
            )
            payloads = _payloads_from_download(raw, activity_id, "tcx")
            if not payloads:
                skipped += 1
                continue
            for payload in payloads:
                # Garmin's own id keeps re-imports idempotent, and matches what
                # the activity is called on their side.
                payload.session_id = f"garmin:{activity_id}"
                name = entry.get("activityName")
                if name:
                    payload.title = name
                sport = _sport_of(entry)
                if sport:
                    payload.sport_type = sport
                process(payload)
                imported += 1
        except Exception:
            skipped += 1
            continue

    remaining = len(entries) - len(batch)
    message = (f"Imported {imported} activity(ies)"
               + (f", skipped {skipped}" if skipped else ""))
    if remaining:
        # Oldest first, so what is left is the more recent end of the history.
        message += (f". {remaining} more to import — the next sync continues "
                    f"from here")
    message += "."

    return SyncOutcome(
        ok=True, imported=imported, skipped=skipped, found=len(entries),
        message=message, complete=complete, reached=reached,
    )
