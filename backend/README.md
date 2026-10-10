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

The QR payload is a string for a client to render as a QR code. After scanning, the client can submit the Medical ID to the emergency endpoint; the server still requires a doctor token and a reason. Emergency access is audited and does not claim face or biometric verification. The hospital directory does not yet calculate nearest facilities or routing.

## Verification

Run the backend suite from this directory:

```powershell
pytest -q
```

The suite mocks Firebase token verification and uses fake database sessions for route tests. It does not verify a live Firebase credential or replace integration testing against a disposable PostgreSQL database.

## Configuration

See [`.env.example`](.env.example). Firebase credentials are required for real authenticated requests. Private medical document uploads use Supabase Storage signed URLs; configure `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a private `medical-documents` bucket before enabling uploads. Keep the Storage service key only in the backend environment. OSRM routing is not implemented.
