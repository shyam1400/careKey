from typing import Any
from uuid import UUID, uuid4
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums import AppRole
from app.models.patient import Patient
from app.models.records import Allergy, Condition, Document, Medication, Surgery
from app.models.user import User
from app.schemas.record import AllergyCreate, ConditionCreate, MedicationCreate, SurgeryCreate
from app.services.storage import create_download_url, create_upload_token, delete_object

router = APIRouter(prefix="/records", tags=["records"])

_KINDS: dict[str, tuple[type[Any], type[BaseModel]]] = {
    "allergies": (Allergy, AllergyCreate),
    "conditions": (Condition, ConditionCreate),
    "medications": (Medication, MedicationCreate),
    "surgeries": (Surgery, SurgeryCreate),
}


@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    patient_id = _patient_id(user, db)
    rows = db.scalars(
        select(Document).where(Document.patient_id == patient_id).order_by(Document.created_at.desc())
    ).all()
    return [_serialize(Document, row) for row in rows]


@router.post("/documents", status_code=status.HTTP_201_CREATED)
def add_document(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    patient_id = _patient_id(user, db)
    file_name = payload.get("file_name")
    doc_type = payload.get("doc_type", "other")
    storage_path = payload.get("storage_path")
    if not isinstance(file_name, str) or not file_name.strip() or len(file_name) > 150:
        raise HTTPException(status_code=422, detail="A valid file name is required")
    if not isinstance(storage_path, str) or not storage_path.startswith(f"{user.firebase_uid}/"):
        raise HTTPException(status_code=422, detail="Invalid storage path")
    row = Document(patient_id=patient_id, file_name=file_name, doc_type=str(doc_type)[:32], storage_path=storage_path)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(Document, row)


@router.post("/documents/upload-token")
def create_document_upload_token(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    _patient_id(user, db)
    file_name = payload.get("file_name")
    content_type = payload.get("content_type")
    if not isinstance(file_name, str) or not file_name.strip() or len(file_name) > 150:
        raise HTTPException(status_code=422, detail="A valid file name is required")
    allowed_types = {
        "application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp",
        "image/heic", "image/heif", "image/tiff", "image/bmp",
    }
    if not isinstance(content_type, str) or content_type.lower() not in allowed_types:
        raise HTTPException(status_code=422, detail="Only PDF and image files are allowed")
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file_name)[:100]
    path = f"{user.firebase_uid}/{uuid4()}-{safe_name}"
    token = create_upload_token(path)
    return {"path": path, "token": token}


@router.post("/documents/{document_id}/download-url")
def get_document_download_url(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    patient_id = _patient_id(user, db)
    row = db.scalar(select(Document).where(Document.id == document_id, Document.patient_id == patient_id))
    if row is None or not row.storage_path:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"url": create_download_url(row.storage_path)}


@router.delete("/documents/storage-object", status_code=status.HTTP_204_NO_CONTENT)
def delete_orphaned_storage_object(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    _patient_id(user, db)
    path = payload.get("path")
    if not isinstance(path, str) or not path.startswith(f"{user.firebase_uid}/"):
        raise HTTPException(status_code=404, detail="Storage object not found")
    delete_object(path)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    patient_id = _patient_id(user, db)
    row = db.scalar(select(Document).where(Document.id == document_id, Document.patient_id == patient_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if row.storage_path:
        delete_object(row.storage_path)
    db.delete(row)
    db.commit()


def _serialize(model: type[Any], row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in model.__table__.columns}


def _patient_id(user: User, db: Session) -> UUID:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can manage personal records")
    patient = db.scalar(select(Patient.id).where(Patient.id == user.id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


def _kind(kind: str) -> tuple[type[Any], type[BaseModel]]:
    try:
        return _KINDS[kind]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record category not found") from exc


def _patch_schema(schema: type[BaseModel]) -> type[BaseModel]:
    fields = {
        name: (field.annotation | None, None)
        for name, field in schema.model_fields.items()
    }
    return create_model(f"{schema.__name__}Patch", __config__=ConfigDict(extra="forbid"), **fields)


@router.get("/{kind}")
def list_records(
    kind: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    model, _ = _kind(kind)
    patient_id = _patient_id(user, db)
    rows = db.scalars(
        select(model).where(model.patient_id == patient_id).order_by(model.created_at.desc())
    ).all()
    return [_serialize(model, row) for row in rows]


@router.post("/{kind}", status_code=status.HTTP_201_CREATED)
def create_record(
    kind: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    model, schema = _kind(kind)
    patient_id = _patient_id(user, db)
    values = schema.model_validate(payload).model_dump()
    row = model(patient_id=patient_id, **values)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(model, row)


@router.patch("/{kind}/{record_id}")
def update_record(
    kind: str,
    record_id: UUID,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    model, schema = _kind(kind)
    patient_id = _patient_id(user, db)
    row = db.scalar(select(model).where(model.id == record_id, model.patient_id == patient_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    values = _patch_schema(schema).model_validate(payload).model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _serialize(model, row)


@router.delete("/{kind}/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    kind: str,
    record_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    model, _ = _kind(kind)
    patient_id = _patient_id(user, db)
    row = db.scalar(select(model).where(model.id == record_id, model.patient_id == patient_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(row)
    db.commit()
