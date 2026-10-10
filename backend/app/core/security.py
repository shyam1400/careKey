"""Firebase ID-token authentication and role checks for FastAPI routes."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.firebase import (
    FirebaseIdentity,
    FirebaseNotConfiguredError,
    FirebaseTokenError,
    verify_id_token,
)
from app.models.enums import AppRole
from app.models.user import User
from app.services.users import get_or_create_user_from_identity

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = {
    "missing": "Missing authorization token",
    "invalid": "Invalid authorization token",
    "expired": "Authorization token has expired",
    "revoked": "Authorization token has been revoked",
    "disabled": "User account is disabled",
}


def _http_error(status_code: int, detail: str) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
    return HTTPException(status_code=status_code, detail=detail, headers=headers)


def get_firebase_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> FirebaseIdentity:
    """Read Authorization: Bearer <token> and verify it with Firebase Admin."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _http_error(status.HTTP_401_UNAUTHORIZED, _UNAUTHORIZED["missing"])

    try:
        return verify_id_token(credentials.credentials)
    except FirebaseNotConfiguredError as exc:
        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Authentication is not configured",
        ) from exc
    except FirebaseTokenError as exc:
        if exc.reason == "unavailable":
            raise _http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Authentication service unavailable",
            ) from exc
        raise _http_error(
            status.HTTP_401_UNAUTHORIZED,
            _UNAUTHORIZED.get(exc.reason, _UNAUTHORIZED["invalid"]),
        ) from exc


def get_current_user(
    identity: FirebaseIdentity = Depends(get_firebase_identity),
    db: Session = Depends(get_db),
) -> User:
    """Return the application user for a verified Firebase identity.

    Role is never taken from the request. New users are bootstrapped as patients.
    """
    user = get_or_create_user_from_identity(db, identity)
    if not user.is_active:
        raise _http_error(status.HTTP_401_UNAUTHORIZED, _UNAUTHORIZED["disabled"])
    user._firebase_auth_time = identity.auth_time
    return user


def require_roles(*allowed_roles: AppRole) -> Callable[..., User]:
    """Allow the request only when the database user role is one of ``allowed_roles``.

    Role is loaded from the ``users`` row, never from the request body, query, or headers.
    """
    if not allowed_roles:
        raise ValueError("require_roles requires at least one role")

    allowed = frozenset(allowed_roles)

    def _require_roles(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        stored = db.scalar(select(User).where(User.id == user.id))
        if stored is None:
            raise _http_error(status.HTTP_401_UNAUTHORIZED, _UNAUTHORIZED["invalid"])
        if not stored.is_active:
            raise _http_error(status.HTTP_401_UNAUTHORIZED, _UNAUTHORIZED["disabled"])
        if stored.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return stored

    return _require_roles
