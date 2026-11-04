from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.api.assessments import generate_assessment
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.health_data import HealthAssessment, HealthMeasurement, PatientAssessmentInput, PatientRiskFactor
from app.models.patient import Patient
from app.models.records import Condition
from app.models.user import User


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Db:
    def __init__(self, patient, measurements=(), risk_factors=(), conditions=(), assessment_inputs=()):
        self.patient = patient
        self.measurements = list(measurements)
        self.risk_factors = list(risk_factors)
        self.conditions = list(conditions)
        self.assessment_inputs = list(assessment_inputs)
        self.added = []
        self.scalar_calls = 0

    def scalar(self, statement):
        self.scalar_calls += 1
        if self.scalar_calls == 1:  # patient id lookup
            return self.patient.id
        if self.scalar_calls == 2:  # patient profile
            return self.patient
        return None  # audit profile name lookup

    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is HealthMeasurement:
            return _Rows([row for row in self.measurements if row.verification_status == "verified"])
        if entity is PatientRiskFactor:
            return _Rows([row for row in self.risk_factors if row.verification_status == "verified"])
        if entity is PatientAssessmentInput:
            return _Rows([row for row in self.assessment_inputs if row.verification_status == "verified"])
        if entity is Condition:
            return _Rows(self.conditions)
        raise AssertionError(f"Unexpected query entity: {entity}")

    def add(self, row):
        self.added.append(row)

    def commit(self):
        pass

    def refresh(self, row):
        pass


def _patient(gender="male", age=55):
    today = datetime.now(timezone.utc).date()
    return Patient(
        id=uuid4(), medical_id="CK12345678",
        date_of_birth=date(today.year - age, today.month, today.day),
        gender=gender,
    )


def _user(patient):
    return User(id=patient.id, firebase_uid="test", role=AppRole.PATIENT, is_active=True)


def test_assessment_uses_only_verified_inputs_and_saves_chart_category_and_provenance():
    patient = _patient()
    now = datetime.now(timezone.utc)
    measurements = [
        HealthMeasurement(
            id=uuid4(), patient_id=patient.id, measurement_type="systolic_blood_pressure",
            value=Decimal("150"), unit="mmHg", observed_at=now, source_type="home_device",
            verification_status="verified",
        ),
        HealthMeasurement(
            id=uuid4(), patient_id=patient.id, measurement_type="total_cholesterol",
            value=Decimal("212.685"), unit="mg/dL", observed_at=now, source_type="lab_report",
            verification_status="verified",
        ),
    ]
    risk_factors = [
        PatientRiskFactor(
            id=uuid4(), patient_id=patient.id, factor_key="current_smoking", value=True,
            observed_at=now, source_type="patient_reported", verification_status="verified",
        ),
        PatientRiskFactor(
            id=uuid4(), patient_id=patient.id, factor_key="diabetes_status", value=False,
            observed_at=now, source_type="patient_reported", verification_status="verified",
        ),
    ]
    db = _Db(patient, measurements, risk_factors)

    assessment = generate_assessment("who_2019_south_asia_cvd", db, _user(patient))

    assert assessment.status == "complete"
    assert assessment.result == {
        "risk_category": "10% to <20%",
        "time_horizon": "10 years",
        "method": "WHO 2019 South Asia laboratory-based chart lookup",
    }
    assert assessment.model_version == "2019-south-asia-lab-chart"
    assert len(assessment.contributing_factors) == 6
    assert assessment.input_snapshot["chart_cell"]["official_chart_value_percent"] == 13
    measurement_refs = {ref["record_id"] for ref in assessment.source_references if ref["record_type"] == "health_measurement"}
    assert measurement_refs == {str(row.id) for row in measurements}
    assert any(isinstance(row, HealthAssessment) and row.result == assessment.result for row in db.added)
    logs = [row for row in db.added if isinstance(row, AccessLog)]
    assert logs and logs[-1].access_type == "health_assessment" and logs[-1].success


