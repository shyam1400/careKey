from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.firebase import FirebaseIdentity
from app.main import app
from app.models.enums import AppRole
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.user import User


class _FakeDb:
    def __init__(self, users=None, patients=None):
        self.users = list(users or [])
        self.patients = list(patients or [])

    def _resolve_bound_value(self, node):
        if node is None:
            return None
        if hasattr(node, "value"):
            value = getattr(node, "value")
            if value is not None:
                return value
        if hasattr(node, "element"):
            value = self._resolve_bound_value(getattr(node, "element"))
            if value is not None:
                return value
        if hasattr(node, "right"):
            value = self._resolve_bound_value(getattr(node, "right"))
            if value is not None:
                return value
        if hasattr(node, "left"):
            value = self._resolve_bound_value(getattr(node, "left"))
            if value is not None:
                return value
        return None

    def _extract_where_value(self, stmt, expected_key=None):
        criteria = getattr(stmt, "_where_criteria", ())
        for criterion in criteria:
            lhs = getattr(criterion, "left", None)
            rhs = getattr(criterion, "right", None)
            if lhs is None or rhs is None:
                continue
            key = getattr(lhs, "key", None)
            if expected_key is not None and key != expected_key:
                continue
            value = self._resolve_bound_value(rhs)
            if value is not None:
                return value
        return None

    def _where_value_for(self, stmt, *keys):
        criteria = getattr(stmt, "_where_criteria", ())
        for criterion in criteria:
            lhs = getattr(criterion, "left", None)
            if lhs is None:
                continue
            key = getattr(lhs, "key", None)
            if key in keys:
                return self._resolve_bound_value(getattr(criterion, "right", None))
        return None

    def _match_user_by_uid(self, firebase_uid):
        for user in self.users:
            if isinstance(user, User) and user.firebase_uid == firebase_uid:
                return user
        return None

    def _match_user_by_id(self, user_id):
        for user in self.users:
            if isinstance(user, User) and user.id == user_id:
                return user
        return None

    def scalar(self, stmt):
        stmt_sql = str(stmt).lower()
        criteria = getattr(stmt, "_where_criteria", ())
        for criterion in criteria:
            lhs = getattr(criterion, "left", None)
            rhs = getattr(criterion, "right", None)
            if lhs is None or rhs is None:
                continue
            key = getattr(lhs, "key", None)
            value = self._resolve_bound_value(rhs)
            if key == "firebase_uid":
                user = self._match_user_by_uid(value)
                if user is not None:
                    return user
            if key == "id" and value is not None:
                if "patients" in stmt_sql:
                    for patient in self.patients:
                        if patient.id == value:
                            return patient
                    continue
                if "profiles" in stmt_sql:
                    for profile in self.users:
                        if isinstance(profile, Profile) and profile.id == value:
                            return profile
                    for user in self.users:
                        if isinstance(user, User) and user.id == value:
                            return user
                    continue
                user = self._match_user_by_id(value)
                if user is not None:
                    return user
                for profile in self.users:
                    if isinstance(profile, Profile) and profile.id == value:
                        return profile
                for patient in self.patients:
                    if patient.id == value:
                        return patient
        return None

    def add(self, obj):
        if isinstance(obj, User):
            self.users.append(obj)
            return
        if isinstance(obj, Profile):
            self.users.append(obj)
            return
        if isinstance(obj, Patient):
            self.patients.append(obj)
            return

    def commit(self):
        return None

    def flush(self):
        return None

    def refresh(self, obj):
        return None

    def scalars(self, stmt):
        sql = str(stmt)
        if "patients" in sql and "LIMIT" in sql:
            return _FakeScalarResult(self.patients)
        return _FakeScalarResult(self.patients)


class _FakeScalarResult:
    def __init__(self, items):
        self.items = items

    def all(self):
        return list(self.items)


def _user(role: AppRole, firebase_uid: str = "uid-1", email: str = "user@example.com", is_active: bool = True) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid4(),
        firebase_uid=firebase_uid,
        email=email,
        is_active=is_active,
        role=role,
        created_at=now,
        updated_at=now,
    )


def _profile(user: User, full_name: str = "Test User") -> Profile:
    return Profile(
        id=user.id,
        firebase_uid=user.firebase_uid,
        full_name=full_name,
        email=user.email,
        created_at=datetime.now(timezone.utc),
    )


def _patient_for(user: User, **kwargs):
    now = datetime.now(timezone.utc)
    profile = _profile(user)
    patient = Patient(
        id=user.id,
        medical_id="CK-12345678",
        date_of_birth=kwargs.get("date_of_birth"),
        gender=kwargs.get("gender"),
        phone=kwargs.get("phone"),
        address=kwargs.get("address"),
        emergency_contact_name=kwargs.get("emergency_contact_name"),
        emergency_contact_phone=kwargs.get("emergency_contact_phone"),
        blood_group=kwargs.get("blood_group"),
        rh_factor=kwargs.get("rh_factor"),
        updated_at=now,
    )
    patient.profile = profile
    return patient


def _override_db_with_user(user: User, patient: Patient | None = None):
    db = _FakeDb(users=[user, _profile(user)], patients=[] if patient is None else [patient])
    if patient is not None:
        db.patients = [patient]

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return db


