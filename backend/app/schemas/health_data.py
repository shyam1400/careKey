from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MeasurementType = Literal[
    "systolic_blood_pressure", "diastolic_blood_pressure", "height", "weight", "bmi",
    "waist_circumference",
    "total_cholesterol", "hdl_cholesterol", "ldl_cholesterol", "triglycerides",
    "fasting_glucose", "random_glucose", "hba1c", "serum_creatinine", "egfr", "uacr",
]
MeasurementSource = Literal["patient_reported", "home_device", "clinician_entered", "lab_report"]
FAMILY_RELATIONSHIPS = {"mother", "father", "sister", "brother", "daughter", "son", "grandmother", "grandfather", "aunt", "uncle", "other"}

ALLOWED_UNITS: dict[str, set[str]] = {
    "systolic_blood_pressure": {"mmHg"}, "diastolic_blood_pressure": {"mmHg"},
    "height": {"cm", "m", "in"}, "weight": {"kg", "lb"}, "bmi": {"kg/m2"},
    "waist_circumference": {"cm"},
    "total_cholesterol": {"mg/dL", "mmol/L"}, "hdl_cholesterol": {"mg/dL", "mmol/L"},
    "ldl_cholesterol": {"mg/dL", "mmol/L"}, "triglycerides": {"mg/dL", "mmol/L"},
    "fasting_glucose": {"mg/dL", "mmol/L"}, "random_glucose": {"mg/dL", "mmol/L"},
    "hba1c": {"%", "mmol/mol"}, "serum_creatinine": {"mg/dL", "umol/L"},
    "egfr": {"mL/min/1.73m2"}, "uacr": {"mg/g", "mg/mmol"},
}


class HealthMeasurementCreate(BaseModel):
    measurement_type: MeasurementType
    value: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    unit: str = Field(min_length=1, max_length=24)
    observed_at: datetime
    source_type: MeasurementSource = "patient_reported"
    source_document_id: UUID | None = None
    note: str | None = Field(default=None, max_length=500)

    @field_validator("observed_at")
    @classmethod
    def require_timezone_and_nonfuture(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Measurement date must include a timezone")
        if value > datetime.now(timezone.utc):
            raise ValueError("Measurement date cannot be in the future")
        return value

    @model_validator(mode="after")
    def validate_unit(self):
        if self.unit not in ALLOWED_UNITS[self.measurement_type]:
            raise ValueError(f"Unit is not supported for {self.measurement_type}")
        if self.source_type == "lab_report" and self.source_document_id is None:
            raise ValueError("Select the source report for a lab result")
        if self.measurement_type == "waist_circumference" and not Decimal("30") <= self.value <= Decimal("250"):
            raise ValueError("Waist circumference must be between 30 and 250 cm")
        return self


class FamilyHistoryCreate(BaseModel):
    relationship_to_patient: str = Field(min_length=1, max_length=24)
    condition: str = Field(min_length=1, max_length=120)
    age_at_diagnosis: int | None = Field(default=None, ge=0, le=120)
    diagnosis_date: date | None = None
    source_type: Literal["patient_reported", "clinician_entered", "medical_record"] = "patient_reported"
    source_document_id: UUID | None = None
    note: str | None = Field(default=None, max_length=500)

    @field_validator("relationship_to_patient")
    @classmethod
    def validate_relationship(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in FAMILY_RELATIONSHIPS:
            raise ValueError("Unsupported family relationship")
        return normalized

    @field_validator("condition")
    @classmethod
    def clean_condition(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Condition cannot be blank")
        return value

    @model_validator(mode="after")
    def require_record_reference(self):
        if self.source_type == "medical_record" and self.source_document_id is None:
            raise ValueError("Select the source medical record")
        return self


class PatientRiskFactorCreate(BaseModel):
    factor_key: Literal["current_smoking", "diabetes_status"]
    value: bool
    observed_at: datetime
    source_type: Literal["patient_reported", "clinician_entered", "medical_record"] = "patient_reported"
    source_document_id: UUID | None = None

    @field_validator("observed_at")
    @classmethod
    def require_timezone_and_nonfuture(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Date must include a timezone")
        if value > datetime.now(timezone.utc):
            raise ValueError("Date cannot be in the future")
        return value

    @model_validator(mode="after")
    def require_source_reference(self):
        if self.source_type == "medical_record" and self.source_document_id is None:
            raise ValueError("Select the source medical record")
        return self


class PatientAssessmentInputCreate(BaseModel):
    input_key: Literal["idrs_physical_activity", "idrs_parental_diabetes"]
    value: Literal["both", "either", "neither", "none", "one_parent", "both_parents"]
    observed_at: datetime
    source_type: Literal["patient_reported", "clinician_entered", "medical_record"] = "patient_reported"
    source_document_id: UUID | None = None

    @field_validator("observed_at")
    @classmethod
    def require_timezone_and_nonfuture(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Date must include a timezone")
        if value > datetime.now(timezone.utc):
            raise ValueError("Date cannot be in the future")
        return value

    @model_validator(mode="after")
    def validate_value_and_source(self):
        allowed = {
            "idrs_physical_activity": {"both", "either", "neither"},
            "idrs_parental_diabetes": {"none", "one_parent", "both_parents"},
        }
        if self.value not in allowed[self.input_key]:
            raise ValueError("Value is not valid for this IDRS input")
        if self.source_type == "medical_record" and self.source_document_id is None:
            raise ValueError("Select the source medical record")
        return self


class HealthMeasurementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    measurement_type: str
    value: Decimal
    unit: str
    observed_at: datetime
    source_type: str
    source_document_id: UUID | None
    verification_status: str
    verified_at: datetime | None = None
    verified_by: UUID | None = None
    note: str | None
    created_at: datetime


class FamilyHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    relationship_to_patient: str
    condition: str
    age_at_diagnosis: int | None
    diagnosis_date: date | None
    source_type: str
    source_document_id: UUID | None
    verification_status: str
    verified_at: datetime | None = None
    verified_by: UUID | None = None
    note: str | None
    created_at: datetime


class PatientRiskFactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    factor_key: str
    value: bool
    observed_at: datetime
    source_type: str
    source_document_id: UUID | None
    verification_status: str
    verified_at: datetime | None
    verified_by: UUID | None
    created_at: datetime


class PatientAssessmentInputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    input_key: str
    value: str
    observed_at: datetime
    source_type: str
    source_document_id: UUID | None
    verification_status: str
    verified_at: datetime | None
    verified_by: UUID | None
    created_at: datetime


class ReportExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    status: str
    candidate_count: int
    parser_version: str
    created_at: datetime


class ReportExtractionCandidateResponse(BaseModel):
    id: UUID
    measurement_type: str
    value: Decimal
    unit: str
    observed_at: datetime | None
    source_page: int
    source_label: str
    review_status: str
    health_measurement_id: UUID | None


class ReportExtractionDetailResponse(ReportExtractionResponse):
    candidates: list[ReportExtractionCandidateResponse]


class VerifyReportCandidate(BaseModel):
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_timezone_and_nonfuture(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Measurement date must include a timezone")
        if value > datetime.now(timezone.utc):
            raise ValueError("Measurement date cannot be in the future")
        return value
