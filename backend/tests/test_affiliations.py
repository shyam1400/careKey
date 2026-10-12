from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.affiliation import HospitalDoctorAffiliation
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.hospital import Hospital
from app.models.profile import Profile
from app.models.user import User


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class _Db:
    def __init__(self, hospital, doctor, profile=None):
        self.hospital, self.doctor, self.profile = hospital, doctor, profile
        self.affiliations = []
        self.events = []

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is Hospital:
            return self.hospital
        if entity is HospitalDoctorAffiliation:
            return self.affiliations[0] if self.affiliations else None
        if entity is User:
            return self.doctor
        return None

    def scalars(self, _statement):
        # The active decision is excluded from this query; production code adds
        # the selected hospital only when the doctor approves it.
        return _Rows([])

    def get(self, model, _key):
        return {Hospital: self.hospital, User: self.doctor, Profile: self.profile}.get(model)

    def add(self, value):
        self.events.append(value)
        if isinstance(value, HospitalDoctorAffiliation) and value not in self.affiliations:
            self.affiliations.append(value)
        if isinstance(value, Profile):
            self.profile = value

    def commit(self):
        pass


def _user(role, *, hospital_id=None):
    return User(id=uuid4(), firebase_uid=f"uid-{uuid4()}", email=f"{role.value}@example.com",
                is_active=True, role=role, hospital_id=hospital_id,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))


def _request(db, user, method, path, **kwargs):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            return getattr(client, method)(path, **kwargs)
    finally:
        app.dependency_overrides.clear()


def _hospital():
    return Hospital(id=uuid4(), name="City Hospital", hospital_code="HOS-1234ABCD",
                    latitude=12.9, longitude=77.6)


def test_doctor_requests_hospital_and_hospital_approval_activates_link():
    hospital = _hospital()
    doctor = _user(AppRole.DOCTOR)
    db = _Db(hospital, doctor)

    request = _request(db, doctor, "post", "/affiliations/request", json={"code": hospital.hospital_code})
    assert request.status_code == 201
    assert request.json()["status"] == "pending_hospital"
    assert db.profile is None

    hospital_admin = _user(AppRole.HOSPITAL, hospital_id=hospital.id)
    decision = _request(db, hospital_admin, "post", f"/affiliations/{request.json()['id']}/decision", json={"approve": True})
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    assert db.profile.organization == hospital.name
    event = next(value for value in db.events if isinstance(value, AccessLog))
    assert event.hospital_id == hospital.id
    assert event.hospital_name == hospital.name


def test_hospital_invitation_stays_pending_until_doctor_approves():
    hospital = _hospital()
    doctor = _user(AppRole.DOCTOR)
    db = _Db(hospital, doctor, Profile(id=doctor.id, full_name="Dr Test"))
    hospital_admin = _user(AppRole.HOSPITAL, hospital_id=hospital.id)

    request = _request(db, hospital_admin, "post", "/affiliations/request", json={"code": "DOC-AB12CD34"})
    assert request.status_code == 201
    assert request.json()["status"] == "pending_doctor"
    assert db.profile.organization is None

    decision = _request(db, doctor, "post", f"/affiliations/{request.json()['id']}/decision", json={"approve": True})
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    assert db.profile.organization == hospital.name
