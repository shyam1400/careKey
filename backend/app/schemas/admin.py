from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.hospital import HospitalCreate, HospitalResponse


class AdminUserUpdate(BaseModel):
    """Admin-managed profile fields. Admin roles are bootstrapped out of band."""

    role: Literal["patient", "doctor", "hospital", "hospital_admin"]
    hospital_id: UUID | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    organization: str | None = Field(default=None, max_length=120)
    specialty: str | None = Field(default=None, max_length=120)


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    full_name: str | None
    role: Literal["patient", "doctor", "hospital", "hospital_admin", "admin"]
    hospital_id: UUID | None = None
    hospital_name: str | None = None
    is_active: bool
    organization: str | None
    specialty: str | None


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


class HospitalAccountCreate(BaseModel):
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    hospital_id: UUID | None = None
    hospital: HospitalCreate | None = None


class HospitalAccountCreated(BaseModel):
    hospital: HospitalResponse
    account: AdminUserResponse
