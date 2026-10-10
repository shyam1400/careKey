from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.user import User

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
    rows = db.scalars(
        select(AccessLog).where(AccessLog.patient_id == user.id)
        .order_by(AccessLog.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "provider_name": row.provider_name,
            "action": row.action,
            "categories": row.categories,
            "reason": row.reason,
            "access_type": row.access_type,
            "verification_result": row.verification_result,
            "success": row.success,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/admin")
def list_recent_activity(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(AppRole.ADMIN)),
) -> list[dict[str, Any]]:
    rows = db.scalars(select(AccessLog).order_by(AccessLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "provider_name": row.provider_name,
            "action": row.action,
            "success": row.success,
            "created_at": row.created_at,
        }
        for row in rows
    ]
