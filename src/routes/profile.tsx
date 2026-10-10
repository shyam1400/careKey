import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { carekeyRequest, type Patient } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BLOOD_GROUPS, SEVERITIES, formatDate } from "@/lib/carekey";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "Medical profile — CareKey" },
      {
        name: "description",
        content:
          "Manage your basic details, blood group, allergies, conditions, medications and surgeries.",
      },
      { property: "og:title", content: "Medical profile — CareKey" },
      {
        property: "og:description",
        content: "Keep your emergency medical information accurate and up to date.",
      },
    ],
  }),
  component: () => (
    <RequireRole roles={["patient"]}>
      <ProfilePage />
    </RequireRole>
  ),
});

function ProfilePage() {
  return (
    <>
      <PageHeading
        title="Medical profile"
        description="This information powers your emergency profile and anything you choose to share."
      />
      <Tabs defaultValue="basic">
        <TabsList className="mb-6 flex flex-wrap">
          <TabsTrigger value="basic">Basic & blood</TabsTrigger>
          <TabsTrigger value="allergies">Allergies</TabsTrigger>
          <TabsTrigger value="conditions">Conditions</TabsTrigger>
          <TabsTrigger value="medications">Medications</TabsTrigger>
          <TabsTrigger value="surgeries">Surgeries</TabsTrigger>
        </TabsList>
        <TabsContent value="basic">
          <BasicSection />
        </TabsContent>
        <TabsContent value="allergies">
          <AllergiesSection />
        </TabsContent>
        <TabsContent value="conditions">
          <ConditionsSection />
        </TabsContent>
        <TabsContent value="medications">
          <MedicationsSection />
        </TabsContent>
        <TabsContent value="surgeries">
          <SurgeriesSection />
        </TabsContent>
      </Tabs>
    </>
  );
}

