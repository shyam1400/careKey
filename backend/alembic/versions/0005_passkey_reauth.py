"""Track the Firebase authentication used for patient passkey enrollment.

Revision ID: 0005_passkey_reauth
Revises: 0004_passkeys
Create Date: 2026-10-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_passkey_reauth"
down_revision: Union[str, Sequence[str], None] = "0004_passkeys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_passkey_registration_auth_time", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_passkey_registration_auth_time")
