from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums import AppRole
from app.models.health_data import FamilyHistory, HealthMeasurement, ReportExtraction, ReportExtractionCandidate
from app.models.patient import Patient
from app.models.records import Document
from app.models.user import User
from app.schemas.health_data import (
    FamilyHistoryCreate, FamilyHistoryResponse,
    HealthMeasurementCreate, HealthMeasurementResponse,
    ReportExtractionDetailResponse, ReportExtractionResponse, VerifyReportCandidate,
)
from app.services.report_extraction import PARSER_VERSION, extract_lab_candidates
from app.services.storage import download_object

router = APIRouter(prefix="/health-data", tags=["health-data"])


def _patient_id(user: User, db: Session) -> UUID:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can manage their health data")
    patient_id = db.scalar(select(Patient.id).where(Patient.id == user.id))
    if patient_id is None:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient_id


def _validate_source_document(
    db: Session, patient_id: UUID, document_id: UUID | None, *, expected_doc_type: str | None = None,
) -> None:
    if document_id is None:
        return
    document = db.scalar(select(Document).where(Document.id == document_id, Document.patient_id == patient_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Source document not found")
    if expected_doc_type and document.doc_type != expected_doc_type:
        raise HTTPException(status_code=422, detail="Source document must be a lab report")


@router.get("/measurements", response_model=list[HealthMeasurementResponse])
def list_measurements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    return db.scalars(select(HealthMeasurement).where(HealthMeasurement.patient_id == patient_id).order_by(HealthMeasurement.observed_at.desc()).limit(500)).all()


@router.post("/measurements", response_model=HealthMeasurementResponse, status_code=status.HTTP_201_CREATED)
def create_measurement(payload: HealthMeasurementCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    _validate_source_document(
        db, patient_id, payload.source_document_id,
        expected_doc_type="lab_report" if payload.source_type == "lab_report" else None,
    )
    row = HealthMeasurement(patient_id=patient_id, verification_status="unverified", **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/measurements/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_measurement(measurement_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    patient_id = _patient_id(user, db)
    row = db.scalar(select(HealthMeasurement).where(HealthMeasurement.id == measurement_id, HealthMeasurement.patient_id == patient_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    db.delete(row)
    db.commit()


@router.get("/family-history", response_model=list[FamilyHistoryResponse])
def list_family_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    return db.scalars(select(FamilyHistory).where(FamilyHistory.patient_id == patient_id).order_by(FamilyHistory.created_at.desc()).limit(500)).all()


@router.post("/family-history", response_model=FamilyHistoryResponse, status_code=status.HTTP_201_CREATED)
def create_family_history(payload: FamilyHistoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    _validate_source_document(db, patient_id, payload.source_document_id)
    row = FamilyHistory(patient_id=patient_id, verification_status="unverified", **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/reports/{document_id}/extract", response_model=ReportExtractionResponse, status_code=status.HTTP_201_CREATED)
def extract_report(document_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    document = db.scalar(select(Document).where(Document.id == document_id, Document.patient_id == patient_id))
    if document is None or not document.storage_path:
        raise HTTPException(status_code=404, detail="Report not found")
    if document.doc_type != "lab_report":
        raise HTTPException(status_code=422, detail="Only documents categorized as lab reports can be extracted")
    pdf_bytes = download_object(document.storage_path)
    candidates = extract_lab_candidates(pdf_bytes)
    extraction = ReportExtraction(
        patient_id=patient_id, document_id=document.id, parser_version=PARSER_VERSION,
        status="review_required" if candidates else "no_candidates", candidate_count=len(candidates),
    )
    db.add(extraction)
    db.flush()
    for candidate in candidates:
        db.add(ReportExtractionCandidate(
            extraction_id=extraction.id, measurement_type=candidate.measurement_type,
            value=candidate.value, unit=candidate.unit, source_page=candidate.source_page,
            source_label=candidate.source_label, review_status="pending",
        ))
    db.commit()
    db.refresh(extraction)
    return extraction


@router.get("/extractions/{extraction_id}", response_model=ReportExtractionDetailResponse)
def read_extraction(extraction_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    extraction = db.scalar(select(ReportExtraction).where(
        ReportExtraction.id == extraction_id, ReportExtraction.patient_id == patient_id,
    ))
    if extraction is None:
        raise HTTPException(status_code=404, detail="Report extraction not found")
    candidates = db.scalars(select(ReportExtractionCandidate).where(
        ReportExtractionCandidate.extraction_id == extraction.id,
    ).order_by(ReportExtractionCandidate.source_page, ReportExtractionCandidate.measurement_type)).all()
    return {**ReportExtractionResponse.model_validate(extraction).model_dump(), "candidates": candidates}


@router.post("/extractions/candidates/{candidate_id}/verify", response_model=HealthMeasurementResponse, status_code=status.HTTP_201_CREATED)
def verify_report_candidate(
    candidate_id: UUID, payload: VerifyReportCandidate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    patient_id = _patient_id(user, db)
    candidate = db.scalar(select(ReportExtractionCandidate).join(
        ReportExtraction, ReportExtraction.id == ReportExtractionCandidate.extraction_id,
    ).where(
        ReportExtractionCandidate.id == candidate_id,
        ReportExtraction.patient_id == patient_id,
    ))
    if candidate is None:
        raise HTTPException(status_code=404, detail="Extracted value not found")
    if candidate.review_status != "pending":
        raise HTTPException(status_code=409, detail="Extracted value has already been reviewed")
    extraction = db.get(ReportExtraction, candidate.extraction_id)
    measurement = HealthMeasurement(
        patient_id=patient_id, measurement_type=candidate.measurement_type, value=candidate.value,
        unit=candidate.unit, observed_at=payload.observed_at, source_type="lab_report",
        source_document_id=extraction.document_id, verification_status="verified",
        note=f"Patient verified extracted value from report page {candidate.source_page}",
    )
    candidate.review_status = "verified"
    candidate.reviewed_at = datetime.now(timezone.utc)
    db.add(measurement)
    db.flush()
    candidate.health_measurement_id = measurement.id
    db.add(candidate)
    db.commit()
    db.refresh(measurement)
    return measurement


@router.post("/extractions/candidates/{candidate_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_report_candidate(candidate_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    patient_id = _patient_id(user, db)
    candidate = db.scalar(select(ReportExtractionCandidate).join(
        ReportExtraction, ReportExtraction.id == ReportExtractionCandidate.extraction_id,
    ).where(
        ReportExtractionCandidate.id == candidate_id,
        ReportExtraction.patient_id == patient_id,
    ))
    if candidate is None:
        raise HTTPException(status_code=404, detail="Extracted value not found")
    if candidate.review_status != "pending":
        raise HTTPException(status_code=409, detail="Extracted value has already been reviewed")
    candidate.review_status = "rejected"
    candidate.reviewed_at = datetime.now(timezone.utc)
    db.add(candidate)
    db.commit()


@router.delete("/family-history/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_family_history(history_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    patient_id = _patient_id(user, db)
    row = db.scalar(select(FamilyHistory).where(FamilyHistory.id == history_id, FamilyHistory.patient_id == patient_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Family history entry not found")
    db.delete(row)
    db.commit()
