import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { startAuthentication, startRegistration, type PublicKeyCredentialCreationOptionsJSON, type PublicKeyCredentialRequestOptionsJSON } from "@simplewebauthn/browser";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { carekeyRequest } from "@/lib/carekey-api";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/lib/carekey";

export const Route = createFileRoute("/emergency")({
  head: () => ({
    meta: [
      { title: "Emergency patient access — CareKey" },
      { name: "description", content: "Audited emergency access to a patient's critical profile." },
    ],
  }),
  component: () => (
    <RequireRole roles={["doctor"]}>
      <EmergencyPage />
    </RequireRole>
  ),
});

type EmergencyProfile = {
  medical_id: string;
  full_name: string | null;
  date_of_birth: string | null;
  blood_group: string | null;
  rh_factor: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  allergies: { allergen: string; reaction: string | null; severity: string }[];
  critical_conditions: { name: string; status: string; critical: boolean }[];
  active_medications: { name: string; dosage: string | null; frequency: string | null }[];
};

const REASONS = [
  "Road traffic accident",
  "Unconscious patient",
  "Cardiac emergency",
  "Fall / trauma",
  "Other medical emergency",
];

function EmergencyPage() {
  const { user, role } = useAuth();
  const qc = useQueryClient();
  const [medicalId, setMedicalId] = useState("");
  const [reason, setReason] = useState(REASONS[0]);
  const [data, setData] = useState<EmergencyProfile | null>(null);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [registrationSetup, setRegistrationSetup] = useState<{ challengeId: string; options: PublicKeyCredentialCreationOptionsJSON } | null>(null);
  const [pendingAccess, setPendingAccess] = useState<{ challengeId: string; options: PublicKeyCredentialRequestOptionsJSON; medicalId: string; reason: string } | null>(null);

  const passkeys = useQuery({
    queryKey: ["doctor-passkeys", user?.id],
    enabled: !!user && role === "doctor",
    queryFn: () => carekeyRequest<Array<{ id: string; created_at: string }>>("/auth/passkeys", user!),
  });

  async function beginPasskeySetup() {
    if (!user) return;
    setBusy(true);
    try {
      const result = await carekeyRequest<{ challenge_id: string; options: PublicKeyCredentialCreationOptionsJSON }>("/auth/passkeys/registration-options", user, { method: "POST" });
      setRegistrationSetup({ challengeId: result.challenge_id, options: result.options });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start passkey setup");
    } finally {
      setBusy(false);
    }
  }

  async function finishPasskeySetup() {
    if (!user || !registrationSetup) return;
    setBusy(true);
    try {
      const credential = await startRegistration({ optionsJSON: registrationSetup.options });
      await carekeyRequest("/auth/passkeys/register", user, {
        method: "POST",
        body: JSON.stringify({ challenge_id: registrationSetup.challengeId, credential }),
      });
      setRegistrationSetup(null);
      toast.success("Device passkey set up");
      await qc.invalidateQueries({ queryKey: ["doctor-passkeys", user.id] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Passkey setup was cancelled or failed");
    } finally {
      setBusy(false);
    }
  }

  async function prepareEmergencyAccess(value = medicalId, reasonValue = reason) {
    const clean = (value.match(/CK-[A-Z0-9]{8}/i)?.[0] ?? value).trim().toUpperCase();
    if (!/^CK-[A-Z0-9]{8}$/.test(clean)) return toast.error("Medical ID format is CK-XXXXXXXX");
    if (!user) return toast.error("Your sign-in has expired. Sign in again.");
    setBusy(true);
    try {
      const result = await carekeyRequest<{ challenge_id: string; options: PublicKeyCredentialRequestOptionsJSON }>("/auth/passkeys/authentication-options", user, { method: "POST" });
      setMedicalId(clean);
      setPendingAccess({ challengeId: result.challenge_id, options: result.options, medicalId: clean, reason: reasonValue });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not prepare device verification");
    } finally {
      setBusy(false);
    }
  }

  async function confirmEmergencyAccess() {
    if (!user || !pendingAccess) return;
    setBusy(true);
    try {
      const credential = await startAuthentication({ optionsJSON: pendingAccess.options });
      const profile = await carekeyRequest<EmergencyProfile>(`/emergency/${pendingAccess.medicalId}`, user, {
        method: "POST",
        body: JSON.stringify({
          reason: pendingAccess.reason,
          passkey_challenge_id: pendingAccess.challengeId,
          passkey_credential: credential,
        }),
      });
      setData(profile);
      setPendingAccess(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Emergency access was denied");
      setPendingAccess(null);
    } finally {
      setBusy(false);
    }
  }

  async function access(id = medicalId) {
    const clean = (id.match(/CK-[A-Z0-9]{8}/i)?.[0] ?? id).trim().toUpperCase();
    if (!/^CK-[A-Z0-9]{8}$/.test(clean)) {
      toast.error("Medical ID format is CK-XXXXXXXX");
      return;
    }
    if (!user) return toast.error("Your sign-in has expired. Sign in again.");
    setMedicalId(clean);
    setData(null);
    setPendingAccess(null);
    void prepareEmergencyAccess(clean, reason);
  }

  function reset() {
    setMedicalId("");
    setData(null);
  }

  return (
    <>
      <PageHeading
        title="Emergency patient access"
        description="Emergency access requires a documented reason. Every attempt is audited by the backend."
        action={data ? <Button variant="outline" onClick={reset}>New patient</Button> : null}
      />
      <div className="mb-6 rounded-lg border-2 border-info bg-info-soft p-4 text-sm">
        Emergency access requires a device passkey with user verification. Your device may use Windows Hello, Touch ID, a phone screen lock, or another passkey. CareKey stores the public credential only; it never receives your face or fingerprint data. This verifies the doctor’s device, not the patient’s identity.
      </div>
      {!data ? (
        <>
        <div className="grid gap-6 md:grid-cols-2">
          <div className="card-surface space-y-4 p-6">
            <h2 className="font-semibold">Enter Medical ID</h2>
            <div className="space-y-1.5">
              <Label htmlFor="mid">Medical ID</Label>
              <Input
                id="mid"
                className="mono-id text-lg uppercase"
                placeholder="CK-7F82A19C"
                value={medicalId}
                maxLength={11}
                onChange={(event) => setMedicalId(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Access reason</Label>
              <Select value={reason} onValueChange={setReason}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {REASONS.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button className="w-full" onClick={() => void access()} disabled={busy}>
              {busy ? "Preparing…" : "Continue to device confirmation"}
            </Button>
            {pendingAccess ? (
              <div className="space-y-2 rounded-md border p-3">
                <p className="text-sm">Confirm the emergency access request on this device.</p>
                <Button className="w-full" onClick={() => void confirmEmergencyAccess()} disabled={busy}>
                  {busy ? "Confirming…" : "Confirm with passkey"}
                </Button>
                <Button className="w-full" variant="outline" onClick={() => setPendingAccess(null)} disabled={busy}>Cancel</Button>
              </div>
            ) : null}
          </div>
          <div className="card-surface space-y-4 p-6">
            <h2 className="font-semibold">Scan QR</h2>
            {scanning ? (
              <QrScanner onResult={(text) => { setScanning(false); void access(text); }} />
            ) : (
              <p className="text-sm text-muted-foreground">The CareKey QR contains a Medical ID only.</p>
            )}
            <Button variant="outline" className="w-full" onClick={() => setScanning((value) => !value)}>
              {scanning ? "Stop camera" : "Start QR scanner"}
            </Button>
          </div>
        </div>
        <div className="card-surface h-fit space-y-3 p-6">
          <h2 className="font-semibold">Device passkey</h2>
          {passkeys.isLoading ? <p className="text-sm text-muted-foreground">Checking passkeys…</p> : null}
          {passkeys.error ? <p role="alert" className="text-sm text-destructive">Could not load passkey status: {passkeys.error.message}</p> : null}
          {passkeys.data?.length ? (
            <p className="text-sm text-muted-foreground">{passkeys.data.length} passkey{passkeys.data.length === 1 ? "" : "s"} registered. Device confirmation is required for each emergency access.</p>
          ) : null}
          {!passkeys.isLoading && !passkeys.error && !passkeys.data?.length ? (
            <p className="text-sm text-muted-foreground">Set up a passkey before requesting emergency access.</p>
          ) : null}
          {!registrationSetup ? (
            <Button variant="outline" className="w-full" onClick={() => void beginPasskeySetup()} disabled={busy}>
              {busy ? "Preparing…" : passkeys.data?.length ? "Add another passkey" : "Set up device passkey"}
            </Button>
          ) : (
            <Button className="w-full" onClick={() => void finishPasskeySetup()} disabled={busy}>
              {busy ? "Setting up…" : "Continue on this device"}
            </Button>
          )}
        </div>
        </>
      ) : <EmergencyView data={data} />}
    </>
  );
}

function QrScanner({ onResult }: { onResult: (text: string) => void }) {
  const id = "qr-reader";
  useEffect(() => {
    let scanner: { stop: () => Promise<void>; clear: () => void } | null = null;
    let done = false;
    void import("html5-qrcode").then(({ Html5Qrcode }) => {
      const instance = new Html5Qrcode(id);
      scanner = instance;
      void instance.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: 220 },
        (text) => { if (!done) { done = true; onResult(text); } },
        () => {},
      ).catch(() => toast.error("Camera unavailable — enter the Medical ID instead"));
    });
    return () => { void scanner?.stop().then(() => scanner?.clear()).catch(() => {}); };
  }, [onResult]);
  return <div id={id} className="overflow-hidden rounded-lg border" />;
}

function EmergencyView({ data }: { data: EmergencyProfile }) {
  const blood = data.blood_group
    ? `${data.blood_group}${data.rh_factor === "negative" ? "−" : "+"}`
    : "Unknown";
  return (
    <div className="space-y-4">
      <div className="rounded-md bg-success-soft p-3 text-sm font-medium">Emergency access was recorded by the backend audit log.</div>
      <div className="card-surface flex flex-wrap items-center justify-between gap-4 p-5">
        <div>
          <p className="text-2xl font-bold">{data.full_name ?? "Patient"}</p>
          <p className="mono-id text-sm text-muted-foreground">{data.medical_id}</p>
          {data.date_of_birth ? <p className="text-sm text-muted-foreground">Born {formatDate(data.date_of_birth)}</p> : null}
        </div>
        <div className="text-right text-sm">
          <p className="text-xs uppercase text-muted-foreground">Emergency contact</p>
          <p className="font-semibold">{data.emergency_contact_name ?? "—"}</p>
          {data.emergency_contact_phone ? <a className="text-primary underline" href={`tel:${data.emergency_contact_phone}`}>{data.emergency_contact_phone}</a> : null}
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border-4 border-critical bg-critical-soft p-6">
          <p className="text-sm font-bold uppercase tracking-widest">Blood group</p>
          <p className="mt-2 text-6xl font-bold">{blood}</p>
        </div>
        <BigCard title="⚠ Allergies" critical={data.allergies.length > 0}>
          {data.allergies.map((item, i) => <li key={i}><strong>{item.allergen}</strong> — {item.reaction ?? "reaction unknown"} <span className="text-xs font-bold uppercase">({item.severity})</span></li>)}
        </BigCard>
        <BigCard title="⚠ Critical conditions" critical={data.critical_conditions.length > 0}>
          {data.critical_conditions.map((item, i) => <li key={i}><strong>{item.name}</strong> ({item.status})</li>)}
        </BigCard>
        <BigCard title="Current medications">
          {data.active_medications.map((item, i) => <li key={i}><strong>{item.name}</strong> {item.dosage ?? ""} {item.frequency ? `· ${item.frequency}` : ""}</li>)}
        </BigCard>
      </div>
    </div>
  );
}

function BigCard({ title, critical, children }: { title: string; critical?: boolean; children: React.ReactNode[] }) {
  return (
    <div className={`rounded-lg p-6 ${critical ? "border-4 border-critical bg-critical-soft" : "card-surface"}`}>
      <p className="text-sm font-bold uppercase tracking-widest">{title}</p>
      {children.length === 0 ? <p className="mt-3 text-base text-muted-foreground">None recorded</p> : <ul className="mt-3 space-y-2 text-base">{children}</ul>}
    </div>
  );
}
