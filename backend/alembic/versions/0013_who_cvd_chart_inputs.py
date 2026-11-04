"""Add verified patient inputs for WHO 2019 South Asia CVD chart."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_who_cvd_chart_inputs"
down_revision = "0012_health_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("health_measurements", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("health_measurements", sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_health_measurements_verified_by_profiles", "health_measurements", "profiles",
        ["verified_by"], ["id"], ondelete="SET NULL",
    )
    op.create_table(
        "patient_risk_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("factor_key", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=24), server_default="patient_reported", nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verification_status", sa.String(length=16), server_default="unverified", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("factor_key IN ('current_smoking', 'diabetes_status')", name="ck_patient_risk_factors_valid_risk_factor_key"),
        sa.CheckConstraint("verification_status IN ('unverified', 'verified', 'rejected')", name="ck_patient_risk_factors_valid_risk_factor_verification_status"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_risk_factors_patient_id", "patient_risk_factors", ["patient_id"])
    op.create_index("ix_patient_risk_factors_factor_key", "patient_risk_factors", ["factor_key"])


def downgrade() -> None:
    op.drop_index("ix_patient_risk_factors_factor_key", table_name="patient_risk_factors")
    op.drop_index("ix_patient_risk_factors_patient_id", table_name="patient_risk_factors")
    op.drop_table("patient_risk_factors")
    op.drop_constraint("fk_health_measurements_verified_by_profiles", "health_measurements", type_="foreignkey")
    op.drop_column("health_measurements", "verified_by")
    op.drop_column("health_measurements", "verified_at")
