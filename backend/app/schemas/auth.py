from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import AppRole


class AuthMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    firebase_uid: str
    email: str | None
    is_active: bool
    role: AppRole
    doctor_code: str | None = None
    hospital_id: UUID | None = None
    hospital_name: str | None = None
    created_at: datetime
    updated_at: datetime
