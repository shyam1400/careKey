"""Add patient opt-in for emergency access notifications."""

from alembic import op
import sqlalchemy as sa


revision = "0006_emergency_alerts"
down_revision = "0005_passkey_reauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("emergency_contact_alerts_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("patients", "emergency_contact_alerts_enabled")
