from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import base64url_to_bytes, verify_authentication_response
from webauthn.helpers import bytes_to_base64url

from app.core.config import get_settings
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.passkey import PasskeyChallenge, PasskeyCredential
from app.models.user import User

CHALLENGE_TTL = timedelta(minutes=3)


def require_doctor(user: User) -> None:
    if not user.is_active or user.role != AppRole.DOCTOR or user.hospital_id is None:
        raise HTTPException(status_code=403, detail="Only active hospital-assigned doctors can manage emergency passkeys")


def require_passkey_user(user: User) -> None:
    if not user.is_active or user.role not in {AppRole.DOCTOR, AppRole.PATIENT} or (user.role == AppRole.DOCTOR and user.hospital_id is None):
        raise HTTPException(status_code=403, detail="Only active patient or doctor accounts can manage passkeys")


def require_recent_password_auth(db: Session, user: User) -> None:
    auth_time = getattr(user, "_firebase_auth_time", None)
    now = int(datetime.now(timezone.utc).timestamp())
    if not isinstance(auth_time, int) or now - auth_time > 300 or auth_time > now + 30:
        raise HTTPException(status_code=401, detail="Please re-enter your password before adding a passkey")
    if user.last_passkey_registration_auth_time is not None and auth_time <= user.last_passkey_registration_auth_time:
        raise HTTPException(status_code=401, detail="Please re-enter your password before adding another passkey")
    user.last_passkey_registration_auth_time = auth_time
    db.add(user)


def origin_context(request: Request) -> tuple[str, str]:
    origin = request.headers.get("origin")
    settings = get_settings()
    if not origin or origin not in settings.cors_origin_list:
        raise HTTPException(status_code=403, detail="Passkey request origin is not allowed")
    parsed = urlsplit(origin)
    if not parsed.hostname or parsed.scheme not in {"https", "http"}:
        raise HTTPException(status_code=400, detail="Invalid passkey request origin")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise HTTPException(status_code=400, detail="Passkeys require a secure HTTPS origin")
    return parsed.hostname, origin


def store_challenge(
    db: Session,
    user: User,
    *,
    challenge: str,
    purpose: str,
    rp_id: str,
    origin: str,
) -> UUID:
    row = PasskeyChallenge(
        id=uuid4(),
        user_id=user.id,
        challenge=challenge,
        purpose=purpose,
        rp_id=rp_id,
        origin=origin,
        expires_at=datetime.now(timezone.utc) + CHALLENGE_TTL,
    )
    db.add(row)
    db.commit()
    return row.id


def verify_emergency_assertion(
    db: Session,
    user: User,
    challenge_id: UUID,
    credential_response: dict,
) -> None:
    verify_assertion(db, user, challenge_id, credential_response, purpose="emergency")


def verify_patient_assertion(
    db: Session,
    user: User,
    challenge_id: UUID,
    credential_response: dict,
) -> None:
    if user.role != AppRole.PATIENT or not user.is_active:
        raise HTTPException(status_code=403, detail="Only active patient accounts can verify with a passkey")
    verify_assertion(db, user, challenge_id, credential_response, purpose="patient_step_up")
    db.add(
        AccessLog(
            patient_id=user.id,
            provider_name=(user.email or "Patient")[:100],
            action="Patient confirmed a sensitive account action with a passkey",
            categories=[],
            access_type="account_security",
            verification_result="webauthn_user_verified",
            success=True,
        )
    )
    db.commit()


def verify_assertion(
    db: Session,
    user: User,
    challenge_id: UUID,
    credential_response: dict,
    *,
    purpose: str,
) -> None:
    challenge = db.scalar(
        select(PasskeyChallenge)
        .where(
            PasskeyChallenge.id == challenge_id,
            PasskeyChallenge.user_id == user.id,
            PasskeyChallenge.purpose == purpose,
        )
        .with_for_update()
    )
    if challenge is None:
        raise HTTPException(status_code=400, detail="Passkey challenge is missing or already used")

    now = datetime.now(timezone.utc)
    if challenge.expires_at <= now:
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=400, detail="Passkey challenge expired; request a new one")

    credential_id = credential_response.get("id")
    credential = db.scalar(
        select(PasskeyCredential).where(
            PasskeyCredential.user_id == user.id,
            PasskeyCredential.credential_id == credential_id,
        )
    ) if isinstance(credential_id, str) else None
    if credential is None:
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=403, detail="This device passkey is not registered to your account")

    try:
        verification = verify_authentication_response(
            credential=credential_response,
            expected_challenge=base64url_to_bytes(challenge.challenge),
            expected_rp_id=challenge.rp_id,
            expected_origin=challenge.origin,
            credential_public_key=base64url_to_bytes(credential.public_key),
            credential_current_sign_count=credential.sign_count,
            require_user_verification=True,
        )
    except Exception:
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=403, detail="Passkey verification failed") from None

    credential.sign_count = verification.new_sign_count
    credential.last_used_at = now
    db.delete(challenge)
    db.commit()
