"""Initial CareKey schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

app_role = postgresql.ENUM(
    "patient", "doctor", "admin", name="app_role", create_type=False
)
consent_status = postgresql.ENUM(
    "pending",
    "active",
    "expired",
    "revoked",
    "rejected",
    name="consent_status",
    create_type=False,
)


def upgrade() -> None:
    app_role.create(op.get_bind(), checkfirst=True)
    consent_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=True),
        sa.Column("full_name", sa.String(length=100), nullable=False, server_default="Unnamed"),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("organization", sa.String(length=120), nullable=True),
        sa.Column("specialty", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_profiles"),
        sa.UniqueConstraint("firebase_uid", name="uq_profiles_firebase_uid"),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", app_role, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE", name="fk_user_roles_user_id_profiles"),
        sa.PrimaryKeyConstraint("id", name="pk_user_roles"),
        sa.UniqueConstraint("user_id", "role", name="uq_user_roles_user_id_role"),
    )

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medical_id", sa.String(length=11), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("emergency_contact_name", sa.String(length=100), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(length=20), nullable=True),
        sa.Column("blood_group", sa.String(length=8), nullable=True),
        sa.Column("rh_factor", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["profiles.id"], ondelete="CASCADE", name="fk_patients_id_profiles"),
        sa.PrimaryKeyConstraint("id", name="pk_patients"),
        sa.UniqueConstraint("medical_id", name="uq_patients_medical_id"),
    )

    op.create_table(
        "allergies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allergen", sa.String(length=80), nullable=False),
        sa.Column("reaction", sa.String(length=120), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="mild"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE", name="fk_allergies_patient_id_patients"),
        sa.PrimaryKeyConstraint("id", name="pk_allergies"),
    )

    op.create_table(
        "conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("diagnosis_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("critical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE", name="fk_conditions_patient_id_patients"),
        sa.PrimaryKeyConstraint("id", name="pk_conditions"),
    )

    op.create_table(
        "medications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("dosage", sa.String(length=60), nullable=True),
        sa.Column("frequency", sa.String(length=60), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE", name="fk_medications_patient_id_patients"),
        sa.PrimaryKeyConstraint("id", name="pk_medications"),
    )

    op.create_table(
        "surgeries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("procedure", sa.String(length=120), nullable=False),
        sa.Column("surgery_date", sa.Date(), nullable=True),
        sa.Column("hospital", sa.String(length=120), nullable=True),
        sa.Column("major", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE", name="fk_surgeries_patient_id_patients"),
        sa.PrimaryKeyConstraint("id", name="pk_surgeries"),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=150), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE", name="fk_documents_patient_id_patients"),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )

    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permissions", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("purpose", sa.String(length=64), nullable=False, server_default="Consultation"),
        sa.Column("status", consent_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE", name="fk_consents_patient_id_patients"),
        sa.ForeignKeyConstraint(["provider_id"], ["profiles.id"], ondelete="CASCADE", name="fk_consents_provider_id_profiles"),
        sa.PrimaryKeyConstraint("id", name="pk_consents"),
    )

    op.create_table(
        "access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("medical_id", sa.String(length=11), nullable=True),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("categories", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("access_type", sa.String(length=32), nullable=False, server_default="consent"),
        sa.Column("verification_result", sa.String(length=64), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL", name="fk_access_logs_patient_id_patients"),
        sa.ForeignKeyConstraint(["provider_id"], ["profiles.id"], ondelete="SET NULL", name="fk_access_logs_provider_id_profiles"),
        sa.PrimaryKeyConstraint("id", name="pk_access_logs"),
    )

    op.create_table(
        "hospitals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("emergency", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("trauma", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ambulance", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("open_24h", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_hospitals"),
    )


def downgrade() -> None:
    op.drop_table("hospitals")
    op.drop_table("access_logs")
    op.drop_table("consents")
    op.drop_table("documents")
    op.drop_table("surgeries")
    op.drop_table("medications")
    op.drop_table("conditions")
    op.drop_table("allergies")
    op.drop_table("patients")
    op.drop_table("user_roles")
    op.drop_table("profiles")
    consent_status.drop(op.get_bind(), checkfirst=True)
    app_role.drop(op.get_bind(), checkfirst=True)
