import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  onAuthStateChanged,
  signOut as firebaseSignOut,
  type User,
} from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { loadAppUser, type AppRole, type Patient } from "@/lib/carekey-api";

export type Role = AppRole;
export type Profile = Pick<Patient, "id" | "full_name" | "email" | "organization" | "specialty">;
export type AuthenticatedUser = Pick<User, "email" | "displayName" | "getIdToken"> & {
  id: string;
  firebaseUid: string;
};

type AuthState = {
  loading: boolean;
  session: User | null;
  user: AuthenticatedUser | null;
  profile: Profile | null;
  role: Role | null;
  medicalId: string | null;
  accountError: string | null;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<User | null>(null);
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [medicalId, setMedicalId] = useState<string | null>(null);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function bootstrap(user: User | null) {
    setAccountError(null);
    if (!user) {
      setUser(null);
      setProfile(null);
      setRole(null);
      setMedicalId(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const result = await loadAppUser(user);
      setUser({
        id: result.user.id,
        firebaseUid: result.user.firebase_uid,
        email: user.email,
        displayName: user.displayName,
        getIdToken: (forceRefresh) => user.getIdToken(forceRefresh),
      });
      setRole(result.user.role);
      if (result.patient) {
        setProfile({ ...result.patient, email: result.patient.email ?? user.email });
        setMedicalId(result.patient.medical_id);
      } else {
        setProfile({
          id: result.user.id,
          full_name: user.displayName || user.email || "CareKey user",
          email: result.user.email,
          organization: null,
          specialty: null,
        });
        setMedicalId(null);
      }
    } catch (error) {
      console.error("Could not load the CareKey account", error);
      setAccountError(
        error instanceof Error
          ? `Your sign-in succeeded, but CareKey could not finish setting up your account: ${error.message}`
          : "Your sign-in succeeded, but CareKey could not finish setting up your account. Please try again.",
      );
      setProfile(null);
      setRole(null);
      setMedicalId(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    try {
      unsubscribe = onAuthStateChanged(getFirebaseAuth(), (nextUser) => {
        setSession(nextUser);
        void bootstrap(nextUser);
      });
    } catch (error) {
      console.error("Firebase Auth could not be started", error);
      setLoading(false);
    }
    return () => unsubscribe?.();
  }, []);

  const value: AuthState = {
    loading,
    session,
    user,
    profile,
    role,
    medicalId,
    accountError,
    refresh: async () => bootstrap(getFirebaseAuth().currentUser),
    signOut: async () => firebaseSignOut(getFirebaseAuth()),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
