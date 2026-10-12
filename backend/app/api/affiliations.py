"""Approval-based doctor and hospital work affiliations."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.affiliation import HospitalDoctorAffiliation
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.hospital import Hospital
from app.models.profile import Profile
from app.models.user import User
from app.schemas.affiliation import AffiliationDecision, AffiliationRequest

router = APIRouter(prefix="/affiliations", tags=["doctor-hospital affiliations"])
HOSPITAL_ROLES = {AppRole.HOSPITAL, AppRole.HOSPITAL_ADMIN}


def _hospital_user(user: User) -> bool:
    return user.role in HOSPITAL_ROLES and user.hospital_id is not None


@router.get("/me")
def my_affiliations(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    if user.role == AppRole.DOCTOR:
        rows = db.execute(
            select(HospitalDoctorAffiliation, Hospital.name, Hospital.hospital_code)
            .join(Hospital, Hospital.id == HospitalDoctorAffiliation.hospital_id)
            .where(HospitalDoctorAffiliation.doctor_id == user.id)
            .order_by(HospitalDoctorAffiliation.requested_at.desc())
        ).all()
        return [{"id": item.id, "hospital_id": item.hospital_id, "hospital_name": name,
                 "hospital_code": code, "doctor_id": user.id, "doctor_code": user.doctor_code,
                 "status": item.status, "initiated_by": item.initiated_by,
                 "requested_at": item.requested_at} for item, name, code in rows]
    if _hospital_user(user):
        rows = db.execute(
            select(HospitalDoctorAffiliation, User.doctor_code, User.email, Profile.full_name, Profile.specialty)
            .join(User, User.id == HospitalDoctorAffiliation.doctor_id)
            .outerjoin(Profile, Profile.id == User.id)
            .where(HospitalDoctorAffiliation.hospital_id == user.hospital_id)
            .order_by(HospitalDoctorAffiliation.requested_at.desc())
        ).all()
        return [{"id": item.id, "hospital_id": item.hospital_id, "doctor_id": item.doctor_id,
                 "doctor_code": code, "doctor_name": name or email or "Doctor", "specialty": specialty,
                 "status": item.status, "initiated_by": item.initiated_by,
                 "requested_at": item.requested_at} for item, code, email, name, specialty in rows]
    raise HTTPException(status_code=403, detail="Doctor or hospital account access is required")


@router.get("/lookup/{code}")
def lookup_affiliation_target(
    code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, str]:
    code = code.strip().upper()
    if user.role == AppRole.DOCTOR and code.startswith("HOS-"):
        hospital = db.scalar(select(Hospital).where(Hospital.hospital_code == code))
        if hospital:
            return {"type": "hospital", "id": str(hospital.id), "code": hospital.hospital_code, "name": hospital.name}
    elif _hospital_user(user) and code.startswith("DOC-"):
        doctor = db.scalar(select(User).where(User.doctor_code == code, User.role == AppRole.DOCTOR, User.is_active.is_(True)))
        if doctor:
            profile = db.get(Profile, doctor.id)
            return {"type": "doctor", "id": str(doctor.id), "code": doctor.doctor_code or code,
                    "name": (profile.full_name if profile else None) or doctor.email or "Doctor"}
    else:
        raise HTTPException(status_code=403, detail="Use a hospital code as a doctor or a doctor code as a hospital")
    raise HTTPException(status_code=404, detail="No matching active account was found for that code")


@router.post("/request", status_code=201)
def request_affiliation(
    payload: AffiliationRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, str]:
    code = payload.code.upper()
    if user.role == AppRole.DOCTOR:
        hospital = db.scalar(select(Hospital).where(Hospital.hospital_code == code))
        if hospital is None:
            raise HTTPException(status_code=404, detail="Hospital not found for that code")
        doctor_id, hospital_id, direction = user.id, hospital.id, "doctor"
        pending_status = "pending_hospital"
    elif _hospital_user(user):
        doctor = db.scalar(select(User).where(User.doctor_code == code, User.role == AppRole.DOCTOR, User.is_active.is_(True)))
        if doctor is None:
            raise HTTPException(status_code=404, detail="Active doctor not found for that code")
        doctor_id, hospital_id, direction = doctor.id, user.hospital_id, "hospital"
        pending_status = "pending_doctor"
    else:
        raise HTTPException(status_code=403, detail="Doctor or hospital account access is required")

    affiliation = db.scalar(select(HospitalDoctorAffiliation).where(
        HospitalDoctorAffiliation.doctor_id == doctor_id,
        HospitalDoctorAffiliation.hospital_id == hospital_id,
    ).with_for_update())
    if affiliation and affiliation.status in {"approved", "pending_hospital", "pending_doctor"}:
        raise HTTPException(status_code=409, detail="An active or pending affiliation already exists")
    if affiliation is None:
        affiliation = HospitalDoctorAffiliation(
            id=uuid4(), doctor_id=doctor_id, hospital_id=hospital_id,
            status=pending_status, initiated_by=direction,
        )
    else:
        affiliation.status = pending_status
        affiliation.initiated_by = direction
        affiliation.requested_at = datetime.now(timezone.utc)
        affiliation.decided_at = None
        affiliation.decided_by = None
    db.add(affiliation)
    db.commit()
    return {"id": str(affiliation.id), "status": affiliation.status}


@router.post("/{affiliation_id}/decision")
def decide_affiliation(
    affiliation_id: UUID, payload: AffiliationDecision,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict[str, str]:
    item = db.scalar(select(HospitalDoctorAffiliation).where(
        HospitalDoctorAffiliation.id == affiliation_id
    ).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Affiliation request not found")
    may_decide = (
        item.status == "pending_hospital" and _hospital_user(user) and item.hospital_id == user.hospital_id
    ) or (
        item.status == "pending_doctor" and user.role == AppRole.DOCTOR and item.doctor_id == user.id
    )
    if not may_decide:
        raise HTTPException(status_code=403, detail="Only the requested party can decide this affiliation")

    item.status = "approved" if payload.approve else "denied"
    item.decided_at = datetime.now(timezone.utc)
    item.decided_by = user.id
    hospital = db.get(Hospital, item.hospital_id)
    doctor = db.get(User, item.doctor_id)
    profile = db.get(Profile, item.doctor_id)
    if profile is None and doctor is not None:
        profile = Profile(id=doctor.id, firebase_uid=doctor.firebase_uid,
                          full_name=(doctor.email or "Doctor")[:100], email=doctor.email)
        db.add(profile)
    approved_names = list(db.scalars(
        select(Hospital.name).join(HospitalDoctorAffiliation, HospitalDoctorAffiliation.hospital_id == Hospital.id)
        .where(HospitalDoctorAffiliation.doctor_id == item.doctor_id,
               HospitalDoctorAffiliation.id != item.id,
               HospitalDoctorAffiliation.status == "approved")
        .order_by(Hospital.name)
    ).all())
    if payload.approve and hospital is not None:
        approved_names.append(hospital.name)
    if profile is not None:
        profile.organization = ", ".join(sorted(set(approved_names))) or None
    db.add(AccessLog(
        provider_id=item.doctor_id,
        provider_name=((profile.full_name if profile else None) or (doctor.email if doctor else None) or "Doctor")[:100],
        hospital_id=item.hospital_id,
        hospital_name=hospital.name if hospital else None,
        action=f"Affiliation {item.status}: {hospital.name if hospital else 'hospital'} and {doctor.email if doctor else 'doctor'}",
        categories=[], access_type="staff_affiliation", verification_result="account_approval",
        success=True,
    ))
    db.commit()
    return {"id": str(item.id), "status": item.status}
