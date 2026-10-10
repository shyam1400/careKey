from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HospitalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = None
    phone: str | None = Field(default=None, max_length=32)
    emergency: bool = True
    trauma: bool = False
    ambulance: bool = True
    open_24h: bool = True


class HospitalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = None
    phone: str | None = Field(default=None, max_length=32)
    emergency: bool | None = None
    trauma: bool | None = None
    ambulance: bool | None = None
    open_24h: bool | None = None


class HospitalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    latitude: float
    longitude: float
    address: str | None
    phone: str | None
    emergency: bool
    trauma: bool
    ambulance: bool
    open_24h: bool
