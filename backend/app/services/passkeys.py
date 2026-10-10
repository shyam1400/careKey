from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import base64url_to_bytes, verify_authentication_response
from webauthn.helpers import bytes_to_base64url

from app.core.config import get_settings
from app.models.enums import AppRole
from app.models.passkey import PasskeyChallenge, PasskeyCredential
from app.models.user import User

CHALLENGE_TTL = timedelta(minutes=3)


def require_doctor(user: User) -> None:
    if not user.is_active or user.role != AppRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Only active doctors can manage emergency passkeys")


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
    challenge = db.scalar(
        select(PasskeyChallenge)
        .where(
            PasskeyChallenge.id == challenge_id,
            PasskeyChallenge.user_id == user.id,
            PasskeyChallenge.purpose == "emergency",
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
