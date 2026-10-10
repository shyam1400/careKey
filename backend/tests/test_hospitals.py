from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.enums import AppRole
from app.models.hospital import Hospital
from app.models.user import User


class _Result:
    def __init__(self, items):
        self.items = items

    def all(self):
        return list(self.items)


class _Db:
    def __init__(self, hospitals=None):
        self.hospitals = hospitals or []

    def scalars(self, _statement):
        return _Result(self.hospitals)

    def add(self, value):
        self.hospitals.append(value)

    def commit(self):
        for hospital in self.hospitals:
            hospital.id = hospital.id or uuid4()

    def refresh(self, _value):
        pass


def _user(role):
    return User(
        id=uuid4(), firebase_uid="firebase-id", email="user@example.com", is_active=True,
        role=role, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def _request(db, user, method, path, **kwargs):
    app.dependency_overrides[get_db] = lambda: db
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            return getattr(client, method)(path, **kwargs)
    finally:
        app.dependency_overrides.clear()


def test_hospital_directory_can_be_filtered():
    hospital = Hospital(
        id=uuid4(), name="City Emergency", latitude=12.9, longitude=77.6,
        emergency=True, trauma=True, ambulance=True, open_24h=True,
    )
    response = _request(_Db([hospital]), None, "get", "/hospitals?trauma=true")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "City Emergency"


def test_only_admin_can_add_hospital():
    user = _user(AppRole.DOCTOR)
    response = _request(
        _Db(), user, "post", "/hospitals",
        json={"name": "New Clinic", "latitude": 12.9, "longitude": 77.6},
    )
    assert response.status_code == 403


def test_admin_can_add_hospital():
    admin = _user(AppRole.ADMIN)
    response = _request(
        _Db(), admin, "post", "/hospitals",
        json={
            "name": "City Emergency", "latitude": 12.9, "longitude": 77.6,
            "trauma": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "City Emergency"
    assert response.json()["trauma"] is True
