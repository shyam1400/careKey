# CareKey API

CareKey is a research prototype built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, and Firebase Authentication. It includes patient profiles, patient-managed provider consent, a restricted emergency summary with server-side access logs, Medical ID lookup support, and a hospital directory. It does not implement biometric verification or a QR image renderer.

## Requirements

- Python 3.11+
- PostgreSQL 14+
- A Firebase project with Firebase Authentication enabled

## Local setup

From the backend directory, create a virtual environment, install dependencies, and create `.env`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set `DATABASE_URL` and configure `FIREBASE_PROJECT_ID` and `FIREBASE_CREDENTIALS_PATH` in `.env`. Store the Firebase service-account JSON at the configured path and keep both it and `.env` out of Git.

Apply migrations and start the API:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

OpenAPI documentation is at `http://localhost:8000/docs`. `/health/ready` checks the PostgreSQL connection.

## API

All authenticated requests use `Authorization: Bearer <Firebase ID token>`. Firebase Admin verifies tokens, including revoked-token checks. Application roles are read from the database; new verified users start as patients. Assign doctor and admin roles through a trusted backend process.

| Method and path | Purpose | Access |
| --- | --- | --- |
| `GET /health`, `GET /health/ready` | Liveness and database readiness | Public |
| `GET /auth/me` | Current application user | Authenticated |
| `POST /patients`, `GET /patients/{patient_id}`, `PATCH /patients/{patient_id}` | Create and manage a patient profile | Patient owns their record; admins can read records |
| `GET /patients/me/medical-id` | Return own Medical ID and canonical QR payload (`carekey://medical-id/{id}`) | Patient |
| `POST /consents` | Grant a doctor named permissions with an optional expiry | Patient |
| `GET /consents` | List the caller's grants | Patient or doctor |
| `POST /consents/{consent_id}/revoke` | Revoke an active grant | Owning patient |
| `POST /emergency/{medical_id}` | Read a restricted emergency summary; requires a reason and writes an access log for successful and denied attempts | Doctor role |
| `GET /hospitals` | Filter and page through hospitals | Public |
| `POST /hospitals` | Add a hospital | Admin |
| `GET /roles/patient`, `GET /roles/doctor`, `GET /roles/admin` | Role-gated probes | Matching role |
| `GET/POST/DELETE /health-data/measurements` | Store patient measurements with units, timestamps, source and verification state | Owning patient |
| `GET/POST/DELETE /health-data/family-history` | Store family conditions and diagnosis timing with source attribution | Owning patient |
| `POST /health-data/reports/{document_id}/extract` | Extract candidate lab values from a private, text-based PDF | Owning patient |
| `GET /health-data/extractions/{id}`, `POST .../candidates/{id}/verify`, `POST .../reject` | Review candidate values; only patient-confirmed values become verified measurements | Owning patient |
| `GET /health-assessments/models`, `GET /health-assessments/history` | View supported-tool catalog and own assessment history | Patient |
| `GET /consents/{consent_id}/assessments` | Read assessments while the doctor’s approved affiliation and the patient’s active `health_assessments` grant remain valid | Authorized doctor |

### AI Health Intelligence foundation

Migrations `0010`–`0012` add measurements, family history, report extraction runs and candidates, and versioned assessment snapshots. Patient-entered and extracted values begin unverified. The current extractor runs locally in the API process, reads private storage server-side, and persists only normalized candidate values, page references, and review state; it does not persist report text or send it to a third-party AI/OCR service. It currently supports labeled results in text-based PDFs only. Scanned PDFs and images are not supported. Patients must confirm each extracted result and its measurement date before a verified lab measurement is created.

The model catalog is intentionally present but all risk calculators are disabled pending tool-specific licensing/use review and implementations. It currently describes AHA PREVENT; the Indian Diabetes Risk Score (screening for prevalent/undiagnosed diabetes, not future-onset risk); QDiabetes-2018 (10-year risk for its UK population); and NCI BCRAT/Gail breast cancer risk. Model population eligibility and limitations are included in the catalog. `POST /health-assessments/{model_key}/run` therefore returns a conflict until a calculator is licensed and enabled. Do not treat catalog entries as available clinical results. Health assessment sharing is a separate patient-selected consent category; doctor reads are permission-checked and audited.

The QR payload is a string for a client to render as a QR code. After scanning, the client can submit the Medical ID to the emergency endpoint; the server still requires a doctor token and a reason. Emergency access is audited and does not claim face or biometric verification. The hospital directory does not yet calculate nearest facilities or routing.

## Verification

Run the backend suite from this directory:

```powershell
pytest -q
```

The suite mocks Firebase token verification and uses fake database sessions for route tests. It does not verify a live Firebase credential or replace integration testing against a disposable PostgreSQL database.

## Configuration

See [`.env.example`](.env.example). Firebase credentials are required for real authenticated requests. Private medical document uploads use Supabase Storage signed URLs; configure `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a private `medical-documents` bucket before enabling uploads. Keep the Storage service key only in the backend environment. OSRM routing is not implemented.

## Emergency contact alerts

Patients can opt in from **Profile → Emergency contact**. After a doctor successfully verifies a passkey and reads an emergency profile, CareKey queues an SMS and automated voice call to the saved contact. Alerts identify the patient, doctor, the organization listed on the doctor's CareKey profile, and the access time; they do not include medical details. Notification delivery is best-effort and does not affect emergency profile access.

Configure these server-only environment variables to enable the opt-in control and delivery:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER` (your Twilio number in E.164 format)

All three are required. Never put the auth token in frontend environment variables. Twilio trial accounts restrict destinations and calling countries, and may not allow custom SMS content; verify the intended emergency-contact number in Twilio and check trial-account capabilities before relying on SMS. The voice call is attempted separately, so one channel failing does not suppress the other.
