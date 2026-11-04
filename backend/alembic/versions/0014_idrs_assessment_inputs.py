"""Add verified categorical inputs for the original IDRS assessment."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0014_idrs_assessment_inputs"
down_revision = "0013_who_cvd_chart_inputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_assessment_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_key", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=24), server_default="patient_reported", nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verification_status", sa.String(length=16), server_default="unverified", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(input_key = 'idrs_physical_activity' AND value IN ('both', 'either', 'neither')) OR "
            "(input_key = 'idrs_parental_diabetes' AND value IN ('none', 'one_parent', 'both_parents'))",
            name="valid_patient_assessment_input_value",
        ),
        sa.CheckConstraint("verification_status IN ('unverified', 'verified', 'rejected')", name="valid_patient_assessment_input_verification_status"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_assessment_inputs_patient_id", "patient_assessment_inputs", ["patient_id"])
    op.create_index("ix_patient_assessment_inputs_input_key", "patient_assessment_inputs", ["input_key"])


def downgrade() -> None:
    op.drop_index("ix_patient_assessment_inputs_input_key", table_name="patient_assessment_inputs")
    op.drop_index("ix_patient_assessment_inputs_patient_id", table_name="patient_assessment_inputs")
    op.drop_table("patient_assessment_inputs")
