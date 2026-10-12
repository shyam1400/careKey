from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.profile import Profile
from app.models.user import User


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class _Db:
    def __init__(self, users=(), profiles=()):
        self.users = {item.id: item for item in users}
        self.profiles = {item.id: item for item in profiles}
        self.added = []

    def scalar(self, _statement):
        # The require_roles dependency asks the DB to re-read the acting user.
        return next(iter(self.users.values()), None)

    def execute(self, _statement):
        return _Rows([])

    def get(self, model, key):
        return (self.users if model is User else self.profiles).get(key)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, User):
            self.users[value.id] = value
        if isinstance(value, Profile):
            self.profiles[value.id] = value

    def commit(self):
        pass

    def refresh(self, _value):
        pass


def _user(role):
    return User(
        id=uuid4(), firebase_uid=f"firebase-{uuid4()}", email="demo@example.com",
        is_active=True, role=role, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def _request(db, actor, method, path, **kwargs):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        with TestClient(app) as client:
            return getattr(client, method)(path, **kwargs)
    finally:
        app.dependency_overrides.clear()


def test_non_admin_cannot_provision_doctor():
    actor = _user(AppRole.PATIENT)
    target = _user(AppRole.PATIENT)
    response = _request(_Db([actor, target]), actor, "patch", f"/admin/users/{target.id}", json={"role": "doctor"})
    assert response.status_code == 403


def test_admin_can_provision_doctor_and_profile():
    admin = _user(AppRole.ADMIN)
    target = _user(AppRole.PATIENT)
    db = _Db([admin, target])
    response = _request(
        db, admin, "patch", f"/admin/users/{target.id}",
        json={"role": "doctor", "full_name": "Demo Doctor", "organization": "Sample Clinic", "specialty": "General Practice"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "doctor"
    assert response.json()["full_name"] == "Demo Doctor"
    assert response.json()["specialty"] == "General Practice"
    assert response.json()["doctor_code"].startswith("DOC-")
    assert len(response.json()["doctor_code"]) == 12
    assert db.profiles[target.id].firebase_uid == target.firebase_uid
    audit_events = [item for item in db.added if isinstance(item, AccessLog)]
    assert len(audit_events) == 1
    assert audit_events[0].access_type == "administration"
    assert "role from patient to doctor" in audit_events[0].action


def test_admin_cannot_change_another_admin_role():
    admin = _user(AppRole.ADMIN)
    other_admin = _user(AppRole.ADMIN)
    response = _request(
        _Db([admin, other_admin]), admin, "patch", f"/admin/users/{other_admin.id}", json={"role": "doctor"}
    )
    assert response.status_code == 403


def test_admin_can_deactivate_doctor_and_audit_change():
    admin = _user(AppRole.ADMIN)
    doctor = _user(AppRole.DOCTOR)
    db = _Db([admin, doctor])
    response = _request(
        db, admin, "patch", f"/admin/users/{doctor.id}/status", json={"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert doctor.is_active is False
    event = next(item for item in db.added if isinstance(item, AccessLog))
    assert event.verification_result == "admin_doctor_status_change"
    assert "deactivated doctor" in event.action


def test_admin_cannot_deactivate_patient_as_a_doctor():
    admin = _user(AppRole.ADMIN)
    patient = _user(AppRole.PATIENT)
    response = _request(
        _Db([admin, patient]), admin, "patch", f"/admin/users/{patient.id}/status", json={"is_active": False}
    )
    assert response.status_code == 403