@pytest.fixture
def authenticated_patient(monkeypatch: pytest.MonkeyPatch):
    user = _user(AppRole.PATIENT, "patient-uid", "patient@example.com")
    monkeypatch.setattr("app.core.security.verify_id_token", lambda _token: FirebaseIdentity(firebase_uid=user.firebase_uid, email=user.email))
    return user


@pytest.fixture
def authenticated_doctor(monkeypatch: pytest.MonkeyPatch):
    doctor = _user(AppRole.DOCTOR, "doctor-uid", "doctor@example.com")
    monkeypatch.setattr("app.core.security.verify_id_token", lambda _token: FirebaseIdentity(firebase_uid=doctor.firebase_uid, email=doctor.email))
    return doctor


@pytest.fixture
def authenticated_admin(monkeypatch: pytest.MonkeyPatch):
    admin = _user(AppRole.ADMIN, "admin-uid", "admin@example.com")
    monkeypatch.setattr("app.core.security.verify_id_token", lambda _token: FirebaseIdentity(firebase_uid=admin.firebase_uid, email=admin.email))
    return admin


def test_create_patient_success(authenticated_patient):
    _override_db_with_user(authenticated_patient)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/patients",
                json={
                    "full_name": "Alice Patient",
                    "date_of_birth": "1990-01-01",
                    "gender": "female",
                    "phone": "+15551234567",
                    "address": "123 Main St",
                    "emergency_contact_name": "Bob",
                    "emergency_contact_phone": "+15557654321",
                    "blood_group": "O+",
                    "rh_factor": "positive",
                },
                headers={"Authorization": "Bearer token"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["full_name"] == "Alice Patient"
    assert response.json()["medical_id"].startswith("CK-")
    assert response.json()["id"] == str(authenticated_patient.id)


def test_get_patient_returns_existing_patient(authenticated_patient):
    patient = _patient_for(authenticated_patient, gender="female")
    _override_db_with_user(authenticated_patient, patient)
    try:
        with TestClient(app) as client:
            response = client.get(f"/patients/{patient.id}", headers={"Authorization": "Bearer token"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["id"] == str(patient.id)
    assert response.json()["gender"] == "female"


def test_patient_can_get_their_medical_id_qr_payload(authenticated_patient):
    patient = _patient_for(authenticated_patient)
    _override_db_with_user(authenticated_patient, patient)
    try:
        with TestClient(app) as client:
            response = client.get("/patients/me/medical-id", headers={"Authorization": "Bearer token"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "medical_id": "CK-12345678",
        "qr_payload": "carekey://medical-id/CK-12345678",
    }


def test_update_patient_allows_permitted_fields(authenticated_patient, monkeypatch):
    monkeypatch.setattr("app.api.patients.verify_patient_assertion", lambda *_args: None)
    patient = _patient_for(authenticated_patient, gender="female", phone="+15550000000")
    _override_db_with_user(authenticated_patient, patient)
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/patients/{patient.id}",
                json={"gender": "male", "phone": "+15551111111", "challenge_id": str(uuid4()), "credential": {"id": "demo"}},
                headers={"Authorization": "Bearer token"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["gender"] == "male"
    assert response.json()["phone"] == "+15551111111"


def test_get_patient_missing_id_returns_404(authenticated_patient):
    _override_db_with_user(authenticated_patient)
    try:
        with TestClient(app) as client:
            response = client.get(f"/patients/{uuid4()}", headers={"Authorization": "Bearer token"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found"


def test_patient_requires_authentication():
    with TestClient(app) as client:
        response = client.get(f"/patients/{uuid4()}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing authorization token"


def test_patient_cannot_access_other_patient_profile(authenticated_patient):
    other_user = _user(AppRole.PATIENT, "other-patient", "other@example.com")
    other_patient = _patient_for(other_user, gender="male")
    _override_db_with_user(authenticated_patient, other_patient)
    try:
        with TestClient(app) as client:
            response = client.get(f"/patients/{other_patient.id}", headers={"Authorization": "Bearer token"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_patient_cannot_update_other_patient_profile(authenticated_patient):
    other_user = _user(AppRole.PATIENT, "other-patient", "other@example.com")
    other_patient = _patient_for(other_user, gender="male")
    _override_db_with_user(authenticated_patient, other_patient)
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/patients/{other_patient.id}",
                json={"gender": "female"},
                headers={"Authorization": "Bearer token"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_create_patient_invalid_request_data(authenticated_patient):
    _override_db_with_user(authenticated_patient)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/patients",
                json={"full_name": "", "date_of_birth": "bad-date"},
                headers={"Authorization": "Bearer token"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_listing_patients_is_admin_only(authenticated_patient):
    _override_db_with_user(authenticated_patient)
    try:
        with TestClient(app) as client:
            response = client.get("/patients", headers={"Authorization": "Bearer token"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403


def test_admin_can_list_patients(authenticated_admin):
    patient_a = _patient_for(_user(AppRole.PATIENT, "patient-a", "a@example.com"))
    patient_b = _patient_for(_user(AppRole.PATIENT, "patient-b", "b@example.com"))
    admin = authenticated_admin
    db = _FakeDb(
        users=[
            _user(AppRole.PATIENT, "patient-a", "a@example.com"),
            _user(AppRole.PATIENT, "patient-b", "b@example.com"),
            admin,
        ],
        patients=[patient_a, patient_b],
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.get("/patients?limit=50&offset=0", headers={"Authorization": "Bearer token"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert len(response.json()) >= 2
