"""
Which sports count as running.

Health Connect reports several activity types, and a device may record walks,
hikes and gym work alongside runs. They are all real training and all worth
storing, but they are not interchangeable: a 10:31/km walk must not set a "5k
personal record", and gym work must not drive a running fitness curve.
"""
from typing import Optional

# Sports whose pace and distance are comparable to a run, and which therefore
# drive running training load, best efforts and personal records.
RUNNING_SPORTS = frozenset({"running", "treadmill"})

# Sports that carry genuine training stress but are not runs. They are stored
# and shown, and contribute their own load, but stay out of running metrics.
CROSS_TRAINING_SPORTS = frozenset({
    "walking", "hiking", "gym", "strength", "cycling", "swimming", "rowing", "other",
})


def is_running(sport_type: Optional[str]) -> bool:
    return (sport_type or "running").lower() in RUNNING_SPORTS


# What kind of session it was, as the athlete describes it. A watch records
# what happened; only the runner knows whether an easy pace was a recovery jog
# or all they had left, and the same numbers mean different things either way.
#
# Deliberately short. A list long enough to describe every session is one
# nobody keeps up with, and an unused tag is worse than none.
WORKOUT_TAGS = (
    "recovery",
    "easy",
    "long",
    "tempo",
    "interval",
    "race",
)


def is_valid_tag(tag) -> bool:
    return tag is None or tag == "" or tag in WORKOUT_TAGS
