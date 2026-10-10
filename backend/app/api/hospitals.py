from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums import AppRole
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.hospital import HospitalCreate, HospitalResponse

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
    db.commit()
    db.refresh(hospital)
    return hospital
