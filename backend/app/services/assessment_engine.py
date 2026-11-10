"""Disease-model catalog and calculator plugin interface."""

from dataclasses import dataclass
from typing import Any, Callable

from app.services.who_cvd_2019 import WHO_CHART_SOURCE, WHO_CHART_VERSION, lookup_who_south_asia
from app.services.idrs_2005 import IDRS_SOURCE, IDRS_VERSION, calculate_idrs
from app.services.trained_models import MODEL_LIMITATIONS, SPECS, predict as predict_trained_model, validate_inputs


@dataclass(frozen=True)
class AssessmentTool:
    key: str
    name: str
    category: str
    version: str
    intended_use: str
    validated_population: str
    required_inputs: tuple[str, ...]
    limitations: tuple[str, ...]
    source_url: str
    license_status: str
    availability: str
    input_schema: tuple[dict[str, Any], ...] = ()
    defaults: dict[str, int | float] | None = None
    dataset: str | None = None
    metrics: str | None = None
    minimum_age: int | None = None
    maximum_age: int | None = None
    chart_minimum_age: int | None = None
    chart_maximum_age: int | None = None


@dataclass(frozen=True)
class AssessmentOutput:
    status: str
    result: dict[str, Any] | None
    contributing_factors: list[dict[str, Any]]
    missing_information: list[str]
    source_references: list[dict[str, Any]]
    input_snapshot: dict[str, Any]
    summary: str


Calculator = Callable[[dict[str, Any]], AssessmentOutput]


