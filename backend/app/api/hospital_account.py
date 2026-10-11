from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.hospital import Hospital, HospitalProcedure
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.user import User
from app.schemas.hospital_account import (
    HospitalProcedureCreate,
    HospitalProcedureResponse,
    HospitalProcedureUpdate,
    HospitalDoctorUpdate,
)

router = APIRouter(prefix="/hospital-account", tags=["hospital account"])


def _hospital_for(user: User, db: Session) -> Hospital:
    if user.role not in {AppRole.HOSPITAL, AppRole.HOSPITAL_ADMIN} or user.hospital_id is None:
        raise HTTPException(status_code=403, detail="Hospital account access is required")
    hospital = db.get(Hospital, user.hospital_id)
    if hospital is None:
        raise HTTPException(status_code=403, detail="This account is not assigned to an active hospital")
    return hospital


def _procedure_rows(db: Session, hospital_id: UUID, *, procedure_id: UUID | None = None) -> list[dict[str, Any]]:
    from sqlalchemy.orm import aliased

    # Patient and doctor profiles use the same table, so join each with its own alias.
    patient_profile = aliased(Profile)
    doctor_profile = aliased(Profile)
    query = (
        select(HospitalProcedure, patient_profile.full_name, doctor_profile.full_name)
        .join(Patient, Patient.id == HospitalProcedure.patient_id)
        .join(patient_profile, patient_profile.id == Patient.id)
        .join(User, User.id == HospitalProcedure.doctor_id)
        .join(doctor_profile, doctor_profile.id == User.id)
        .where(HospitalProcedure.hospital_id == hospital_id)
    )
    if procedure_id is not None:
        query = query.where(HospitalProcedure.id == procedure_id)
    rows = db.execute(query.order_by(HospitalProcedure.started_at.desc())).all()
    return [
        {
            "id": item.id,
            "hospital_id": item.hospital_id,
            "patient_id": item.patient_id,
            "patient_name": patient_name,
            "doctor_id": item.doctor_id,
            "doctor_name": doctor_name,
            "name": item.name,
            "status": item.status,
            "notes": item.notes,
            "started_at": item.started_at,
            "ended_at": item.ended_at,
            "created_at": item.created_at,
        }
        for item, patient_name, doctor_name in rows
    ]


