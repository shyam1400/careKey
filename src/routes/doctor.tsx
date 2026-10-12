import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { formatDateTime, categoryLabel } from "@/lib/carekey";
import { MyProcedures } from "@/components/MyProcedures";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const Route = createFileRoute("/doctor")({
  head: () => ({
    meta: [
      { title: "My patients — CareKey" },
      { name: "description", content: "Patients who have granted you consent-based access in CareKey." },
      { property: "og:title", content: "My patients — CareKey" },
      { property: "og:description", content: "Patients who have granted you consent-based access in CareKey." },
    ],
  }),
  component: () => (
    <RequireRole roles={["doctor"]}>
      <DoctorPage />
    </RequireRole>
  ),
});

function DoctorPage() {
  const { user } = useAuth();
  const [openConsent, setOpenConsent] = useState<string | null>(null);
  const [hospitalCode, setHospitalCode] = useState("");
  const [hospitalMatch, setHospitalMatch] = useState<{ id: string; code: string; name: string } | null>(null);
  const [affiliationMessage, setAffiliationMessage] = useState("");
  const affiliations = useQuery({ queryKey: ["affiliations", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Array<{ id: string; hospital_id: string; hospital_name: string; hospital_code: string; status: string; initiated_by: string }>>("/affiliations/me", user!) });
  async function lookupHospital() {
    if (!user) return;
    try { const match = await carekeyRequest<{ id: string; code: string; name: string }>(`/affiliations/lookup/${encodeURIComponent(hospitalCode.trim().toUpperCase())}`, user);
      setHospitalMatch(match); setAffiliationMessage("");
    } catch (error) { setHospitalMatch(null); setAffiliationMessage(error instanceof Error ? error.message : "Hospital not found"); }
  }
  async function requestHospital() {
    if (!user) return;
    try { await carekeyRequest("/affiliations/request", user, { method: "POST", body: JSON.stringify({ code: hospitalMatch?.code }) });
      setHospitalCode(""); setHospitalMatch(null); setAffiliationMessage("Request sent to the hospital for approval."); await affiliations.refetch();
    } catch (error) { setAffiliationMessage(error instanceof Error ? error.message : "Could not send request"); }
  }
  async function decide(id: string, approve: boolean) {
    if (!user) return;
    try { await carekeyRequest(`/affiliations/${id}/decision`, user, { method: "POST", body: JSON.stringify({ approve }) }); await affiliations.refetch(); }
    catch (error) { setAffiliationMessage(error instanceof Error ? error.message : "Could not update request"); }
  }
  const { data, isLoading, error } = useQuery({
    queryKey: ["doctor-consents", user?.id],
    enabled: !!user,
    queryFn: async () => {
      return carekeyRequest<Array<{
        id: string; patient_id: string; permissions: string[]; status: string; expires_at: string | null;
      }>>("/consents", user!);
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-semibold">My patients</h1><p className="text-sm text-muted-foreground">Doctor ID: {user?.doctorCode ?? "Being assigned"}</p></div>
        <Link to="/emergency" className="text-sm text-primary underline">Emergency mode</Link>
      </div>
      <section className="card-surface space-y-3 p-5">
        <div><h2 className="text-lg font-semibold">Hospital affiliations</h2><p className="text-sm text-muted-foreground">Each hospital must approve your request before it appears as an active affiliation.</p></div>
        <div className="flex gap-2"><Input aria-label="Hospital ID" placeholder="HOS-XXXXXXXX" value={hospitalCode} onChange={(event) => { setHospitalCode(event.target.value.toUpperCase()); setHospitalMatch(null); }} /><Button variant="outline" onClick={() => void lookupHospital()} disabled={!/^HOS-[0-9A-F]{8}$/.test(hospitalCode)}>Find</Button></div>
        {hospitalMatch ? <div className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm"><span>{hospitalMatch.name} · {hospitalMatch.code}</span><Button size="sm" onClick={() => void requestHospital()}>Request affiliation</Button></div> : null}
        {affiliationMessage ? <p role="status" className="text-sm text-muted-foreground">{affiliationMessage}</p> : null}
        {affiliations.data?.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3"><p className="text-sm"><strong>{item.hospital_name}</strong> · {item.hospital_code} · {item.status.replaceAll("_", " ")}</p>
          {item.status === "pending_doctor" && item.initiated_by === "hospital" ? <div className="flex gap-2"><Button size="sm" onClick={() => void decide(item.id, true)}>Approve</Button><Button size="sm" variant="outline" onClick={() => void decide(item.id, false)}>Deny</Button></div> : null}</div>)}
        {!affiliations.data?.length ? <p className="text-sm text-muted-foreground">No hospital affiliations yet.</p> : null}
      </section>
      <MyProcedures audience="doctor" />
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <div role="alert" className="card-surface p-5 text-sm text-destructive">{error.message}</div>
      ) : !data?.length ? (
        <div className="card-surface p-6 text-sm text-muted-foreground">No patients have shared records with you yet.</div>
      ) : (
        <ul className="space-y-2">
          {data.map((c) => (
            <li key={c.id} className="card-surface p-4">
              <p className="font-medium">Patient {c.patient_id.slice(0, 8)} · {c.status}</p>
              <p className="text-xs text-muted-foreground">
                {c.permissions.map(categoryLabel).join(", ")} · expires {formatDateTime(c.expires_at)}
              </p>
              {c.status === "active" ? (
                <button
                  className="mt-3 text-sm text-primary underline"
                  onClick={() => setOpenConsent(openConsent === c.id ? null : c.id)}
                >
                  {openConsent === c.id ? "Close shared records" : "View shared records"}
                </button>
              ) : null}
              {openConsent === c.id && user ? <ConsentedRecords consentId={c.id} user={user} /> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ConsentedRecords({ consentId, user }: { consentId: string; user: NonNullable<ReturnType<typeof useAuth>["user"]> }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["consented-records", consentId],
    queryFn: () => carekeyRequest<Record<string, unknown>>(`/consents/${consentId}/records`, user),
  });
  if (isLoading) return <p className="mt-3 text-sm text-muted-foreground">Loading shared records…</p>;
  if (error) return <p className="mt-3 text-sm text-destructive">{error.message}</p>;
  if (!data) return null;
  const headings: Record<string, string> = {
    basic: "Basic information", blood: "Blood group", allergies: "Allergies",
    medications: "Medications", conditions: "Conditions", surgeries: "Surgeries",
  };
  return (
    <div className="mt-4 space-y-3 border-t pt-4">
      {Object.entries(data).filter(([key]) => key !== "consent_id" && key !== "permissions").map(([key, value]) => (
        <section key={key}>
          <h3 className="text-sm font-semibold">{headings[key] ?? key}</h3>
          {Array.isArray(value) ? (
            value.length ? <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
              {value.map((row, index) => <li key={index} className="rounded bg-muted p-2">
                {row && typeof row === "object" && "url" in row && typeof row.url === "string" ? (
                  <a className="text-primary underline" href={row.url} target="_blank" rel="noreferrer">Open {"file_name" in row ? String(row.file_name) : "document"}</a>
                ) : formatRecord(row)}
              </li>)}
            </ul> : <p className="mt-1 text-xs text-muted-foreground">None recorded</p>
          ) : <p className="mt-1 text-xs text-muted-foreground">{formatRecord(value)}</p>}
        </section>
      ))}
    </div>
  );
}

function formatRecord(value: unknown): string {
  if (value && typeof value === "object") {
    return Object.entries(value).map(([key, item]) =>
      `${key.replaceAll("_", " ")}: ${item == null || item === "" ? "—" : String(item)}`,
    ).join(" · ");
  }
  return value == null || value === "" ? "—" : String(value);
}
