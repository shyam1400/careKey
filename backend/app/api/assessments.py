from datetime import datetime, timezone
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
from app.schemas.assessment import AssessmentToolResponse, HealthAssessmentResponse
from app.services.assessment_engine import TOOLS, run_calculator
from app.services.who_cvd_2019 import WHO_CHART_SOURCE, WHO_CHART_VERSION, lookup_who_south_asia

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
    return [AssessmentToolResponse(
        key=tool.key, name=tool.name, category=tool.category, version=tool.version,
        intended_use=tool.intended_use, validated_population=tool.validated_population,
        required_inputs=list(tool.required_inputs), limitations=list(tool.limitations),
        source_url=tool.source_url, license_status=tool.license_status, availability=tool.availability,
        minimum_age=tool.minimum_age, maximum_age=tool.maximum_age,
        chart_minimum_age=tool.chart_minimum_age, chart_maximum_age=tool.chart_maximum_age,
    ) for tool in TOOLS.values()]


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
def generate_assessment(model_key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
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
