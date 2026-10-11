import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { createUserWithEmailAndPassword, signInWithEmailAndPassword, updateProfile } from "firebase/auth";
import { useAuth, type Role } from "@/hooks/useAuth";
import { getFirebaseAuth, isFirebaseConfigured } from "@/lib/firebase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CareKeyLogo } from "@/components/CareKeyLogo";
import { ThemeToggle } from "@/components/ThemeToggle";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "Sign in — CareKey" },
      {
        name: "description",
        content: "Sign in or register a CareKey demo account as a patient, doctor or admin.",
      },
      { property: "og:title", content: "Sign in — CareKey" },
      {
        property: "og:description",
        content: "Access your CareKey emergency profile, records and sharing controls.",
      },
    ],
  }),
  component: AuthPage,
});

const schema = z.object({
  email: z.string().trim().email("Enter a valid email").max(255),
  password: z.string().min(6, "Password must be at least 6 characters").max(72),
  fullName: z.string().trim().max(100).optional(),
});

const roleHome: Record<Role, string> = {
  patient: "/dashboard",
  doctor: "/doctor",
  hospital: "/hospital-account",
  hospital_admin: "/hospital-account",
  admin: "/admin",
};

function AuthPage() {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false);
  const { session, role: currentRole, loading, accountError, refresh } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && session && currentRole) {
      void navigate({ to: roleHome[currentRole] });
    }
  }, [loading, session, currentRole, navigate]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = schema.safeParse({ email, password, fullName });
    if (!parsed.success) {
      toast.error(parsed.error.issues[0].message);
      return;
    }
    if (!isFirebaseConfigured()) {
      toast.error("Firebase client settings are missing. Configure the VITE_FIREBASE_* environment values.");
      return;
    }
    setBusy(true);
    try {
      const auth = getFirebaseAuth();
      if (mode === "signup") {
        const credential = await createUserWithEmailAndPassword(
          auth,
          parsed.data.email,
          parsed.data.password,
        );
        await updateProfile(credential.user, { displayName: fullName.trim() || parsed.data.email });
        await credential.user.getIdToken(true);
        const assignedRole = await refresh();
        if (!assignedRole) throw new Error("Your account was created, but CareKey could not finish setting it up. Please try signing in again.");
        toast.success("Account created. Signing you in…");
        await navigate({ to: roleHome[assignedRole] });
      } else {
        const credential = await signInWithEmailAndPassword(auth, parsed.data.email, parsed.data.password);
        await credential.user.getIdToken(true);
        const assignedRole = await refresh();
        if (assignedRole) await navigate({ to: roleHome[assignedRole] });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <div className="bg-warning-soft px-4 py-1.5 text-center text-xs font-medium text-warning-foreground">
        Research Prototype — Not for Clinical Use. Use synthetic data only.
      </div>
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <CareKeyLogo linked={false} />
        <div className="flex items-center gap-2">
          <Link to="/" className="rounded-md px-3 py-2 text-sm text-muted-foreground transition hover:bg-secondary hover:text-foreground">Back to home</Link>
          <ThemeToggle />
        </div>
      </header>
      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="card-surface w-full max-w-md p-8">
          <div className="mb-6"><CareKeyLogo linked={false} /></div>
          <h1 className="text-xl font-semibold">
            {mode === "signin" ? "Sign in" : "Create an account"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "signin"
              ? "Sign in with your CareKey account."
              : "Create a patient account. Doctor and admin access is provisioned by an administrator."}
          </p>

          {accountError ? (
            <div role="alert" className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {accountError}
            </div>
          ) : null}

          <form className="mt-6 space-y-4" onSubmit={submit}>
            {mode === "signup" ? (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="fullName">Full name</Label>
                  <Input
                    id="fullName"
                    value={fullName}
                    maxLength={100}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Aarav Mehta"
                  />
                </div>
              </>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                maxLength={255}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                maxLength={72}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <button
            type="button"
            className="mt-5 w-full text-center text-sm text-muted-foreground underline-offset-4 hover:underline"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          >
            {mode === "signin"
              ? "No account? Register a demo account"
              : "Already registered? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
