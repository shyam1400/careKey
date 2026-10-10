from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)
    blood_group: str | None = Field(default=None, max_length=8)
    rh_factor: str | None = Field(default=None, max_length=16)


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)
    blood_group: str | None = Field(default=None, max_length=8)
    rh_factor: str | None = Field(default=None, max_length=16)


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medical_id: str
    firebase_uid: str | None = None
    full_name: str | None = None
    email: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    phone: str | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    blood_group: str | None = None
    rh_factor: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            medical_id=obj.medical_id,
            firebase_uid=getattr(obj, "firebase_uid", None),
            full_name=getattr(obj, "full_name", None),
            email=getattr(obj, "email", None),
            date_of_birth=getattr(obj, "date_of_birth", None),
            gender=getattr(obj, "gender", None),
            phone=getattr(obj, "phone", None),
            address=getattr(obj, "address", None),
            emergency_contact_name=getattr(obj, "emergency_contact_name", None),
            emergency_contact_phone=getattr(obj, "emergency_contact_phone", None),
            blood_group=getattr(obj, "blood_group", None),
            rh_factor=getattr(obj, "rh_factor", None),
            created_at=getattr(obj, "created_at", None),
            updated_at=getattr(obj, "updated_at", None),
        )


class PatientMedicalIdResponse(BaseModel):
    medical_id: str
    qr_payload: str
