"""Add hospital as a first-class application account role."""

from alembic import op


revision = "0008_hospital_role"
down_revision = "0007_hospital_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep hospital_admin for existing deployments; new hospital accounts use hospital.
    op.execute("ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'hospital'")
    # This constraint was created with raw SQL in 0007, so use its literal name.
    # op.drop_constraint applies the metadata naming convention and would prefix it twice.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_staff_hospital_required")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_staff_hospital_required "
        "CHECK (role::text NOT IN ('doctor', 'hospital', 'hospital_admin') OR hospital_id IS NOT NULL) NOT VALID"
    )


def downgrade() -> None:
    # PostgreSQL enum labels are intentionally retained on downgrade; rebuilding the
    # enum could invalidate existing user_roles or users rows.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_staff_hospital_required")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_staff_hospital_required "
        "CHECK (role::text NOT IN ('doctor', 'hospital', 'hospital_admin') OR hospital_id IS NOT NULL) NOT VALID"
    )
