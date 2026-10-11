from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AppRole

if TYPE_CHECKING:
    from app.models.hospital import Hospital


class User(Base):
    """Firebase-authenticated application user.

    ``role`` is stored in the database and is the only source for authorization.
    """

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_firebase_uid", "firebase_uid", unique=True),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    firebase_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    hospital_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    hospital: Mapped["Hospital | None"] = relationship(lazy="joined")

    @property
    def hospital_name(self) -> str | None:
        return self.hospital.name if self.hospital is not None else None
    last_passkey_registration_auth_time: Mapped[int | None] = mapped_column(nullable=True)
    role: Mapped[AppRole] = mapped_column(
        ENUM(
            AppRole,
            name="app_role",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
