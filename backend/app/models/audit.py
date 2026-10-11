from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccessLog(Base):
    __tablename__ = "access_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    medical_id: Mapped[str | None] = mapped_column(String(11), nullable=True)
    provider_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hospital_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    hospital_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_type: Mapped[str] = mapped_column(String(32), nullable=False, default="consent")
    verification_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
