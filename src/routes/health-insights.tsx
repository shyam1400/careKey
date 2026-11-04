import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type Tool = {
  key: string; name: string; category: string; version: string; intended_use: string;
  validated_population: string; required_inputs: string[]; limitations: string[];
  source_url: string; license_status: string; availability: string;
  minimum_age: number | null; maximum_age: number | null;
  chart_minimum_age: number | null; chart_maximum_age: number | null;
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
  const qc = useQueryClient();
  const tools = useQuery({ queryKey: ["assessment-models"], enabled: !!user,
    queryFn: () => carekeyRequest<Tool[]>("/health-assessments/models", user!) });
  const history = useQuery({ queryKey: ["assessment-history", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Assessment[]>("/health-assessments/history", user!) });
  const runAssessment = useMutation({
    mutationFn: (modelKey: string) => carekeyRequest<Assessment>(`/health-assessments/${modelKey}/run`, user!, { method: "POST" }),
    onSuccess: async (assessment) => {
      await qc.invalidateQueries({ queryKey: ["assessment-history", user?.id] });
      toast(assessment.result ? "Assessment saved to your history" : "No category generated. Review the missing information.");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Assessment could not be generated"),
  });

  return <>
    <PageHeading title="Health insights" description="Risk assessments use structured, verified information when a suitable tool is available. They support health conversations and do not diagnose disease." />
    <section className="mb-6 grid gap-4 md:grid-cols-2">{(tools.data ?? []).map((tool) => <article key={tool.key} className="card-surface space-y-3 p-5">
      <div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">{tool.name}</h2><p className="text-sm text-muted-foreground">{tool.category.replaceAll("_", " ")} · version {tool.version}</p></div><Badge variant="outline">{tool.availability === "enabled" ? "Available" : "Not enabled"}</Badge></div>
      <p className="text-sm">{tool.intended_use}</p>
      <p className="text-xs text-muted-foreground"><strong>Validated population:</strong> {tool.validated_population}</p>
      {tool.minimum_age !== null ? <p className="text-xs text-muted-foreground"><strong>Age eligibility:</strong> {tool.minimum_age}{tool.maximum_age !== null ? `–${tool.maximum_age}` : "+"} years</p> : null}
      {tool.chart_minimum_age !== null && tool.chart_maximum_age !== null ? <p className="text-xs text-muted-foreground"><strong>Published chart ages available:</strong> {tool.chart_minimum_age}–{tool.chart_maximum_age}. For eligible ages without a chart row, CareKey will not estimate a category.</p> : null}
      <p className="text-xs text-muted-foreground"><strong>Needed information:</strong> {tool.required_inputs.map((item) => item.replaceAll("_", " ")).join(", ")}</p>
      {tool.limitations.map((limitation) => <p key={limitation} className="text-xs text-muted-foreground">• {limitation}</p>)}
      <p className="text-xs">Tool access: {tool.license_status.replaceAll("_", " ")}</p>
      <a className="text-sm text-primary underline" href={tool.source_url} target="_blank" rel="noreferrer">Read about this tool</a>
      {tool.availability === "enabled" ? <Button className="block" disabled={runAssessment.isPending} onClick={() => runAssessment.mutate(tool.key)}>{runAssessment.isPending ? "Generating…" : "Run assessment"}</Button> : null}
    </article>)}</section>
    <section className="card-surface p-5"><h2 className="font-semibold">Assessment history</h2>
      {history.isLoading ? <p className="mt-3 text-sm text-muted-foreground">Loading history…</p> : null}
      {!history.data?.length && !history.isLoading ? <p className="mt-3 text-sm text-muted-foreground">No assessments have been generated yet.</p> : null}
      <div className="mt-3 divide-y">{(history.data ?? []).map((item) => <article key={item.id} className="py-4">
        <div className="flex flex-wrap justify-between gap-2"><strong>{item.model_key.replaceAll("_", " ")} · v{item.model_version}</strong><span className="text-sm text-muted-foreground">{new Date(item.assessed_at).toLocaleString()}</span></div>
        {item.summary ? <p className="mt-2 text-sm">{item.summary}</p> : null}
        {item.result?.risk_category ? <p className="mt-2 text-lg font-semibold">10-year category: {String(item.result.risk_category)}</p> : null}
        {item.result?.idrs_score !== undefined ? <div className="mt-2"><p className="text-lg font-semibold">IDRS screening score: {String(item.result.idrs_score)} / 100</p><p className="font-medium">Screening category: {String(item.result.screening_category)}</p><p className="text-xs text-muted-foreground">This screening score is not a diagnosis or future-onset prediction.</p></div> : null}
        {!item.result?.risk_category && item.result?.idrs_score === undefined && item.result ? <p className="mt-1 text-sm">Result: {Object.entries(item.result).map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`).join(" · ")}</p> : null}
        {item.missing_information.length ? <p className="mt-1 text-sm text-muted-foreground">Missing information: {item.missing_information.join(", ")}</p> : null}
        {item.contributing_factors.length ? <p className="mt-1 text-sm text-muted-foreground">Factors: {item.contributing_factors.map((factor) => `${factor.label ?? "Factor"}: ${String(factor.value ?? "recorded")}`).join(" · ")}</p> : null}
        <p className="mt-1 text-xs text-muted-foreground">Status: {item.status.replaceAll("_", " ")}</p>
      </article>)}</div>
    </section>
  </>;
}
