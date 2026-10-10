# CareKey on free plans

This guide keeps the project off paid plans. Do not add a payment method or enable billing for any provider. Free plans can still change their quotas and may pause or disable service when limits are reached; they do not provide an uptime guarantee.

## Planned services

- **Sign-in:** Firebase Authentication on the Spark plan.
- **Frontend:** Cloudflare Workers Free. The regular `npm run build` uses the existing Nitro Cloudflare target.
- **API:** Render Free web service. Expect the service to sleep after inactivity and take time to wake up.
- **Database and private document storage:** Supabase Free. A free project may pause after inactivity and has storage, database, and bandwidth limits.

Do not use Firebase App Hosting for this setup: it requires the Blaze billing plan. The Firebase Hosting configuration in `FIREBASE_HOSTING.md` is an optional paid-plan path and is not part of this zero-cost setup.

## Supabase setup for document uploads

1. Use the existing Supabase project on its Free plan.
2. Create a private Storage bucket named `medical-documents`. Set a 10 MB file-size limit and allow PDF and image MIME types only.
3. Create a server-side secret API key in Supabase Project Settings → API Keys. Add it to the backend environment as `SUPABASE_SERVICE_ROLE_KEY`; also set `SUPABASE_URL` and `SUPABASE_STORAGE_BUCKET=medical-documents`.
4. Keep the secret key out of the frontend, `.env.example`, source control, and chat. The frontend uses only the Supabase URL and publishable key to upload to short-lived signed URLs issued by the API.

The current local backend `.env` has no Supabase secret key, so upload-token, download-link, and storage-delete calls return a configuration error until the backend secret and bucket are configured.

## Deployment order

1. Create a Supabase Free project and run the backend Alembic migrations against its PostgreSQL connection string. Use the direct connection string if the deployment host supports IPv6; otherwise use Supabase's session pooler.
2. Deploy `backend` as a Render Free web service using the repository's `render.yaml` Blueprint. It installs `backend/requirements.txt`, applies Alembic upgrades to the new hosted database at startup, and starts Uvicorn. Set its environment variables from `backend/.env.example`, including the Firebase Admin credential configuration, Supabase storage values, and `CORS_ORIGINS`. Upload the Firebase service-account JSON in the Render service's Environment → Secret Files as `firebase-service-account.json`; Render exposes it at `/etc/secrets/firebase-service-account.json`.
3. In Cloudflare Workers & Pages, connect this repository and set the production branch to `new` and the root directory to `/`. Use `npm install` as the install command, `npm run build` as the build command, and `npx nitro deploy --prebuilt` as the deploy command. For preview deployments, use `npx wrangler preview` or disable previews. Add the browser variables from the root `.env.example` as build variables, including `VITE_CAREKEY_API_URL` for the public Render API URL. The Firebase web configuration and Supabase publishable key are public client settings; never add private service credentials there.
4. Add the Cloudflare site's origin to the backend `CORS_ORIGINS`, redeploy the API, then verify sign-in, profile load, consent grant/revoke, emergency access logging, and a document upload/download/delete.

For the one-time trusted first-admin bootstrap and subsequent doctor provisioning, follow [ADMIN_SETUP.md](ADMIN_SETUP.md).

Cloudflare Workers Free has request and CPU limits. Render Free may sleep when idle. Supabase Free may pause inactive projects and has finite database, storage, and egress quotas. When any limit blocks the app, keep the services on their free plans and reduce usage or wait for quota reset; do not upgrade or add billing details.

## Local verification

```powershell
# frontend type check
npx tsc --noEmit

# frontend build
npm run build

# backend tests (from backend)
pytest -q
```

Cloud deployment has not been performed from this workspace.