@router.get("/me")
def my_hospital(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    hospital = _hospital_for(user, db)
    profile = db.get(Profile, user.id)
    return {"id": str(hospital.id), "name": hospital.name, "admin_name": profile.full_name if profile else user.email}


@router.get("/dashboard")
def hospital_dashboard(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    hospital = _hospital_for(user, db)
    doctors = db.scalar(
        select(func.count()).select_from(User).where(
            User.hospital_id == hospital.id, User.role == AppRole.DOCTOR, User.is_active.is_(True)
        )
    ) or 0
    patients = db.scalar(
        select(func.count()).select_from(Patient).where(or_(
            select(AccessLog.id).where(AccessLog.hospital_id == hospital.id,
                                      AccessLog.patient_id == Patient.id).exists(),
            select(AccessLog.id).join(User, User.id == AccessLog.provider_id).where(
                User.hospital_id == hospital.id, AccessLog.patient_id == Patient.id).exists(),
            select(HospitalProcedure.id).where(HospitalProcedure.hospital_id == hospital.id,
                                               HospitalProcedure.patient_id == Patient.id).exists(),
        ))
    ) or 0
    ongoing = db.scalar(
        select(func.count()).select_from(HospitalProcedure).where(
            HospitalProcedure.hospital_id == hospital.id, HospitalProcedure.status == "in_progress"
        )
    ) or 0
    return {"hospital_id": str(hospital.id), "hospital_name": hospital.name,
            "doctor_count": doctors, "patient_count": patients, "ongoing_procedure_count": ongoing}


@router.get("/doctors")
def hospital_doctors(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    hospital = _hospital_for(user, db)
    rows = db.execute(
        select(User.id, User.email, User.is_active, Profile.full_name, Profile.specialty)
        .join(Profile, Profile.id == User.id, isouter=True)
        .where(User.hospital_id == hospital.id, User.role == AppRole.DOCTOR)
        .order_by(Profile.full_name, User.email)
    ).all()
    return [{"id": row.id, "email": row.email, "is_active": row.is_active,
             "full_name": row.full_name or row.email or "Doctor", "specialty": row.specialty}
            for row in rows]


@router.patch("/doctors/{doctor_id}/status")
def update_doctor_status(
    doctor_id: UUID,
    is_active: bool,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    hospital = _hospital_for(user, db)
    doctor = db.scalar(select(User).where(
        User.id == doctor_id, User.hospital_id == hospital.id, User.role == AppRole.DOCTOR
    ))
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found in this hospital")
    doctor.is_active = is_active
    db.commit()
    return {"id": str(doctor.id), "is_active": doctor.is_active}


@router.patch("/doctors/{doctor_id}")
def update_doctor_profile(
    doctor_id: UUID,
    payload: HospitalDoctorUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    hospital = _hospital_for(user, db)
    doctor = db.scalar(select(User).where(
        User.id == doctor_id, User.hospital_id == hospital.id, User.role == AppRole.DOCTOR
    ))
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found in this hospital")
    profile = db.get(Profile, doctor.id)
    if profile is None:
        profile = Profile(id=doctor.id, firebase_uid=doctor.firebase_uid, email=doctor.email)
        db.add(profile)
    profile.full_name = payload.full_name.strip()
    profile.specialty = payload.specialty.strip() if payload.specialty else None
    profile.organization = hospital.name
    db.commit()
    return {"id": str(doctor.id), "full_name": profile.full_name, "specialty": profile.specialty}


@router.get("/patients")
def hospital_patients(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    hospital = _hospital_for(user, db)
    query = (
        select(Patient.id, Patient.medical_id, Profile.full_name, Profile.email)
        .join(Profile, Profile.id == Patient.id)
        .where(or_(
            select(AccessLog.id).where(AccessLog.hospital_id == hospital.id, AccessLog.patient_id == Patient.id).exists(),
            select(AccessLog.id).join(User, User.id == AccessLog.provider_id).where(
                User.hospital_id == hospital.id, AccessLog.patient_id == Patient.id).exists(),
            select(HospitalProcedure.id).where(HospitalProcedure.hospital_id == hospital.id,
                                               HospitalProcedure.patient_id == Patient.id).exists(),
        ))
        .order_by(Profile.full_name)
    )
    rows = db.execute(query).all()
    return [{"id": row.id, "medical_id": row.medical_id, "full_name": row.full_name, "email": row.email}
            for row in rows]


@router.get("/procedures", response_model=list[HospitalProcedureResponse])
def list_procedures(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(planned|in_progress|completed|cancelled)$"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    hospital = _hospital_for(user, db)
    rows = _procedure_rows(db, hospital.id)
    return [row for row in rows if status_filter is None or row["status"] == status_filter]


@router.post("/procedures", response_model=HospitalProcedureResponse, status_code=status.HTTP_201_CREATED)
def create_procedure(
    payload: HospitalProcedureCreate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    hospital = _hospital_for(user, db)
    patient = db.get(Patient, payload.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    doctor = db.get(User, payload.doctor_id)
    if doctor is None or doctor.role != AppRole.DOCTOR or doctor.hospital_id != hospital.id or not doctor.is_active:
        raise HTTPException(status_code=422, detail="Choose an active doctor assigned to this hospital")
    row = HospitalProcedure(hospital_id=hospital.id, patient_id=patient.id, doctor_id=doctor.id,
                            name=payload.name.strip(), notes=payload.notes)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _procedure_rows(db, hospital.id, procedure_id=row.id)[0]


@router.patch("/procedures/{procedure_id}", response_model=HospitalProcedureResponse)
def update_procedure(
    procedure_id: UUID,
    payload: HospitalProcedureUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    hospital = _hospital_for(user, db)
    row = db.scalar(select(HospitalProcedure).where(
        HospitalProcedure.id == procedure_id, HospitalProcedure.hospital_id == hospital.id
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Procedure not found")
    changes = payload.model_dump(exclude_unset=True)
    if "doctor_id" in changes:
        doctor = db.get(User, changes["doctor_id"])
        if doctor is None or doctor.role != AppRole.DOCTOR or doctor.hospital_id != hospital.id or not doctor.is_active:
            raise HTTPException(status_code=422, detail="Choose an active doctor assigned to this hospital")
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
    for key, value in changes.items():
        setattr(row, key, value)
    if row.status in {"completed", "cancelled"} and row.ended_at is None:
        row.ended_at = datetime.now(timezone.utc)
    elif row.status in {"planned", "in_progress"}:
        row.ended_at = None
    db.commit()
    return _procedure_rows(db, hospital.id, procedure_id=row.id)[0]


@router.get("/access-logs")
def hospital_access_logs(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    hospital = _hospital_for(user, db)
    rows = db.execute(
        select(AccessLog, Profile.full_name.label("patient_name"), Hospital.name.label("current_hospital_name"))
        .outerjoin(Profile, Profile.id == AccessLog.patient_id)
        .outerjoin(User, User.id == AccessLog.provider_id)
        .outerjoin(Hospital, Hospital.id == func.coalesce(AccessLog.hospital_id, User.hospital_id))
        .where(or_(AccessLog.hospital_id == hospital.id, User.hospital_id == hospital.id))
        .order_by(AccessLog.created_at.desc()).limit(limit)
    ).all()
    return [{"id": log.id, "patient_name": patient_name, "patient_id": log.patient_id,
             "doctor_name": log.provider_name, "hospital_name": log.hospital_name or current_hospital_name,
             "action": log.action, "categories": log.categories, "reason": log.reason,
             "access_type": log.access_type, "verification_result": log.verification_result,
             "success": log.success, "created_at": log.created_at}
            for log, patient_name, current_hospital_name in rows]
