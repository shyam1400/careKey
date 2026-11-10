from datetime import datetime, timezone
import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums import AppRole
from app.models.audit import AccessLog
from app.models.health_data import HealthAssessment, HealthMeasurement, PatientAssessmentInput, PatientRiskFactor
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.records import Condition
from app.models.user import User
from app.schemas.assessment import AssessmentToolResponse, HealthAssessmentResponse, TrainedAssessmentRequest
from app.services.assessment_engine import TOOLS, run_calculator
from app.services.who_cvd_2019 import WHO_CHART_SOURCE, WHO_CHART_VERSION, lookup_who_south_asia
from app.services.trained_models import MODEL_LIMITATIONS, ModelUnavailable, SPECS, model_available, predict as predict_trained_model, validate_inputs

router = APIRouter(prefix="/health-assessments", tags=["health-assessments"])


def _audit(db: Session, patient_id: UUID, user: User, action: str, *, success: bool, model_key: str | None = None) -> None:
    profile = db.scalar(select(Profile).where(Profile.id == user.id))
    db.add(AccessLog(
        patient_id=patient_id, provider_id=user.id,
        provider_name=profile.full_name if profile else ("Patient" if user.role == AppRole.PATIENT else "Care provider"),
        action=action[:500], categories=["health_assessments"],
        reason=(model_key or "Patient health assessment")[:64],
        access_type="health_assessment", success=success,
    ))
    db.commit()


def _patient_id(user: User, db: Session) -> UUID:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can manage their health assessments")
    patient_id = db.scalar(select(Patient.id).where(Patient.id == user.id))
    if patient_id is None:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient_id


@router.get("/models", response_model=list[AssessmentToolResponse])
def list_assessment_models(user: User = Depends(get_current_user)):
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can view assessment models")
    responses = []
    for key, spec in SPECS.items():
        limitations = list(MODEL_LIMITATIONS)
        if key in {"diabetes_brfss", "heart_disease_brfss"}:
            limitations.append("The BRFSS models use U.S. survey features and are not validated for Indian or CareKey patients.")
        responses.append(AssessmentToolResponse(
        key=key, name=spec.name, category=spec.category, version=spec.version,
        intended_use=spec.purpose, validated_population="General adult screening prototype; not clinically validated for CareKey users",
        required_inputs=list(spec.features), limitations=limitations,
        source_url="https://www.cdc.gov/brfss/" if key != "lung_cancer_survey" else "",
        license_status="Local project artifact; research/educational use only",
        availability="enabled" if model_available(key) else "disabled",
        input_schema=list(spec.field_specs), defaults=spec.defaults,
        dataset=spec.dataset, metrics=spec.metrics,
        availability_reason=None if model_available(key) else "Model weights or inference runtime are unavailable or failed the inference check.",
        ))
    return responses


@router.get("/history", response_model=list[HealthAssessmentResponse])
def list_my_assessments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    rows = db.scalars(select(HealthAssessment).where(
        HealthAssessment.patient_id == patient_id,
    ).order_by(HealthAssessment.assessed_at.desc()).limit(100)).all()
    _audit(db, patient_id, user, "Patient viewed assessment history", success=True)
    return rows


