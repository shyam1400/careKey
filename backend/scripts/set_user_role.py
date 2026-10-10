"""Backend-controlled role elevation for local development.

Usage (from the backend directory, venv active):

    python scripts/set_user_role.py --email user@example.com --role doctor

Roles are never accepted from the frontend. This script updates PostgreSQL only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.models.enums import AppRole
from app.models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(description="Set an application user's role.")
    parser.add_argument("--email", required=True, help="User email stored on first login")
    parser.add_argument(
        "--role",
        required=True,
        choices=[role.value for role in AppRole],
        help="New role (patient, doctor, or admin)",
    )
    args = parser.parse_args()
    role = AppRole(args.role)

    session: Session = get_session_factory()()
    try:
        user = session.scalar(select(User).where(User.email == args.email))
        if user is None:
            raise SystemExit(f"No application user with email {args.email!r}. Sign in once first.")
        user.role = role
        session.commit()
        print(f"Updated {user.email} ({user.firebase_uid}) to role={user.role.value}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
