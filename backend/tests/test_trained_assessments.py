from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.assessments import generate_assessment, list_assessment_models
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.patient import Patient
from app.models.user import User
from app.schemas.assessment import TrainedAssessmentRequest
from app.services.trained_models import SPECS


class _Rows:
    def all(self):
        return []


class _Db:
    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.patient = Patient(id=patient_id, date_of_birth=None, gender=None)
        self.scalar_calls = 0
        self.added = []

    def scalar(self, statement):
        self.scalar_calls += 1
        entity = statement.column_descriptions[0]["entity"]
        if entity is Patient:
            return self.patient_id if self.scalar_calls == 1 else self.patient
        return None

    def scalars(self, _statement):
        return _Rows()

    def add(self, row):
        self.added.append(row)

    def commit(self):
        pass

    def refresh(self, _row):
        pass


@pytest.mark.parametrize("model_key", list(SPECS))
def test_trained_assessment_saves_immutable_output_and_audit(model_key):
    patient_id = uuid4()
    user = User(id=patient_id, firebase_uid="uid", role=AppRole.PATIENT, is_active=True)
    spec = SPECS[model_key]
    payload = TrainedAssessmentRequest(inputs=spec.defaults, patient_confirmed=True)
    db = _Db(patient_id)

    result = generate_assessment(model_key, db, user, payload)

    assert result.status == "complete"
    assert result.model_key == model_key
    assert result.model_version == spec.version
    assert result.result["threshold"] == 0.5
    assert result.input_snapshot["feature_order"] == list(spec.features)
    assert result.input_snapshot["input_verification_status"] == "patient_confirmed_at_run_time"
    assert any(isinstance(row, AccessLog) and row.success for row in db.added)


def test_trained_assessment_requires_patient_confirmation():
    patient_id = uuid4()
    user = User(id=patient_id, firebase_uid="uid", role=AppRole.PATIENT, is_active=True)
    payload = TrainedAssessmentRequest(inputs=SPECS["diabetes_brfss"].defaults, patient_confirmed=False)
    with pytest.raises(HTTPException) as error:
        generate_assessment("diabetes_brfss", _Db(patient_id), user, payload)
    assert error.value.status_code == 422


def test_model_catalog_exposes_only_the_three_successfully_inferred_local_models():
    user = User(id=uuid4(), firebase_uid="uid", role=AppRole.PATIENT, is_active=True)
    models = list_assessment_models(user)
    assert {item.key for item in models} == set(SPECS)
    assert all(item.availability == "enabled" and len(item.input_schema) == len(item.required_inputs) for item in models)