TOOLS: dict[str, AssessmentTool] = {
    "who_2019_south_asia_cvd": AssessmentTool(
        key="who_2019_south_asia_cvd", name="WHO 2019 South Asia cardiovascular risk chart",
        category="cardiovascular", version=WHO_CHART_VERSION,
        intended_use="Experimental 10-year cardiovascular risk category for health discussions; not diagnosis",
        validated_population="Underlying model derived for ages 40–80 in South Asia; published South Asia chart has age bands only through 70–74",
        required_inputs=("age", "sex", "current_smoking", "diabetes_status", "systolic_blood_pressure", "total_cholesterol"),
        limitations=(
            "Uses published chart bins and reports only the chart's risk category; exact chart lookup is available for ages 40–74.",
            "Ages 75–80 are within the underlying model derivation range, but the published South Asia categorical chart has no corresponding rows; CareKey does not extrapolate.",
            "Not independently validated for CareKey users or specifically validated for Indian patients.",
            "Does not include family history, treatment, HDL, or other clinical factors; not for people with established cardiovascular disease.",
        ),
        source_url=WHO_CHART_SOURCE,
        license_status="published_who_chart_attributed",
        availability="enabled",
        minimum_age=40, maximum_age=80, chart_minimum_age=40, chart_maximum_age=74,
    ),
    "prevent_cvd": AssessmentTool(
        key="prevent_cvd", name="AHA PREVENT CVD", category="cardiovascular",
        version="2026-10-14", intended_use="Clinician-patient primary prevention discussion",
        validated_population="U.S. adults ages 30–79 without known CVD; additional exclusions apply",
        required_inputs=("age", "sex", "systolic_blood_pressure", "total_cholesterol", "hdl_cholesterol", "egfr", "bmi", "diabetes", "smoking", "blood_pressure_treatment", "lipid_lowering_therapy"),
        limitations=("Derived from U.S. populations; use cautiously outside the U.S.", "Not for known CVD or specified high-risk conditions", "AHA code license agreement required; current release includes an October 2026 HbA1c predictor correction"),
        source_url="https://professional.heart.org/en/guidelines-and-statements/about-prevent-calculator",
        license_status="agreement_required", availability="disabled",
    ),
    "idrs_type2_diabetes": AssessmentTool(
        key="idrs_type2_diabetes", name="Indian Diabetes Risk Score (IDRS)", category="type_2_diabetes",
        version=IDRS_VERSION, intended_use="Screening for possible previously undiagnosed diabetes; not a diagnosis or future-onset prediction",
        validated_population="Indian adult populations; performance and thresholds depend on the population and setting",
        required_inputs=("age", "sex", "waist_circumference", "physical_activity", "family_history_of_diabetes"),
        limitations=(
            "Screens for possible previously undiagnosed diabetes; it does not diagnose diabetes or estimate future-onset probability.",
            "Uses the original MDRF-IDRS activity categories and parental family-history definitions; later adaptations may use different categories.",
            "Original score derived from CURES in Chennai; performance may differ across settings and populations.",
            "Original CURES derivation cohort was sampled from adults aged 20–80; ages 18–19 and over 80 are outside the configured population.",
            "Independent implementation follows the published scoring table with attribution and does not copy proprietary model code or weights.",
        ),
        source_url=IDRS_SOURCE,
        license_status="published_method_attributed_independent_implementation",
        availability="enabled", minimum_age=20, maximum_age=80,
    ),
    "qdiabetes_2018": AssessmentTool(
        key="qdiabetes_2018", name="QDiabetes-2018", category="type_2_diabetes",
        version="2018", intended_use="Ten-year future-onset type 2 diabetes risk for people without a diabetes diagnosis",
        validated_population="UK adults ages 25–84; UK-specific baseline risk and postcode deprivation input",
        required_inputs=("age", "sex", "ethnicity", "smoking", "family_history_of_diabetes", "systolic_blood_pressure", "bmi", "relevant_conditions", "medications", "hba1c_or_fasting_glucose"),
        limitations=("Developed for the UK population; do not extrapolate to India or the U.S.", "Not for people already diagnosed with diabetes", "Implementation must use the authoritative code and pass reference-vector tests; AGPL and QDiabetes use terms need review"),
        source_url="https://qdiabetes.org/",
        license_status="AGPL_and_authorized_use_review_required", availability="disabled",
    ),
    "bcrat_breast_cancer": AssessmentTool(
        key="bcrat_breast_cancer", name="NCI Breast Cancer Risk Assessment Tool (Gail/BCRAT)", category="breast_cancer",
        version="4.1", intended_use="Absolute invasive breast-cancer risk estimate over a defined interval",
        validated_population="Specified U.S. populations; not applicable to everyone",
        required_inputs=("age", "race_ethnicity", "age_at_menarche", "age_at_first_live_birth", "first_degree_relatives_with_breast_cancer", "prior_breast_biopsies", "atypical_hyperplasia"),
        limitations=("Not accurate for BRCA1/2 carriers or people with prior invasive/DCIS/LCIS breast cancer", "Can underestimate risk in some subgroups", "NCI software agreement states software is not intended for treating or diagnosing human subjects"),
        source_url="https://bcrisktool.cancer.gov/about.html",
        license_status="agreement_and_use_review_required", availability="disabled",
    ),
    "sybil_lung_cancer": AssessmentTool(
        key="sybil_lung_cancer", name="Sybil lung cancer risk model", category="lung_cancer",
        version="official-release-check-required", intended_use="Research prototype: future lung cancer risk from one low-dose axial chest CT; not diagnosis",
        validated_population="NLST development cohort, with external validation at MGH (United States) and CGMH (Taiwan); not established for India",
        required_inputs=("one complete axial low-dose chest CT DICOM series", "official pretrained checkpoint"),
        limitations=(
            "Research only; the model authors do not intend the code for clinical decision-making.",
            "The repository code is MIT licensed, but checkpoint-specific licensing and release terms have not been independently established for CareKey.",
            "NLST source data are controlled-access and are not bundled; the public model checkpoint is not NLST data.",
            "No Indian population validation; CareKey has no imaging upload or verified inference pipeline for this model.",
        ),
        source_url="https://github.com/reginabarzilaygroup/Sybil",
        license_status="checkpoint_terms_and_inference_environment_review_required",
        availability="disabled",
    ),
    "mirai_breast_cancer": AssessmentTool(
        key="mirai_breast_cancer", name="Mirai breast cancer risk model", category="breast_cancer",
        version="official-release-check-required", intended_use="Research prototype: future breast cancer risk from four-view screening mammography; not diagnosis",
        validated_population="MGH (United States), Karolinska (Sweden), and Chang Gung Memorial Hospital (Taiwan); not established for India",
        required_inputs=("L CC For Presentation mammogram", "L MLO For Presentation mammogram", "R CC For Presentation mammogram", "R MLO For Presentation mammogram", "official pretrained checkpoints"),
        limitations=(
            "The official MIT repository says the codebase is for research and is not intended for clinical decision-making or other clinical use.",
            "The repository states that the trained model and code are MIT licensed; the named OncoServe image/checkpoint package and its distribution terms still require confirmation before deployment.",
            "Requires four standard For Presentation views; it does not support unilateral exams, For Processing images, or marked-up images.",
            "The authors report testing on Hologic Selenia/Selenia Dimensions devices; performance on other devices is unestablished.",
            "No Indian population validation; CareKey has no mammography upload or verified inference pipeline for this model.",
        ),
        source_url="https://github.com/yala/Mirai",
        license_status="research_code_mit_checkpoint_package_review_required",
        availability="disabled",
    ),
}

