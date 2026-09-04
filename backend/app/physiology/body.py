"""
Body composition from a tape measure.

BMI is weight over height squared and knows nothing else. It cannot tell muscle
from fat, which is why it reads a lean, heavily trained runner as overweight
and a sedentary person of the same weight as fine. It is reported here because
it is the figure everyone recognises, and immediately alongside something that
answers the question BMI is usually being asked.

That something is the US Navy circumference method (Hodgdon and Beckett, 1984),
which estimates body fat from girths: neck and waist for men, and hips as well
for women, against height. It is not a DEXA scan. It is repeatable with a tape
measure at home, which is what makes it useful for watching a direction of
travel rather than chasing an absolute.

Both are estimates and both are labelled as such. Neither is a diagnosis.
"""
import math
from typing import Any, Dict, Optional

# Plausible human measurements. Outside these the entry was a slip -- a waist
# in inches, or a height in metres -- and an estimate from it is worse than
# none, because it looks like an answer.
LIMITS = {
    "height_cm": (100.0, 250.0),
    "weight_kg": (25.0, 300.0),
    "neck_cm": (20.0, 70.0),
    "waist_cm": (40.0, 200.0),
    "hip_cm": (50.0, 200.0),
}

# The method breaks down outside roughly this range, and a figure it cannot
# support should not be shown as though it could.
MIN_BODY_FAT = 3.0
MAX_BODY_FAT = 60.0


def _valid(name: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    low, high = LIMITS[name]
    return float(value) if low <= float(value) <= high else None


def bmi(weight_kg: Optional[float], height_cm: Optional[float]) -> Optional[float]:
    weight = _valid("weight_kg", weight_kg)
    height = _valid("height_cm", height_cm)
    if weight is None or height is None:
        return None
    return round(weight / ((height / 100.0) ** 2), 1)


def body_fat_percent(
    sex: Optional[str],
    height_cm: Optional[float],
    neck_cm: Optional[float],
    waist_cm: Optional[float],
    hip_cm: Optional[float] = None,
) -> Optional[float]:
    """
    US Navy circumference estimate, in percent, or None if it cannot be made.

    The two formulas are not interchangeable: the female one includes hips and
    has its own coefficients, so an athlete who has not said which applies gets
    no estimate rather than the wrong one.
    """
    height = _valid("height_cm", height_cm)
    neck = _valid("neck_cm", neck_cm)
    waist = _valid("waist_cm", waist_cm)
    if height is None or neck is None or waist is None:
        return None

    normalised = (sex or "").strip().lower()
    if normalised == "female":
        hip = _valid("hip_cm", hip_cm)
        if hip is None:
            return None
        girth = waist + hip - neck
        if girth <= 0:
            return None
        value = 495.0 / (1.29579
                         - 0.35004 * math.log10(girth)
                         + 0.22100 * math.log10(height)) - 450.0
    elif normalised == "male":
        girth = waist - neck
        # A waist no bigger than the neck is a mistyped measurement, and the
        # logarithm below is undefined for it either way.
        if girth <= 0:
            return None
        value = 495.0 / (1.0324
                         - 0.19077 * math.log10(girth)
                         + 0.15456 * math.log10(height)) - 450.0
    else:
        return None

    if not (MIN_BODY_FAT <= value <= MAX_BODY_FAT):
        return None
    return round(value, 1)


# Ranges as the American Council on Exercise publishes them. Shown as context,
# never as a verdict: "athletic" and "fit" overlap for a reason.
_BANDS = {
    "male":   [(6.0, "Essential"), (14.0, "Athletic"), (18.0, "Fit"),
               (25.0, "Average"), (100.0, "Above average")],
    "female": [(14.0, "Essential"), (21.0, "Athletic"), (25.0, "Fit"),
               (32.0, "Average"), (100.0, "Above average")],
}


def body_fat_band(sex: Optional[str], percent: Optional[float]) -> Optional[str]:
    bands = _BANDS.get((sex or "").strip().lower())
    if bands is None or percent is None:
        return None
    for ceiling, label in bands:
        if percent < ceiling:
            return label
    return bands[-1][1]


def composition(profile) -> Dict[str, Any]:
    """Everything derivable from the stored measurements."""
    fat = body_fat_percent(
        getattr(profile, "gender", None),
        getattr(profile, "height_cm", None),
        getattr(profile, "neck_cm", None),
        getattr(profile, "waist_cm", None),
        getattr(profile, "hip_cm", None),
    )
    weight = _valid("weight_kg", getattr(profile, "weight_kg", None))
    return {
        "bmi": bmi(getattr(profile, "weight_kg", None), getattr(profile, "height_cm", None)),
        "body_fat_percent": fat,
        "body_fat_band": body_fat_band(getattr(profile, "gender", None), fat),
        # Lean mass is the figure worth watching across a training block: it is
        # what should hold steady while weight moves.
        "lean_mass_kg": round(weight * (1 - fat / 100.0), 1)
        if fat is not None and weight is not None else None,
    }
