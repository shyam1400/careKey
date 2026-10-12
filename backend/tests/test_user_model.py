from app.models.enums import AppRole
from app.models.user import User


def test_user_table_columns():
    columns = {column.name for column in User.__table__.columns}
    assert columns == {
        "id", "firebase_uid", "email", "doctor_code", "hospital_id", "is_active", "role", "created_at", "updated_at",
        "last_passkey_registration_auth_time",
    }


def test_firebase_uid_is_unique_and_indexed():
    firebase_uid = User.__table__.c.firebase_uid
    unique_indexes = [index for index in User.__table__.indexes if index.unique]
    assert any("firebase_uid" in index.columns for index in unique_indexes)
    assert firebase_uid.nullable is False


def test_user_is_active_defaults_to_true_and_is_required():
    assert User.__table__.c.is_active.nullable is False
    assert User.__table__.c.is_active.default is not None


def test_user_roles_are_limited():
    assert {role.value for role in AppRole} == {"patient", "doctor", "hospital", "hospital_admin", "admin"}
    assert User.__table__.c.role.nullable is False
