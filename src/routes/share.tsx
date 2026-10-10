import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { startAuthentication, type PublicKeyCredentialRequestOptionsJSON } from "@simplewebauthn/browser";
import { toast } from "sonner";
import { carekeyRequest } from "@/lib/carekey-api";
import { patientPasskeyOptionsPath } from "@/lib/passkey-device";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  CATEGORIES,
  DURATIONS,
  PURPOSES,
  categoryLabel,
  formatDateTime,
  type Category,
} from "@/lib/carekey";

export const Route = createFileRoute("/share")({
  head: () => ({
    meta: [
      { title: "Share medical information — CareKey" },
      {
        name: "description",
        content: "Grant a doctor time-limited access to selected categories of your medical record.",
      },
      { property: "og:title", content: "Share medical information — CareKey" },
      {
        property: "og:description",
        content: "Patient-controlled, expiring, revocable consent for your medical data.",
      },
    ],
  }),
  component: () => (
    <RequireRole roles={["patient"]}>
      <SharePage />
    </RequireRole>
  ),
});

type ConsentRow = {
  id: string;
  provider_id: string;
  permissions: string[];
  purpose: string;
  status: string;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
};

function SharePage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [providerId, setProviderId] = useState("");
  const [perms, setPerms] = useState<Category[]>([]);
  const [duration, setDuration] = useState("168");
  const [customDate, setCustomDate] = useState("");
  const [purpose, setPurpose] = useState("Consultation");
  const [busy, setBusy] = useState(false);
  const [pendingGrant, setPendingGrant] = useState<{
    challengeId: string;
    options: PublicKeyCredentialRequestOptionsJSON;
    payload: { provider_id: string; permissions: Category[]; purpose: string; expires_at: string };
  } | null>(null);
  const [pendingRevoke, setPendingRevoke] = useState<{
    consentId: string;
    challengeId: string;
    options: PublicKeyCredentialRequestOptionsJSON;
  } | null>(null);

  const doctors = useQuery({
    queryKey: ["doctors", user?.id],
    enabled: !!user,
    queryFn: () => carekeyRequest<Array<{ id: string; full_name: string; organization: string | null; specialty: string | null }>>("/roles/doctors", user!),
  });

  const consents = useQuery({
    queryKey: ["my-consents", user?.id],
    enabled: !!user,
    queryFn: async () => {
      return carekeyRequest<ConsentRow[]>("/consents", user!);
    },
  });

  const doctorList = (doctors.data ?? []).filter((d) => d.id !== user?.id);
  const nameOf = (id: string) => {
    const d = doctorList.find((x) => x.id === id);
    return d ? `${d.full_name}${d.organization ? ` · ${d.organization}` : ""}` : "Provider";
  };

  async function grant() {
    if (!user) return;
    if (!providerId) return toast.error("Select a healthcare provider");
    if (perms.length === 0) return toast.error("Select at least one category");
    let expires: Date;
    if (duration === "custom") {
      if (!customDate) return toast.error("Pick a custom expiry date");
      expires = new Date(customDate);
      if (expires <= new Date()) return toast.error("Expiry must be in the future");
    } else {
      expires = new Date(Date.now() + Number(duration) * 3600_000);
    }
    setBusy(true);
    try {
      const result = await carekeyRequest<{ challenge_id: string; options: PublicKeyCredentialRequestOptionsJSON }>(
        patientPasskeyOptionsPath("/auth/passkeys/authentication-options"), user, { method: "POST" },
      );
      setPendingGrant({
        challengeId: result.challenge_id,
        options: result.options,
        payload: { provider_id: providerId, permissions: perms, purpose, expires_at: expires.toISOString() },
      });
    } catch (error) {
      setBusy(false);
      return toast.error(error instanceof Error ? error.message : "Could not prepare phone verification");
    }
    setBusy(false);
  }

  async function confirmGrant() {
    if (!user || !pendingGrant) return;
    setBusy(true);
    try {
      const credential = await startAuthentication({ optionsJSON: pendingGrant.options });
      await carekeyRequest("/consents", user, {
        method: "POST",
        body: JSON.stringify({ ...pendingGrant.payload, challenge_id: pendingGrant.challengeId, credential }),
      });
      setPendingGrant(null);
    } catch (error) {
      setPendingGrant(null);
      setBusy(false);
      return toast.error(error instanceof Error ? error.message : "Could not grant access");
    }
    setBusy(false);
    toast.success("Access granted");
    setPerms([]);
    await qc.invalidateQueries({ queryKey: ["my-consents"] });
  }

  async function setStatus(c: ConsentRow, status: "revoked" | "active" | "rejected") {
    if (status !== "revoked") return;
    setBusy(true);
    try {
      const result = await carekeyRequest<{ challenge_id: string; options: PublicKeyCredentialRequestOptionsJSON }>(
        patientPasskeyOptionsPath("/auth/passkeys/authentication-options"), user!, { method: "POST" },
      );
      setPendingRevoke({ consentId: c.id, challengeId: result.challenge_id, options: result.options });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not prepare phone verification");
    } finally {
      setBusy(false);
    }
  }

  async function confirmRevoke() {
    if (!user || !pendingRevoke) return;
    setBusy(true);
    try {
      const credential = await startAuthentication({ optionsJSON: pendingRevoke.options });
      await carekeyRequest(`/consents/${pendingRevoke.consentId}/revoke`, user, {
        method: "POST",
        body: JSON.stringify({ challenge_id: pendingRevoke.challengeId, credential }),
      });
      setPendingRevoke(null);
    } catch (error) {
      setPendingRevoke(null);
      setBusy(false);
      return toast.error(error instanceof Error ? error.message : "Could not revoke access");
    }
    setBusy(false);
    toast.success("Access revoked");
    await qc.invalidateQueries({ queryKey: ["my-consents"] });
  }

  const pending = (consents.data ?? []).filter((c) => c.status === "pending");
  const others = (consents.data ?? []).filter((c) => c.status !== "pending");

  return (
    <>
      <PageHeading
        title="Share medical information"
        description="You decide who sees what, and for how long. Access can be revoked at any time."
      />


      {pending.length > 0 ? (
        <section className="mb-6 rounded-lg border-2 border-warning bg-warning-soft p-5">
          <h2 className="font-semibold">Access requests ({pending.length})</h2>
          <div className="mt-3 space-y-3">
            {pending.map((c) => (
              <div key={c.id} className="card-surface flex flex-wrap items-center gap-3 p-4">
                <div className="flex-1">
                  <p className="font-medium">{nameOf(c.provider_id)}</p>
                  <p className="text-sm text-muted-foreground">
                    Requests: {c.permissions.map(categoryLabel).join(", ")} · Purpose: {c.purpose} ·
                    Until {formatDateTime(c.expires_at)}
                  </p>
                </div>
                <Button size="sm" onClick={() => setStatus(c, "active")}>
                  Approve
                </Button>
                <Button size="sm" variant="outline" onClick={() => setStatus(c, "rejected")}>
                  Reject
                </Button>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
        <div className="card-surface h-fit space-y-5 p-6">
          <div className="space-y-1.5">
            <Label>Healthcare provider</Label>
            <Select value={providerId} onValueChange={setProviderId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a doctor" />
              </SelectTrigger>
              <SelectContent>
                {doctorList.length === 0 ? (
                  <div className="p-3 text-sm text-muted-foreground">
                    No doctors registered yet.
                  </div>
                ) : (
                  doctorList.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.full_name}
                      {d.organization ? ` — ${d.organization}` : ""}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Information to share</Label>
            <div className="mt-2 grid gap-2">
              {CATEGORIES.map((c) => (
                <label key={c.key} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={perms.includes(c.key)}
                    onCheckedChange={(v) =>
                      setPerms(v ? [...perms, c.key] : perms.filter((p) => p !== c.key))
                    }
                  />
                  {c.label}
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Access duration</Label>
            <Select value={duration} onValueChange={setDuration}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DURATIONS.map((d) => (
                  <SelectItem key={d.hours} value={String(d.hours)}>
                    {d.label}
                  </SelectItem>
                ))}
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
            {duration === "custom" ? (
              <Input
                type="datetime-local"
                value={customDate}
                onChange={(e) => setCustomDate(e.target.value)}
              />
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label>Purpose</Label>
            <Select value={purpose} onValueChange={setPurpose}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PURPOSES.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {pendingGrant ? (
            <div className="space-y-2 rounded-md border p-3">
              <p className="text-sm">Confirm this sharing request on your phone.</p>
              <Button className="w-full" onClick={() => void confirmGrant()} disabled={busy}>{busy ? "Waiting for your phone…" : "Verify on phone and grant"}</Button>
              <Button className="w-full" variant="outline" onClick={() => setPendingGrant(null)} disabled={busy}>Cancel</Button>
            </div>
          ) : <Button className="w-full" onClick={() => void grant()} disabled={busy}>{busy ? "Preparing…" : "Grant access"}</Button>}
        </div>

        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Consents
          </h2>
          {others.length === 0 ? (
            <div className="card-surface p-6 text-sm text-muted-foreground">
              You haven't shared anything yet.
            </div>
          ) : (
            others.map((c) => (
              <div key={c.id} className="card-surface p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">{nameOf(c.provider_id)}</p>
                  <StatusBadge status={c.status} />
                  <span className="ml-auto text-xs text-muted-foreground">{c.purpose}</span>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">Can access:</p>
                <ul className="mt-1 flex flex-wrap gap-2">
                  {c.permissions.map((p) => (
                    <li key={p} className="rounded-md bg-success-soft px-2 py-0.5 text-sm">
                      ✓ {categoryLabel(p)}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-sm">
                  {c.status === "revoked"
                    ? `Revoked ${formatDateTime(c.revoked_at)}`
                    : `Expires ${formatDateTime(c.expires_at)}`}
                </p>
                {c.status === "active" ? (
                  pendingRevoke?.consentId === c.id ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button size="sm" variant="destructive" onClick={() => void confirmRevoke()} disabled={busy}>{busy ? "Waiting for your phone…" : "Verify on phone and revoke"}</Button>
                      <Button size="sm" variant="outline" onClick={() => setPendingRevoke(null)} disabled={busy}>Cancel</Button>
                    </div>
                  ) : (
                    <Button size="sm" variant="destructive" className="mt-3" onClick={() => void setStatus(c, "revoked")} disabled={busy}>Revoke access</Button>
                  )
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "active"
      ? "default"
      : status === "revoked" || status === "rejected"
        ? "destructive"
        : "secondary";
  return <Badge variant={variant}>{status}</Badge>;
}
