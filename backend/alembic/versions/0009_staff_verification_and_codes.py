"""Add verification-based multi-hospital doctor affiliations and lookup codes."""

import secrets
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_staff_verification"
down_revision = "0008_hospital_role"
branch_labels = None
depends_on = None


def _code(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def upgrade() -> None:
    op.add_column("users", sa.Column("doctor_code", sa.String(length=12), nullable=True))
    op.add_column("hospitals", sa.Column("hospital_code", sa.String(length=12), nullable=True))
    op.create_unique_constraint("uq_users_doctor_code", "users", ["doctor_code"])
    op.create_unique_constraint("uq_hospitals_hospital_code", "hospitals", ["hospital_code"])

    connection = op.get_bind()
    doctors = connection.execute(sa.text("SELECT id FROM users WHERE role::text = 'doctor' AND doctor_code IS NULL")).all()
    hospitals = connection.execute(sa.text("SELECT id FROM hospitals WHERE hospital_code IS NULL")).all()
    for (doctor_id,) in doctors:
        connection.execute(sa.text("UPDATE users SET doctor_code = :code WHERE id = :id"), {"id": doctor_id, "code": _code("DOC")})
    for (hospital_id,) in hospitals:
        connection.execute(sa.text("UPDATE hospitals SET hospital_code = :code WHERE id = :id"), {"id": hospital_id, "code": _code("HOS")})
    op.alter_column("hospitals", "hospital_code", nullable=False)

    op.create_table(
        "hospital_doctor_affiliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("initiated_by", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], name="fk_hospital_doctor_affiliations_doctor_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"], name="fk_hospital_doctor_affiliations_hospital_id_hospitals", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], name="fk_hospital_doctor_affiliations_decided_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_hospital_doctor_affiliations"),
        sa.UniqueConstraint("hospital_id", "doctor_id", name="hospital_doctor_pair"),
        sa.CheckConstraint("status IN ('pending_hospital', 'pending_doctor', 'approved', 'denied')", name="ck_hospital_doctor_affiliations_valid_status"),
        sa.CheckConstraint("initiated_by IN ('doctor', 'hospital', 'migration')", name="ck_hospital_doctor_affiliations_valid_initiator"),
    )
    op.create_index("ix_hospital_doctor_affiliations_hospital_id", "hospital_doctor_affiliations", ["hospital_id"])
    op.create_index("ix_hospital_doctor_affiliations_doctor_id", "hospital_doctor_affiliations", ["doctor_id"])

    # Existing doctor-to-hospital assignments are grandfathered as approved links.
    affiliations = sa.table(
        "hospital_doctor_affiliations",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("hospital_id", postgresql.UUID(as_uuid=True)),
        sa.column("doctor_id", postgresql.UUID(as_uuid=True)),
        sa.column("status", sa.String()),
        sa.column("initiated_by", sa.String()),
    )
    legacy = connection.execute(sa.text("SELECT id, hospital_id FROM users WHERE role::text = 'doctor' AND hospital_id IS NOT NULL")).all()
    if legacy:
        connection.execute(affiliations.insert(), [
            {"id": uuid.uuid4(), "hospital_id": hospital_id, "doctor_id": doctor_id,
             "status": "approved", "initiated_by": "migration"}
            for doctor_id, hospital_id in legacy
        ])

    # Preserve attribution on historical audit rows before clearing the legacy field.
    connection.execute(sa.text("""
        UPDATE access_logs AS logs
        SET hospital_id = users.hospital_id,
            hospital_name = hospitals.name
        FROM users JOIN hospitals ON hospitals.id = users.hospital_id
        WHERE logs.provider_id = users.id
          AND users.role::text = 'doctor'
          AND logs.hospital_id IS NULL
    """))

    # Doctors now get hospital assignments only through approved affiliations.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_staff_hospital_required")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_staff_hospital_required "
        "CHECK (role::text NOT IN ('hospital', 'hospital_admin') OR hospital_id IS NOT NULL) NOT VALID"
    )
    op.execute("UPDATE users SET hospital_id = NULL WHERE role::text = 'doctor'")


def downgrade() -> None:
    # Preserve current data on downgrade; restore the former single-hospital check
    # only when all doctors are assigned to that legacy column.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_staff_hospital_required")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_staff_hospital_required "
        "CHECK (role::text NOT IN ('doctor', 'hospital', 'hospital_admin') OR hospital_id IS NOT NULL) NOT VALID"
    )
    op.drop_index("ix_hospital_doctor_affiliations_doctor_id", table_name="hospital_doctor_affiliations")
    op.drop_index("ix_hospital_doctor_affiliations_hospital_id", table_name="hospital_doctor_affiliations")
    op.drop_table("hospital_doctor_affiliations")
    op.drop_constraint("uq_hospitals_hospital_code", "hospitals", type_="unique")
    op.drop_column("hospitals", "hospital_code")
    op.drop_constraint("uq_users_doctor_code", "users", type_="unique")
    op.drop_column("users", "doctor_code")
