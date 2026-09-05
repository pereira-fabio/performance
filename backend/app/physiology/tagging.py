"""
Working out what kind of session a run was.

A watch records what happened; the athlete knows what it was for. This closes
some of that gap automatically, so most runs arrive already described and only
the interesting ones need correcting.

Two decisions shape the whole thing.

**It judges a session against the athlete's own runs, not against absolutes.**
Intensity factor is measured against threshold pace, which is a figure people
set once and often not at all. Left at its default, every run of a slower
athlete looks like a recovery jog and every run of a faster one looks like a
race. Comparing a session with the median of their recent ones is immune to
that: it asks "was this harder than usual for you", which is the actual
question, and it stays right even when the threshold is wrong.

**It never guesses "race".** A race and a hard tempo look identical in the
data, and the cost of the two mistakes is not symmetric -- an untagged race is
a moment's work to label, while a training run recorded as a race quietly
becomes part of a history that never happened.
"""
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

from backend.app.core.sports import is_running

# A session needs this many complete kilometres before its variability means
# anything. Below it one traffic light is the whole signal.
MIN_SPLITS_FOR_INTERVALS = 4

# How much the second-by-second pace has to swing before a run is structured.
#
# Splits alone are not enough: three-minute repetitions average out inside a
# kilometre, so a session of them reads as perfectly even and gets called a
# tempo. The smoothed speed trace still shows the alternation plainly, and only
# misses repetitions shorter than the smoothing window.
#
# A steady run varies by a few percent from GPS noise and gradient; hills push
# that to around a tenth. Repetitions are far beyond both.
INTERVAL_SPEED_VARIATION = 0.18

# How much the kilometres have to differ before a run is structured rather than
# merely undulating. Measured on grade-adjusted pace where it exists, so hills
# do not read as repetitions.
INTERVAL_SPREAD = 0.08

# And the quick end has to be genuinely quick, not just the flat kilometre in a
# hilly run.
INTERVAL_FAST_MARGIN = 0.10

# An hour is the floor for a long run whatever the athlete's history, and this
# much longer than their usual makes it long for them.
LONG_RUN_MIN_SEC = 3600
LONG_RUN_RATIO = 1.35

# Long enough that it is a long run for anyone.
LONG_RUN_ABSOLUTE_SEC = 5400

# Against the athlete's own median intensity. Wide enough that ordinary
# variation between easy days stays "easy".
RELATIVE_EASY = 0.90
RELATIVE_HARD = 1.12

# Used only when there is no history to compare with. These are the textbook
# fractions of threshold speed, and they assume the threshold pace is right.
ABSOLUTE_EASY = 0.78
ABSOLUTE_HARD = 0.90


def _spread(values: Sequence[float]) -> Optional[float]:
    """How much a set of paces varies, relative to its own middle."""
    kept = [v for v in values if v and v > 0]
    if len(kept) < MIN_SPLITS_FOR_INTERVALS:
        return None
    middle = median(kept)
    if middle <= 0:
        return None
    spread = sum(abs(v - middle) for v in kept) / len(kept) / middle
    return spread


def looks_like_intervals(splits: Sequence[Dict[str, Any]]) -> bool:
    """
    Whether the kilometres alternate rather than hold.

    Grade-adjusted pace is used where every split has it, so a hilly steady run
    is not mistaken for a session of repetitions. Falling back to raw pace when
    it is missing is deliberate: the alternative is never detecting intervals
    for anyone whose device records no elevation.
    """
    full = [s for s in splits if not s.get("is_partial")]
    if len(full) < MIN_SPLITS_FOR_INTERVALS:
        return False

    gaps = [s.get("gap_sec_km") for s in full]
    paces = [g for g in gaps if g] if all(gaps) else [s.get("pace_sec_km") for s in full]
    paces = [p for p in paces if p and p > 0]
    if len(paces) < MIN_SPLITS_FOR_INTERVALS:
        return False

    spread = _spread(paces)
    if spread is None or spread < INTERVAL_SPREAD:
        return False

    middle = median(paces)
    quickest = min(paces)
    return (middle - quickest) / middle >= INTERVAL_FAST_MARGIN


def suggest_tag(
    sport_type: Optional[str],
    moving_time_sec: Optional[float],
    intensity_factor: Optional[float],
    splits: Optional[Sequence[Dict[str, Any]]] = None,
    typical_intensity: Optional[float] = None,
    typical_duration_sec: Optional[float] = None,
    speed_variation: Optional[float] = None,
) -> Optional[str]:
    """
    A tag for one session, or None when nothing can be said with confidence.

    None is a real answer here. A session with no useful signal is better left
    untagged than labelled "easy" by default, which would put a word the athlete
    did not choose on a run nobody looked at.
    """
    # Tags describe running. A walk is not a recovery run and a gym session is
    # not a tempo, and stretching the vocabulary to cover them would make every
    # tag mean less.
    if not is_running(sport_type):
        return None

    # Two ways of seeing the same thing. The trace catches short repetitions
    # that vanish inside a kilometre; the splits catch long ones on a device
    # that recorded no usable speed.
    if speed_variation is not None and speed_variation >= INTERVAL_SPEED_VARIATION:
        return "interval"
    if looks_like_intervals(splits or []):
        return "interval"

    duration = moving_time_sec or 0.0
    if duration >= LONG_RUN_ABSOLUTE_SEC:
        return "long"
    if duration >= LONG_RUN_MIN_SEC and typical_duration_sec:
        if duration >= typical_duration_sec * LONG_RUN_RATIO:
            return "long"

    if not intensity_factor or intensity_factor <= 0:
        return None

    # Against the athlete's own runs where there are enough of them. This is
    # what keeps the tags right when threshold pace is wrong.
    if typical_intensity and typical_intensity > 0:
        relative = intensity_factor / typical_intensity
        if relative <= RELATIVE_EASY:
            return "recovery"
        if relative >= RELATIVE_HARD:
            return "tempo"
        return "easy"

    # No history yet, so the textbook fractions of threshold speed, which are
    # only as good as the threshold pace they are measured against.
    if intensity_factor <= ABSOLUTE_EASY:
        return "recovery"
    if intensity_factor >= ABSOLUTE_HARD:
        return "tempo"
    return "easy"


def speed_variation(
    speeds: Sequence[float],
    smooth_sec: int = 30,
    sample_interval_sec: float = 1.0,
) -> Optional[float]:
    """
    How much the pace swings over a session, on a smoothed trace.

    Smoothed first, because raw GPS speed jumps around far more than the runner
    does and would make every run look like intervals. Only moving samples
    count, so a session with a long stop is not read as one enormous rep.

    The window is given in seconds and converted using the spacing of the
    samples, because these do not always arrive one a second: a stored stream
    is thinned on the way into the database, and smoothing thirty of those as
    though they were thirty seconds would flatten a session far past the point
    where repetitions are still visible.

    Returned as mean absolute deviation over the median, which a single dropout
    moves far less than a standard deviation would.
    """
    moving = [float(v) for v in speeds if v is not None and v > 0.5]
    window = max(1, int(round(smooth_sec / max(sample_interval_sec, 0.001))))
    # Two smoothing windows of data at the very least, or the smoothing has
    # nothing to average and the answer is noise.
    if len(moving) < window * 2:
        return None

    half = max(1, window // 2)
    smoothed = []
    for i in range(len(moving)):
        low, high = max(0, i - half), min(len(moving), i + half + 1)
        window = moving[low:high]
        smoothed.append(sum(window) / len(window))

    middle = median(smoothed)
    if middle <= 0:
        return None
    return sum(abs(v - middle) for v in smoothed) / len(smoothed) / middle
