from datetime import date

from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from typing import Any


class EmergencyAccessRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=500)
    hospital_id: UUID
    passkey_challenge_id: UUID
    passkey_credential: dict[str, Any]

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 4:
            raise ValueError("Reason must contain at least 4 non-whitespace characters")
        return value


class EmergencyAllergy(BaseModel):
    allergen: str
    reaction: str | None
    severity: str


class EmergencyCondition(BaseModel):
    name: str
    status: str
    critical: bool


class EmergencyMedication(BaseModel):
    name: str
    dosage: str | None
    frequency: str | None


class EmergencyProfileResponse(BaseModel):
    medical_id: str
    full_name: str | None
    date_of_birth: date | None
    blood_group: str | None
    rh_factor: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    allergies: list[EmergencyAllergy]
    critical_conditions: list[EmergencyCondition]
    active_medications: list[EmergencyMedication]
