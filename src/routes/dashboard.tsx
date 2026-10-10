import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/carekey";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Patient dashboard — CareKey" },
      {
        name: "description",
        content:
          "Your CareKey dashboard: emergency profile summary, records, sharing, QR and access history.",
      },
      { property: "og:title", content: "Patient dashboard — CareKey" },
      {
        property: "og:description",
        content: "Emergency profile summary, medical records and sharing controls.",
      },
    ],
  }),
  component: () => (
    <RequireRole roles={["patient"]}>
      <Dashboard />
    </RequireRole>
  ),
});

const cards = [
  { to: "/profile", title: "Emergency profile", body: "Blood group, allergies, conditions" },
  { to: "/records", title: "Medical records", body: "Documents and reports" },
  { to: "/share", title: "Shared access", body: "Grant, review and revoke consent" },
  { to: "/qr", title: "Emergency QR", body: "Your Medical ID code" },
  { to: "/hospitals", title: "Nearby hospitals", body: "Emergency-capable hospitals" },
  { to: "/history", title: "Access history", body: "Who accessed your information" },
] as const;

function Dashboard() {
  const { user, medicalId, profile } = useAuth();

  const { data } = useQuery({
    queryKey: ["dashboard-summary", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const [patient, allergies, medications, conditions, logs] = await Promise.all([
        carekeyRequest<import("@/lib/carekey-api").Patient>(`/patients/${user!.id}`, user!),
        carekeyRequest<Array<{ allergen: string; severity: string }>>("/records/allergies", user!),
        carekeyRequest<Array<{ name: string; dosage: string | null; active: boolean }>>("/records/medications", user!),
        carekeyRequest<Array<{ name: string; critical: boolean }>>("/records/conditions", user!),
        carekeyRequest<Array<{ provider_name: string | null; action: string; created_at: string }>>("/audit/me?limit=3", user!),
      ]);
      return {
        patient,
        allergies,
        meds: medications.filter((med) => med.active),
        conditions: conditions.filter((condition) => condition.critical),
        logs,
      };
    },
  });

  const blood = data?.patient?.blood_group
    ? `${data.patient.blood_group}${data.patient.rh_factor === "negative" ? "−" : "+"}`
    : "Not set";

  return (
    <>
      <PageHeading
        title={`Welcome, ${profile?.full_name ?? ""}`}
        description="Your emergency information and sharing controls."
        action={
          <div className="text-right">
            <p className="text-xs uppercase text-muted-foreground">Medical ID</p>
            <p className="mono-id text-base font-semibold">{medicalId ?? "—"}</p>
          </div>
        }
      />

      <section className="mb-8 grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border-2 border-critical bg-critical-soft p-5">
          <p className="text-xs font-semibold uppercase tracking-wide">Blood group</p>
          <p className="mt-2 text-3xl font-bold">{blood}</p>
        </div>
        <SummaryCard
          label="Allergies"
          items={(data?.allergies ?? []).map(
            (a) => `${a.allergen}${a.severity === "severe" ? " (severe)" : ""}`,
          )}
          warn
        />
        <SummaryCard
          label="Current medications"
          items={(data?.meds ?? []).map((m) => `${m.name} ${m.dosage ?? ""}`.trim())}
        />
        <SummaryCard
          label="Critical conditions"
          items={(data?.conditions ?? []).map((c) => c.name)}
          warn
        />
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {cards.map((c) => (
          <Link key={c.to} to={c.to} className="card-surface p-5 transition-colors hover:bg-secondary">
            <h2 className="font-semibold">{c.title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{c.body}</p>
          </Link>
        ))}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Recent access
        </h2>
        <div className="card-surface divide-y">
          {(data?.logs ?? []).length === 0 ? (
            <p className="p-5 text-sm text-muted-foreground">No access recorded yet.</p>
          ) : (
            data!.logs.map((l, i) => (
              <div key={i} className="flex items-center justify-between p-4 text-sm">
                <span>
                  <strong>{l.provider_name ?? "Unknown provider"}</strong> — {l.action}
                </span>
                <span className="text-muted-foreground">{formatDateTime(l.created_at)}</span>
              </div>
            ))
          )}
        </div>
      </section>
    </>
  );
}

function SummaryCard({
  label,
  items,
  warn,
}: {
  label: string;
  items: string[];
  warn?: boolean;
}) {
  return (
    <div className={`card-surface p-5 ${warn && items.length ? "border-warning" : ""}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">None recorded</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {items.slice(0, 4).map((t, i) => (
            <li key={i} className="text-sm font-medium">
              {t}
            </li>
          ))}
          {items.length > 4 ? (
            <Badge variant="secondary">+{items.length - 4} more</Badge>
          ) : null}
        </ul>
      )}
    </div>
  );
}
