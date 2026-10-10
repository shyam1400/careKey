from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enums import AppRole
from app.models.passkey import PasskeyChallenge, PasskeyCredential
from app.models.user import User
from app.services.passkeys import require_recent_password_auth, verify_emergency_assertion


class _Db:
    def __init__(self, challenge, credential=None):
        self.challenge = challenge
        self.credential = credential
        self.deleted = []
        self.added = []
        self.commits = 0

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return self.challenge if entity is PasskeyChallenge else self.credential

    def delete(self, value):
        self.deleted.append(value)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1


def _user():
    return User(id=uuid4(), firebase_uid="doctor-uid", email="doctor@example.com", role=AppRole.DOCTOR, is_active=True)


def _challenge(user, expires_at):
    return PasskeyChallenge(
        id=uuid4(), user_id=user.id, challenge="YQ", purpose="emergency", rp_id="carekey.example",
        origin="https://carekey.example", expires_at=expires_at,
    )


def test_expired_emergency_challenge_is_consumed():
    user = _user()
    challenge = _challenge(user, datetime.now(timezone.utc) - timedelta(seconds=1))
    db = _Db(challenge)

    with pytest.raises(HTTPException) as error:
        verify_emergency_assertion(db, user, challenge.id, {"id": "credential-id"})

    assert error.value.detail == "Passkey challenge expired; request a new one"
    assert db.deleted == [challenge]
    assert db.commits == 1


def test_verified_emergency_challenge_updates_counter_and_is_consumed(monkeypatch):
    user = _user()
    challenge = _challenge(user, datetime.now(timezone.utc) + timedelta(minutes=1))
    credential = PasskeyCredential(
        id=uuid4(), user_id=user.id, credential_id="credential-id", public_key="Yg", sign_count=4,
    )
    db = _Db(challenge, credential)
    monkeypatch.setattr(
        "app.services.passkeys.verify_authentication_response",
        lambda **_kwargs: SimpleNamespace(new_sign_count=5),
    )

    verify_emergency_assertion(db, user, challenge.id, {"id": "credential-id"})

    assert credential.sign_count == 5
    assert credential.last_used_at is not None
    assert db.deleted == [challenge]
    assert db.commits == 1


def test_passkey_registration_requires_fresh_one_time_firebase_password_authentication():
    user = _user()
    user._firebase_auth_time = int(datetime.now(timezone.utc).timestamp())
    db = _Db(None)
    require_recent_password_auth(db, user)
    assert user.last_passkey_registration_auth_time == user._firebase_auth_time

    with pytest.raises(HTTPException) as error:
        require_recent_password_auth(db, user)
    assert error.value.status_code == 401
    assert error.value.detail == "Please re-enter your password before adding another passkey"
