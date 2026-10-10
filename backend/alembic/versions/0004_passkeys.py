"""Store WebAuthn public credentials and short-lived challenges.

Revision ID: 0004_passkeys
Revises: 0003_user_is_active
Create Date: 2026-10-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_passkeys"
down_revision: Union[str, Sequence[str], None] = "0003_user_is_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "passkey_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_id", sa.String(length=1024), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_passkey_credentials_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_passkey_credentials"),
    )
    op.create_index("uq_passkey_credentials_credential_id", "passkey_credentials", ["credential_id"], unique=True)
    op.create_index("ix_passkey_credentials_user_id", "passkey_credentials", ["user_id"], unique=False)

    op.create_table(
        "passkey_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("challenge", sa.String(length=256), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("rp_id", sa.String(length=253), nullable=False),
        sa.Column("origin", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_passkey_challenges_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_passkey_challenges"),
    )
    op.create_index("ix_passkey_challenges_user_purpose", "passkey_challenges", ["user_id", "purpose"], unique=False)
    op.create_index("ix_passkey_challenges_expires_at", "passkey_challenges", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_passkey_challenges_expires_at", table_name="passkey_challenges")
    op.drop_index("ix_passkey_challenges_user_purpose", table_name="passkey_challenges")
    op.drop_table("passkey_challenges")
    op.drop_index("ix_passkey_credentials_user_id", table_name="passkey_credentials")
    op.drop_index("uq_passkey_credentials_credential_id", table_name="passkey_credentials")
    op.drop_table("passkey_credentials")
