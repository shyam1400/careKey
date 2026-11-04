from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssessmentToolResponse(BaseModel):
    key: str
    name: str
    category: str
    version: str
    intended_use: str
    validated_population: str
    required_inputs: list[str]
    limitations: list[str]
    source_url: str
    license_status: str
    availability: str


class HealthAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    model_key: str
    model_version: str
    status: str
    result: dict[str, Any] | None
    contributing_factors: list[dict[str, Any]]
    missing_information: list[str]
    source_references: list[dict[str, Any]]
    summary: str | None
    assessed_at: datetime
