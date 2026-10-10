from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.user import User


class _Db:
    def __init__(self, patient):
        self.patient = patient
        self.profile = None
        self.logs = []

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return self.patient if entity is Patient else self.profile

    def add(self, value):
        if isinstance(value, Profile):
            self.profile = value
        if isinstance(value, AccessLog):
            self.logs.append(value)

    def flush(self):
        pass

    def commit(self):
        pass


def _user(role):
    return User(
        id=uuid4(), firebase_uid=f"uid-{role.value}", email=f"{role.value}@example.com",
        is_active=True, role=role, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def _call(db, user, medical_id, reason="Emergency assessment"):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            return client.post(f"/emergency/{medical_id}", json={"reason": reason})
    finally:
        app.dependency_overrides.clear()


def test_doctor_can_access_restricted_emergency_summary_with_audit():
    doctor = _user(AppRole.DOCTOR)
    patient = Patient(
        id=uuid4(), medical_id="CK-12345678", blood_group="O+", rh_factor="positive",
    )
    patient.profile = Profile(id=patient.id, firebase_uid="patient-firebase", full_name="Test Patient")
    patient.allergies = []
    patient.conditions = []
    patient.medications = []
    db = _Db(patient)
    response = _call(db, doctor, patient.medical_id)
    assert response.status_code == 200
    assert response.json()["blood_group"] == "O+"
    assert db.logs[0].success is True
    assert db.logs[0].access_type == "emergency"
    assert db.logs[0].reason == "Emergency assessment"


def test_non_doctor_emergency_access_is_denied_and_audited():
    patient_user = _user(AppRole.PATIENT)
    db = _Db(None)
    response = _call(db, patient_user, "CK-12345678")
    assert response.status_code == 403
    assert len(db.logs) == 1
    assert db.logs[0].success is False


def test_emergency_access_requires_a_reason():
    doctor = _user(AppRole.DOCTOR)
    response = _call(_Db(None), doctor, "CK-12345678", reason=" ")
    assert response.status_code == 422
