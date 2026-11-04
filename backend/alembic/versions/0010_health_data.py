"""Add patient health measurements and family history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_health_data"
down_revision = "0009_staff_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("measurement_type", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verification_status", sa.String(length=16), server_default="unverified", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("verification_status IN ('unverified', 'verified', 'rejected')", name="ck_health_measurements_valid_verification_status"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_measurements_patient_id", "health_measurements", ["patient_id"])
    op.create_index("ix_health_measurements_measurement_type", "health_measurements", ["measurement_type"])

    op.create_table(
        "family_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_to_patient", sa.String(length=24), nullable=False),
        sa.Column("condition", sa.String(length=120), nullable=False),
        sa.Column("age_at_diagnosis", sa.Integer(), nullable=True),
        sa.Column("diagnosis_date", sa.Date(), nullable=True),
        sa.Column("source_type", sa.String(length=24), server_default="patient_reported", nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verification_status", sa.String(length=16), server_default="unverified", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("verification_status IN ('unverified', 'verified', 'rejected')", name="ck_family_history_valid_verification_status"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_family_history_patient_id", "family_history", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_family_history_patient_id", table_name="family_history")
    op.drop_table("family_history")
    op.drop_index("ix_health_measurements_measurement_type", table_name="health_measurements")
    op.drop_index("ix_health_measurements_patient_id", table_name="health_measurements")
    op.drop_table("health_measurements")
