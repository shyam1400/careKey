from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums import AppRole
from app.models.audit import AccessLog
from app.models.health_data import HealthAssessment
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.user import User
from app.schemas.assessment import AssessmentToolResponse, HealthAssessmentResponse
from app.services.assessment_engine import TOOLS, run_calculator

router = APIRouter(prefix="/health-assessments", tags=["health-assessments"])


def _audit(db: Session, patient_id: UUID, user: User, action: str, *, success: bool, model_key: str | None = None) -> None:
    profile = db.scalar(select(Profile).where(Profile.id == user.id))
    db.add(AccessLog(
        patient_id=patient_id, provider_id=user.id,
        provider_name=profile.full_name if profile else ("Patient" if user.role == AppRole.PATIENT else "Care provider"),
        action=action[:500], categories=["health_assessments"],
        reason=(model_key or "Patient health assessment")[:64],
        access_type="health_assessment", success=success,
    ))
    db.commit()


def _patient_id(user: User, db: Session) -> UUID:
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can manage their health assessments")
    patient_id = db.scalar(select(Patient.id).where(Patient.id == user.id))
    if patient_id is None:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient_id


@router.get("/models", response_model=list[AssessmentToolResponse])
def list_assessment_models(user: User = Depends(get_current_user)):
    if user.role != AppRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can view assessment models")
    return [AssessmentToolResponse(
        key=tool.key, name=tool.name, category=tool.category, version=tool.version,
        intended_use=tool.intended_use, validated_population=tool.validated_population,
        required_inputs=list(tool.required_inputs), limitations=list(tool.limitations),
        source_url=tool.source_url, license_status=tool.license_status, availability=tool.availability,
    ) for tool in TOOLS.values()]


@router.get("/history", response_model=list[HealthAssessmentResponse])
def list_my_assessments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    rows = db.scalars(select(HealthAssessment).where(
        HealthAssessment.patient_id == patient_id,
    ).order_by(HealthAssessment.assessed_at.desc()).limit(100)).all()
    _audit(db, patient_id, user, "Patient viewed assessment history", success=True)
    return rows


@router.get("/{assessment_id}", response_model=HealthAssessmentResponse)
def read_my_assessment(assessment_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    assessment = db.scalar(select(HealthAssessment).where(
        HealthAssessment.id == assessment_id, HealthAssessment.patient_id == patient_id,
    ))
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _audit(db, patient_id, user, "Patient viewed a health assessment", success=True, model_key=assessment.model_key)
    return assessment


@router.post("/{model_key}/run", response_model=HealthAssessmentResponse)
def generate_assessment(model_key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient_id = _patient_id(user, db)
    try:
        run_calculator(model_key, {})
    except KeyError:
        _audit(db, patient_id, user, "Health assessment generation attempted for unknown model", success=False, model_key=model_key)
        raise HTTPException(status_code=404, detail="Assessment model not found") from None
    except PermissionError as exc:
        _audit(db, patient_id, user, "Health assessment generation blocked", success=False, model_key=model_key)
        raise HTTPException(status_code=409, detail=str(exc)) from None
    raise HTTPException(status_code=422, detail="Assessment inputs are not yet available")
