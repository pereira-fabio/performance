"""
Written commentary on training, from a locally hosted language model.

The model is given only figures this server has already computed, formatted as
prose, and is told not to produce a number that is not in front of it. It
phrases; it never calculates. Everything shown as a measurement elsewhere in
the app stays a measurement, and this sits beside it clearly marked as
generated text.

Two findings from testing against real models shaped the brief:

  * Data-quality fields must be kept out of it. Given "heart_rate_coverage_pct:
    97", every model tested read it as effort -- "you pushed to 97% of maximum"
    -- rather than as how much of the session was measured. Coverage decides
    server-side whether a metric is trustworthy enough to include at all, and
    then is not mentioned.
  * Small models should not be asked to do arithmetic. Given "74" minutes one
    model wrote "just under an hour". Every value is pre-formatted the way it
    should be read aloud.
"""
import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

SYSTEM_PROMPT = """You are a running coach writing a short note to an athlete.

Rules, most important first:
1. Never state a number that does not appear in the brief. Do not convert, round or recalculate anything.
2. Do not restate the whole brief. Pick the two or three things that actually matter and say what they mean.
3. Never give medical advice, and never suggest the athlete may be ill or injured.
4. Do not prescribe specific training. You may note that a session was hard or easy; you may not tell the athlete what to do tomorrow.
5. At most three sentences. Address the athlete as you. Plain prose, no headings, no lists, no markdown, no preamble, no sign-off."""

DEFAULT_MODEL = "qwen2.5:7b"
REQUEST_TIMEOUT_SEC = 120


@dataclass
class CoachResult:
    ok: bool
    text: str = ""
    model: str = ""
    seconds: float = 0.0
    error: str = ""


def _pace(seconds_per_km: Optional[float]) -> Optional[str]:
    if not seconds_per_km or seconds_per_km <= 0:
        return None
    return f"{int(seconds_per_km // 60)}:{int(seconds_per_km % 60):02d} per km"


