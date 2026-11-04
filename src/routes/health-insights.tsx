import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";

type Tool = {
  key: string; name: string; category: string; version: string; intended_use: string;
  validated_population: string; required_inputs: string[]; limitations: string[];
  source_url: string; license_status: string; availability: string;
};
type Assessment = {
  id: string; model_key: string; model_version: string; status: string;
  result: Record<string, unknown> | null; contributing_factors: Array<{ label?: string; value?: unknown }>;
  missing_information: string[]; source_references: Array<{ record_type?: string; record_id?: string }>;
  summary: string | null; assessed_at: string;
};

export const Route = createFileRoute("/health-insights")({
  head: () => ({ meta: [{ title: "Health insights — CareKey" }] }),
  component: () => <RequireRole roles={["patient"]}><HealthInsightsPage /></RequireRole>,
});

function HealthInsightsPage() {
  const { user } = useAuth();
  const tools = useQuery({ queryKey: ["assessment-models"], enabled: !!user,
    queryFn: () => carekeyRequest<Tool[]>("/health-assessments/models", user!) });
  const history = useQuery({ queryKey: ["assessment-history", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Assessment[]>("/health-assessments/history", user!) });

  return <>
    <PageHeading title="Health insights" description="Risk assessments use structured, verified information when a suitable tool is available. They support health conversations and do not diagnose disease." />
    <section className="mb-6 grid gap-4 md:grid-cols-2">{(tools.data ?? []).map((tool) => <article key={tool.key} className="card-surface space-y-3 p-5">
      <div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">{tool.name}</h2><p className="text-sm text-muted-foreground">{tool.category.replaceAll("_", " ")} · version {tool.version}</p></div><Badge variant="outline">{tool.availability === "enabled" ? "Available" : "Not enabled"}</Badge></div>
      <p className="text-sm">{tool.intended_use}</p>
      <p className="text-xs text-muted-foreground"><strong>Validated population:</strong> {tool.validated_population}</p>
      <p className="text-xs text-muted-foreground"><strong>Needed information:</strong> {tool.required_inputs.map((item) => item.replaceAll("_", " ")).join(", ")}</p>
      {tool.limitations.map((limitation) => <p key={limitation} className="text-xs text-muted-foreground">• {limitation}</p>)}
      <p className="text-xs">Tool access: {tool.license_status.replaceAll("_", " ")}</p>
      <a className="text-sm text-primary underline" href={tool.source_url} target="_blank" rel="noreferrer">Read about this tool</a>
    </article>)}</section>
    <section className="card-surface p-5"><h2 className="font-semibold">Assessment history</h2>
      {history.isLoading ? <p className="mt-3 text-sm text-muted-foreground">Loading history…</p> : null}
      {!history.data?.length && !history.isLoading ? <p className="mt-3 text-sm text-muted-foreground">No assessments have been generated. Tools will appear here after their permissions and implementation are cleared.</p> : null}
      <div className="mt-3 divide-y">{(history.data ?? []).map((item) => <article key={item.id} className="py-4">
        <div className="flex flex-wrap justify-between gap-2"><strong>{item.model_key.replaceAll("_", " ")} · v{item.model_version}</strong><span className="text-sm text-muted-foreground">{new Date(item.assessed_at).toLocaleString()}</span></div>
        {item.summary ? <p className="mt-2 text-sm">{item.summary}</p> : null}
        {item.result ? <p className="mt-1 text-sm">Result: {Object.entries(item.result).map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`).join(" · ")}</p> : null}
        {item.missing_information.length ? <p className="mt-1 text-sm text-muted-foreground">Missing information: {item.missing_information.join(", ")}</p> : null}
        {item.contributing_factors.length ? <p className="mt-1 text-sm text-muted-foreground">Factors: {item.contributing_factors.map((factor) => `${factor.label ?? "Factor"}: ${String(factor.value ?? "recorded")}`).join(" · ")}</p> : null}
        <p className="mt-1 text-xs text-muted-foreground">Status: {item.status.replaceAll("_", " ")}</p>
      </article>)}</div>
    </section>
  </>;
}
