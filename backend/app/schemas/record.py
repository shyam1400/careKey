from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecordBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    created_at: datetime


class AllergyCreate(BaseModel):
    allergen: str = Field(min_length=1, max_length=80)
    reaction: str | None = Field(default=None, max_length=120)
    severity: str = Field(default="mild", max_length=16)


class ConditionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    diagnosis_date: date | None = None
    status: str = Field(default="active", max_length=32)
    critical: bool = False
    notes: str | None = None


class MedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dosage: str | None = Field(default=None, max_length=60)
    frequency: str | None = Field(default=None, max_length=60)
    start_date: date | None = None
    end_date: date | None = None
    active: bool = True


class SurgeryCreate(BaseModel):
    procedure: str = Field(min_length=1, max_length=120)
    surgery_date: date | None = None
    hospital: str | None = Field(default=None, max_length=120)
    major: bool = False
    notes: str | None = None


class AllergyResponse(RecordBase):
    allergen: str
    reaction: str | None
    severity: str


class ConditionResponse(RecordBase):
    name: str
    diagnosis_date: date | None
    status: str
    critical: bool
    notes: str | None


class MedicationResponse(RecordBase):
    name: str
    dosage: str | None
    frequency: str | None
    start_date: date | None
    end_date: date | None
    active: bool


class SurgeryResponse(RecordBase):
    procedure: str
    surgery_date: date | None
    hospital: str | None
    major: bool
    notes: str | None
