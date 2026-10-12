from pydantic import BaseModel, Field


class AffiliationRequest(BaseModel):
    code: str = Field(pattern=r"^(DOC|HOS)-[A-F0-9]{8}$", min_length=12, max_length=12)


class AffiliationDecision(BaseModel):
    approve: bool
