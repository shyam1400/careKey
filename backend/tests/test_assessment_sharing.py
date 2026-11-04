from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.consents import read_consented_assessments
from app.models.audit import AccessLog
from app.models.consent import Consent
from app.models.enums import AppRole, ConsentStatus
from app.models.health_data import HealthAssessment
from app.models.hospital import Hospital
from app.models.profile import Profile
from app.models.user import User


class _Result:
    def __init__(self, values): self.values = values
    def all(self): return self.values


class _Db:
    def __init__(self, consent):
        self.consent = consent
        self.hospital = Hospital(id=uuid4(), name="CareKey Hospital", hospital_code="HOS-1234ABCD", latitude=12.9, longitude=77.6)
        self.profile = Profile(id=consent.provider_id, full_name="Dr Test")
        self.assessment = HealthAssessment(
            id=uuid4(), patient_id=consent.patient_id, model_key="idrs_type2_diabetes", model_version="mdrf-idrs-original-2005",
            status="complete", result={"idrs_score": 60, "maximum_score": 100, "screening_category": "high", "assessment_type": "screening"}, contributing_factors=[], missing_information=[],
            source_references=[], input_snapshot={}, assessed_at=datetime.now(timezone.utc),
        )
        self.added = []

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return {Consent: self.consent, Hospital: self.hospital, Profile: self.profile}.get(entity)

    def scalars(self, _statement): return _Result([self.assessment])
    def add(self, row): self.added.append(row)
    def commit(self): pass


def _doctor(consent):
    return User(id=consent.provider_id, firebase_uid="doctor-uid", role=AppRole.DOCTOR, email="doctor@example.com", is_active=True)


def _consent(permissions):
    return Consent(
        id=uuid4(), patient_id=uuid4(), provider_id=uuid4(), permissions=permissions,
        purpose="Consultation", status=ConsentStatus.ACTIVE, expires_at=None,
    )


def test_doctor_can_read_assessments_only_with_active_assessment_consent():
    consent = _consent(["health_assessments"])
    db = _Db(consent)
    rows = read_consented_assessments(consent.id, db, _doctor(consent))
    assert rows[0]["model_key"] == "idrs_type2_diabetes"
    assert rows[0]["result"]["screening_category"] == "high"
    assert any(isinstance(row, AccessLog) and row.access_type == "health_assessment" and row.success for row in db.added)


def test_doctor_assessment_read_is_denied_and_audited_without_category_permission():
    consent = _consent(["lab_reports"])
    db = _Db(consent)
    with pytest.raises(HTTPException) as error:
        read_consented_assessments(consent.id, db, _doctor(consent))
    assert error.value.status_code == 403
    assert any(isinstance(row, AccessLog) and row.access_type == "health_assessment" and not row.success for row in db.added)
