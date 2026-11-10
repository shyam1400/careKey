from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt


class TrainedAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: dict[str, StrictInt | StrictFloat] = Field(min_length=1)
    defaulted_inputs: list[str] = Field(default_factory=list)
    patient_confirmed: bool


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
    minimum_age: int | None = None
    maximum_age: int | None = None
    chart_minimum_age: int | None = None
    chart_maximum_age: int | None = None
    input_schema: list[dict[str, Any]] = Field(default_factory=list)
    defaults: dict[str, int | float] | None = None
    dataset: str | None = None
    metrics: str | None = None
    availability_reason: str | None = None


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
    input_snapshot: dict[str, Any]
    summary: str | None
    assessed_at: datetime
