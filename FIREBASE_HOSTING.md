# Firebase deployment setup

The frontend is configured for Firebase App Hosting with `npm run build:firebase` and `apphosting.yaml`.

Before connecting the repository in Firebase Console:

1. In the connected Supabase project, create a **private** Storage bucket named `medical-documents`, set its maximum file size to 10 MB, and allow only PDF and supported image MIME types. Keep usage within the Free plan's storage and bandwidth quotas.
2. Deploy the FastAPI backend and PostgreSQL database to a public HTTPS endpoint. The current database and backend configuration are local; App Hosting cannot reach them.
3. In the App Hosting backend's build environment, set `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, and `VITE_CAREKEY_API_URL` to the browser config and public backend URL. These are browser configuration values; never place Firebase service-account credentials or a Supabase service-role key here.
4. Add the App Hosting domain to the backend's `CORS_ORIGINS` setting, then connect the repository and choose the `backend`-independent app root (the repository root) and build command `npm run build:firebase`.

Create a Supabase secret API key in Project Settings → API Keys and set it only in the FastAPI backend as `SUPABASE_SERVICE_ROLE_KEY`; also set `SUPABASE_URL` and `SUPABASE_STORAGE_BUCKET=medical-documents`. Do not add the secret to frontend environment variables or source control. Supabase Free has storage and bandwidth quotas and may pause inactive projects.

Firebase App Hosting requires a billing account and the Blaze plan, even though it has no-cost usage allowances. If you do not want to link billing, this SSR hosting target cannot be deployed there; the existing Cloudflare Worker build is the no-billing hosting alternative to evaluate. No cloud deployment has been run from this workspace.
