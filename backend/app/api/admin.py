from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.profile import Profile
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.admin import AdminUserResponse, AdminUserStatusUpdate, AdminUserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(AppRole.ADMIN)),
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            User.id,
            User.email,
            User.role,
            User.is_active,
            Profile.full_name,
            Profile.organization,
            Profile.specialty,
            User.hospital_id,
            Hospital.name.label("hospital_name"),
        )
        .outerjoin(Profile, Profile.id == User.id)
        .outerjoin(Hospital, Hospital.id == User.hospital_id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {
            "id": row.id,
            "email": row.email,
            "role": row.role,
            "is_active": row.is_active,
            "full_name": row.full_name,
            "organization": row.organization,
            "specialty": row.specialty,
            "hospital_id": row.hospital_id,
            "hospital_name": row.hospital_name,
        }
        for row in rows
    ]


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(AppRole.ADMIN)),
) -> dict[str, Any]:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == AppRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin roles can only be changed through the trusted database setup")

    requested_role = AppRole(payload.role)
    selected_hospital_id = payload.hospital_id
    if requested_role in {AppRole.DOCTOR, AppRole.HOSPITAL_ADMIN}:
        selected_hospital_id = selected_hospital_id or target.hospital_id
        if selected_hospital_id is None or db.get(Hospital, selected_hospital_id) is None:
            raise HTTPException(status_code=422, detail="Assign a hospital to every doctor and hospital administrator")
    else:
        selected_hospital_id = None
    previous_role = target.role.value
    target.role = requested_role
    target.hospital_id = selected_hospital_id
    assigned_hospital = None
    profile = db.get(Profile, target.id)
    if profile is None:
        profile = Profile(
            id=target.id,
            firebase_uid=target.firebase_uid,
            full_name=payload.full_name or "CareKey user",
            email=target.email,
        )
        db.add(profile)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field not in {"role", "hospital_id"}:
            setattr(profile, field, value)
    if requested_role in {AppRole.DOCTOR, AppRole.HOSPITAL_ADMIN}:
        assigned_hospital = db.get(Hospital, selected_hospital_id)
        profile.organization = assigned_hospital.name
    db.add(target)
    db.add(profile)
    db.add(
        AccessLog(
            provider_name=(admin.email or str(admin.id))[:100],
            action=f"Admin changed {target.email or target.id} role from {previous_role} to {target.role.value}",
            categories=[],
            access_type="administration",
            verification_result="admin_role_change",
            success=True,
        )
    )
    db.commit()
    db.refresh(target)
    db.refresh(profile)
    return {
        "id": target.id,
        "email": target.email,
        "role": target.role,
        "is_active": target.is_active,
        "full_name": profile.full_name,
        "organization": profile.organization,
        "specialty": profile.specialty,
        "hospital_id": target.hospital_id,
        "hospital_name": assigned_hospital.name if assigned_hospital else None,
    }


@router.patch("/users/{user_id}/status", response_model=AdminUserResponse)
def update_doctor_status(
    user_id: UUID,
    payload: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(AppRole.ADMIN)),
) -> dict[str, Any]:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role != AppRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Only doctor accounts can be deactivated here")
    target.is_active = payload.is_active
    profile = db.get(Profile, target.id)
    db.add(target)
    assigned_hospital = db.get(Hospital, target.hospital_id) if target.hospital_id else None
    db.add(
        AccessLog(
            provider_name=(admin.email or str(admin.id))[:100],
            action=f"Admin {'activated' if payload.is_active else 'deactivated'} doctor {target.email or target.id}",
            categories=[],
            access_type="administration",
            verification_result="admin_doctor_status_change",
            success=True,
        )
    )
    db.commit()
    db.refresh(target)
    return {
        "id": target.id,
        "email": target.email,
        "role": target.role,
        "is_active": target.is_active,
        "full_name": profile.full_name if profile else None,
        "organization": profile.organization if profile else None,
        "specialty": profile.specialty if profile else None,
        "hospital_id": target.hospital_id,
        "hospital_name": assigned_hospital.name if assigned_hospital else None,
    }
