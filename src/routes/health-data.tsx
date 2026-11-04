import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

const measurementOptions = [
  ["systolic_blood_pressure", "Systolic blood pressure", "mmHg"],
  ["diastolic_blood_pressure", "Diastolic blood pressure", "mmHg"],
  ["height", "Height", "cm"], ["weight", "Weight", "kg"], ["bmi", "BMI", "kg/m2"],
  ["total_cholesterol", "Total cholesterol", "mg/dL"], ["hdl_cholesterol", "HDL cholesterol", "mg/dL"],
  ["ldl_cholesterol", "LDL cholesterol", "mg/dL"], ["triglycerides", "Triglycerides", "mg/dL"],
  ["fasting_glucose", "Fasting glucose", "mg/dL"], ["random_glucose", "Random glucose", "mg/dL"],
  ["hba1c", "HbA1c", "%"], ["serum_creatinine", "Serum creatinine", "mg/dL"],
  ["egfr", "eGFR", "mL/min/1.73m2"], ["uacr", "Urine albumin-creatinine ratio", "mg/g"],
] as const;

type Measurement = {
  id: string; measurement_type: string; value: string; unit: string; observed_at: string;
  source_type: string; source_document_id: string | null; verification_status: string;
};
type FamilyHistory = {
  id: string; relationship_to_patient: string; condition: string; age_at_diagnosis: number | null;
  diagnosis_date: string | null; source_type: string; verification_status: string;
};
type PatientRiskFactor = {
  id: string; factor_key: "current_smoking" | "diabetes_status"; value: boolean;
  observed_at: string; source_type: string; verification_status: string;
};
type ExtractionDetail = {
  id: string; status: string; candidate_count: number;
  candidates: Array<{ id: string; measurement_type: string; value: string; unit: string; source_page: number; review_status: string }>;
};

export const Route = createFileRoute("/health-data")({
  head: () => ({ meta: [{ title: "Health data — CareKey" }] }),
  component: () => <RequireRole roles={["patient"]}><HealthDataPage /></RequireRole>,
});

function HealthDataPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [type, setType] = useState<(typeof measurementOptions)[number][0]>("systolic_blood_pressure");
  const [unit, setUnit] = useState("mmHg");
  const [value, setValue] = useState("");
  const [observedAt, setObservedAt] = useState("");
  const [sourceType, setSourceType] = useState("patient_reported");
  const [documentId, setDocumentId] = useState("");
  const [relative, setRelative] = useState("mother");
  const [condition, setCondition] = useState("");
  const [age, setAge] = useState("");
  const [diagnosisDate, setDiagnosisDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [reportId, setReportId] = useState("");
  const [extractionId, setExtractionId] = useState("");
  const [candidateDates, setCandidateDates] = useState<Record<string, string>>({});
  const [factorKey, setFactorKey] = useState<PatientRiskFactor["factor_key"]>("current_smoking");
  const [factorValue, setFactorValue] = useState("false");
  const [factorObservedAt, setFactorObservedAt] = useState("");

  const measurements = useQuery({
    queryKey: ["health-measurements", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Measurement[]>("/health-data/measurements", user!),
  });
  const familyHistory = useQuery({
    queryKey: ["family-history", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<FamilyHistory[]>("/health-data/family-history", user!),
  });
  const riskFactors = useQuery({
    queryKey: ["patient-risk-factors", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<PatientRiskFactor[]>("/health-data/risk-factors", user!),
  });
  const documents = useQuery({
    queryKey: ["documents", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Array<{ id: string; file_name: string; doc_type: string }>>("/records/documents", user!),
  });
  const extraction = useQuery({
    queryKey: ["report-extraction", extractionId], enabled: !!user && !!extractionId,
    queryFn: () => carekeyRequest<ExtractionDetail>(`/health-data/extractions/${extractionId}`, user!),
  });

  async function runExtraction() {
    if (!user || !reportId) return toast.error("Choose a lab report first");
    setBusy(true);
    try {
      const result = await carekeyRequest<{ id: string }>(`/health-data/reports/${reportId}/extract`, user, { method: "POST" });
      setExtractionId(result.id);
      toast.success("Report processed. Review each value before saving it.");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not extract report"); }
    finally { setBusy(false); }
  }

  async function reviewCandidate(candidateId: string, action: "verify" | "reject") {
    if (!user) return;
    try {
      await carekeyRequest(`/health-data/extractions/candidates/${candidateId}/${action}`, user, {
        method: "POST",
        ...(action === "verify" ? { body: JSON.stringify({ observed_at: candidateDates[candidateId] ? new Date(candidateDates[candidateId]).toISOString() : null }) } : {}),
      });
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["report-extraction", extractionId] }),
        qc.invalidateQueries({ queryKey: ["health-measurements", user.id] }),
      ]);
      toast.success(action === "verify" ? "Value confirmed and added to health data" : "Value rejected");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not review value"); }
  }

  async function addMeasurement(event: React.FormEvent) {
    event.preventDefault();
    if (!user || !observedAt || !value) return toast.error("Enter the value and date measured");
    setBusy(true);
    try {
      await carekeyRequest("/health-data/measurements", user, { method: "POST", body: JSON.stringify({
        measurement_type: type, value: Number(value), unit, observed_at: new Date(observedAt).toISOString(),
        source_type: sourceType, source_document_id: sourceType === "lab_report" ? documentId : null,
      }) });
      setValue("");
      await qc.invalidateQueries({ queryKey: ["health-measurements", user.id] });
      toast.success("Measurement saved. It is marked unverified until confirmed.");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not save measurement"); }
    finally { setBusy(false); }
  }

  async function addRiskFactor(event: React.FormEvent) {
    event.preventDefault();
    if (!user || !factorObservedAt) return toast.error("Enter when this information was true");
    setBusy(true);
    try {
      await carekeyRequest("/health-data/risk-factors", user, { method: "POST", body: JSON.stringify({
        factor_key: factorKey, value: factorValue === "true", observed_at: new Date(factorObservedAt).toISOString(),
        source_type: "patient_reported",
      }) });
      await qc.invalidateQueries({ queryKey: ["patient-risk-factors", user.id] });
      toast.success("Information saved. Confirm it below before it can be used in an assessment.");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not save this information"); }
    finally { setBusy(false); }
  }

  async function verifyRiskFactor(id: string) {
    if (!user) return;
    try {
      await carekeyRequest(`/health-data/risk-factors/${id}/verify`, user, { method: "POST" });
      await qc.invalidateQueries({ queryKey: ["patient-risk-factors", user.id] });
      toast.success("Information confirmed");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not confirm information"); }
  }

  async function verifyMeasurement(id: string) {
    if (!user) return;
    try {
      await carekeyRequest(`/health-data/measurements/${id}/verify`, user, { method: "POST" });
      await qc.invalidateQueries({ queryKey: ["health-measurements", user.id] });
      toast.success("Measurement confirmed");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not confirm measurement"); }
  }

  async function addFamilyHistory(event: React.FormEvent) {
    event.preventDefault();
    if (!user || !condition.trim()) return toast.error("Enter a condition");
    setBusy(true);
    try {
      await carekeyRequest("/health-data/family-history", user, { method: "POST", body: JSON.stringify({
        relationship_to_patient: relative, condition: condition.trim(), age_at_diagnosis: age ? Number(age) : null,
        diagnosis_date: diagnosisDate || null,
      }) });
      setCondition(""); setAge(""); setDiagnosisDate("");
      await qc.invalidateQueries({ queryKey: ["family-history", user.id] });
      toast.success("Family history saved as patient reported");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not save family history"); }
    finally { setBusy(false); }
  }

  async function remove(path: string, id: string, key: string) {
    if (!user) return;
    try {
      await carekeyRequest(`${path}/${id}`, user, { method: "DELETE" });
      await qc.invalidateQueries({ queryKey: [key, user.id] });
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not delete entry"); }
  }

  const selected = measurementOptions.find(([key]) => key === type)!;
  return <>
    <PageHeading title="Health data" description="Record measurements and family history with dates and source details. Entries remain unverified until confirmed." />
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="card-surface space-y-4 p-5">
        <div className="space-y-3 rounded-md border p-4">
          <h2 className="font-semibold">WHO cardiovascular chart inputs</h2>
          <p className="text-xs text-muted-foreground">Record current smoking and any history of diabetes. CareKey only uses the latest entry after you confirm it. Patient confirmation records your review; it is not independent clinical verification.</p>
          <form className="grid gap-3 sm:grid-cols-2" onSubmit={addRiskFactor}>
            <div className="space-y-1.5"><Label>Information</Label><Select value={factorKey} onValueChange={(v) => setFactorKey(v as PatientRiskFactor["factor_key"])}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="current_smoking">Current smoking</SelectItem><SelectItem value="diabetes_status">Diabetes status</SelectItem></SelectContent></Select></div>
            <div className="space-y-1.5"><Label>{factorKey === "current_smoking" ? "Currently smoking?" : "Have a history of diabetes?"}</Label><Select value={factorValue} onValueChange={setFactorValue}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="true">Yes</SelectItem><SelectItem value="false">No</SelectItem></SelectContent></Select></div>
            <div className="space-y-1.5 sm:col-span-2"><Label>Date and time this status was true</Label><Input required type="datetime-local" value={factorObservedAt} onChange={(e) => setFactorObservedAt(e.target.value)} /></div>
            <Button type="submit" disabled={busy}>Save status</Button>
          </form>
          <div className="divide-y rounded-md border">{(riskFactors.data ?? []).map((row) => <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
            <span>{row.factor_key === "current_smoking" ? "Current smoking" : "Diabetes"}: <strong>{row.value ? "Yes" : "No"}</strong><span className="block text-xs text-muted-foreground">{new Date(row.observed_at).toLocaleString()} · {row.source_type.replaceAll("_", " ")}</span></span>
            <div className="flex items-center gap-2"><Badge variant="outline">{row.verification_status}</Badge>{row.verification_status === "unverified" ? <Button size="sm" variant="outline" onClick={() => void verifyRiskFactor(row.id)}>Confirm</Button> : null}<Button size="sm" variant="ghost" onClick={() => void remove("/health-data/risk-factors", row.id, "patient-risk-factors")}>Delete</Button></div>
          </div>)}{!riskFactors.data?.length ? <p className="p-3 text-xs text-muted-foreground">No smoking or diabetes status recorded.</p> : null}</div>
        </div>
        <h2 className="font-semibold">Add a measurement</h2>
        <form className="space-y-3" onSubmit={addMeasurement}>
          <div className="space-y-1.5"><Label>Measurement</Label><Select value={type} onValueChange={(next) => {
            const option = measurementOptions.find(([key]) => key === next)!; setType(option[0]); setUnit(option[2]);
          }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{measurementOptions.map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}</SelectContent></Select></div>
          <div className="grid grid-cols-2 gap-3"><div className="space-y-1.5"><Label>Value</Label><Input required type="number" step="any" value={value} onChange={(e) => setValue(e.target.value)} /></div>
            <div className="space-y-1.5"><Label>Unit</Label><Select value={unit} onValueChange={setUnit}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{(type === "height" ? ["cm", "m", "in"] : type === "weight" ? ["kg", "lb"] : type.includes("cholesterol") || type === "triglycerides" || type.includes("glucose") ? ["mg/dL", "mmol/L"] : type === "hba1c" ? ["%", "mmol/mol"] : type === "serum_creatinine" ? ["mg/dL", "umol/L"] : type === "uacr" ? ["mg/g", "mg/mmol"] : [selected[2]]).map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent></Select></div></div>
          <div className="space-y-1.5"><Label>Date and time measured</Label><Input required type="datetime-local" value={observedAt} onChange={(e) => setObservedAt(e.target.value)} /></div>
          <div className="space-y-1.5"><Label>Source</Label><Select value={sourceType} onValueChange={setSourceType}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="patient_reported">Patient reported</SelectItem><SelectItem value="home_device">Home device</SelectItem><SelectItem value="clinician_entered">Clinician entered</SelectItem><SelectItem value="lab_report">Lab report</SelectItem></SelectContent></Select></div>
          {sourceType === "lab_report" ? <div className="space-y-1.5"><Label>Source report</Label><Select value={documentId} onValueChange={setDocumentId}><SelectTrigger><SelectValue placeholder="Choose uploaded report" /></SelectTrigger><SelectContent>{(documents.data ?? []).map((doc) => <SelectItem key={doc.id} value={doc.id}>{doc.file_name}</SelectItem>)}</SelectContent></Select></div> : null}
          <Button type="submit" disabled={busy || (sourceType === "lab_report" && !documentId)}>Save measurement</Button>
        </form>
        <div className="divide-y rounded-md border">{(measurements.data ?? []).map((row) => <div key={row.id} className="flex items-center justify-between gap-3 p-3 text-sm">
          <span>{row.measurement_type.replaceAll("_", " ")}: <strong>{row.value} {row.unit}</strong><span className="block text-xs text-muted-foreground">{new Date(row.observed_at).toLocaleString()} · {row.source_type.replaceAll("_", " ")}</span></span>
          <div className="flex items-center gap-2"><Badge variant="outline">{row.verification_status}</Badge>{row.verification_status === "unverified" ? <Button size="sm" variant="outline" onClick={() => void verifyMeasurement(row.id)}>Confirm</Button> : null}<Button size="sm" variant="ghost" onClick={() => void remove("/health-data/measurements", row.id, "health-measurements")}>Delete</Button></div>
        </div>)}{!measurements.data?.length ? <p className="p-4 text-sm text-muted-foreground">No measurements saved yet.</p> : null}</div>
        <div className="space-y-3 rounded-md border p-4">
          <h3 className="text-sm font-semibold">Extract lab values from a report</h3>
          <p className="text-xs text-muted-foreground">Text-based PDFs only. Extracted results stay pending until you check each value and confirm its measurement date.</p>
          <div className="flex gap-2"><Select value={reportId} onValueChange={setReportId}><SelectTrigger><SelectValue placeholder="Choose uploaded lab report" /></SelectTrigger><SelectContent>{(documents.data ?? []).filter((doc) => doc.doc_type === "lab_report").map((doc) => <SelectItem key={doc.id} value={doc.id}>{doc.file_name}</SelectItem>)}</SelectContent></Select><Button variant="outline" onClick={() => void runExtraction()} disabled={busy || !reportId}>Extract</Button></div>
          {extraction.data ? <div className="space-y-2 border-t pt-3"><p className="text-xs text-muted-foreground">{extraction.data.status.replaceAll("_", " ")} · {extraction.data.candidate_count} candidate value(s)</p>{extraction.data.candidates.map((candidate) => <div key={candidate.id} className="space-y-2 rounded-md bg-muted p-3 text-sm"><p><strong>{candidate.measurement_type.replaceAll("_", " ")}: {candidate.value} {candidate.unit}</strong> · page {candidate.source_page} · {candidate.review_status}</p>{candidate.review_status === "pending" ? <div className="flex flex-wrap items-end gap-2"><div className="space-y-1"><Label>Measurement date</Label><Input type="datetime-local" value={candidateDates[candidate.id] ?? ""} onChange={(e) => setCandidateDates({ ...candidateDates, [candidate.id]: e.target.value })} /></div><Button size="sm" disabled={!candidateDates[candidate.id]} onClick={() => void reviewCandidate(candidate.id, "verify")}>Confirm value</Button><Button size="sm" variant="outline" onClick={() => void reviewCandidate(candidate.id, "reject")}>Reject</Button></div> : null}</div>)}</div> : null}
        </div>
      </section>

      <section className="card-surface space-y-4 p-5">
        <h2 className="font-semibold">Family medical history</h2>
        <form className="space-y-3" onSubmit={addFamilyHistory}>
          <div className="space-y-1.5"><Label>Relative</Label><Select value={relative} onValueChange={setRelative}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["mother", "father", "sister", "brother", "daughter", "son", "grandmother", "grandfather", "aunt", "uncle", "other"].map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1.5"><Label>Condition</Label><Input required value={condition} maxLength={120} placeholder="For example, type 2 diabetes" onChange={(e) => setCondition(e.target.value)} /></div>
          <div className="grid grid-cols-2 gap-3"><div className="space-y-1.5"><Label>Age when diagnosed</Label><Input type="number" min="0" max="120" value={age} onChange={(e) => setAge(e.target.value)} /></div><div className="space-y-1.5"><Label>Diagnosis date (optional)</Label><Input type="date" value={diagnosisDate} onChange={(e) => setDiagnosisDate(e.target.value)} /></div></div>
          <Button type="submit" disabled={busy}>Save family history</Button>
        </form>
        <div className="divide-y rounded-md border">{(familyHistory.data ?? []).map((row) => <div key={row.id} className="flex items-center justify-between gap-3 p-3 text-sm">
          <span><strong>{row.condition}</strong> · {row.relationship_to_patient}<span className="block text-xs text-muted-foreground">{row.age_at_diagnosis == null ? "Age unknown" : `Diagnosed at ${row.age_at_diagnosis}`} · {row.source_type.replaceAll("_", " ")}</span></span>
          <div className="flex items-center gap-2"><Badge variant="outline">{row.verification_status}</Badge><Button size="sm" variant="ghost" onClick={() => void remove("/health-data/family-history", row.id, "family-history")}>Delete</Button></div>
        </div>)}{!familyHistory.data?.length ? <p className="p-4 text-sm text-muted-foreground">No family history entries yet.</p> : null}</div>
      </section>
    </div>
  </>;
}