for _key, _spec in SPECS.items():
    TOOLS[_key] = AssessmentTool(
        key=_key, name=_spec.name, category=_spec.category, version=_spec.version,
        intended_use=_spec.purpose, validated_population="General adult screening prototype; not clinically validated for CareKey users",
        required_inputs=_spec.features, limitations=MODEL_LIMITATIONS,
        source_url="https://www.cdc.gov/brfss/" if _key != "lung_cancer_survey" else "",
        license_status="Local project artifact; research/educational use only",
        availability="enabled",
        input_schema=_spec.field_specs, defaults=_spec.defaults,
        dataset=_spec.dataset, metrics=_spec.metrics,
    )

def _who_south_asia_calculator(inputs: dict[str, Any]) -> AssessmentOutput:
    cell = lookup_who_south_asia(
        age=inputs["age"], sex=inputs["sex"], smoking=inputs["smoking"],
        diabetes=inputs["diabetes"], sbp_mmhg=inputs["systolic_blood_pressure"],
        cholesterol_mmol_l=inputs["total_cholesterol_mmol_l"],
    )
    # Only the official categorical band is a user-facing result. The integer
    # chart value is retained in the immutable input snapshot for traceability.
    result = {
        "risk_category": cell["risk_category"],
        "time_horizon": "10 years",
        "method": "WHO 2019 South Asia laboratory-based chart lookup",
    }
    factors = [
        {"label": "Chart input: age band", "value": cell["age_band"]},
        {"label": "Chart input: sex", "value": cell["sex"]},
        {"label": "Chart input: current smoking", "value": "yes" if cell["current_smoker"] else "no"},
        {"label": "Chart input: diabetes", "value": "yes" if cell["diabetes"] else "no"},
        {"label": "Chart input: systolic blood pressure band", "value": cell["systolic_blood_pressure_band"] + " mmHg"},
        {"label": "Chart input: total cholesterol band", "value": cell["cholesterol_band"] + " mmol/L"},
    ]
    return AssessmentOutput(
        status="complete", result=result, contributing_factors=factors,
        missing_information=[],
        source_references=[{"title": "WHO 2019 South Asia laboratory-based cardiovascular risk chart", "url": WHO_CHART_SOURCE, "version": WHO_CHART_VERSION}],
        input_snapshot={**inputs, "official_chart_cell_percent": cell["chart_value_percent"], "chart_categories": ["<5%", "5% to <10%", "10% to <20%", "20% to <30%", "≥30%"]},
        summary=f"Experimental WHO chart lookup: 10-year cardiovascular risk category {cell['risk_category']}. This is not a diagnosis and has not been validated for CareKey users or specifically for Indian patients.",
    )