def _duration(seconds: Optional[float]) -> Optional[str]:
    if not seconds or seconds <= 0:
        return None
    hours, minutes = int(seconds // 3600), int((seconds % 3600) // 60)
    if hours and minutes:
        return f"{hours} hour{'s' if hours > 1 else ''} {minutes} minutes"
    if hours:
        return f"{hours} hour{'s' if hours > 1 else ''}"
    return f"{minutes} minutes"


def _line(label: str, value: Any) -> Optional[str]:
    return f"- {label}: {value}" if value not in (None, "") else None


def build_activity_brief(activity, context: Dict[str, Any]) -> str:
    """
    Describe one session in prose the model can only rephrase.

    Anything the server could not measure is left out entirely rather than
    marked absent: a model told a field is missing tends to speculate about why.
    """
    measured = [
        _line("Distance", f"{activity.distance_meters / 1000:.2f} km"
              if activity.distance_meters else None),
        _line("Moving time", _duration(activity.moving_time_sec)),
        _line("Average pace", _pace(activity.avg_pace_sec_km)),
        _line("Grade-adjusted pace", _pace(activity.gap_pace_sec_km)),
        _line("Average heart rate",
              f"{activity.avg_hr} bpm, peaking at {activity.max_hr} bpm"
              if activity.avg_hr and activity.max_hr else None),
        _line("Cadence", f"{round(activity.avg_cadence)} steps per minute"
              if activity.avg_cadence else None),
        _line("Ascent", f"{round(activity.elevation_gain_m)} m"
              if activity.elevation_gain_m else None),
        _line("Calories", f"{round(activity.calories_kcal)}"
              if activity.calories_kcal else None),
    ]
    if activity.aerobic_decoupling_pct is not None:
        drift = activity.aerobic_decoupling_pct
        # A number carries its own baggage: given "decoupling 10.9 percent" a
        # model reaches for fatigue even when the value is negative and the
        # brief says the opposite. A good result is therefore described in
        # words alone, and only a genuine drift is quantified.
        if drift <= 0:
            measured.append("- Pace and heart rate held together well; "
                            "the athlete was no less efficient by the end")
        elif drift < 5:
            measured.append(f"- Pace and heart rate held together reasonably well, "
                            f"drifting apart by {drift:.1f} percent, which is normal")
        else:
            measured.append(f"- Heart rate drifted upward relative to pace by "
                            f"{drift:.1f} percent, which is more than usual and "
                            f"suggests the effort was hard to hold")

    estimated = [
        _line("Training load", f"{round(activity.r_tss)}, against a typical session of "
              f"{round(context['typical_load'])} for this athlete"
              if activity.r_tss and context.get("typical_load") else None),
        _line("Training effect", f"{activity.training_effect_aerobic} out of 5"
              if activity.training_effect_aerobic else None),
        _line("Suggested recovery", f"{activity.recovery_hours} hours"
              if activity.recovery_hours else None),
    ]

    standing = [
        _line("Fitness, meaning their 42-day average training load",
              round(context["ctl"]) if context.get("ctl") else None),
        _line("Form, meaning fitness minus recent fatigue",
              f"{round(context['tsb'])}, so carrying some fatigue"
              if context.get("tsb", 0) < -5 else
              (f"{round(context['tsb'])}, so reasonably fresh"
               if context.get("tsb") is not None else None)),
    ]
    if context.get("longest_recent"):
        standing.append("- This was their longest run in the past 28 days")

    when = activity.start_time.strftime("%A %d %B %Y")
    parts = [f"Session on {when}, {activity.sport_type}.", "", "What was measured:"]
    parts += [m for m in measured if m]
    kept = [e for e in estimated if e]
    if kept:
        parts += ["", "What was estimated from those figures:"] + kept
    kept = [s for s in standing if s]
    if kept:
        parts += ["", "Where the athlete stands:"] + kept
    return "\n".join(parts)


def build_weekly_brief(summary: Dict[str, Any], activities: List[Any]) -> str:
    """Describe the last seven days."""
    lines = [f"The athlete's last seven days, ending {datetime.utcnow():%A %d %B %Y}.", ""]
    lines.append(f"They trained {len(activities)} time{'s' if len(activities) != 1 else ''}.")

    by_sport: Dict[str, List[Any]] = {}
    for a in activities:
        by_sport.setdefault(a.sport_type, []).append(a)
    for sport, group in sorted(by_sport.items(), key=lambda kv: -len(kv[1])):
        km = sum((a.distance_meters or 0) for a in group) / 1000
        time = _duration(sum(a.moving_time_sec or 0 for a in group))
        detail = f"{len(group)} {sport} session{'s' if len(group) != 1 else ''}"
        if km > 0.5:
            detail += f" covering {km:.1f} km in total across the week"
        if time:
            detail += f", {time} of moving time in total"
        lines.append(f"- {detail}")

    lines += ["", "Where they stand:"]
    for label, value in (
        ("Fitness, meaning their 42-day average training load", summary.get("ctl")),
        ("Fatigue, meaning their 7-day average load", summary.get("atl")),
    ):
        if value is not None:
            lines.append(f"- {label}: {round(value)}")
    tsb = summary.get("tsb")
    if tsb is not None:
        mood = ("carrying meaningful fatigue" if tsb < -15 else
                "carrying some fatigue" if tsb < -5 else
                "reasonably fresh" if tsb < 10 else "well rested")
        lines.append(f"- Form, meaning fitness minus fatigue: {round(tsb)}, so {mood}")
    drift = summary.get("avg_decoupling_28d")
    if drift is not None:
        lines.append(f"- Average aerobic decoupling over 28 days: {drift:.1f} percent")
    return "\n".join(lines)


REVIEW_SYSTEM_PROMPT = """You are a running coach writing a review of a training period that has finished.

Rules, most important first:
1. Never state a number that does not appear in the brief. Do not convert, round or recalculate anything. If the brief does not give a figure, do not estimate one.
2. Say what changed against the period before, and what it means. That comparison is the reason the athlete is reading this.
3. Never give medical advice, and never suggest the athlete may be ill or injured.
4. Do not prescribe specific training. You may say a period was heavy, light, consistent or patchy; you may not write next week's plan.
5. Four to six sentences of plain prose. Address the athlete as you. No headings, no lists, no markdown, no preamble, no sign-off."""


def _delta_phrase(label: str, delta: Optional[Dict[str, Any]], unit: str = "") -> Optional[str]:
    """
    A change, written as a direction rather than a signed number.

    Models reliably mishandle a leading minus -- "-8.2 km" came back as an
    eight-kilometre week more than once in testing -- so the direction is
    stated in words and only the size is given as a figure.
    """
    if not delta or delta.get("change") is None:
        return None
    change = delta["change"]
    if abs(change) < 0.05:
        return f"- {label}: unchanged"
    direction = "up" if change > 0 else "down"
    text = f"- {label}: {direction} by {abs(change):g}{unit}"
    pct = delta.get("pct")
    if pct is not None and abs(pct) >= 1:
        # Phrased without an article: "a 11 percent" and "a 18 percent" are
        # wrong, and the brief is meant to be readable straight off the page.
        text += f", which is {abs(pct):.0f} percent {'more' if change > 0 else 'less'}"
    return text


# Sports read as nouns, not as the labels they are stored under. A model given
# "1 walking" writes "one walking", and the whole point of this brief is that
# every value arrives pre-phrased.
_SPORT_NOUNS = {
    "walking": ("walk", "walks"),
    "hiking": ("hike", "hikes"),
    "cycling": ("ride", "rides"),
    "swimming": ("swim", "swims"),
    "rowing": ("row", "rows"),
    "gym": ("gym session", "gym sessions"),
    "strength": ("strength session", "strength sessions"),
    "treadmill": ("treadmill run", "treadmill runs"),
    "other": ("other session", "other sessions"),
}


def _count_of(sport: str, count: int) -> str:
    singular, plural = _SPORT_NOUNS.get(
        (sport or "").lower(), (f"{sport} session", f"{sport} sessions"))
    return f"{count} {singular if count == 1 else plural}"


def build_period_brief(report: Dict[str, Any]) -> str:
    """Describe a finished week, month or year against the one before it."""
    totals = report.get("totals") or {}
    deltas = report.get("deltas") or {}
    previous = (report.get("previous") or {}).get("totals") or {}
    noun = {"week": "week", "month": "month", "year": "year"}.get(report.get("kind"), "period")

    lines = [f"A review of the athlete's training {noun}, {report.get('label')}.", ""]

    measured = [
        _line("Sessions", totals.get("sessions")),
        _line("Runs", totals.get("runs")),
        _line("Running distance", f"{totals['km']:g} km" if totals.get("km") else None),
        _line("Running time", _duration(totals.get("moving_sec"))),
        _line("Days trained", f"{totals['days_trained']} out of {report.get('day_count', 7)}"
              if totals.get("days_trained") is not None and report.get("day_count") else None),
        _line("Average pace", _pace(totals.get("avg_pace_sec_km"))),
        _line("Average heart rate", f"{totals['avg_hr']:.0f} bpm" if totals.get("avg_hr") else None),
        _line("Elevation climbed", f"{totals['elevation_gain_m']:.0f} m"
              if totals.get("elevation_gain_m") else None),
        _line("Longest run", f"{totals['longest_km']:g} km" if totals.get("longest_km") else None),
        _line("Quickest run", _pace(totals.get("fastest_pace_sec_km"))),
        _line("Training load", round(totals["load"]) if totals.get("load") else None),
    ]
    lines += [m for m in measured if m]

    changes = [
        _delta_phrase("Distance", deltas.get("km"), " km"),
        _delta_phrase("Training load", deltas.get("load")),
        _delta_phrase("Number of runs", deltas.get("runs")),
        _delta_phrase("Days trained", deltas.get("days_trained")),
        _delta_phrase("Elevation climbed", deltas.get("elevation_gain_m"), " m"),
    ]
    # Pace improving means the number falling, which every model tested read
    # backwards. It is given as a plain statement of which was quicker instead.
    now_pace, was_pace = totals.get("avg_pace_sec_km"), previous.get("avg_pace_sec_km")
    if now_pace and was_pace:
        if abs(now_pace - was_pace) < 2:
            changes.append("- Average pace: the same as the period before")
        else:
            quicker = "quicker" if now_pace < was_pace else "slower"
            changes.append(
                f"- Average pace: {quicker} than the period before, "
                f"which was {_pace(was_pace)}"
            )
    kept = [c for c in changes if c]
    if kept:
        lines += ["", f"Against the previous {noun} ({(report.get('previous') or {}).get('label')}):"] + kept

    other = report.get("other_sports") or {}
    if other:
        parts = [_count_of(sport, v["count"])
                 for sport, v in sorted(other.items(), key=lambda kv: -kv[1]["count"])]
        lines += ["", f"They also did {', '.join(parts)}. This is not running and is not in the figures above."]

    records = [r for r in (report.get("records") or []) if r.get("is_personal_record")]
    if records:
        # A race time needs its seconds: _duration would render 25:30 as "25m".
        best = ", ".join(f"{r['label']} in {format_seconds(r['time_seconds'])}" for r in records)
        lines += ["", f"They set a personal record this {noun}: {best}."]

    form = report.get("form") or {}
    standing = [
        _line("Fitness at the end, meaning their 42-day average training load", 
              round(form["ctl_end"]) if form.get("ctl_end") is not None else None),
        _line("Form at the end, meaning fitness minus fatigue",
              round(form["tsb_end"]) if form.get("tsb_end") is not None else None),
        _line("Average aerobic decoupling, where under 5 percent is a well-paced aerobic effort",
              f"{totals['avg_decoupling_pct']:.1f} percent" if totals.get("avg_decoupling_pct") else None),
    ]
    kept = [s for s in standing if s]
    if kept:
        lines += ["", "Where they stand:"] + kept
    return "\n".join(lines)


def format_seconds(seconds: Optional[float]) -> Optional[str]:
    """A short duration read as minutes and seconds, for race times."""
    if not seconds or seconds <= 0:
        return None
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} hours {minutes} minutes"
    return f"{minutes} minutes {secs} seconds"


