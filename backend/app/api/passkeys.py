import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.passkey import PasskeyChallenge, PasskeyCredential
from app.models.profile import Profile
from app.models.user import User
from app.schemas.passkey import PasskeyListItem, PasskeyOptions, PasskeyRegistrationVerify
from app.services.passkeys import origin_context, require_doctor, store_challenge

router = APIRouter(prefix="/auth/passkeys", tags=["passkeys"])


@router.get("", response_model=list[PasskeyListItem])
def list_passkeys(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PasskeyCredential]:
    require_doctor(user)
    return list(
        db.scalars(
            select(PasskeyCredential)
            .where(PasskeyCredential.user_id == user.id)
            .order_by(PasskeyCredential.created_at)
        ).all()
    )


@router.post("/registration-options", response_model=PasskeyOptions)
def registration_options(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    require_doctor(user)
    rp_id, origin = origin_context(request)
    credentials = db.scalars(
        select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
    ).all()
    profile = db.get(Profile, user.id)
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=get_settings().app_name,
        user_id=user.id.bytes,
        user_name=user.email or str(user.id),
        user_display_name=(profile.full_name if profile else None) or user.email or "CareKey doctor",
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(item.credential_id))
            for item in credentials
        ],
    )
    challenge_id = store_challenge(
        db,
        user,
        challenge=bytes_to_base64url(options.challenge),
        purpose="registration",
        rp_id=rp_id,
        origin=origin,
    )
    return {"challenge_id": challenge_id, "options": json.loads(options_to_json(options))}


@router.post("/register", status_code=201)
def register_passkey(
    payload: PasskeyRegistrationVerify,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    require_doctor(user)
    challenge = _load_challenge(db, payload.challenge_id, user, "registration")
    if challenge.expires_at <= datetime.now(timezone.utc):
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=400, detail="Passkey setup expired; start again")
    try:
        verification = verify_registration_response(
            credential=payload.credential,
            expected_challenge=base64url_to_bytes(challenge.challenge),
            expected_rp_id=challenge.rp_id,
            expected_origin=challenge.origin,
            require_user_verification=True,
        )
    except Exception:
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=400, detail="Passkey registration could not be verified") from None

    credential_id = bytes_to_base64url(verification.credential_id)
    existing = db.scalar(
        select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
    )
    db.delete(challenge)
    if existing is not None:
        db.commit()
        raise HTTPException(status_code=409, detail="That passkey is already registered")
    db.add(
        PasskeyCredential(
            id=uuid4(),
            user_id=user.id,
            credential_id=credential_id,
            public_key=bytes_to_base64url(verification.credential_public_key),
            sign_count=verification.sign_count,
        )
    )
    db.commit()
    return {"status": "verified"}


@router.post("/authentication-options", response_model=PasskeyOptions)
def authentication_options(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    require_doctor(user)
    credentials = db.scalars(
        select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
    ).all()
    if not credentials:
        raise HTTPException(status_code=409, detail="Set up a device passkey before emergency access")
    rp_id, origin = origin_context(request)
    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(item.credential_id))
            for item in credentials
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge_id = store_challenge(
        db,
        user,
        challenge=bytes_to_base64url(options.challenge),
        purpose="emergency",
        rp_id=rp_id,
        origin=origin,
    )
    return {"challenge_id": challenge_id, "options": json.loads(options_to_json(options))}


def _load_challenge(db: Session, challenge_id: UUID, user: User, purpose: str) -> PasskeyChallenge:
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
    return challenge
