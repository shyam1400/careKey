from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.hospital import Hospital
from app.models.hospital import HospitalProcedure
from app.models.user import User
from app.schemas.hospital import HospitalCreate, HospitalResponse, HospitalUpdate

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=list[HospitalResponse])
def list_hospitals(
    emergency: bool | None = None,
    trauma: bool | None = None,
    ambulance: bool | None = None,
    open_24h: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Hospital]:
    query = select(Hospital)
    for field, value in (
        (Hospital.emergency, emergency),
        (Hospital.trauma, trauma),
        (Hospital.ambulance, ambulance),
        (Hospital.open_24h, open_24h),
    ):
        if value is not None:
            query = query.where(field == value)
    query = query.order_by(Hospital.name).limit(limit).offset(offset)
    return list(db.scalars(query).all())


@router.post("", response_model=HospitalResponse, status_code=status.HTTP_201_CREATED)
def create_hospital(
    payload: HospitalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Hospital:
    if user.role != AppRole.ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    hospital = Hospital(**payload.model_dump())
    db.add(hospital)
    db.add(
        AccessLog(
            provider_name=(user.email or str(user.id))[:100],
            action=f"Admin added hospital directory entry: {hospital.name}",
            categories=[],
            access_type="administration",
            verification_result="admin_hospital_create",
            success=True,
        )
    )
    db.commit()
    db.refresh(hospital)
    return hospital


@router.patch("/{hospital_id}", response_model=HospitalResponse)
def update_hospital(
    hospital_id: UUID,
    payload: HospitalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Hospital:
    if user.role != AppRole.ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one hospital field to update")
    if any(field in changes and changes[field] is None for field in ("name", "latitude", "longitude", "emergency", "trauma", "ambulance", "open_24h")):
        raise HTTPException(status_code=422, detail="Name, coordinates, and facility capabilities cannot be null")
    if "name" in changes and not changes["name"].strip():
        raise HTTPException(status_code=422, detail="Hospital name cannot be blank")
    for field, value in changes.items():
        setattr(hospital, field, value.strip() if isinstance(value, str) else value)
    db.add(hospital)
    db.add(
        AccessLog(
            provider_name=(user.email or str(user.id))[:100],
            action=f"Admin updated hospital directory entry: {hospital.name}",
            categories=[],
            access_type="administration",
            verification_result="admin_hospital_update",
            success=True,
        )
    )
    db.commit()
    db.refresh(hospital)
    return hospital


@router.delete("/{hospital_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hospital(
    hospital_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    if user.role != AppRole.ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    attached_users = db.scalar(select(User.id).where(User.hospital_id == hospital.id).limit(1))
    existing_procedures = db.scalar(select(HospitalProcedure.id).where(HospitalProcedure.hospital_id == hospital.id).limit(1))
    if attached_users or existing_procedures:
        raise HTTPException(status_code=409, detail="Reassign hospital accounts and retain procedure records before deleting this hospital")
    name = hospital.name
    db.add(
        AccessLog(
            provider_name=(user.email or str(user.id))[:100],
            action=f"Admin deleted hospital directory entry: {name}",
            categories=[],
            access_type="administration",
            verification_result="admin_hospital_delete",
            success=True,
        )
    )
    db.delete(hospital)
    db.commit()
