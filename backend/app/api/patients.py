from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.enums import AppRole
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientMedicalIdResponse, PatientResponse, PatientUpdate
from app.utils.ids import generate_medical_id

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/me/medical-id", response_model=PatientMedicalIdResponse)
def get_my_medical_id(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PatientMedicalIdResponse:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    patient = db.scalar(select(Patient).where(Patient.id == user.id))
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
    return PatientMedicalIdResponse(
        medical_id=patient.medical_id,
        qr_payload=f"carekey://medical-id/{patient.medical_id}",
    )


@router.post("/me/medical-id/regenerate", response_model=PatientMedicalIdResponse)
def regenerate_my_medical_id(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PatientMedicalIdResponse:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    patient = db.scalar(select(Patient).where(Patient.id == user.id))
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
    patient.medical_id = generate_medical_id()
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return PatientMedicalIdResponse(
        medical_id=patient.medical_id,
        qr_payload=f"carekey://medical-id/{patient.medical_id}",
    )


def _require_patient_access(user: User, patient_id: UUID, db: Session) -> Patient:
    patient = db.scalar(select(Patient).where(Patient.id == patient_id))
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    if user.role == AppRole.PATIENT:
        profile_linked = patient.profile is not None and patient.profile.id == user.id
        if not profile_linked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return patient

    if user.role == AppRole.DOCTOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if user.role == AppRole.ADMIN:
        return patient

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Patient:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if db.scalar(select(Patient).where(Patient.id == user.id)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Patient profile already exists")

    profile = db.scalar(select(Profile).where(Profile.id == user.id))
    if profile is None:
        profile = Profile(id=user.id, firebase_uid=user.firebase_uid, full_name=payload.full_name, email=user.email)
        db.add(profile)
        db.flush()
    else:
        if payload.full_name and payload.full_name != profile.full_name:
            profile.full_name = payload.full_name

    patient = Patient(
        id=user.id,
        medical_id=generate_medical_id(),
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        phone=payload.phone,
        address=payload.address,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
        blood_group=payload.blood_group,
        rh_factor=payload.rh_factor,
    )
    patient.profile = profile
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Patient:
    patient = _require_patient_access(user, patient_id, db)
    return patient


@router.patch("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: UUID,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Patient:
    patient = _require_patient_access(user, patient_id, db)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return patient

    for field, value in update_data.items():
        if field == "full_name":
            if patient.profile is not None:
                patient.profile.full_name = value
            continue
        setattr(patient, field, value)

    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientResponse])
def list_patients(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(AppRole.ADMIN)),
) -> Sequence[Patient]:
    del user
    return db.scalars(select(Patient).limit(limit).offset(offset)).all()
