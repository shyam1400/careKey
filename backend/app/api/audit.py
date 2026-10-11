from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.user import User
from app.models.hospital import Hospital

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/me")
def list_my_access_logs(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    if user.role != AppRole.PATIENT:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Only patients can view their access history")
    rows = db.execute(
        select(AccessLog, Hospital.name)
        .outerjoin(User, User.id == AccessLog.provider_id)
        .outerjoin(Hospital, Hospital.id == func.coalesce(AccessLog.hospital_id, User.hospital_id))
        .where(AccessLog.patient_id == user.id)
        .order_by(AccessLog.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": log.id,
            "provider_name": log.provider_name,
            "hospital_name": log.hospital_name or hospital_name,
            "action": log.action,
            "categories": log.categories,
            "reason": log.reason,
            "access_type": log.access_type,
            "verification_result": log.verification_result,
            "success": log.success,
            "created_at": log.created_at,
        }
        for log, hospital_name in rows
    ]


@router.get("/admin")
def list_recent_activity(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(AppRole.ADMIN)),
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AccessLog, Hospital.name)
        .outerjoin(User, User.id == AccessLog.provider_id)
        .outerjoin(Hospital, Hospital.id == func.coalesce(AccessLog.hospital_id, User.hospital_id))
        .order_by(AccessLog.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": log.id,
            "provider_name": log.provider_name,
            "hospital_name": log.hospital_name or hospital_name,
            "hospital_id": log.hospital_id,
            "action": log.action,
            "success": log.success,
            "created_at": log.created_at,
        }
        for log, hospital_name in rows
    ]
