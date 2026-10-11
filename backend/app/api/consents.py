from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.consent import Consent
from app.models.audit import AccessLog
from app.models.enums import AppRole, ConsentStatus
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.records import Allergy, Condition, Document, Medication, Surgery
from app.models.user import User
from app.schemas.consent import ConsentCreate, ConsentResponse, ConsentRevokeProof
from app.services.passkeys import verify_patient_assertion

router = APIRouter(prefix="/consents", tags=["consents"])


def _ensure_provider_profile(db: Session, user: User) -> Profile:
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


@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
def grant_consent(
    payload: ConsentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Consent:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can grant consent")
    if payload.challenge_id is None or payload.credential is None:
        raise HTTPException(status_code=403, detail="Verify granting access with your phone passkey")
    verify_patient_assertion(db, user, payload.challenge_id, payload.credential)
    patient = db.scalar(select(Patient).where(Patient.id == user.id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    provider = db.scalar(select(User).where(User.id == payload.provider_id))
    if provider is None or provider.role != AppRole.DOCTOR or not provider.is_active or provider.hospital_id is None:
        raise HTTPException(status_code=404, detail="Active doctor not found")
    now = datetime.now(timezone.utc)
    if payload.expires_at is not None and payload.expires_at <= now:
        raise HTTPException(status_code=422, detail="Consent expiration must be in the future")

    provider_profile = _ensure_provider_profile(db, provider)
    provider_hospital = db.get(Hospital, provider.hospital_id)
    consent = Consent(
        patient_id=patient.id,
        provider_id=provider_profile.id,
        permissions=list(dict.fromkeys(permission.strip() for permission in payload.permissions if permission.strip())),
        purpose=payload.purpose.strip(),
        status=ConsentStatus.ACTIVE,
        expires_at=payload.expires_at,
    )
    if not consent.permissions or not consent.purpose:
        raise HTTPException(status_code=422, detail="Permissions and purpose cannot be blank")
    db.add(consent)
    db.add(AccessLog(
        patient_id=patient.id,
        provider_id=provider_profile.id,
        provider_name=provider_profile.full_name,
        hospital_id=provider_hospital.id if provider_hospital else None,
        hospital_name=provider_hospital.name if provider_hospital else None,
        action=f"Patient granted access to {provider_profile.full_name}",
        categories=consent.permissions,
        reason=consent.purpose,
        access_type="consent_change",
        success=True,
    ))
    db.commit()
    db.refresh(consent)
    return consent


@router.get("", response_model=list[ConsentResponse])
def list_consents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Consent]:
    if user.role == AppRole.PATIENT:
        query = select(Consent).where(Consent.patient_id == user.id)
    elif user.role == AppRole.DOCTOR:
        if user.hospital_id is None:
            raise HTTPException(status_code=403, detail="Your doctor account must be assigned to a hospital")
        query = select(Consent).where(Consent.provider_id == user.id)
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    consents = list(db.scalars(query.order_by(Consent.created_at.desc())).all())
    now = datetime.now(timezone.utc)
    expired = False
    for consent in consents:
        if (
            consent.status == ConsentStatus.ACTIVE
            and consent.expires_at is not None
            and consent.expires_at <= now
        ):
            consent.status = ConsentStatus.EXPIRED
            expired = True
    if expired:
        db.commit()
    return consents


@router.get("/{consent_id}/records")
def read_consented_records(
    consent_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role != AppRole.DOCTOR or user.hospital_id is None:
        raise HTTPException(status_code=403, detail="Only hospital-assigned doctors can view consented records")
    consent = db.scalar(select(Consent).where(Consent.id == consent_id))
    if consent is None or consent.provider_id != user.id:
        raise HTTPException(status_code=404, detail="Consent not found")
    now = datetime.now(timezone.utc)
    if consent.status != ConsentStatus.ACTIVE or (consent.expires_at is not None and consent.expires_at <= now):
        if consent.status == ConsentStatus.ACTIVE:
            consent.status = ConsentStatus.EXPIRED
            db.add(consent)
            db.commit()
        raise HTTPException(status_code=403, detail="Consent is no longer active")

    patient = db.scalar(select(Patient).where(Patient.id == consent.patient_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient record not found")
    permissions = set(consent.permissions)
    result: dict[str, object] = {"consent_id": str(consent.id), "permissions": sorted(permissions)}
    if "basic" in permissions:
        result["basic"] = {
            "full_name": patient.full_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,
            "phone": patient.phone,
        }
    if "blood" in permissions:
        result["blood"] = {"blood_group": patient.blood_group, "rh_factor": patient.rh_factor}
    if "allergies" in permissions:
        result["allergies"] = [
            {"allergen": item.allergen, "reaction": item.reaction, "severity": item.severity}
            for item in db.scalars(select(Allergy).where(Allergy.patient_id == patient.id)).all()
        ]
    if "medications" in permissions:
        result["medications"] = [
            {"name": item.name, "dosage": item.dosage, "frequency": item.frequency, "active": item.active}
            for item in db.scalars(select(Medication).where(Medication.patient_id == patient.id)).all()
        ]
    if "conditions" in permissions:
        result["conditions"] = [
            {"name": item.name, "diagnosis_date": item.diagnosis_date, "status": item.status,
             "critical": item.critical, "notes": item.notes}
            for item in db.scalars(select(Condition).where(Condition.patient_id == patient.id)).all()
        ]
    if "surgeries" in permissions:
        result["surgeries"] = [
            {"procedure": item.procedure, "surgery_date": item.surgery_date, "hospital": item.hospital,
             "major": item.major, "notes": item.notes}
            for item in db.scalars(select(Surgery).where(Surgery.patient_id == patient.id)).all()
        ]
    doc_types: set[str] = set()
    if "prescriptions" in permissions:
        doc_types.add("prescription")
    if "lab_reports" in permissions:
        doc_types.add("lab_report")
    if "documents" in permissions:
        doc_types.update({"discharge_summary", "imaging_report", "other"})
    if doc_types:
        docs = db.scalars(
            select(Document).where(Document.patient_id == patient.id, Document.doc_type.in_(doc_types))
        ).all()
        result["documents"] = []
        for doc in docs:
            if doc.storage_path:
                result["documents"].append({
                    "file_name": doc.file_name,
                    "doc_type": doc.doc_type,
                    "url": create_download_url(doc.storage_path),
                })

    provider_profile = db.scalar(select(Profile).where(Profile.id == user.id))
    provider_hospital = db.get(Hospital, user.hospital_id)
    db.add(AccessLog(
        patient_id=patient.id,
        provider_id=user.id,
        provider_name=provider_profile.full_name if provider_profile else (user.email or "Doctor")[:100],
        hospital_id=provider_hospital.id if provider_hospital else None,
        hospital_name=provider_hospital.name if provider_hospital else None,
        action="Consent-based medical record access",
        categories=sorted(permissions),
        reason=consent.purpose,
        access_type="consent",
        success=True,
    ))
    db.commit()
    return result


@router.post("/{consent_id}/revoke", response_model=ConsentResponse)
def revoke_consent(
    consent_id: UUID,
    payload: ConsentRevokeProof,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Consent:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can revoke consent")
    verify_patient_assertion(db, user, payload.challenge_id, payload.credential)
    consent = db.scalar(select(Consent).where(Consent.id == consent_id))
    if consent is None or consent.patient_id != user.id:
        raise HTTPException(status_code=404, detail="Consent not found")
    if consent.status != ConsentStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Only active consent can be revoked")
    consent.status = ConsentStatus.REVOKED
    consent.revoked_at = datetime.now(timezone.utc)
    db.add(consent)
    provider_profile = db.scalar(select(Profile).where(Profile.id == consent.provider_id))
    provider_user = db.get(User, consent.provider_id)
    provider_hospital = db.get(Hospital, provider_user.hospital_id) if provider_user and provider_user.hospital_id else None
    db.add(AccessLog(
        patient_id=consent.patient_id,
        provider_id=consent.provider_id,
        provider_name=provider_profile.full_name if provider_profile else "Healthcare provider",
        hospital_id=provider_hospital.id if provider_hospital else None,
        hospital_name=provider_hospital.name if provider_hospital else None,
        action="Patient revoked shared access",
        categories=consent.permissions,
        reason=consent.purpose,
        access_type="consent_change",
        success=True,
    ))
    db.commit()
    db.refresh(consent)
    return consent
