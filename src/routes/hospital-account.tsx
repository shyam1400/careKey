import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { useAuth } from "@/hooks/useAuth";
import { carekeyRequest } from "@/lib/carekey-api";
import { formatDateTime } from "@/lib/carekey";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/hospital-account")({
  head: () => ({ meta: [{ title: "Hospital dashboard — CareKey" }] }),
  component: () => <RequireRole roles={["hospital", "hospital_admin"]}><HospitalAccountPage /></RequireRole>,
});

type Doctor = { id: string; email: string | null; full_name: string; specialty: string | null; is_active: boolean };
type Patient = { id: string; medical_id: string; full_name: string; email: string | null };
type ProcedurePatient = Pick<Patient, "id" | "medical_id" | "full_name">;
type Procedure = {
  id: string; patient_id: string; patient_name: string; doctor_id: string; doctor_name: string;
  name: string; status: "planned" | "in_progress" | "completed" | "cancelled"; notes: string | null;
  started_at: string; ended_at: string | null;
};
type AccessLog = {
  id: string; patient_name: string | null; doctor_name: string | null; hospital_name: string | null;
  action: string; reason: string | null; success: boolean; created_at: string;
};

function HospitalAccountPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const hospital = useQuery({ queryKey: ["hospital-account", "me", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<{ id: string; name: string; admin_name: string | null }>("/hospital-account/me", user!) });
  const dashboard = useQuery({ queryKey: ["hospital-account", "dashboard", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<{ doctor_count: number; patient_count: number; ongoing_procedure_count: number }>("/hospital-account/dashboard", user!) });
  const doctors = useQuery({ queryKey: ["hospital-account", "doctors", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Doctor[]>("/hospital-account/doctors", user!) });
  const patients = useQuery({ queryKey: ["hospital-account", "patients", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Patient[]>("/hospital-account/patients", user!) });
  const procedures = useQuery({ queryKey: ["hospital-account", "procedures", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<Procedure[]>("/hospital-account/procedures", user!) });
  const logs = useQuery({ queryKey: ["hospital-account", "logs", user?.id], enabled: !!user,
    queryFn: () => carekeyRequest<AccessLog[]>("/hospital-account/access-logs", user!) });
  const [medicalId, setMedicalId] = useState("");
  const [procedurePatient, setProcedurePatient] = useState<ProcedurePatient | null>(null);
  const [doctorId, setDoctorId] = useState("");

  async function findProcedurePatient() {
    if (!user || !medicalId.trim()) return;
    setProcedurePatient(null);
    try {
      const patient = await carekeyRequest<ProcedurePatient>(`/hospital-account/patients/lookup?medical_id=${encodeURIComponent(medicalId.trim())}`, user);
      setProcedurePatient(patient);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not find that patient");
    }
  }

  async function addProcedure(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;
    const form = new FormData(event.currentTarget);
    try {
      await carekeyRequest("/hospital-account/procedures", user, { method: "POST", body: JSON.stringify({
        patient_id: procedurePatient?.id, doctor_id: doctorId, name: String(form.get("name") || "").trim(),
        notes: String(form.get("notes") || "").trim() || null,
      }) });
      toast.success("Procedure added to the hospital tracker");
      event.currentTarget.reset(); setMedicalId(""); setProcedurePatient(null); setDoctorId("");
      await Promise.all([qc.invalidateQueries({ queryKey: ["hospital-account", "procedures"] }),
        qc.invalidateQueries({ queryKey: ["hospital-account", "dashboard"] }),
        qc.invalidateQueries({ queryKey: ["hospital-account", "patients"] })]);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not add procedure"); }
  }

  async function updateProcedure(id: string, status: Procedure["status"]) {
    if (!user) return;
    try {
      await carekeyRequest(`/hospital-account/procedures/${id}`, user, { method: "PATCH", body: JSON.stringify({ status }) });
      await Promise.all([qc.invalidateQueries({ queryKey: ["hospital-account", "procedures"] }),
        qc.invalidateQueries({ queryKey: ["hospital-account", "dashboard"] })]);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not update procedure"); }
  }

  async function setDoctorActive(doctor: Doctor) {
    if (!user || !window.confirm(`${doctor.is_active ? "Deactivate" : "Reactivate"} ${doctor.full_name}?`)) return;
    try {
      await carekeyRequest(`/hospital-account/doctors/${doctor.id}/status?is_active=${!doctor.is_active}`, user, { method: "PATCH" });
      toast.success(doctor.is_active ? "Doctor deactivated" : "Doctor reactivated");
      await qc.invalidateQueries({ queryKey: ["hospital-account", "doctors"] });
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not update doctor"); }
  }

  async function saveDoctor(doctor: Doctor, fullName: string, specialty: string): Promise<boolean> {
    if (!user) return false;
    try {
      await carekeyRequest(`/hospital-account/doctors/${doctor.id}`, user, { method: "PATCH", body: JSON.stringify({
        full_name: fullName.trim(), specialty: specialty.trim() || null,
      }) });
      toast.success("Doctor profile updated");
      await qc.invalidateQueries({ queryKey: ["hospital-account", "doctors"] });
      return true;
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not update doctor"); return false; }
  }

  return <div className="space-y-7">
    <PageHeading title={hospital.data?.name ?? "Hospital dashboard"} description="Manage your hospital’s care team, patient activity and ongoing procedures." />
    {hospital.error ? <p role="alert" className="text-sm text-destructive">Could not load hospital account: {hospital.error.message}</p> : null}
    <section className="grid gap-3 sm:grid-cols-3">
      {[ ["Doctors", dashboard.data?.doctor_count], ["Patients seen", dashboard.data?.patient_count], ["Ongoing procedures", dashboard.data?.ongoing_procedure_count] ].map(([label, count]) =>
        <div key={label} className="card-surface p-4"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-semibold">{count ?? "—"}</p></div>)}
    </section>
    <section className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-3"><h2 className="text-lg font-semibold">Doctors</h2>
        {(doctors.data ?? []).map((doctor) => <HospitalDoctorRow key={doctor.id} doctor={doctor}
          onSave={(name, specialty) => saveDoctor(doctor, name, specialty)} onToggle={() => setDoctorActive(doctor)} />)}
        {!doctors.isLoading && !doctors.data?.length ? <p className="card-surface p-4 text-sm text-muted-foreground">No doctors are assigned to this hospital yet. A platform administrator can assign them.</p> : null}
      </div>
      <div className="space-y-3"><h2 className="text-lg font-semibold">Patient roster</h2>
        {(patients.data ?? []).map((patient) => <div key={patient.id} className="card-surface p-3"><p className="font-medium">{patient.full_name}</p><p className="text-sm text-muted-foreground">Medical ID {patient.medical_id}</p></div>)}
        {!patients.isLoading && !patients.data?.length ? <p className="card-surface p-4 text-sm text-muted-foreground">Patients appear here after access at this hospital is recorded or a procedure is added.</p> : null}
      </div>
    </section>
    <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <form className="card-surface space-y-3 p-5" onSubmit={(event) => void addProcedure(event)}>
        <div><h2 className="text-lg font-semibold">Track a procedure</h2><p className="text-sm text-muted-foreground">Choose a patient and a doctor from this hospital.</p></div>
        <div className="space-y-1.5"><Label htmlFor="procedure-medical-id">Patient CareKey Medical ID</Label><div className="flex gap-2"><Input id="procedure-medical-id" placeholder="CK-XXXXXXXX" value={medicalId} onChange={(event) => { setMedicalId(event.target.value.toUpperCase()); setProcedurePatient(null); }} /><Button type="button" variant="outline" onClick={() => void findProcedurePatient()} disabled={!/^CK-[0-9A-F]{8}$/.test(medicalId.trim())}>Find patient</Button></div>
          {procedurePatient ? <p className="text-sm text-success">Selected: {procedurePatient.full_name} · {procedurePatient.medical_id}</p> : <p className="text-xs text-muted-foreground">Enter the ID shown on the patient’s CareKey profile or emergency QR.</p>}</div>
        <div className="space-y-1.5"><Label>Doctor</Label><select className="h-10 w-full rounded-md border bg-background px-3 text-sm" required value={doctorId} onChange={(event) => setDoctorId(event.target.value)}><option value="">Select doctor</option>{(doctors.data ?? []).filter((doctor) => doctor.is_active).map((doctor) => <option key={doctor.id} value={doctor.id}>{doctor.full_name}</option>)}</select></div>
        <div className="space-y-1.5"><Label>Procedure</Label><Input name="name" required maxLength={160} /></div>
        <div className="space-y-1.5"><Label>Notes</Label><Input name="notes" /></div>
        {!doctors.isLoading && !doctors.data?.some((doctor) => doctor.is_active) ? <p role="alert" className="text-sm text-destructive">No active doctor is assigned to this hospital. Ask a platform administrator to assign one before tracking a procedure.</p> : null}
        <Button type="submit" disabled={!procedurePatient || !doctorId || !doctors.data?.some((doctor) => doctor.is_active)}>Add to tracker</Button>
      </form>
      <div className="space-y-3"><h2 className="text-lg font-semibold">Procedures</h2>
        {(procedures.data ?? []).map((procedure) => <div key={procedure.id} className="card-surface space-y-2 p-4">
          <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-medium">{procedure.name}</p><p className="text-sm text-muted-foreground">{procedure.patient_name} · Dr. {procedure.doctor_name}</p></div>
            <select aria-label={`Status for ${procedure.name}`} className="h-9 rounded-md border bg-background px-2 text-sm" value={procedure.status} onChange={(event) => void updateProcedure(procedure.id, event.target.value as Procedure["status"])}>{["planned", "in_progress", "completed", "cancelled"].map((value) => <option key={value} value={value}>{value.replace("_", " ")}</option>)}</select></div>
          {procedure.notes ? <p className="text-sm">{procedure.notes}</p> : null}<p className="text-xs text-muted-foreground">Started {formatDateTime(procedure.started_at)}{procedure.ended_at ? ` · ended ${formatDateTime(procedure.ended_at)}` : ""}</p>
        </div>)}
        {!procedures.isLoading && !procedures.data?.length ? <p className="card-surface p-4 text-sm text-muted-foreground">No procedures are being tracked.</p> : null}
      </div>
    </section>
    <section className="space-y-3"><div><h2 className="text-lg font-semibold">Doctor access activity</h2><p className="text-sm text-muted-foreground">Records accessed by doctors assigned to this hospital.</p></div>
      {(logs.data ?? []).map((log) => <div key={log.id} className="card-surface p-3 text-sm"><p className="font-medium">{log.action}</p><p className="text-xs text-muted-foreground">{log.doctor_name || "Unknown doctor"} · {log.hospital_name || hospital.data?.name || "Hospital"}{log.patient_name ? ` · Patient: ${log.patient_name}` : ""} · {formatDateTime(log.created_at)} · {log.success ? "success" : "failed"}</p>{log.reason ? <p className="mt-1 text-xs">Reason: {log.reason}</p> : null}</div>)}
      {!logs.isLoading && !logs.data?.length ? <p className="card-surface p-4 text-sm text-muted-foreground">No doctor access activity yet.</p> : null}
    </section>
  </div>;
}

function HospitalDoctorRow({ doctor, onSave, onToggle }: {
  doctor: Doctor; onSave: (name: string, specialty: string) => Promise<boolean>; onToggle: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(doctor.full_name);
  const [specialty, setSpecialty] = useState(doctor.specialty ?? "");
  return <div className="card-surface space-y-3 p-3">
    {editing ? <>
      <div className="space-y-1.5"><Label>Doctor name</Label><Input value={name} maxLength={100} onChange={(event) => setName(event.target.value)} /></div>
      <div className="space-y-1.5"><Label>Specialty</Label><Input value={specialty} maxLength={120} onChange={(event) => setSpecialty(event.target.value)} /></div>
      <div className="flex gap-2"><Button size="sm" onClick={() => void onSave(name, specialty).then((saved) => { if (saved) setEditing(false); })}>Save</Button><Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancel</Button></div>
    </> : <div className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="font-medium">{doctor.full_name}</p><p className="text-sm text-muted-foreground">{doctor.specialty || "Doctor"} · {doctor.email || ""} · {doctor.is_active ? "Active" : "Inactive"}</p></div>
      <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setEditing(true)}>Edit profile</Button><Button size="sm" variant="outline" onClick={onToggle}>{doctor.is_active ? "Deactivate" : "Reactivate"}</Button></div>
    </div>}
  </div>;
}
