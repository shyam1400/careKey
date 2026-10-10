from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminUserUpdate(BaseModel):
    """Admin-managed profile fields. Admin roles are bootstrapped out of band."""

    role: Literal["patient", "doctor"]
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    organization: str | None = Field(default=None, max_length=120)
    specialty: str | None = Field(default=None, max_length=120)


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    full_name: str | None
    role: Literal["patient", "doctor", "admin"]
    is_active: bool
    organization: str | None
    specialty: str | None


class AdminUserStatusUpdate(BaseModel):
    is_active: bool
