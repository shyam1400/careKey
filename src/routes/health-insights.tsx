import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
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
  input_schema: InputField[]; defaults: Record<string, number> | null; dataset: string | null; metrics: string | null;
  availability_reason: string | null;
};
type InputField = { name: string; label: string; type: "boolean" | "select" | "number"; min?: number; max?: number; step?: number; options?: Array<{ value: number; label: string }> };
type AssessmentRequest = { inputs: Record<string, number>; defaulted_inputs: string[]; patient_confirmed: boolean };
type Measurement = { id: string; measurement_type: string; value: string; unit: string; observed_at: string; verification_status: string };
type RiskFactor = { id: string; factor_key: string; value: boolean; observed_at: string; verification_status: string };
type PatientInfo = { date_of_birth?: string | null; gender?: string | null };
type Assessment = {
  id: string; model_key: string; model_version: string; status: string;
  result: Record<string, unknown> | null; contributing_factors: Array<{ label?: string; value?: unknown }>;
  missing_information: string[]; source_references: Array<{ record_type?: string; record_id?: string }>; input_snapshot: Record<string, unknown>;
  summary: string | null; assessed_at: string;
};

export const Route = createFileRoute("/health-insights")({
  head: () => ({ meta: [{ title: "Health insights — CareKey" }] }),
  component: () => <RequireRole roles={["patient"]}><HealthInsightsPage /></RequireRole>,
});

function HealthInsightsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [selectedTool, setSelectedTool] = useState<string | null>(null);
  const tools = useQuery({ queryKey: ["assessment-models"], enabled: !!user,
    queryFn: () => carekeyRequest<Tool[]>("/health-assessments/models", user!) });
  const patientInputs = useQuery({ queryKey: ["assessment-prefill", user?.id], enabled: !!user, queryFn: async () => {
    const [patient, measurements, riskFactors] = await Promise.all([
      carekeyRequest<PatientInfo>(`/patients/${user!.id}`, user!),
      carekeyRequest<Measurement[]>("/health-data/measurements", user!),
      carekeyRequest<RiskFactor[]>("/health-data/risk-factors", user!),
    ]);
    return { patient, measurements, riskFactors };
  } });
  const history = useQuery({ queryKey: ["assessment-history", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Assessment[]>("/health-assessments/history", user!) });
  const runAssessment = useMutation({
    mutationFn: ({ modelKey, request }: { modelKey: string; request: AssessmentRequest }) => carekeyRequest<Assessment>(`/health-assessments/${modelKey}/run`, user!, { method: "POST", body: JSON.stringify(request) }),
    onSuccess: async (assessment) => {
      await qc.invalidateQueries({ queryKey: ["assessment-history", user?.id] });
      toast(assessment.result ? "Assessment saved to your history" : "No category generated. Review the missing information.");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Assessment could not be generated"),
  });

  return <>
    <PageHeading title="Health insights" description="Choose an experimental model, review only its required questions, and confirm the inputs before running it." />
    <section className="mb-6 grid w-full grid-cols-1 gap-4">{(tools.data ?? []).map((tool) => <article key={tool.key} className="card-surface w-full space-y-3 p-5">
      <div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">{tool.name}</h2><p className="text-sm text-muted-foreground">{tool.category.replaceAll("_", " ")} · version {tool.version}</p></div><Badge variant="outline">{tool.availability === "enabled" ? "Available" : "Not enabled"}</Badge></div>
      <p className="text-sm">{tool.intended_use}</p>
      <p className="text-xs text-muted-foreground"><strong>Dataset:</strong> {tool.dataset ?? tool.validated_population}</p>
      <p className="text-xs text-muted-foreground"><strong>Evaluation:</strong> {tool.metrics ?? "Not reported"}</p>
      <p className="text-xs text-muted-foreground"><strong>Inputs:</strong> {tool.required_inputs.length} model-specific fields</p>
      {tool.limitations.map((limitation) => <p key={limitation} className="text-xs text-muted-foreground">• {limitation}</p>)}
      {tool.source_url ? <a className="text-sm text-primary underline" href={tool.source_url} target="_blank" rel="noreferrer">Read about the source dataset</a> : null}
      {tool.availability === "enabled" ? <Button className="block" disabled={runAssessment.isPending} onClick={() => setSelectedTool(selectedTool === tool.key ? null : tool.key)}>{selectedTool === tool.key ? "Close assessment" : "Start assessment"}</Button> : <p className="text-sm text-muted-foreground">{tool.availability_reason}</p>}
      {selectedTool === tool.key ? <AssessmentInputForm tool={tool} patientInputs={patientInputs.data} onSubmit={(request) => runAssessment.mutate({ modelKey: tool.key, request })} busy={runAssessment.isPending} /> : null}
    </article>)}</section>
    <p className="mb-6 rounded-md border border-warning/40 bg-warning-soft p-4 text-sm">CareKey is an academic prototype. Experimental model outputs are not diagnoses, do not rule out disease, and are not a substitute for qualified medical advice.</p>
    <section className="card-surface p-5"><h2 className="font-semibold">Assessment history</h2>
      {history.isLoading ? <p className="mt-3 text-sm text-muted-foreground">Loading history…</p> : null}
      {!history.data?.length && !history.isLoading ? <p className="mt-3 text-sm text-muted-foreground">No assessments have been generated yet.</p> : null}
      <div className="mt-3 divide-y">{(history.data ?? []).map((item) => <article key={item.id} className="py-4">
        <div className="flex flex-wrap justify-between gap-2"><strong>{item.model_key.replaceAll("_", " ")} · v{item.model_version}</strong><span className="text-sm text-muted-foreground">{new Date(item.assessed_at).toLocaleString()}</span></div>
        {item.summary ? <p className="mt-2 text-sm">{item.summary}</p> : null}
        {item.result?.risk_category ? <p className="mt-2 text-lg font-semibold">10-year category: {String(item.result.risk_category)}</p> : null}
        {item.result?.idrs_score !== undefined ? <div className="mt-2"><p className="text-lg font-semibold">IDRS screening score: {String(item.result.idrs_score)} / 100</p><p className="font-medium">Screening category: {String(item.result.screening_category)}</p><p className="text-xs text-muted-foreground">This screening score is not a diagnosis or future-onset prediction.</p></div> : null}
        {item.result?.sigmoid_output !== undefined ? <div className="mt-2 rounded-md border bg-muted/30 p-3"><p className="font-semibold">Model category: {String(item.result.category).replaceAll("_", " ")}</p><p className="text-sm">Sigmoid output: {Number(item.result.sigmoid_output).toFixed(4)} (classification threshold: 0.5)</p><p className="text-xs text-muted-foreground">This is the model's uncalibrated output, not a clinical risk percentage.</p></div> : null}
        {!item.result?.risk_category && item.result?.idrs_score === undefined && item.result ? <p className="mt-1 text-sm">Result: {Object.entries(item.result).map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`).join(" · ")}</p> : null}
        {item.missing_information.length ? <p className="mt-1 text-sm text-muted-foreground">Missing information: {item.missing_information.join(", ")}</p> : null}
        {item.contributing_factors.length ? <p className="mt-1 text-sm text-muted-foreground">Factors: {item.contributing_factors.map((factor) => `${factor.label ?? "Factor"}: ${String(factor.value ?? "recorded")}`).join(" · ")}</p> : null}
        {item.input_snapshot?.inputs ? <details className="mt-2 text-sm"><summary className="cursor-pointer font-medium">Input snapshot and provenance</summary><div className="mt-2 space-y-1 text-xs text-muted-foreground">{Object.entries(item.input_snapshot.inputs as Record<string, unknown>).map(([key, value]) => <p key={key}>{key}: {String(value)}</p>)}<p>Input status: {String(item.input_snapshot.input_verification_status ?? "recorded")}</p>{Array.isArray(item.input_snapshot.defaulted_inputs) && item.input_snapshot.defaulted_inputs.length ? <p>Documented defaults selected for: {(item.input_snapshot.defaulted_inputs as string[]).join(", ")}</p> : null}{item.input_snapshot.source_by_feature ? <div className="mt-2 border-t pt-2"><p className="font-medium">Source by input</p>{Object.entries(item.input_snapshot.source_by_feature as Record<string, { source_type?: string; verification_status?: string; observed_at?: string; value_date?: string }>).map(([key, source]) => <p key={key}>{key}: {source.source_type ?? "recorded"}{source.verification_status ? ` · ${source.verification_status}` : ""}{source.observed_at ? ` · ${new Date(source.observed_at).toLocaleString()}` : ""}{source.value_date ? ` · value date ${source.value_date}` : ""}</p>)}</div> : null}</div></details> : null}
        <p className="mt-1 text-xs text-muted-foreground">Status: {item.status.replaceAll("_", " ")}</p>
      </article>)}</div>
    </section>
  </>;
}

function AssessmentInputForm({ tool, patientInputs, onSubmit, busy }: {
  tool: Tool;
  patientInputs?: { patient: PatientInfo; measurements: Measurement[]; riskFactors: RiskFactor[] };
  onSubmit: (request: AssessmentRequest) => void;
  busy: boolean;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [defaulted, setDefaulted] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  useEffect(() => {
    if (!patientInputs) return;
    const prefilled: Record<string, string> = {};
    const fields = new Set(tool.input_schema.map((field) => field.name));
    const gender = patientInputs.patient.gender?.toLowerCase();
    if ((fields.has("Sex") || fields.has("GENDER")) && (gender === "female" || gender === "male")) prefilled[fields.has("Sex") ? "Sex" : "GENDER"] = gender === "female" ? "0" : "1";
    if (fields.has("AGE") && patientInputs.patient.date_of_birth) {
      const dob = new Date(patientInputs.patient.date_of_birth);
      const today = new Date();
      let age = today.getFullYear() - dob.getFullYear();
      if (today < new Date(today.getFullYear(), dob.getMonth(), dob.getDate())) age--;
      if (age >= 18 && age <= 120) prefilled.AGE = String(age);
    }
    if (fields.has("Age") && patientInputs.patient.date_of_birth) {
      const dob = new Date(patientInputs.patient.date_of_birth);
      const today = new Date();
      let age = today.getFullYear() - dob.getFullYear();
      if (today < new Date(today.getFullYear(), dob.getMonth(), dob.getDate())) age--;
      const band = age <= 24 ? 1 : age <= 29 ? 2 : age <= 34 ? 3 : age <= 39 ? 4 : age <= 44 ? 5 : age <= 49 ? 6 : age <= 54 ? 7 : age <= 59 ? 8 : age <= 64 ? 9 : age <= 69 ? 10 : age <= 74 ? 11 : age <= 79 ? 12 : 13;
      if (age >= 18) prefilled.Age = String(band);
    }
    const bmi = patientInputs.measurements.filter((item) => item.measurement_type === "bmi" && item.verification_status === "verified").sort((a, b) => b.observed_at.localeCompare(a.observed_at))[0];
    if (fields.has("BMI") && bmi) prefilled.BMI = bmi.value;
    const diabetes = patientInputs.riskFactors.filter((item) => item.factor_key === "diabetes_status" && item.verification_status === "verified").sort((a, b) => b.observed_at.localeCompare(a.observed_at))[0];
    if (fields.has("Diabetes_binary") && diabetes) prefilled.Diabetes_binary = diabetes.value ? "1" : "0";
    setValues((current) => {
      const merged = { ...current };
      for (const [key, value] of Object.entries(prefilled)) if (merged[key] === undefined || merged[key] === "") merged[key] = value;
      return merged;
    });
  }, [patientInputs, tool]);

  function useDefault(name: string) {
    const fallback = tool.defaults?.[name];
    if (fallback === undefined) return;
    setValues((current) => ({ ...current, [name]: String(fallback) }));
    setDefaulted((current) => current.includes(name) ? current : [...current, name]);
  }
  function setValue(name: string, value: string) {
    setValues((current) => ({ ...current, [name]: value }));
    setDefaulted((current) => current.filter((item) => item !== name));
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!confirmed) return toast.error("Review the values and confirm them before running the assessment");
    if (tool.input_schema.some((field) => values[field.name] === undefined || values[field.name] === "")) return toast.error("Complete each input or choose Not sure to use its documented default");
    const inputs = Object.fromEntries(tool.input_schema.map((field) => [field.name, Number(values[field.name])]));
    onSubmit({ inputs, defaulted_inputs: defaulted, patient_confirmed: true });
  }

  return <form onSubmit={submit} className="space-y-4 rounded-lg border bg-background p-4">
    <p className="text-sm font-medium">Review each value. Choose <em>Not sure</em> to apply the documented model default.</p>
    <div className="grid gap-3 sm:grid-cols-2">{tool.input_schema.map((field) => {
      const record = field.name === "BMI" ? patientInputs?.measurements.filter((item) => item.measurement_type === "bmi" && item.verification_status === "verified").sort((a, b) => b.observed_at.localeCompare(a.observed_at))[0] : undefined;
      const prefilled = ["Sex", "GENDER", "Age", "AGE"].includes(field.name) && !!patientInputs?.patient.date_of_birth || !!record || field.name === "Diabetes_binary" && !!patientInputs?.riskFactors.some((item) => item.factor_key === "diabetes_status" && item.verification_status === "verified");
      return <div key={field.name} className="space-y-1">
        <label htmlFor={`${tool.key}-${field.name}`} className="text-sm font-medium">{field.label}</label>
        <div className="flex gap-2">
          {field.type === "number" ? <input id={`${tool.key}-${field.name}`} className="h-10 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm" type="number" min={field.min} max={field.max} step={field.step} value={values[field.name] ?? ""} onChange={(event) => setValue(field.name, event.target.value)} required /> : <select id={`${tool.key}-${field.name}`} className="h-10 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm" value={values[field.name] ?? ""} onChange={(event) => setValue(field.name, event.target.value)} required><option value="" disabled>Select an answer</option>{field.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>}
          <Button type="button" size="sm" variant="outline" onClick={() => useDefault(field.name)}>Not sure</Button>
        </div>
        {prefilled ? <p className="text-xs text-muted-foreground">{field.name === "BMI" && record ? `Verified BMI measurement from ${new Date(record.observed_at).toLocaleDateString()}.` : field.name === "Diabetes_binary" ? `Verified diabetes status recorded ${new Date(patientInputs!.riskFactors.find((item) => item.factor_key === "diabetes_status" && item.verification_status === "verified")!.observed_at).toLocaleDateString()}.` : ["Sex", "GENDER"].includes(field.name) ? `Prefilled from your profile gender (${patientInputs?.patient.gender ?? "not available"}).` : `Prefilled from your profile date of birth (${patientInputs?.patient.date_of_birth ?? "not available"}).`} Review and confirm.</p> : null}
        {defaulted.includes(field.name) ? <p className="text-xs text-muted-foreground">Using documented default: {tool.defaults?.[field.name]}</p> : null}
      </div>;
    })}</div>
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" />I reviewed these values and confirm they are accurate to the best of my knowledge, including any documented defaults I selected.</label>
    <Button type="submit" disabled={busy || !confirmed}>{busy ? "Running model…" : "Run assessment"}</Button>
  </form>;
}
