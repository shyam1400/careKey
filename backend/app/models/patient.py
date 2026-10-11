from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.ids import generate_medical_id

if TYPE_CHECKING:
    from app.models.consent import Consent
    from app.models.profile import Profile
    from app.models.records import Allergy, Condition, Document, Medication, Surgery


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    medical_id: Mapped[str] = mapped_column(
        String(11),
        unique=True,
        nullable=False,
        default=generate_medical_id,
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_contact_alerts_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    blood_group: Mapped[str | None] = mapped_column(String(8), nullable=True)
    rh_factor: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="patient")
    allergies: Mapped[list["Allergy"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    conditions: Mapped[list["Condition"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    medications: Mapped[list["Medication"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    surgeries: Mapped[list["Surgery"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    consents: Mapped[list["Consent"]] = relationship(back_populates="patient", cascade="all, delete-orphan")

    @property
    def firebase_uid(self) -> str | None:
        return self.profile.firebase_uid if self.profile is not None else None

    @property
    def full_name(self) -> str | None:
        return self.profile.full_name if self.profile is not None else None

    @property
    def email(self) -> str | None:
        return self.profile.email if self.profile is not None else None

    @property
    def created_at(self) -> datetime | None:
        return self.profile.created_at if self.profile is not None else None
