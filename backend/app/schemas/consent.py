from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ConsentStatus

SUPPORTED_PERMISSIONS = {
    "basic", "blood", "allergies", "medications", "conditions", "surgeries",
    "prescriptions", "lab_reports", "documents",
}


class ConsentCreate(BaseModel):
    provider_id: UUID
    permissions: list[str] = Field(min_length=1, max_length=20)
    purpose: str = Field(default="Consultation", min_length=1, max_length=64)
    expires_at: datetime | None = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, values: list[str]) -> list[str]:
        unsupported = set(values) - SUPPORTED_PERMISSIONS
        if unsupported:
            raise ValueError("One or more selected record categories are not available for sharing yet")
        return values

    @field_validator("expires_at")
    @classmethod
    def validate_expiration_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Consent expiration must include a timezone")
        return value


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    provider_id: UUID
    permissions: list[str]
    purpose: str
    status: ConsentStatus
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