def _idrs_calculator(inputs: dict[str, Any]) -> AssessmentOutput:
    calculated = calculate_idrs(
        age=inputs["age"], sex=inputs["sex"], waist_cm=inputs["waist_circumference_cm"],
        physical_activity=inputs["physical_activity"], parental_diabetes=inputs["parental_diabetes"],
    )
    score = calculated["score"]
    category = calculated["screening_category"]
    descriptions = {
        "low": "low screening score",
        "moderate": "moderate screening score",
        "high": "high screening score",
    }
    labels = {
        "both": "regular leisure exercise and strenuous work activity",
        "either": "either regular leisure exercise or strenuous work activity",
        "neither": "neither regular leisure exercise nor strenuous work activity",
    }
    family_labels = {"none": "neither parent", "one_parent": "one parent", "both_parents": "both parents"}
    factors = [
        {"label": "Age", "value": f"{inputs['age']} years ({calculated['points']['age']} points)"},
        {"label": "Waist circumference", "value": f"{inputs['waist_circumference_cm']} cm ({calculated['points']['waist_circumference']} points)"},
        {"label": "Physical activity", "value": f"{labels[inputs['physical_activity']]} ({calculated['points']['physical_activity']} points)"},
        {"label": "Diabetes in parents", "value": f"{family_labels[inputs['parental_diabetes']]} ({calculated['points']['parental_diabetes_history']} points)"},
    ]
    return AssessmentOutput(
        status="complete",
        result={"idrs_score": score, "maximum_score": 100, "screening_category": category, "assessment_type": "screening"},
        contributing_factors=factors,
        missing_information=[],
        source_references=[{"title": "A Simplified Indian Diabetes Risk Score for Screening for Undiagnosed Diabetic Subjects", "url": IDRS_SOURCE, "version": IDRS_VERSION}],
        input_snapshot={**inputs, "idrs_points": calculated["points"], "score": score, "screening_category": category},
        summary=f"Experimental IDRS screening result: {descriptions[category]} ({score}/100). This is a screening score for possible previously undiagnosed diabetes, not a diagnosis and not an estimate of future-onset probability. Confirm with an appropriate clinical test.",
    )


CALCULATORS: dict[str, Calculator] = {
    "who_2019_south_asia_cvd": _who_south_asia_calculator,
    "idrs_type2_diabetes": _idrs_calculator,
}


def _trained_model_calculator(model_key: str) -> Calculator:
    spec = SPECS[model_key]

    def calculate(inputs: dict[str, Any]) -> AssessmentOutput:
        checked = validate_inputs(model_key, inputs)
        result = predict_trained_model(model_key, checked)
        return AssessmentOutput(
            status="complete", result=result,
            contributing_factors=[{"label": field["label"], "value": checked[field["name"]]} for field in spec.field_specs],
            missing_information=[],
            source_references=[{"record_type": "local_model_artifacts", "model_file": spec.model_file, "scaler_file": spec.scaler_file, "version": spec.version, "dataset": spec.dataset, "evaluation_metrics": spec.metrics}],
            input_snapshot={"inputs": checked, "feature_order": list(spec.features), "model_version": spec.version},
            summary=f"Experimental model output: {result['category'].replace('_', ' ')} at a 0.5 threshold. It is not a diagnosis or calibrated clinical risk estimate; a low output does not rule out disease.",
        )

    return calculate


for _model_key in SPECS:
    CALCULATORS[_model_key] = _trained_model_calculator(_model_key)


def register_calculator(model_key: str, calculator: Calculator) -> None:
    if model_key not in TOOLS:
        raise KeyError(f"Unknown assessment tool: {model_key}")
    CALCULATORS[model_key] = calculator


def run_calculator(model_key: str, inputs: dict[str, Any]) -> AssessmentOutput:
    tool = TOOLS.get(model_key)
    if tool is None:
        raise KeyError(f"Unknown assessment tool: {model_key}")
    calculator = CALCULATORS.get(model_key)
    if tool.availability != "enabled" or calculator is None:
        raise PermissionError("This assessment tool is not enabled; required usage rights or implementation review are pending")
    return calculator(inputs)