def brief_fingerprint(brief: str, model: str, system: str = SYSTEM_PROMPT) -> str:
    """
    Identifies a brief, so a note is regenerated only when the facts change.

    The instructions are part of the identity, not just the facts: changing how
    the coach is told to write should produce a new note, and without this a
    reworded prompt would silently keep serving text written under the old one.
    """
    return hashlib.sha256(f"{model}\n{system}\n{brief}".encode("utf-8")).hexdigest()[:32]


def list_models(base_url: str, timeout: int = 8) -> List[str]:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as r:
            return sorted(m["name"] for m in json.loads(r.read()).get("models", []))
    except Exception:
        return []


def generate(base_url: str, model: str, brief: str,
             timeout: int = REQUEST_TIMEOUT_SEC,
             system: str = SYSTEM_PROMPT, max_tokens: int = 200) -> CoachResult:
    """
    Ask the model to phrase the brief.

    Failure is soft on purpose: an unreachable or slow model must leave the
    dashboard exactly as it was, because none of the actual training data
    depends on it.
    """
    payload = json.dumps({
        "model": model,
        "stream": False,
        # Reasoning models otherwise spend the token budget thinking out loud.
        "think": False,
        "options": {"temperature": 0.3, "num_predict": max_tokens},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": brief},
        ],
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat", data=payload,
        headers={"Content-Type": "application/json"},
    )
    started = datetime.utcnow()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.URLError as exc:
        return CoachResult(ok=False, error=f"Could not reach the model at {base_url}: {exc.reason}")
    except Exception as exc:
        return CoachResult(ok=False, error=f"The model did not answer: {exc}")

    text = (body.get("message") or {}).get("content", "").strip()
    if not text:
        return CoachResult(ok=False, error="The model returned nothing.")

    return CoachResult(
        ok=True, text=text, model=model,
        seconds=(datetime.utcnow() - started).total_seconds(),
    )
