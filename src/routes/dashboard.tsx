import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/carekey";
import { Activity, ArrowUpRight, FileText, HeartPulse, History, MapPin, QrCode, Share2, ShieldCheck } from "lucide-react";

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
  { to: "/profile", title: "Medical profile", body: "Keep your emergency details current", icon: HeartPulse },
  { to: "/records", title: "Medical records", body: "Documents, reports and results", icon: FileText },
  { to: "/share", title: "Sharing & consent", body: "Choose who can see your records", icon: Share2 },
  { to: "/qr", title: "Emergency QR", body: "Open your Medical ID code", icon: QrCode },
  { to: "/hospitals", title: "Find hospitals", body: "Browse nearby care locations", icon: MapPin },
  { to: "/history", title: "Access history", body: "Review recent record access", icon: History },
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
      <section className="relative mb-8 overflow-hidden rounded-2xl border bg-gradient-to-br from-primary/10 via-card to-accent/30 p-6 shadow-sm sm:p-8">
        <div className="relative z-10 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-xl">
            <p className="mb-3 inline-flex items-center gap-2 rounded-full border bg-card/80 px-3 py-1 text-xs font-medium text-primary">
              <ShieldCheck className="size-3.5" /> Your health information, in your hands
            </p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Welcome{profile?.full_name ? `, ${profile.full_name.split(" ")[0]}` : ""}</h1>
            <p className="mt-2 text-sm text-muted-foreground sm:text-base">Keep your emergency details ready and choose when to share your records.</p>
          </div>
          <Link to="/qr" className="group flex min-w-56 items-center justify-between gap-5 rounded-xl border bg-card p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Your Medical ID</p>
              <p className="mono-id mt-1 text-lg font-semibold">{medicalId ?? "—"}</p>
              <p className="mt-1 text-xs text-primary">Show emergency QR</p>
            </div>
            <span className="grid size-11 place-items-center rounded-lg bg-primary text-primary-foreground"><QrCode className="size-5" /></span>
          </Link>
        </div>
        <div className="pointer-events-none absolute -right-12 -top-20 size-64 rounded-full border-[36px] border-primary/5" />
      </section>

      <section className="mb-9">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div><h2 className="font-semibold">Emergency summary</h2><p className="text-sm text-muted-foreground">A quick view of the details that matter most.</p></div>
          <Link to="/profile" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">Review profile <ArrowUpRight className="size-4" /></Link>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-critical/30 bg-critical-soft p-5">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-critical"><Activity className="size-4" /> Blood group</p>
          <p className="mt-3 text-3xl font-bold tracking-tight">{blood}</p>
          <p className="mt-1 text-xs text-muted-foreground">{blood === "Not set" ? "Add this to your profile" : "Emergency information"}</p>
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
        </div>
      </section>

      <section className="mb-9">
        <div className="mb-3"><h2 className="font-semibold">Your CareKey</h2><p className="text-sm text-muted-foreground">Manage your information and account.</p></div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((c) => (
          <Link key={c.to} to={c.to} className="group card-surface flex items-center gap-4 p-4 transition duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-secondary text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground"><c.icon className="size-5" /></span>
            <span className="min-w-0 flex-1"><span className="block font-semibold">{c.title}</span><span className="mt-0.5 block text-sm text-muted-foreground">{c.body}</span></span>
            <ArrowUpRight className="size-4 shrink-0 text-muted-foreground transition group-hover:text-primary" />
          </Link>
        ))}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold">Recent access</h2><p className="text-sm text-muted-foreground">See when your information was viewed.</p></div><Link to="/history" className="text-sm font-medium text-primary hover:underline">Full history</Link></div>
        <div className="card-surface divide-y">
          {(data?.logs ?? []).length === 0 ? (
            <p className="p-5 text-sm text-muted-foreground">No access recorded yet.</p>
          ) : (
            data!.logs.map((l, i) => (
              <div key={i} className="flex flex-col gap-1 p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
                <span className="min-w-0">
                  <strong>{l.provider_name ?? "Unknown provider"}</strong> — {l.action}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">{formatDateTime(l.created_at)}</span>
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