def test_missing_or_unverified_inputs_are_saved_without_a_prediction():
    patient = _patient()
    now = datetime.now(timezone.utc)
    unverified = HealthMeasurement(
        id=uuid4(), patient_id=patient.id, measurement_type="systolic_blood_pressure",
        value=Decimal("130"), unit="mmHg", observed_at=now, source_type="patient_reported",
        verification_status="unverified",
    )
    db = _Db(patient, measurements=[unverified])

    assessment = generate_assessment("who_2019_south_asia_cvd", db, _user(patient))

    assert assessment.status == "insufficient_data"
    assert assessment.result is None
    assert "current_smoking" in assessment.missing_information
    assert "diabetes_status" in assessment.missing_information
    assert "systolic_blood_pressure" in assessment.missing_information
    logs = [row for row in db.added if isinstance(row, AccessLog)]
    assert logs and not logs[-1].success


def test_idrs_assessment_uses_verified_inputs_and_saves_score_and_sources():
    patient = _patient(age=60)
    now = datetime.now(timezone.utc)
    waist = HealthMeasurement(
        id=uuid4(), patient_id=patient.id, measurement_type="waist_circumference",
        value=Decimal("101"), unit="cm", observed_at=now, source_type="clinician_entered",
        verification_status="verified",
    )
    assessment_inputs = [
        PatientAssessmentInput(
            id=uuid4(), patient_id=patient.id, input_key="idrs_physical_activity",
            value="either", observed_at=now, source_type="patient_reported", verification_status="verified",
        ),
        PatientAssessmentInput(
            id=uuid4(), patient_id=patient.id, input_key="idrs_parental_diabetes",
            value="both_parents", observed_at=now, source_type="patient_reported", verification_status="verified",
        ),
    ]
    db = _Db(patient, measurements=[waist], assessment_inputs=assessment_inputs)
    assessment = generate_assessment("idrs_type2_diabetes", db, _user(patient))

    assert assessment.status == "complete", assessment.missing_information
    assert assessment.model_version == "mdrf-idrs-original-2005"
    assert assessment.result == {
        "idrs_score": 90, "maximum_score": 100,
        "screening_category": "high", "assessment_type": "screening",
    }
    assert len(assessment.contributing_factors) == 4
    assert assessment.input_snapshot["score"] == 90
    assert len([r for r in assessment.source_references if r["record_type"] == "health_measurement"]) == 1
    assert len([r for r in assessment.source_references if r["record_type"] == "patient_assessment_input"]) == 2
    assert "not an estimate of future-onset probability" in assessment.summary
    logs = [row for row in db.added if isinstance(row, AccessLog)]
    assert logs and logs[-1].success and logs[-1].access_type == "health_assessment"


def test_idrs_unverified_or_missing_values_do_not_produce_score():
    patient = _patient(age=35)
    now = datetime.now(timezone.utc)
    unverified = HealthMeasurement(
        id=uuid4(), patient_id=patient.id, measurement_type="waist_circumference",
        value=Decimal("80"), unit="cm", observed_at=now, source_type="patient_reported",
        verification_status="unverified",
    )
    db = _Db(patient, measurements=[unverified])

    assessment = generate_assessment("idrs_type2_diabetes", db, _user(patient))

    assert assessment.status == "insufficient_data"
    assert assessment.result is None
    assert "verified waist circumference" in assessment.missing_information
    logs = [row for row in db.added if isinstance(row, AccessLog)]
    assert logs and not logs[-1].success


@pytest.mark.parametrize("age", [19, 81])
def test_idrs_outside_original_derivation_age_range_is_not_eligible(age):
    patient = _patient(age=age)
    assessment = generate_assessment("idrs_type2_diabetes", _Db(patient), _user(patient))
    assert assessment.status == "not_eligible"
    assert assessment.result is None
    assert any("original IDRS derivation population age range is 20–80" in item for item in assessment.missing_information)


@pytest.mark.parametrize("age", [39, 81])
def test_who_outside_model_age_range_is_not_eligible(age):
    patient = _patient(age=age)
    assessment = generate_assessment("who_2019_south_asia_cvd", _Db(patient), _user(patient))
    assert assessment.status == "not_eligible"
    assert assessment.result is None
    assert any("WHO 2019 model age range is 40–80" in item for item in assessment.missing_information)


@pytest.mark.parametrize("age", [75, 80])
def test_who_model_age_without_published_chart_row_is_unavailable(age):
    patient = _patient(age=age)
    assessment = generate_assessment("who_2019_south_asia_cvd", _Db(patient), _user(patient))
    assert assessment.status == "unavailable"
    assert assessment.result is None
    assert any("no exact age band" in item for item in assessment.missing_information)
