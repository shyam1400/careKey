from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.audit import router as audit_router
from app.api.admin import router as admin_router
from app.api.consents import router as consents_router
from app.api.emergency import router as emergency_router
from app.api.health import router as health_router
from app.api.hospitals import router as hospitals_router
from app.api.patients import router as patients_router
from app.api.roles import router as roles_router
from app.api.records import router as records_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "CareKey API (research prototype). Authentication uses Firebase ID tokens. "
        "Role checks read the application user role from the database. "
        "Patient, consent, audited emergency profile, and hospital APIs are available for this research prototype."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(patients_router)
app.include_router(records_router)
app.include_router(consents_router)
app.include_router(audit_router)
app.include_router(admin_router)
app.include_router(emergency_router)
app.include_router(hospitals_router)
