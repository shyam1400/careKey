"""Add private report extraction runs and patient-reviewable candidates."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_report_extractions"
down_revision = "0010_health_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_extractions_patient_id", "report_extractions", ["patient_id"])
    op.create_index("ix_report_extractions_document_id", "report_extractions", ["document_id"])

    op.create_table(
        "report_extraction_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("measurement_type", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.Column("source_label", sa.String(length=100), nullable=False),
        sa.Column("review_status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("health_measurement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("review_status IN ('pending', 'verified', 'rejected')", name="ck_report_extraction_candidates_valid_review_status"),
        sa.ForeignKeyConstraint(["extraction_id"], ["report_extractions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["health_measurement_id"], ["health_measurements.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_extraction_candidates_extraction_id", "report_extraction_candidates", ["extraction_id"])


def downgrade() -> None:
    op.drop_index("ix_report_extraction_candidates_extraction_id", table_name="report_extraction_candidates")
    op.drop_table("report_extraction_candidates")
    op.drop_index("ix_report_extractions_document_id", table_name="report_extractions")
    op.drop_index("ix_report_extractions_patient_id", table_name="report_extractions")
    op.drop_table("report_extractions")
