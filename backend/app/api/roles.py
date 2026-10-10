"""Minimal role-gated probes so RBAC can be exercised without domain APIs."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.enums import AppRole
from app.models.profile import Profile
from app.models.user import User
from app.schemas.auth import AuthMeResponse

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/patient", response_model=AuthMeResponse)
def patient_access(user: User = Depends(require_roles(AppRole.PATIENT))) -> User:
    return user


@router.get("/doctor", response_model=AuthMeResponse)
def doctor_access(user: User = Depends(require_roles(AppRole.DOCTOR))) -> User:
    return user


@router.get("/admin", response_model=AuthMeResponse)
def admin_access(user: User = Depends(require_roles(AppRole.ADMIN))) -> User:
    return user


@router.get("/doctors")
def list_doctors(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(User.id, Profile.full_name, Profile.organization, Profile.specialty)
        .join(Profile, Profile.id == User.id)
        .where(User.role == AppRole.DOCTOR, User.is_active.is_(True))
        .order_by(Profile.full_name)
    ).all()
    return [
        {"id": str(row.id), "full_name": row.full_name, "organization": row.organization, "specialty": row.specialty}
        for row in rows
    ]
