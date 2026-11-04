import pytest

from app.services.who_cvd_2019 import _CHART_ROWS, AGE_BANDS, SBP_BANDS, lookup_who_south_asia, risk_category


def test_official_chart_table_contains_every_published_row_and_cell():
    assert len(_CHART_ROWS) == len(AGE_BANDS) * len(SBP_BANDS) == 35
    assert all(len(no_diabetes) == len(diabetes) == 20 for _, _, no_diabetes, diabetes in _CHART_ROWS)


@pytest.mark.parametrize(
    ("kwargs", "published_value", "category"),
    [
        # WHO chart p. 1: 40–44, men non-smoker, no diabetes, SBP <120, TC <4.
        (dict(age=42, sex="male", smoking=False, diabetes=False, sbp_mmhg=119, cholesterol_mmol_l=3.9), 1, "<5%"),
        # WHO chart p. 1: 40–44, men smoker, no diabetes, SBP 140–159, TC >=7.
        (dict(age=44, sex="male", smoking=True, diabetes=False, sbp_mmhg=150, cholesterol_mmol_l=7.0), 10, "10% to <20%"),
        # WHO chart p. 1: 60–64, men smoker, diabetes, SBP 160–179, TC >=7.
        (dict(age=62, sex="male", smoking=True, diabetes=True, sbp_mmhg=170, cholesterol_mmol_l=7.2), 39, "≥30%"),
        # WHO chart p. 1: 55–59, women non-smoker, no diabetes, SBP <120, TC <4.
        (dict(age=57, sex="female", smoking=False, diabetes=False, sbp_mmhg=115, cholesterol_mmol_l=3.8), 3, "<5%"),
        # WHO chart p. 1: 70–74, women smoker, diabetes, SBP >=180, TC >=7.
        (dict(age=71, sex="female", smoking=True, diabetes=True, sbp_mmhg=185, cholesterol_mmol_l=8.0), 44, "≥30%"),
    ],
)
def test_official_who_south_asia_chart_reference_cells(kwargs, published_value, category):
    result = lookup_who_south_asia(**kwargs)
    assert result["chart_value_percent"] == published_value
    assert result["risk_category"] == category


def test_who_chart_boundaries_select_published_bins():
    assert lookup_who_south_asia(40, "male", False, False, 120, 4)["systolic_blood_pressure_band"] == "120-139"
    assert lookup_who_south_asia(40, "male", False, False, 140, 5)["systolic_blood_pressure_band"] == "140-159"
    assert lookup_who_south_asia(40, "male", False, False, 160, 6)["systolic_blood_pressure_band"] == "160-179"
    assert lookup_who_south_asia(40, "male", False, False, 180, 7)["systolic_blood_pressure_band"] == "≥180"
    assert [risk_category(value) for value in (4, 5, 10, 20, 30)] == [
        "<5%", "5% to <10%", "10% to <20%", "20% to <30%", "≥30%",
    ]


@pytest.mark.parametrize("age", [39, 75, 80])
def test_who_chart_rejects_age_outside_published_chart(age):
    with pytest.raises(ValueError):
        lookup_who_south_asia(age, "female", False, False, 120, 4)


def test_who_chart_rejects_missing_or_invalid_required_inputs():
    with pytest.raises(ValueError):
        lookup_who_south_asia(50, "other", False, False, 120, 4)
    with pytest.raises(ValueError):
        lookup_who_south_asia(50, "female", None, False, 120, 4)
    with pytest.raises(ValueError):
        lookup_who_south_asia(50, "female", False, False, 120, 0)
