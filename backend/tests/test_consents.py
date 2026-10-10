from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.consent import Consent
from app.models.audit import AccessLog
from app.models.enums import AppRole, ConsentStatus
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.user import User
from app.models.records import Allergy
from app.schemas.consent import ConsentCreate
from pydantic import ValidationError


class _Result:
    def __init__(self, value):
        self.value = value

    def all(self):
        return list(self.value)


class _Db:
    def __init__(self, patient, doctor, profile=None, consent=None):
        self.patient, self.doctor, self.profile, self.consent = patient, doctor, profile, consent
        self.added = []

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return {Patient: self.patient, User: self.doctor, Profile: self.profile, Consent: self.consent}.get(entity)

    def scalars(self, _statement):
        return _Result([self.consent] if self.consent else [])

    def add(self, value):
        self.added.append(value)
        if isinstance(value, Profile):
            self.profile = value
        if isinstance(value, Consent):
            self.consent = value

    def flush(self):
        pass

    def commit(self):
        if isinstance(self.consent, Consent):
            self.consent.id = self.consent.id or uuid4()
            self.consent.created_at = self.consent.created_at or datetime.now(timezone.utc)

    def refresh(self, _value):
        pass


def _user(role):
    return User(
        id=uuid4(), firebase_uid=f"uid-{role.value}", email=f"{role.value}@example.com",
        is_active=True, role=role, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def _request(db, user, method, path, **kwargs):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            return getattr(client, method)(path, **kwargs)
    finally:
        app.dependency_overrides.clear()


def test_patient_can_grant_explicit_consent_to_active_doctor(monkeypatch):
    monkeypatch.setattr("app.api.consents.verify_patient_assertion", lambda *_args: None)
    patient_user, doctor = _user(AppRole.PATIENT), _user(AppRole.DOCTOR)
    patient = Patient(id=patient_user.id, medical_id="CK-12345678")
    db = _Db(patient, doctor)
    response = _request(
        db, patient_user, "post", "/consents",
        json={"provider_id": str(doctor.id), "permissions": ["allergies"], "purpose": "Emergency care", "challenge_id": str(uuid4()), "credential": {"id": "demo"}},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "active"
    assert response.json()["permissions"] == ["allergies"]
    assert db.profile is not None and db.profile.id == doctor.id


def test_consent_rejects_unknown_record_categories():
    with pytest.raises(ValidationError):
        ConsentCreate(provider_id=uuid4(), permissions=["admin_data"])


def test_doctor_can_only_read_categories_on_own_active_consent():
    patient_user, doctor = _user(AppRole.PATIENT), _user(AppRole.DOCTOR)
    patient = Patient(id=patient_user.id, medical_id="CK-12345678", blood_group="O+")
    consent = Consent(
        id=uuid4(), patient_id=patient.id, provider_id=doctor.id,
        permissions=["allergies"], purpose="Consultation", status=ConsentStatus.ACTIVE,
        expires_at=None,
    )
    allergy = Allergy(patient_id=patient.id, allergen="Peanuts", reaction="Hives", severity="severe")

    class AccessDb(_Db):
        def scalars(self, statement):
            entity = statement.column_descriptions[0]["entity"]
            return _Result([allergy] if entity is Allergy else [])

    db = AccessDb(patient, doctor, Profile(id=doctor.id, full_name="Dr Doctor"), consent)
    response = _request(db, doctor, "get", f"/consents/{consent.id}/records")

    assert response.status_code == 200
    assert response.json()["allergies"] == [{"allergen": "Peanuts", "reaction": "Hives", "severity": "severe"}]
    assert "blood" not in response.json()
    assert any(isinstance(item, AccessLog) and item.access_type == "consent" for item in db.added)


def test_patient_can_revoke_own_active_consent(monkeypatch):
    monkeypatch.setattr("app.api.consents.verify_patient_assertion", lambda *_args: None)
    patient_user, doctor = _user(AppRole.PATIENT), _user(AppRole.DOCTOR)
    consent = Consent(
        id=uuid4(), patient_id=patient_user.id, provider_id=doctor.id,
        permissions=["allergies"], purpose="Care", status=ConsentStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
    )
    db = _Db(None, doctor, consent=consent)
    response = _request(db, patient_user, "post", f"/consents/{consent.id}/revoke", json={"challenge_id": str(uuid4()), "credential": {"id": "demo"}})
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"
    assert consent.revoked_at is not None


def test_doctor_cannot_grant_patient_consent():
    doctor = _user(AppRole.DOCTOR)
    response = _request(
        _Db(None, doctor), doctor, "post", "/consents",
        json={"provider_id": str(uuid4()), "permissions": ["allergies"]},
    )
    assert response.status_code == 403
