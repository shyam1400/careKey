"""Firebase Admin SDK initialization and ID-token verification."""

from dataclasses import dataclass
from pathlib import Path

import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin import App as FirebaseApp
from firebase_admin.auth import (
    CertificateFetchError,
    ExpiredIdTokenError,
    InvalidIdTokenError,
    RevokedIdTokenError,
    UserDisabledError,
)

from app.core.config import get_settings

_firebase_app: FirebaseApp | None = None


class FirebaseNotConfiguredError(RuntimeError):
    """Raised when Firebase Admin cannot start because env or credentials are missing."""


def firebase_is_configured() -> bool:
    """True when project id and a readable credentials file are set."""
    settings = get_settings()
    project_id = (settings.firebase_project_id or "").strip()
    creds_path = (settings.firebase_credentials_path or "").strip()
    return bool(project_id and creds_path and Path(creds_path).is_file())


def get_firebase_app() -> FirebaseApp:
    """Return the singleton Firebase Admin app, initializing it on first use."""
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    try:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app
    except ValueError:
        pass

    settings = get_settings()
    project_id = (settings.firebase_project_id or "").strip()
    creds_path = (settings.firebase_credentials_path or "").strip()

    if not project_id or not creds_path:
        raise FirebaseNotConfiguredError(
            "Firebase is not configured. Set FIREBASE_PROJECT_ID and "
            "FIREBASE_CREDENTIALS_PATH to a service-account JSON file."
        )

    path = Path(creds_path)
    if not path.is_file():
        raise FirebaseNotConfiguredError(f"Firebase credentials file not found: {path}")

    cred = credentials.Certificate(path)
    _firebase_app = firebase_admin.initialize_app(
        cred,
        options={"projectId": project_id},
    )
    return _firebase_app


@dataclass(frozen=True)
class FirebaseIdentity:
    """Claims taken from a verified Firebase ID token only."""

    firebase_uid: str
    email: str | None
    auth_time: int | None = None


class FirebaseTokenError(Exception):
    """Verified-token failure. `reason` is a stable code for HTTP mapping."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def verify_id_token(id_token: str) -> FirebaseIdentity:
    """Verify a Firebase ID token and return uid/email from Firebase, not the client."""
    token = (id_token or "").strip()
    if not token:
        raise FirebaseTokenError("invalid")

    try:
        decoded = auth.verify_id_token(token, app=get_firebase_app(), check_revoked=True)
    except FirebaseNotConfiguredError:
        raise
    except ExpiredIdTokenError as exc:
        raise FirebaseTokenError("expired") from exc
    except RevokedIdTokenError as exc:
        raise FirebaseTokenError("revoked") from exc
    except UserDisabledError as exc:
        raise FirebaseTokenError("disabled") from exc
    except CertificateFetchError as exc:
        raise FirebaseTokenError("unavailable") from exc
    except (InvalidIdTokenError, ValueError) as exc:
        raise FirebaseTokenError("invalid") from exc

    uid = decoded.get("uid")
    if not isinstance(uid, str) or not uid.strip():
        raise FirebaseTokenError("invalid")

    raw_email = decoded.get("email")
    email = raw_email.strip() if isinstance(raw_email, str) and raw_email.strip() else None
    auth_time = decoded.get("auth_time")
    return FirebaseIdentity(
        firebase_uid=uid.strip(),
        email=email,
        auth_time=auth_time if isinstance(auth_time, int) else None,
    )
