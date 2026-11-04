from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.records import Document


class HealthMeasurement(Base):
    __tablename__ = "health_measurements"
    __table_args__ = (
        CheckConstraint("verification_status IN ('unverified', 'verified', 'rejected')", name="valid_verification_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    measurement_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified", server_default="unverified")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    patient: Mapped["Patient"] = relationship()
    source_document: Mapped["Document | None"] = relationship()


class FamilyHistory(Base):
    __tablename__ = "family_history"
    __table_args__ = (
        CheckConstraint("verification_status IN ('unverified', 'verified', 'rejected')", name="valid_verification_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_to_patient: Mapped[str] = mapped_column(String(24), nullable=False)
    condition: Mapped[str] = mapped_column(String(120), nullable=False)
    age_at_diagnosis: Mapped[int | None] = mapped_column(nullable=True)
    diagnosis_date: Mapped[date | None] = mapped_column(nullable=True)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, default="patient_reported", server_default="patient_reported")
    source_document_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified", server_default="unverified")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    patient: Mapped["Patient"] = relationship()
    source_document: Mapped["Document | None"] = relationship()


class ReportExtraction(Base):
    __tablename__ = "report_extractions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    candidate_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReportExtractionCandidate(Base):
    __tablename__ = "report_extraction_candidates"
    __table_args__ = (
        CheckConstraint("review_status IN ('pending', 'verified', 'rejected')", name="valid_review_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    extraction_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("report_extractions.id", ondelete="CASCADE"), nullable=False, index=True)
    measurement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_page: Mapped[int] = mapped_column(nullable=False)
    source_label: Mapped[str] = mapped_column(String(100), nullable=False)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    health_measurement_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("health_measurements.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    extraction: Mapped["ReportExtraction"] = relationship()


class HealthAssessment(Base):
    """Immutable snapshot of one versioned disease-specific assessment."""
    __tablename__ = "health_assessments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    model_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    contributing_factors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_information: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_references: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
