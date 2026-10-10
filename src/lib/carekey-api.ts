import type { User } from "firebase/auth";

export type FirebaseTokenProvider = Pick<User, "getIdToken">;

const apiBaseUrl = (import.meta.env.VITE_CAREKEY_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class CareKeyApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "CareKeyApiError";
  }
}

export type AppRole = "patient" | "doctor" | "admin";

export type AppUser = {
  id: string;
  firebase_uid: string;
  email: string | null;
  is_active: boolean;
  role: AppRole;
  created_at: string;
  updated_at: string;
};

export type Patient = {
  id: string;
  medical_id: string;
  full_name: string | null;
  email: string | null;
  organization?: string | null;
  specialty?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  phone?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  blood_group?: string | null;
  rh_factor?: string | null;
};

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let message = `CareKey API request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the status-based message when the API did not return JSON.
    }
    throw new CareKeyApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function loadAppUser(firebaseUser: User): Promise<{ user: AppUser; patient: Patient | null }> {
  const token = await firebaseUser.getIdToken();
  const user = await request<AppUser>("/auth/me", token);
  if (user.role !== "patient") return { user, patient: null };

  let patient: Patient;
  try {
    patient = await request<Patient>(`/patients/${user.id}`, token);
  } catch (error) {
    if (!(error instanceof CareKeyApiError) || error.status !== 404) throw error;
    patient = await request<Patient>("/patients", token, {
      method: "POST",
      body: JSON.stringify({ full_name: firebaseUser.displayName || firebaseUser.email || "CareKey patient" }),
    });
  }
  return { user, patient };
}

export function carekeyRequest<T>(path: string, firebaseUser: FirebaseTokenProvider, init?: RequestInit) {
  return firebaseUser.getIdToken().then((token) => request<T>(path, token, init));
}

export async function regenerateMedicalId(firebaseUser: FirebaseTokenProvider) {
  const token = await firebaseUser.getIdToken();
  return request<{ medical_id: string; qr_payload: string }>(
    "/patients/me/medical-id/regenerate",
    token,
    { method: "POST" },
  );
}
