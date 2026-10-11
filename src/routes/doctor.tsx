import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { formatDateTime, categoryLabel } from "@/lib/carekey";

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
        <div><h1 className="text-2xl font-semibold">My patients</h1><p className="text-sm text-muted-foreground">{user?.hospitalName ? `Doctor at ${user.hospitalName}` : "Your account needs a hospital assignment"}</p></div>
        <Link to="/emergency" className="text-sm text-primary underline">Emergency mode</Link>
      </div>
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
