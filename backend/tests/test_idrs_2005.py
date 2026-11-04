import pytest

from app.services.idrs_2005 import calculate_idrs


@pytest.mark.parametrize(
    "age,sex,waist,activity,family,expected",
    [
        (60, "male", 101, "either", "both_parents", (90, "high")),
        (53, "female", 88, "either", "one_parent", (70, "high")),
        (45, "male", 92, "either", "one_parent", (60, "high")),
        (47, "female", 79, "either", "one_parent", (50, "moderate")),
        (32, "male", 96, "neither", "none", (40, "moderate")),
        (29, "female", 77, "either", "none", (20, "low")),
        (25, "male", 80, "both", "none", (0, "low")),
    ],
)
def test_original_published_examples(age, sex, waist, activity, family, expected):
    result = calculate_idrs(
        age=age, sex=sex, waist_cm=waist,
        physical_activity=activity, parental_diabetes=family,
    )
    assert (result["score"], result["screening_category"]) == expected


@pytest.mark.parametrize(
    "age,expected",
    [(20, 0), (34, 0), (35, 20), (49, 20), (50, 30), (80, 30)],
)
def test_age_point_boundaries(age, expected):
    result = calculate_idrs(
        age=age, sex="male", waist_cm=80,
        physical_activity="both", parental_diabetes="none",
    )
    assert result["points"]["age"] == expected


@pytest.mark.parametrize(
    "sex,waist,expected",
    [
        ("female", 79.99, 0), ("female", 80, 10), ("female", 89.99, 10), ("female", 90, 20),
        ("male", 89.99, 0), ("male", 90, 10), ("male", 99.99, 10), ("male", 100, 20),
    ],
)
def test_sex_specific_waist_boundaries(sex, waist, expected):
    result = calculate_idrs(
        age=20, sex=sex, waist_cm=waist,
        physical_activity="both", parental_diabetes="none",
    )
    assert result["points"]["waist_circumference"] == expected


@pytest.mark.parametrize("activity,expected", [("both", 0), ("either", 20), ("neither", 30)])
def test_original_physical_activity_points(activity, expected):
    result = calculate_idrs(
        age=20, sex="female", waist_cm=70,
        physical_activity=activity, parental_diabetes="none",
    )
    assert result["points"]["physical_activity"] == expected


@pytest.mark.parametrize("family,expected", [("none", 0), ("one_parent", 10), ("both_parents", 20)])
def test_parental_history_points(family, expected):
    result = calculate_idrs(
        age=20, sex="female", waist_cm=70,
        physical_activity="both", parental_diabetes=family,
    )
    assert result["points"]["parental_diabetes_history"] == expected


@pytest.mark.parametrize("waist", [0, 29.99, 250.01, 300])
def test_rejects_invalid_waist(waist):
    with pytest.raises(ValueError):
        calculate_idrs(
            age=18, sex="female", waist_cm=waist,
            physical_activity="both", parental_diabetes="none",
        )


@pytest.mark.parametrize("age", [19, 81])
def test_rejects_age_outside_original_derivation_population(age):
    with pytest.raises(ValueError):
        calculate_idrs(
            age=age, sex="female", waist_cm=70,
            physical_activity="both", parental_diabetes="none",
        )
