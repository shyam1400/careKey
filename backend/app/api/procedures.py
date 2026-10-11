"""Role-scoped views of hospital-tracked procedures for patients and doctors."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums import AppRole
from app.models.hospital import Hospital, HospitalProcedure
from app.models.profile import Profile
from app.models.user import User

router = APIRouter(prefix="/procedures", tags=["procedures"])


@router.get("/me")
def list_my_procedures(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    """Return procedures linked to the signed-in patient or assigned doctor only."""
    patient_profile = aliased(Profile)
    doctor_profile = aliased(Profile)
    query = (
        select(
            HospitalProcedure,
            patient_profile.full_name.label("patient_name"),
            doctor_profile.full_name.label("doctor_name"),
            Hospital.name.label("hospital_name"),
        )
        .join(patient_profile, patient_profile.id == HospitalProcedure.patient_id)
        .join(doctor_profile, doctor_profile.id == HospitalProcedure.doctor_id)
        .join(Hospital, Hospital.id == HospitalProcedure.hospital_id)
    )

    if user.role == AppRole.PATIENT:
        query = query.where(HospitalProcedure.patient_id == user.id)
    elif user.role == AppRole.DOCTOR:
        if user.hospital_id is None:
            raise HTTPException(status_code=403, detail="Your doctor account must be assigned to a hospital")
        query = query.where(
            HospitalProcedure.doctor_id == user.id,
            HospitalProcedure.hospital_id == user.hospital_id,
        )
    else:
        raise HTTPException(status_code=403, detail="Patient or doctor account access is required")

    rows = db.execute(query.order_by(HospitalProcedure.started_at.desc())).all()
    return [
        {
            "id": procedure.id,
            "patient_id": procedure.patient_id,
            "patient_name": patient_name,
            "doctor_id": procedure.doctor_id,
            "doctor_name": doctor_name,
            "hospital_id": procedure.hospital_id,
            "hospital_name": hospital_name,
            "name": procedure.name,
            "status": procedure.status,
            "notes": procedure.notes,
            "started_at": procedure.started_at,
            "ended_at": procedure.ended_at,
            "created_at": procedure.created_at,
        }
        for procedure, patient_name, doctor_name, hospital_name in rows
    ]
