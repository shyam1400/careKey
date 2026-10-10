from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PasskeyRegistrationVerify(BaseModel):
    challenge_id: UUID
    credential: dict[str, Any]


class PasskeyListItem(BaseModel):
    id: UUID
    created_at: datetime
    last_used_at: datetime | None


class PasskeyOptions(BaseModel):
    challenge_id: UUID
    options: dict[str, Any]


class PasskeyAssertion(BaseModel):
    challenge_id: UUID
    credential: dict[str, Any]
