import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { EmailAuthProvider, reauthenticateWithCredential } from "firebase/auth";
import {
  startAuthentication,
  startRegistration,
  type PublicKeyCredentialCreationOptionsJSON,
  type PublicKeyCredentialRequestOptionsJSON,
} from "@simplewebauthn/browser";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { carekeyRequest } from "@/lib/carekey-api";
import { patientPasskeyOptionsPath } from "@/lib/passkey-device";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type PasskeyEntry = { id: string; created_at: string; last_used_at: string | null };

export function PatientPasskeyPanel() {
  const { user, session } = useAuth();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [registration, setRegistration] = useState<{
    challengeId: string;
    options: PublicKeyCredentialCreationOptionsJSON;
  } | null>(null);
  const [verification, setVerification] = useState<{
    challengeId: string;
    options: PublicKeyCredentialRequestOptionsJSON;
  } | null>(null);

  const passkeys = useQuery({
    queryKey: ["patient-passkeys", user?.id],
    enabled: !!user,
    queryFn: () => carekeyRequest<PasskeyEntry[]>("/auth/passkeys", user!),
  });

  async function beginRegistration() {
    if (!user || !session?.email) {
      toast.error("Sign in with your email and password before adding a passkey");
      return;
    }
    if (!password) {
      toast.error("Re-enter your password to confirm this change");
      return;
    }
    setBusy(true);
    try {
      await reauthenticateWithCredential(
        session,
        EmailAuthProvider.credential(session.email, password),
      );
      await session.getIdToken(true);
      const result = await carekeyRequest<{
        challenge_id: string;
        options: PublicKeyCredentialCreationOptionsJSON;
      }>(patientPasskeyOptionsPath("/auth/passkeys/registration-options"), user, { method: "POST" });
      setRegistration({ challengeId: result.challenge_id, options: result.options });
      setPassword("");
      toast.success("Password confirmed. Continue to create the passkey on your phone.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not confirm your password");
    } finally {
      setBusy(false);
    }
  }

  async function finishRegistration() {
    if (!user || !registration) return;
    setBusy(true);
    try {
      const credential = await startRegistration({ optionsJSON: registration.options });
      await carekeyRequest("/auth/passkeys/register", user, {
        method: "POST",
        body: JSON.stringify({ challenge_id: registration.challengeId, credential }),
      });
      setRegistration(null);
      toast.success("Phone passkey added");
      await queryClient.invalidateQueries({ queryKey: ["patient-passkeys", user.id] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Passkey setup was cancelled or failed");
    } finally {
      setBusy(false);
    }
  }

  async function beginVerification() {
    if (!user) return;
    setBusy(true);
    try {
      const result = await carekeyRequest<{
        challenge_id: string;
        options: PublicKeyCredentialRequestOptionsJSON;
      }>(patientPasskeyOptionsPath("/auth/passkeys/authentication-options"), user, { method: "POST" });
      setVerification({ challengeId: result.challenge_id, options: result.options });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start passkey verification");
    } finally {
      setBusy(false);
    }
  }

  async function finishVerification() {
    if (!user || !verification) return;
    setBusy(true);
    try {
      const credential = await startAuthentication({ optionsJSON: verification.options });
      await carekeyRequest("/auth/passkeys/verify", user, {
        method: "POST",
        body: JSON.stringify({ challenge_id: verification.challengeId, credential }),
      });
      setVerification(null);
      toast.success("Passkey verified on your phone");
      await queryClient.invalidateQueries({ queryKey: ["patient-passkeys", user.id] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Passkey verification was cancelled or failed");
      setVerification(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card-surface mb-6 space-y-4 p-5" aria-labelledby="patient-passkey-title">
      <div>
        <h2 id="patient-passkey-title" className="font-semibold">Patient passkey</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Add and verify a passkey from your phone. Your phone may ask for Face ID, a fingerprint, or its screen lock.
          CareKey receives a signed verification, never your face or fingerprint.
        </p>
      </div>
      {passkeys.isLoading ? <p className="text-sm text-muted-foreground">Checking passkeys…</p> : null}
      {passkeys.error ? <p role="alert" className="text-sm text-destructive">Could not load passkeys: {passkeys.error.message}</p> : null}
      {passkeys.data?.length ? <p className="text-sm">{passkeys.data.length} passkey{passkeys.data.length === 1 ? "" : "s"} registered.</p> : null}
      {!passkeys.isLoading && !passkeys.error && !passkeys.data?.length ? (
        <p className="text-sm text-muted-foreground">No passkey registered yet.</p>
      ) : null}

      {!registration ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-56 flex-1 space-y-1.5">
            <Label htmlFor="passkey-password">Confirm with your password before adding a passkey</Label>
            <Input
              id="passkey-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <Button onClick={() => void beginRegistration()} disabled={busy || !password}>
            {busy ? "Confirming…" : "Add passkey"}
          </Button>
        </div>
      ) : (
        <div className="space-y-2 rounded-md border p-3">
          <p className="text-sm">On a computer, choose the browser option to use a phone. Scan its QR code with your phone and finish the prompts there.</p>
          <Button onClick={() => void finishRegistration()} disabled={busy}>
            {busy ? "Waiting for your phone…" : "Continue on phone"}
          </Button>
          <Button variant="outline" onClick={() => setRegistration(null)} disabled={busy}>Cancel</Button>
        </div>
      )}

      {verification ? (
        <div className="space-y-2 rounded-md border p-3">
          <p className="text-sm">Use your phone to complete the browser’s passkey verification prompt.</p>
          <Button onClick={() => void finishVerification()} disabled={busy}>
            {busy ? "Waiting for your phone…" : "Verify on phone"}
          </Button>
          <Button variant="outline" onClick={() => setVerification(null)} disabled={busy}>Cancel</Button>
        </div>
      ) : (
        <Button variant="outline" onClick={() => void beginVerification()} disabled={busy || !passkeys.data?.length}>
          Verify with passkey
        </Button>
      )}
      <p className="text-xs text-muted-foreground">
        Browser passkeys require device verification, but the phone controls whether that uses biometrics or its PIN. The browser supplies the QR flow on supported computers.
      </p>
    </section>
  );
}