@router.get("/{assessment_id}", response_model=HealthAssessmentResponse)
def read_my_assessment(assessment_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    assessment = db.scalar(select(HealthAssessment).where(
        HealthAssessment.id == assessment_id, HealthAssessment.patient_id == patient_id,
    ))
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _audit(db, patient_id, user, "Patient viewed a health assessment", success=True, model_key=assessment.model_key)
    return assessment


@router.post("/{model_key}/run", response_model=HealthAssessmentResponse)
def generate_assessment(
    model_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    payload: TrainedAssessmentRequest | None = None,
):
    patient_id = _patient_id(user, db)
    if model_key in SPECS:
        if payload is None or not payload.patient_confirmed:
            _audit(db, patient_id, user, "Trained assessment rejected: confirmation missing", success=False, model_key=model_key)
            raise HTTPException(status_code=422, detail="Review and confirm all assessment inputs before continuing")
        return _generate_trained_assessment(model_key, payload, db, user, patient_id)
    tool = TOOLS.get(model_key)
    if tool is None:
        _audit(db, patient_id, user, "Health assessment generation attempted for unknown model", success=False, model_key=model_key)
        raise HTTPException(status_code=404, detail="Assessment model not found")
    if model_key == "who_2019_south_asia_cvd":
        return _generate_who_cvd_assessment(db, user, patient_id)
    if model_key == "idrs_type2_diabetes":
        return _generate_idrs_assessment(db, user, patient_id)
    try:
        run_calculator(model_key, {})
    except KeyError:
        _audit(db, patient_id, user, "Health assessment generation attempted for unknown model", success=False, model_key=model_key)
        raise HTTPException(status_code=404, detail="Assessment model not found") from None
    except PermissionError as exc:
        _audit(db, patient_id, user, "Health assessment generation blocked", success=False, model_key=model_key)
        raise HTTPException(status_code=409, detail=str(exc)) from None
    raise HTTPException(status_code=422, detail="Assessment inputs are not yet available")


def _generate_trained_assessment(model_key: str, payload: TrainedAssessmentRequest, db: Session, user: User, patient_id: UUID) -> HealthAssessment:
    spec = SPECS[model_key]
    try:
        inputs = validate_inputs(model_key, payload.inputs)
        if not set(payload.defaulted_inputs).issubset(spec.features):
            raise ValueError("Defaulted field list does not match this assessment")
        if any(inputs[name] != spec.defaults[name] for name in payload.defaulted_inputs):
            raise ValueError("A field marked as defaulted must use the documented model default")
        result = predict_trained_model(model_key, inputs)
    except ModelUnavailable as exc:
        _audit(db, patient_id, user, "Trained model inference failed", success=False, model_key=model_key)
        raise HTTPException(status_code=503, detail="This model is temporarily unavailable; no result was saved") from exc
    except (TypeError, ValueError, KeyError) as exc:
        _audit(db, patient_id, user, "Trained assessment rejected invalid inputs", success=False, model_key=model_key)
        raise HTTPException(status_code=422, detail="One or more assessment inputs are invalid") from exc

    assessed_at = datetime.now(timezone.utc)
    version = spec.version
    defaulted = set(payload.defaulted_inputs)
    source_by_feature = {
        name: ({"source_type": "documented_model_default", "verification_status": "patient_selected_default"} if name in defaulted else
               {"source_type": "patient_confirmed", "verification_status": "patient_confirmed_at_run_time", "observed_at": assessed_at.isoformat()})
        for name in spec.features
    }
    source_references = [{
        "record_type": "local_model_artifacts", "model_file": spec.model_file,
        "scaler_file": spec.scaler_file, "version": version,
        "dataset": spec.dataset, "evaluation_metrics": spec.metrics,
    }]
    patient = db.scalar(select(Patient).where(Patient.id == patient_id))
    if patient and patient.date_of_birth:
        today = assessed_at.date()
        age = today.year - patient.date_of_birth.year - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
        if "AGE" in inputs and "AGE" not in defaulted and inputs["AGE"] == age:
            source_by_feature["AGE"] = {"source_type": "patient_profile", "field": "date_of_birth", "value_date": patient.date_of_birth.isoformat()}
        if "Age" in inputs and "Age" not in defaulted and 18 <= age <= 120:
            age_band = age <= 24 and 1 or age <= 29 and 2 or age <= 34 and 3 or age <= 39 and 4 or age <= 44 and 5 or age <= 49 and 6 or age <= 54 and 7 or age <= 59 and 8 or age <= 64 and 9 or age <= 69 and 10 or age <= 74 and 11 or age <= 79 and 12 or 13
            if inputs["Age"] == age_band:
                source_by_feature["Age"] = {"source_type": "patient_profile", "field": "date_of_birth", "value_date": patient.date_of_birth.isoformat(), "encoding": age_band}
        sex = (patient.gender or "").lower()
        for feature in ("Sex", "GENDER"):
            if feature in inputs and feature not in defaulted and sex in {"female", "male"} and inputs[feature] == (0 if sex == "female" else 1):
                source_by_feature[feature] = {"source_type": "patient_profile", "field": "gender", "observed_at": assessed_at.isoformat()}
    if "BMI" in inputs and "BMI" not in defaulted:
        bmi_records = db.scalars(select(HealthMeasurement).where(
            HealthMeasurement.patient_id == patient_id,
            HealthMeasurement.measurement_type == "bmi",
            HealthMeasurement.verification_status == "verified",
        ).order_by(HealthMeasurement.observed_at.desc())).all()
        bmi_record = next((row for row in bmi_records if math.isclose(float(row.value), float(inputs["BMI"]), abs_tol=0.01)), None)
        if bmi_record:
            source_by_feature["BMI"] = {"source_type": "verified_health_measurement", "record_id": str(bmi_record.id), "observed_at": bmi_record.observed_at.isoformat(), "unit": bmi_record.unit}
            source_references.append({"record_type": "health_measurement", "record_id": str(bmi_record.id), "measurement_type": "bmi", "observed_at": bmi_record.observed_at.isoformat()})
    if "Diabetes_binary" in inputs and "Diabetes_binary" not in defaulted:
        diabetes_records = db.scalars(select(PatientRiskFactor).where(
            PatientRiskFactor.patient_id == patient_id,
            PatientRiskFactor.factor_key == "diabetes_status",
            PatientRiskFactor.verification_status == "verified",
        ).order_by(PatientRiskFactor.observed_at.desc())).all()
        diabetes_record = next((row for row in diabetes_records if int(row.value) == int(inputs["Diabetes_binary"])), None)
        if diabetes_record:
            source_by_feature["Diabetes_binary"] = {"source_type": "verified_patient_risk_factor", "record_id": str(diabetes_record.id), "observed_at": diabetes_record.observed_at.isoformat()}
            source_references.append({"record_type": "patient_risk_factor", "record_id": str(diabetes_record.id), "factor_key": "diabetes_status", "observed_at": diabetes_record.observed_at.isoformat()})
    summary = (
        f"Experimental model output: {result['category'].replace('_', ' ')}; sigmoid output {result['sigmoid_output']:.3f} "
        "at the supplied 0.5 threshold. This is not a diagnosis or a calibrated clinical risk estimate. "
        "A low output does not rule out disease. Review health concerns with a qualified clinician."
    )
    assessment = HealthAssessment(
        patient_id=patient_id, model_key=model_key, model_version=version,
        status="complete", result=result,
        contributing_factors=[{"label": field["label"], "value": inputs[field["name"]]} for field in spec.field_specs],
        missing_information=[],
        source_references=source_references,
        input_snapshot={
            "inputs": inputs, "feature_order": list(spec.features),
            "patient_confirmed": True, "input_verification_status": "patient_confirmed_at_run_time",
            "input_source": "patient_reviewed_or_explicitly_defaulted",
            "source_by_feature": source_by_feature,
            "defaulted_inputs": sorted(payload.defaulted_inputs),
            "model_version": version,
        },
        summary=summary, assessed_at=assessed_at,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    _audit(db, patient_id, user, "Experimental trained-model assessment generated", success=True, model_key=model_key)
    return assessment


def _generate_who_cvd_assessment(db: Session, user: User, patient_id: UUID) -> HealthAssessment:
    assessed_at = datetime.now(timezone.utc)
    patient = db.scalar(select(Patient).where(Patient.id == patient_id))
    if patient is None:
        _audit(db, patient_id, user, "WHO cardiovascular assessment blocked: patient profile missing", success=False, model_key="who_2019_south_asia_cvd")
        raise HTTPException(status_code=404, detail="Patient profile not found")

    missing: list[str] = []
    snapshot: dict = {"chart": WHO_CHART_VERSION, "source": WHO_CHART_SOURCE}
    references: list[dict] = [{"record_type": "who_chart", "url": WHO_CHART_SOURCE, "version": WHO_CHART_VERSION}]
    inputs: dict = {}

    if patient.date_of_birth is None:
        missing.append("date_of_birth")
    else:
        today = assessed_at.date()
        age = today.year - patient.date_of_birth.year - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
        inputs["age"] = age
        snapshot["date_of_birth"] = patient.date_of_birth.isoformat()
        snapshot["age_at_assessment"] = age
        references.append({"record_type": "patient_profile", "record_id": str(patient.id), "field": "date_of_birth"})
        model = TOOLS["who_2019_south_asia_cvd"]
        if (model.minimum_age is not None and age < model.minimum_age) or (model.maximum_age is not None and age > model.maximum_age):
            missing.append(f"not eligible: WHO 2019 model age range is {model.minimum_age}–{model.maximum_age}")
        elif (model.chart_minimum_age is not None and age < model.chart_minimum_age) or (model.chart_maximum_age is not None and age > model.chart_maximum_age):
            missing.append(f"chart unavailable: the published South Asia chart has no exact age band for ages outside {model.chart_minimum_age}–{model.chart_maximum_age}; no category was generated")

    sex = (patient.gender or "").strip().lower()
    if sex not in ("male", "female"):
        missing.append("sex (WHO chart supports male or female)")
    else:
        inputs["sex"] = sex
        references.append({"record_type": "patient_profile", "record_id": str(patient.id), "field": "gender"})

    verified_factors = db.scalars(select(PatientRiskFactor).where(
        PatientRiskFactor.patient_id == patient_id,
        PatientRiskFactor.verification_status == "verified",
    ).order_by(PatientRiskFactor.observed_at.desc())).all()
    latest_factors: dict[str, PatientRiskFactor] = {}
    for factor in verified_factors:
        latest_factors.setdefault(factor.factor_key, factor)
    factor_input_names = {"current_smoking": "smoking", "diabetes_status": "diabetes"}
    for key, input_name in factor_input_names.items():
        factor = latest_factors.get(key)
        if factor is None:
            missing.append(key)
            continue
        inputs[input_name] = bool(factor.value)
        snapshot[key] = {"value": bool(factor.value), "observed_at": factor.observed_at.isoformat(), "source_type": factor.source_type}
        references.append({"record_type": "patient_risk_factor", "record_id": str(factor.id), "factor": key, "observed_at": factor.observed_at.isoformat(), "source_type": factor.source_type, "source_document_id": str(factor.source_document_id) if factor.source_document_id else None})

    verified_measurements = db.scalars(select(HealthMeasurement).where(
        HealthMeasurement.patient_id == patient_id,
        HealthMeasurement.verification_status == "verified",
        HealthMeasurement.measurement_type.in_(("systolic_blood_pressure", "total_cholesterol")),
    ).order_by(HealthMeasurement.observed_at.desc())).all()
    latest_measurements: dict[str, HealthMeasurement] = {}
    for measurement in verified_measurements:
        latest_measurements.setdefault(measurement.measurement_type, measurement)
    for key, input_name in (("systolic_blood_pressure", "systolic_blood_pressure"), ("total_cholesterol", "total_cholesterol_mmol_l")):
        measurement = latest_measurements.get(key)
        if measurement is None:
            missing.append(key)
            continue
        value = float(measurement.value)
        if key == "systolic_blood_pressure":
            if measurement.unit != "mmHg" or value <= 0:
                missing.append(f"{key} (invalid unit or value)")
                continue
        else:
            if measurement.unit == "mg/dL":
                value /= 38.67
            elif measurement.unit != "mmol/L":
                missing.append(f"{key} (unsupported unit)")
                continue
            if value <= 0:
                missing.append(f"{key} (must be a positive measurement)")
                continue
        inputs[input_name] = value
        snapshot[key] = {"value": str(measurement.value), "unit": measurement.unit, "observed_at": measurement.observed_at.isoformat(), "source_type": measurement.source_type}
        references.append({"record_type": "health_measurement", "record_id": str(measurement.id), "measurement_type": key, "observed_at": measurement.observed_at.isoformat(), "source_type": measurement.source_type, "source_document_id": str(measurement.source_document_id) if measurement.source_document_id else None})

    established_cvd_terms = ("cardiovascular disease", "coronary artery disease", "coronary heart disease", "myocardial infarction", "heart attack", "stroke", "peripheral artery disease", "heart failure", "cardiomyopathy", "angina", "aortic aneurysm")
    conditions = db.scalars(select(Condition).where(Condition.patient_id == patient_id, Condition.status == "active")).all()
    established_cvd = [condition.name for condition in conditions if any(term in condition.name.lower() for term in established_cvd_terms)]
    if established_cvd:
        missing.append("not eligible: existing cardiovascular disease recorded")

    result = None
    factors: list[dict] = []
    status = "insufficient_data" if missing else "complete"
    if any(item.startswith("not eligible:") for item in missing) or established_cvd:
        status = "not_eligible"
    elif any(item.startswith("chart unavailable:") for item in missing):
        status = "unavailable"
    summary = "No risk category was generated. Complete or verify the listed information before running this assessment."
    if status == "not_eligible":
        summary = "No risk category was generated because this patient is outside the WHO model eligibility rules. This is unavailable, not a low-risk result."
    elif status == "unavailable":
        summary = "No category was generated because the published South Asia chart has no exact row for this age. This is unavailable, not a low-risk result."
    if not missing:
        try:
            cell = lookup_who_south_asia(
                age=inputs["age"], sex=inputs["sex"], smoking=inputs["smoking"],
                diabetes=inputs["diabetes"], sbp_mmhg=inputs["systolic_blood_pressure"],
                cholesterol_mmol_l=inputs["total_cholesterol_mmol_l"],
            )
        except (TypeError, ValueError):
            status = "insufficient_data"
            missing.append("one or more values do not fit a WHO chart input")
        else:
            result = {
                "risk_category": cell["risk_category"],
                "time_horizon": "10 years",
                "method": "WHO 2019 South Asia laboratory-based chart lookup",
            }
            snapshot["chart_cell"] = {
                "age_band": cell["age_band"],
                "systolic_blood_pressure_band": cell["systolic_blood_pressure_band"],
                "cholesterol_band": cell["cholesterol_band"],
                "official_chart_value_percent": cell["chart_value_percent"],
            }
            factors = [
                {"label": "Chart input: age band", "value": cell["age_band"]},
                {"label": "Chart input: sex", "value": cell["sex"]},
                {"label": "Chart input: current smoking", "value": "yes" if cell["current_smoker"] else "no"},
                {"label": "Chart input: diabetes", "value": "yes" if cell["diabetes"] else "no"},
                {"label": "Chart input: systolic pressure band", "value": cell["systolic_blood_pressure_band"] + " mmHg"},
                {"label": "Chart input: total cholesterol band", "value": cell["cholesterol_band"] + " mmol/L"},
            ]
            status = "complete"
            summary = f"Experimental lookup from the WHO 2019 South Asia chart: 10-year cardiovascular risk category {cell['risk_category']}. This is not a diagnosis and has not been validated for CareKey users or specifically for Indian patients."

    assessment = HealthAssessment(
        patient_id=patient_id, model_key="who_2019_south_asia_cvd", model_version=WHO_CHART_VERSION,
        status=status, result=result, contributing_factors=factors,
        missing_information=missing, source_references=references,
        input_snapshot=snapshot, summary=summary, assessed_at=assessed_at,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    _audit(db, patient_id, user, "WHO cardiovascular risk chart assessment generated", success=result is not None, model_key="who_2019_south_asia_cvd")
    return assessment


def _generate_idrs_assessment(db: Session, user: User, patient_id: UUID) -> HealthAssessment:
    assessed_at = datetime.now(timezone.utc)
    patient = db.scalar(select(Patient).where(Patient.id == patient_id))
    if patient is None:
        _audit(db, patient_id, user, "IDRS screening blocked: patient profile missing", success=False, model_key="idrs_type2_diabetes")
        raise HTTPException(status_code=404, detail="Patient profile not found")

    missing: list[str] = []
    inputs: dict = {}
    snapshot: dict = {"source": "https://repository.ias.ac.in/80170/1/80170.pdf"}
    references: list[dict] = [{"record_type": "published_method", "url": "https://repository.ias.ac.in/80170/1/80170.pdf", "version": "mdrf-idrs-original-2005"}]
    today = assessed_at.date()
    if patient.date_of_birth is None:
        missing.append("date_of_birth")
    else:
        age = today.year - patient.date_of_birth.year - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
        inputs["age"] = age
        snapshot["date_of_birth"] = patient.date_of_birth.isoformat()
        snapshot["age_at_assessment"] = age
        references.append({"record_type": "patient_profile", "record_id": str(patient.id), "field": "date_of_birth"})
        idrs_tool = TOOLS["idrs_type2_diabetes"]
        if (idrs_tool.minimum_age is not None and age < idrs_tool.minimum_age) or (idrs_tool.maximum_age is not None and age > idrs_tool.maximum_age):
            age_range = f"{idrs_tool.minimum_age}+" if idrs_tool.maximum_age is None else f"{idrs_tool.minimum_age}–{idrs_tool.maximum_age}"
            missing.append(f"not eligible: original IDRS derivation population age range is {age_range}")

    sex = (patient.gender or "").strip().lower()
    if sex not in ("male", "female"):
        missing.append("sex (original IDRS uses sex-specific waist cut-offs)")
    else:
        inputs["sex"] = sex
        references.append({"record_type": "patient_profile", "record_id": str(patient.id), "field": "gender"})

    verified_measurements = db.scalars(select(HealthMeasurement).where(
        HealthMeasurement.patient_id == patient_id,
        HealthMeasurement.verification_status == "verified",
        HealthMeasurement.measurement_type == "waist_circumference",
    ).order_by(HealthMeasurement.observed_at.desc())).all()
    measurement = verified_measurements[0] if verified_measurements else None
    if measurement is None:
        missing.append("verified waist circumference")
    elif measurement.unit != "cm" or not 30 <= float(measurement.value) <= 250:
        missing.append("waist circumference (must be a valid measurement in cm)")
    else:
        inputs["waist_circumference_cm"] = float(measurement.value)
        snapshot["waist_circumference"] = {"value": str(measurement.value), "unit": measurement.unit, "observed_at": measurement.observed_at.isoformat(), "source_type": measurement.source_type}
        references.append({"record_type": "health_measurement", "record_id": str(measurement.id), "measurement_type": "waist_circumference", "observed_at": measurement.observed_at.isoformat(), "source_type": measurement.source_type, "source_document_id": str(measurement.source_document_id) if measurement.source_document_id else None})

    verified_inputs = db.scalars(select(PatientAssessmentInput).where(
        PatientAssessmentInput.patient_id == patient_id,
        PatientAssessmentInput.verification_status == "verified",
        PatientAssessmentInput.input_key.in_(("idrs_physical_activity", "idrs_parental_diabetes")),
    ).order_by(PatientAssessmentInput.observed_at.desc())).all()
    latest: dict[str, PatientAssessmentInput] = {}
    for row in verified_inputs:
        latest.setdefault(row.input_key, row)
    for key, input_name in (("idrs_physical_activity", "physical_activity"), ("idrs_parental_diabetes", "parental_diabetes")):
        row = latest.get(key)
        if row is None:
            missing.append(key)
            continue
        inputs[input_name] = row.value
        snapshot[key] = {"value": row.value, "observed_at": row.observed_at.isoformat(), "source_type": row.source_type}
        references.append({"record_type": "patient_assessment_input", "record_id": str(row.id), "input_key": key, "observed_at": row.observed_at.isoformat(), "source_type": row.source_type, "source_document_id": str(row.source_document_id) if row.source_document_id else None})

    conditions = db.scalars(select(Condition).where(Condition.patient_id == patient_id, Condition.status == "active")).all()
    diagnosed_diabetes = [
        condition.name for condition in conditions
        if "diabetes" in condition.name.lower()
        and "prediabetes" not in condition.name.lower()
        and "pre-diabetes" not in condition.name.lower()
    ]
    diabetes_rows = db.scalars(select(PatientRiskFactor).where(
        PatientRiskFactor.patient_id == patient_id,
        PatientRiskFactor.factor_key == "diabetes_status",
        PatientRiskFactor.verification_status == "verified",
    ).order_by(PatientRiskFactor.observed_at.desc())).all()
    if diagnosed_diabetes or (diabetes_rows and diabetes_rows[0].value):
        missing.append("not eligible: this tool screens for previously undiagnosed diabetes")

    result = None
    factors: list[dict] = []
    status = "insufficient_data" if missing else "complete"
    summary = "No IDRS score was generated. Complete and confirm the listed information first."
    if any(item.startswith("not eligible:") for item in missing):
        status = "not_eligible"
        summary = "No IDRS screening score was generated because this tool screens for previously undiagnosed diabetes and the patient is not eligible. This is not a low-risk result."
    elif not missing:
        try:
            output = run_calculator("idrs_type2_diabetes", inputs)
        except (KeyError, TypeError, ValueError) as exc:
            status = "insufficient_data"
            missing.append(f"IDRS inputs invalid: {str(exc)}")
        else:
            result = output.result
            factors = output.contributing_factors
            summary = output.summary
            snapshot.update(output.input_snapshot)
            status = output.status

    assessment = HealthAssessment(
        patient_id=patient_id, model_key="idrs_type2_diabetes", model_version="mdrf-idrs-original-2005",
        status=status, result=result, contributing_factors=factors,
        missing_information=missing, source_references=references,
        input_snapshot=snapshot, summary=summary, assessed_at=assessed_at,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    _audit(db, patient_id, user, "IDRS diabetes screening generated", success=result is not None, model_key="idrs_type2_diabetes")
    return assessment
