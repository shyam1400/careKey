from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import get_current_user
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.user import User
from app.schemas.emergency import EmergencyAccessRequest, EmergencyProfileResponse
from app.services.passkeys import verify_emergency_assertion
from app.services.emergency_notifications import emergency_access_time, send_emergency_contact_alert

router = APIRouter(prefix="/emergency", tags=["emergency"])


@router.get("/alerts/status")
def emergency_alerts_status(user: User = Depends(get_current_user)) -> dict[str, bool]:
    del user
    return {"configured": get_settings().twilio_configured}


def _provider_profile(db: Session, user: User) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.id == user.id))
    if profile is None:
        profile = Profile(
            id=user.id,
            firebase_uid=user.firebase_uid,
            full_name=(user.email[:100] if user.email else "Unnamed"),
            email=user.email,
        )
        db.add(profile)
        db.flush()
    return profile


def _audit(
    db: Session,
    user: User,
    reason: str,
    medical_id: str,
    *,
    patient: Patient | None,
    success: bool,
    verification_result: str = "firebase_id_token",
) -> None:
    profile = _provider_profile(db, user)
    db.add(
        AccessLog(
            patient_id=patient.id if patient else None,
            medical_id=medical_id,
            provider_id=profile.id,
            provider_name=profile.full_name,
            action="Emergency profile access",
            categories=["emergency_profile", "allergies", "critical_conditions", "active_medications"],
            reason=reason,
            access_type="emergency",
            verification_result=verification_result,
            success=success,
        )
    )
    db.commit()


@router.post("/{medical_id}", response_model=EmergencyProfileResponse)
def read_emergency_profile(
    medical_id: str,
    payload: EmergencyAccessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EmergencyProfileResponse:
    reason = payload.reason.strip()
    if user.role != AppRole.DOCTOR:
        _audit(db, user, reason, medical_id, patient=None, success=False)
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        verify_emergency_assertion(
            db,
            user,
            payload.passkey_challenge_id,
            payload.passkey_credential,
        )
    except HTTPException:
        _audit(
            db,
            user,
            reason,
            medical_id,
            patient=None,
            success=False,
            verification_result="webauthn_failed",
        )
        raise

    patient = db.scalar(select(Patient).where(Patient.medical_id == medical_id))
    if patient is None:
        _audit(
            db,
            user,
            reason,
            medical_id,
            patient=None,
            success=False,
            verification_result="webauthn_user_verified",
        )
        raise HTTPException(status_code=404, detail="Patient not found")

    _audit(
        db,
        user,
        reason,
        medical_id,
        patient=patient,
        success=True,
        verification_result="webauthn_user_verified",
    )
    if patient.emergency_contact_alerts_enabled and patient.emergency_contact_name and patient.emergency_contact_phone:
        provider = db.scalar(select(Profile).where(Profile.id == user.id))
        background_tasks.add_task(
            send_emergency_contact_alert,
            phone=patient.emergency_contact_phone,
            patient_name=patient.full_name or "CareKey patient",
            doctor_name=provider.full_name if provider else (user.email or "CareKey doctor"),
            organization=provider.organization if provider else None,
            accessed_at=emergency_access_time(),
        )
    return EmergencyProfileResponse(
        medical_id=patient.medical_id,
        full_name=patient.full_name,
        date_of_birth=patient.date_of_birth,
        blood_group=patient.blood_group,
        rh_factor=patient.rh_factor,
        emergency_contact_name=patient.emergency_contact_name,
        emergency_contact_phone=patient.emergency_contact_phone,
        allergies=[
            {"allergen": item.allergen, "reaction": item.reaction, "severity": item.severity}
            for item in patient.allergies
        ],
        critical_conditions=[
            {"name": item.name, "status": item.status, "critical": item.critical}
            for item in patient.conditions
            if item.critical
        ],
        active_medications=[
            {"name": item.name, "dosage": item.dosage, "frequency": item.frequency}
            for item in patient.medications
            if item.active
        ],
    )
