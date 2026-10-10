import { getApp, getApps, initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export function isFirebaseConfigured() {
  return [config.apiKey, config.authDomain, config.projectId, config.appId].every(
    (value) => typeof value === "string" && value.length > 0,
  );
}

export function getFirebaseAuth() {
  if (!isFirebaseConfigured()) {
    throw new Error("Firebase is not configured. Set the VITE_FIREBASE_* values in the local environment.");
  }
  const app = getApps().length ? getApp() : initializeApp(config);
  return getAuth(app);
}
