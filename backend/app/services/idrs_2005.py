"""Independent implementation of the published original MDRF-IDRS score.

Source: Mohan et al., J Assoc Physicians India. 2005;53:759-763.
https://repository.ias.ac.in/80170/1/80170.pdf

This is a screening score for previously undiagnosed diabetes, not a diagnosis,
ML model, or estimate of future-onset probability.
"""

from __future__ import annotations

IDRS_VERSION = "mdrf-idrs-original-2005"
IDRS_SOURCE = "https://repository.ias.ac.in/80170/1/80170.pdf"


def calculate_idrs(
    *, age: int, sex: str, waist_cm: float, physical_activity: str,
    parental_diabetes: str,
) -> dict:
    """Calculate the original 0–100 MDRF-IDRS and its screening category."""
    if isinstance(age, bool) or not isinstance(age, int) or not 20 <= age <= 80:
        raise ValueError("Original IDRS derivation population covers adults aged 20–80")
    sex = sex.strip().lower()
    if sex not in {"male", "female"}:
        raise ValueError("IDRS waist thresholds require sex recorded as male or female")
    if not 30 <= waist_cm <= 250:
        raise ValueError("Waist circumference must be between 30 and 250 cm")
    if physical_activity not in {"both", "either", "neither"}:
        raise ValueError("Unsupported IDRS physical-activity category")
    if parental_diabetes not in {"none", "one_parent", "both_parents"}:
        raise ValueError("Unsupported IDRS parental diabetes category")

    age_points = 0 if age < 35 else 20 if age < 50 else 30
    if sex == "female":
        waist_points = 0 if waist_cm < 80 else 10 if waist_cm < 90 else 20
    else:
        waist_points = 0 if waist_cm < 90 else 10 if waist_cm < 100 else 20
    activity_points = {"both": 0, "either": 20, "neither": 30}[physical_activity]
    family_points = {"none": 0, "one_parent": 10, "both_parents": 20}[parental_diabetes]
    score = age_points + waist_points + activity_points + family_points

    if score < 30:
        category = "low"
    elif score <= 50:
        category = "moderate"
    elif score >= 60:
        category = "high"
    else:  # No score in 51–59 is reachable with the published point increments.
        raise ValueError("The computed score falls between published IDRS categories")

    return {
        "score": score,
        "maximum_score": 100,
        "screening_category": category,
        "points": {
            "age": age_points,
            "waist_circumference": waist_points,
            "physical_activity": activity_points,
            "parental_diabetes_history": family_points,
        },
    }
