from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class HospitalProcedureCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    name: str = Field(min_length=1, max_length=160)
    notes: str | None = None


class HospitalDoctorUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    specialty: str | None = Field(default=None, max_length=120)


class HospitalProcedureUpdate(BaseModel):
    doctor_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = None
    status: Literal["planned", "in_progress", "completed", "cancelled"] | None = None


class HospitalProcedureResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    patient_name: str
    doctor_id: UUID
    doctor_name: str
    name: str
    status: str
    notes: str | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
