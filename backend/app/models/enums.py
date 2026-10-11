from enum import StrEnum


class AppRole(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    HOSPITAL = "hospital"
    # Kept for existing accounts created before Hospital became a first-class role.
    HOSPITAL_ADMIN = "hospital_admin"
    ADMIN = "admin"


class ConsentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REJECTED = "rejected"