function BasicSection() {
  const { user, profile, refresh } = useAuth();
  const [form, setForm] = useState({
    full_name: "",
    date_of_birth: "",
    gender: "",
    phone: "",
    address: "",
    emergency_contact_name: "",
    emergency_contact_phone: "",
    blood_group: "",
    rh_factor: "positive",
  });
  const [busy, setBusy] = useState(false);

  const { data } = useQuery({
    queryKey: ["patient-basic", user?.id],
    enabled: !!user,
    queryFn: async () => {
      return carekeyRequest<Patient>(`/patients/${user!.id}`, user!);
    },
  });

  useEffect(() => {
    if (!data) return;
    setForm({
      full_name: profile?.full_name ?? "",
      date_of_birth: data.date_of_birth ?? "",
      gender: data.gender ?? "",
      phone: data.phone ?? "",
      address: data.address ?? "",
      emergency_contact_name: data.emergency_contact_name ?? "",
      emergency_contact_phone: data.emergency_contact_phone ?? "",
      blood_group: data.blood_group ?? "",
      rh_factor: data.rh_factor ?? "positive",
    });
  }, [data, profile]);

  async function save() {
    if (!user) return;
    if (!form.full_name.trim()) {
      toast.error("Full name is required");
      return;
    }
    setBusy(true);
    try {
      await carekeyRequest(`/patients/${user.id}`, user, {
        method: "PATCH",
        body: JSON.stringify({
        full_name: form.full_name.trim().slice(0, 100),
        date_of_birth: form.date_of_birth || null,
        gender: form.gender || null,
        phone: form.phone.slice(0, 20) || null,
        address: form.address.slice(0, 300) || null,
        emergency_contact_name: form.emergency_contact_name.slice(0, 100) || null,
        emergency_contact_phone: form.emergency_contact_phone.slice(0, 20) || null,
        blood_group: form.blood_group || null,
        rh_factor: form.rh_factor || null,
        }),
      });
    } catch (error) {
      setBusy(false);
      toast.error(error instanceof Error ? error.message : "Could not save profile");
      return;
    }
    setBusy(false);
    await refresh();
    toast.success("Profile saved");
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="card-surface space-y-4 p-6">
        <h2 className="font-semibold">Basic information</h2>
        <Field label="Full name">
          <Input
            value={form.full_name}
            maxLength={100}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </Field>
        <Field label="Date of birth">
          <Input
            type="date"
            value={form.date_of_birth}
            onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
          />
        </Field>
        <Field label="Gender">
          <Select
            value={form.gender || undefined}
            onValueChange={(v) => setForm({ ...form, gender: v })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="female">Female</SelectItem>
              <SelectItem value="male">Male</SelectItem>
              <SelectItem value="other">Other</SelectItem>
              <SelectItem value="undisclosed">Prefer not to say</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Phone">
          <Input
            value={form.phone}
            maxLength={20}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
        </Field>
        <Field label="Address">
          <Textarea
            value={form.address}
            maxLength={300}
            onChange={(e) => setForm({ ...form, address: e.target.value })}
          />
        </Field>
      </div>

      <div className="space-y-6">
        <div className="card-surface space-y-4 p-6">
          <h2 className="font-semibold">Emergency contact</h2>
          <Field label="Contact name">
            <Input
              value={form.emergency_contact_name}
              maxLength={100}
              onChange={(e) => setForm({ ...form, emergency_contact_name: e.target.value })}
            />
          </Field>
          <Field label="Contact phone">
            <Input
              value={form.emergency_contact_phone}
              maxLength={20}
              onChange={(e) => setForm({ ...form, emergency_contact_phone: e.target.value })}
            />
          </Field>
        </div>

        <div className="card-surface space-y-4 p-6">
          <h2 className="font-semibold">Blood information</h2>
          <Field label="Blood group">
            <Select
              value={form.blood_group || undefined}
              onValueChange={(v) => setForm({ ...form, blood_group: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select" />
              </SelectTrigger>
              <SelectContent>
                {BLOOD_GROUPS.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Rh factor">
            <Select
              value={form.rh_factor}
              onValueChange={(v) => setForm({ ...form, rh_factor: v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="positive">Positive (+)</SelectItem>
                <SelectItem value="negative">Negative (−)</SelectItem>
              </SelectContent>
            </Select>
          </Field>
        </div>

        <Button onClick={save} disabled={busy} className="w-full">
          {busy ? "Saving…" : "Save profile"}
        </Button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function useList(table: "allergies" | "conditions" | "medications" | "surgeries") {
  const { user } = useAuth();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: [table, user?.id],
    enabled: !!user,
    queryFn: async () => {
      return carekeyRequest<Record<string, unknown>[]>(`/records/${table}`, user!);
    },
  });

  return {
    ...query,
    userId: user?.id,
    async add(values: Record<string, unknown>) {
      try {
        await carekeyRequest(`/records/${table}`, user!, { method: "POST", body: JSON.stringify(values) });
      } catch (error) {
        return toast.error(error instanceof Error ? error.message : "Could not add record");
      }
      await qc.invalidateQueries({ queryKey: [table, user?.id] });
      toast.success("Added");
    },
    async remove(id: string) {
      try {
        await carekeyRequest(`/records/${table}/${id}`, user!, { method: "DELETE" });
      } catch (error) {
        return toast.error(error instanceof Error ? error.message : "Could not delete record");
      }
      await qc.invalidateQueries({ queryKey: [table, user?.id] });
      toast.success("Deleted");
    },
    async update(id: string, values: Record<string, unknown>) {
      try {
        await carekeyRequest(`/records/${table}/${id}`, user!, { method: "PATCH", body: JSON.stringify(values) });
      } catch (error) {
        return toast.error(error instanceof Error ? error.message : "Could not update record");
      }
      await qc.invalidateQueries({ queryKey: [table, user?.id] });
      toast.success("Updated");
    },
  };
}

function SectionShell({
  title,
  form,
  children,
}: {
  title: string;
  form: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-6 md:grid-cols-[360px_1fr]">
      <div className="card-surface h-fit space-y-4 p-6">
        <h2 className="font-semibold">{title}</h2>
        {form}
      </div>
      <div className="card-surface divide-y">{children}</div>
    </div>
  );
}

function AllergiesSection() {
  const list = useList("allergies");
  const [v, setV] = useState({ allergen: "", reaction: "", severity: "mild" });

  return (
    <SectionShell
      title="Add allergy"
      form={
        <>
          <Field label="Allergen">
            <Input value={v.allergen} maxLength={80} onChange={(e) => setV({ ...v, allergen: e.target.value })} />
          </Field>
          <Field label="Reaction">
            <Input value={v.reaction} maxLength={120} onChange={(e) => setV({ ...v, reaction: e.target.value })} />
          </Field>
          <Field label="Severity">
            <Select value={v.severity} onValueChange={(s) => setV({ ...v, severity: s })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SEVERITIES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Button
            className="w-full"
            onClick={async () => {
              if (!v.allergen.trim()) return toast.error("Allergen is required");
              await list.add(v);
              setV({ allergen: "", reaction: "", severity: "mild" });
            }}
          >
            Add allergy
          </Button>
        </>
      }
    >
      {(list.data ?? []).length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">No allergies recorded.</p>
      ) : (
        list.data!.map((row) => (
          <div key={String(row.id)} className="flex items-start justify-between gap-4 p-4">
            <div>
              <p className="font-medium">
                {String(row.allergen)}{" "}
                <Badge variant={row.severity === "severe" ? "destructive" : "secondary"}>
                  {String(row.severity)}
                </Badge>
              </p>
              <p className="text-sm text-muted-foreground">{String(row.reaction ?? "—")}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => list.remove(String(row.id))}>
              Delete
            </Button>
          </div>
        ))
      )}
    </SectionShell>
  );
}

function ConditionsSection() {
  const list = useList("conditions");
  const [v, setV] = useState({
    name: "",
    diagnosis_date: "",
    status: "active",
    critical: false,
    notes: "",
  });

  return (
    <SectionShell
      title="Add condition"
      form={
        <>
          <Field label="Condition">
            <Input value={v.name} maxLength={100} onChange={(e) => setV({ ...v, name: e.target.value })} />
          </Field>
          <Field label="Diagnosis date">
            <Input
              type="date"
              value={v.diagnosis_date}
              onChange={(e) => setV({ ...v, diagnosis_date: e.target.value })}
            />
          </Field>
          <Field label="Status">
            <Select value={v.status} onValueChange={(s) => setV({ ...v, status: s })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="managed">Managed</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <div className="flex items-center justify-between">
            <Label htmlFor="critical">Critical condition</Label>
            <Switch
              id="critical"
              checked={v.critical}
              onCheckedChange={(c) => setV({ ...v, critical: c })}
            />
          </div>
          <Field label="Notes">
            <Textarea value={v.notes} maxLength={300} onChange={(e) => setV({ ...v, notes: e.target.value })} />
          </Field>
          <Button
            className="w-full"
            onClick={async () => {
              if (!v.name.trim()) return toast.error("Condition is required");
              await list.add({ ...v, diagnosis_date: v.diagnosis_date || null });
              setV({ name: "", diagnosis_date: "", status: "active", critical: false, notes: "" });
            }}
          >
            Add condition
          </Button>
        </>
      }
    >
      {(list.data ?? []).length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">No conditions recorded.</p>
      ) : (
        list.data!.map((row) => (
          <div key={String(row.id)} className="flex items-start justify-between gap-4 p-4">
            <div>
              <p className="font-medium">
                {String(row.name)}{" "}
                {row.critical ? <Badge variant="destructive">critical</Badge> : null}{" "}
                <Badge variant="secondary">{String(row.status)}</Badge>
              </p>
              <p className="text-sm text-muted-foreground">
                Diagnosed {formatDate(row.diagnosis_date as string)} · {String(row.notes ?? "—")}
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => list.remove(String(row.id))}>
              Delete
            </Button>
          </div>
        ))
      )}
    </SectionShell>
  );
}

function MedicationsSection() {
  const list = useList("medications");
  const [v, setV] = useState({
    name: "",
    dosage: "",
    frequency: "",
    start_date: "",
    end_date: "",
    active: true,
  });

  return (
    <SectionShell
      title="Add medication"
      form={
        <>
          <Field label="Medicine name">
            <Input value={v.name} maxLength={100} onChange={(e) => setV({ ...v, name: e.target.value })} />
          </Field>
          <Field label="Dosage">
            <Input value={v.dosage} maxLength={60} onChange={(e) => setV({ ...v, dosage: e.target.value })} />
          </Field>
          <Field label="Frequency">
            <Input value={v.frequency} maxLength={60} onChange={(e) => setV({ ...v, frequency: e.target.value })} />
          </Field>
          <Field label="Start date">
            <Input type="date" value={v.start_date} onChange={(e) => setV({ ...v, start_date: e.target.value })} />
          </Field>
          <Field label="End date">
            <Input type="date" value={v.end_date} onChange={(e) => setV({ ...v, end_date: e.target.value })} />
          </Field>
          <div className="flex items-center justify-between">
            <Label htmlFor="active">Currently taking</Label>
            <Switch id="active" checked={v.active} onCheckedChange={(c) => setV({ ...v, active: c })} />
          </div>
          <Button
            className="w-full"
            onClick={async () => {
              if (!v.name.trim()) return toast.error("Medicine name is required");
              await list.add({
                ...v,
                start_date: v.start_date || null,
                end_date: v.end_date || null,
              });
              setV({ name: "", dosage: "", frequency: "", start_date: "", end_date: "", active: true });
            }}
          >
            Add medication
          </Button>
        </>
      }
    >
      {(list.data ?? []).length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">No medications recorded.</p>
      ) : (
        list.data!.map((row) => (
          <div key={String(row.id)} className="flex items-start justify-between gap-4 p-4">
            <div>
              <p className="font-medium">
                {String(row.name)} {String(row.dosage ?? "")}{" "}
                {row.active ? <Badge variant="secondary">active</Badge> : <Badge variant="outline">stopped</Badge>}
              </p>
              <p className="text-sm text-muted-foreground">
                {String(row.frequency ?? "—")} · from {formatDate(row.start_date as string)}
              </p>
            </div>
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => list.update(String(row.id), { active: !row.active })}
              >
                {row.active ? "Stop" : "Resume"}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => list.remove(String(row.id))}>
                Delete
              </Button>
            </div>
          </div>
        ))
      )}
    </SectionShell>
  );
}

function SurgeriesSection() {
  const list = useList("surgeries");
  const [v, setV] = useState({
    procedure: "",
    surgery_date: "",
    hospital: "",
    major: false,
    notes: "",
  });

  return (
    <SectionShell
      title="Add surgery"
      form={
        <>
          <Field label="Procedure">
            <Input value={v.procedure} maxLength={120} onChange={(e) => setV({ ...v, procedure: e.target.value })} />
          </Field>
          <Field label="Date">
            <Input type="date" value={v.surgery_date} onChange={(e) => setV({ ...v, surgery_date: e.target.value })} />
          </Field>
          <Field label="Hospital">
            <Input value={v.hospital} maxLength={120} onChange={(e) => setV({ ...v, hospital: e.target.value })} />
          </Field>
          <div className="flex items-center justify-between">
            <Label htmlFor="major">Major surgery</Label>
            <Switch id="major" checked={v.major} onCheckedChange={(c) => setV({ ...v, major: c })} />
          </div>
          <Field label="Notes">
            <Textarea value={v.notes} maxLength={300} onChange={(e) => setV({ ...v, notes: e.target.value })} />
          </Field>
          <Button
            className="w-full"
            onClick={async () => {
              if (!v.procedure.trim()) return toast.error("Procedure is required");
              await list.add({ ...v, surgery_date: v.surgery_date || null });
              setV({ procedure: "", surgery_date: "", hospital: "", major: false, notes: "" });
            }}
          >
            Add surgery
          </Button>
        </>
      }
    >
      {(list.data ?? []).length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">No surgeries recorded.</p>
      ) : (
        list.data!.map((row) => (
          <div key={String(row.id)} className="flex items-start justify-between gap-4 p-4">
            <div>
              <p className="font-medium">
                {String(row.procedure)} {row.major ? <Badge variant="destructive">major</Badge> : null}
              </p>
              <p className="text-sm text-muted-foreground">
                {formatDate(row.surgery_date as string)} · {String(row.hospital ?? "—")}
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => list.remove(String(row.id))}>
              Delete
            </Button>
          </div>
        ))
      )}
    </SectionShell>
  );
}
