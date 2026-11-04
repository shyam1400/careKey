from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.health_data import _patient_id, _validate_source_document, create_assessment_input, create_measurement, verify_assessment_input
from app.models.enums import AppRole
from app.models.audit import AccessLog
from app.models.health_data import PatientAssessmentInput
from app.models.user import User
from app.models.records import Document
from app.schemas.health_data import FamilyHistoryCreate, HealthMeasurementCreate, PatientAssessmentInputCreate


class _Db:
    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.added = []

    def scalar(self, _statement):
        return self.patient_id

    def add(self, row):
        self.added.append(row)

    def commit(self):
        pass

    def refresh(self, _row):
        pass


def _user(role=AppRole.PATIENT):
    return User(id=uuid4(), firebase_uid="test", email="test@example.com", role=role, is_active=True)


def test_patient_health_measurement_is_stored_as_unverified_with_source_metadata():
    user = _user()
    db = _Db(user.id)
    payload = HealthMeasurementCreate(
        measurement_type="hba1c", value="6.1", unit="%",
        observed_at=datetime.now(timezone.utc), source_type="patient_reported",
    )

    result = create_measurement(payload, db, user)

    assert result.patient_id == user.id
    assert result.verification_status == "unverified"
    assert result.source_type == "patient_reported"
    assert result.value == payload.value


def test_doctor_cannot_manage_patient_health_data():
    doctor = _user(AppRole.DOCTOR)
    with pytest.raises(HTTPException) as error:
        _patient_id(doctor, _Db(doctor.id))
    assert error.value.status_code == 403


def test_measurement_rejects_incompatible_units_and_naive_time():
    with pytest.raises(ValidationError):
        HealthMeasurementCreate(measurement_type="hba1c", value=6.1, unit="mg/dL", observed_at=datetime.now(timezone.utc))
    with pytest.raises(ValidationError):
        HealthMeasurementCreate(measurement_type="weight", value=72, unit="kg", observed_at=datetime(2025, 1, 1))


def test_idrs_waist_measurement_requires_centimeters_and_sane_range():
    valid = HealthMeasurementCreate(
        measurement_type="waist_circumference", value=90, unit="cm",
        observed_at=datetime.now(timezone.utc),
    )
    assert valid.unit == "cm"
    for value, unit in ((29, "cm"), (251, "cm"), (90, "in")):
        with pytest.raises(ValidationError):
            HealthMeasurementCreate(
                measurement_type="waist_circumference", value=value, unit=unit,
                observed_at=datetime.now(timezone.utc),
            )


def test_idrs_categorical_inputs_enforce_matching_values_and_timezone():
    valid = PatientAssessmentInputCreate(
        input_key="idrs_parental_diabetes", value="one_parent",
        observed_at=datetime.now(timezone.utc),
    )
    assert valid.source_type == "patient_reported"
    with pytest.raises(ValidationError):
        PatientAssessmentInputCreate(
            input_key="idrs_parental_diabetes", value="neither",
            observed_at=datetime.now(timezone.utc),
        )
    with pytest.raises(ValidationError):
        PatientAssessmentInputCreate(
            input_key="idrs_physical_activity", value="both",
            observed_at=datetime(2026, 1, 1),
        )


def test_idrs_input_is_stored_unverified_then_patient_confirmation_is_audited():
    user = _user()
    now = datetime.now(timezone.utc)
    payload = PatientAssessmentInputCreate(
        input_key="idrs_physical_activity", value="either", observed_at=now,
    )
    created = create_assessment_input(payload, _Db(user.id), user)
    assert created.verification_status == "unverified"
    assert created.source_type == "patient_reported"
    assert created.observed_at == now

    class VerifyDb(_Db):
        def __init__(self, patient_id, row):
            super().__init__(patient_id)
            self.row = row
            self.calls = 0

        def scalar(self, _statement):
            self.calls += 1
            return self.patient_id if self.calls == 1 else self.row

    row = PatientAssessmentInput(
        id=uuid4(), patient_id=user.id, input_key="idrs_physical_activity",
        value="either", observed_at=now, verification_status="unverified",
    )
    db = VerifyDb(user.id, row)
    verified = verify_assessment_input(row.id, db, user)
    assert verified.verification_status == "verified"
    assert verified.verified_at is not None
    assert any(isinstance(item, AccessLog) and item.access_type == "health_data" for item in db.added)


def test_lab_measurement_requires_linked_report():
    with pytest.raises(ValidationError):
        HealthMeasurementCreate(
            measurement_type="fasting_glucose", value=98, unit="mg/dL",
            observed_at=datetime.now(timezone.utc), source_type="lab_report",
        )


def test_family_history_normalizes_relationship_and_requires_source_document_for_medical_record():
    entry = FamilyHistoryCreate(relationship_to_patient=" Mother ", condition="Type 2 diabetes", age_at_diagnosis=52)
    assert entry.relationship_to_patient == "mother"
    with pytest.raises(ValidationError):
        FamilyHistoryCreate(relationship_to_patient="cousin", condition="cancer")
    with pytest.raises(ValidationError):
        FamilyHistoryCreate(relationship_to_patient="father", condition="cancer", source_type="medical_record")


def test_lab_result_source_must_be_a_patient_owned_lab_report():
    patient_id = uuid4()
    report = Document(id=uuid4(), patient_id=patient_id, file_name="record.pdf", doc_type="prescription")

    class Db:
        def scalar(self, _statement): return report

    with pytest.raises(HTTPException) as error:
        _validate_source_document(Db(), patient_id, report.id, expected_doc_type="lab_report")
    assert error.value.status_code == 422
