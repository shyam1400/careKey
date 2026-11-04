"""Add immutable, versioned patient assessment history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_health_assessments"
down_revision = "0011_report_extractions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_key", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("contributing_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_information", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_assessments_patient_id", "health_assessments", ["patient_id"])
    op.create_index("ix_health_assessments_model_key", "health_assessments", ["model_key"])


def downgrade() -> None:
    op.drop_index("ix_health_assessments_model_key", table_name="health_assessments")
    op.drop_index("ix_health_assessments_patient_id", table_name="health_assessments")
    op.drop_table("health_assessments")
