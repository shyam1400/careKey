"""Add hospital accounts, doctor affiliation, audit hospital snapshots and procedure tracking."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_hospital_accounts"
down_revision = "0006_emergency_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enum values are intentionally retained on downgrade: removing a value
    # safely requires rebuilding the enum and can invalidate rows in live databases.
    op.execute("ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'hospital_admin'")

    op.add_column("users", sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_users_hospital_id", "users", ["hospital_id"])
    op.create_foreign_key(
        "fk_users_hospital_id_hospitals", "users", "hospitals", ["hospital_id"], ["id"], ondelete="SET NULL"
    )
    # Existing unassigned doctor rows can be repaired from the platform admin UI;
    # NOT VALID skips historical rows but enforces the rule on all new/changed rows.
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_staff_hospital_required "
        "CHECK (role::text NOT IN ('doctor', 'hospital_admin') OR hospital_id IS NOT NULL) NOT VALID"
    )

    op.add_column("access_logs", sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("access_logs", sa.Column("hospital_name", sa.String(length=200), nullable=True))
    op.create_index("ix_access_logs_hospital_id", "access_logs", ["hospital_id"])
    op.create_foreign_key(
        "fk_access_logs_hospital_id_hospitals", "access_logs", "hospitals", ["hospital_id"], ["id"], ondelete="SET NULL"
    )

    op.create_table(
        "hospital_procedures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="in_progress", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], name="fk_hospital_procedures_doctor_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"], name="fk_hospital_procedures_hospital_id_hospitals", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], name="fk_hospital_procedures_patient_id_patients", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_hospital_procedures"),
    )
    op.create_index("ix_hospital_procedures_hospital_id", "hospital_procedures", ["hospital_id"])
    op.create_index("ix_hospital_procedures_patient_id", "hospital_procedures", ["patient_id"])
    op.create_index("ix_hospital_procedures_doctor_id", "hospital_procedures", ["doctor_id"])


def downgrade() -> None:
    op.drop_index("ix_hospital_procedures_doctor_id", table_name="hospital_procedures")
    op.drop_index("ix_hospital_procedures_patient_id", table_name="hospital_procedures")
    op.drop_index("ix_hospital_procedures_hospital_id", table_name="hospital_procedures")
    op.drop_table("hospital_procedures")
    op.drop_constraint("fk_access_logs_hospital_id_hospitals", "access_logs", type_="foreignkey")
    op.drop_index("ix_access_logs_hospital_id", table_name="access_logs")
    op.drop_column("access_logs", "hospital_name")
    op.drop_column("access_logs", "hospital_id")
    op.drop_constraint("fk_users_hospital_id_hospitals", "users", type_="foreignkey")
    op.drop_constraint("ck_users_staff_hospital_required", "users", type_="check")
    op.drop_index("ix_users_hospital_id", table_name="users")
    op.drop_column("users", "hospital_id")
