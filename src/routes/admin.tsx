import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { formatDateTime } from "@/lib/carekey";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Admin — CareKey" },
      { name: "description", content: "Manage CareKey demo users, hospitals, and access activity." },
      { property: "og:title", content: "Admin — CareKey" },
      { property: "og:description", content: "CareKey administration for the research prototype." },
    ],
  }),
  component: () => (
    <RequireRole roles={["admin"]}>
      <AdminPage />
    </RequireRole>
  ),
});

type AdminUser = {
  id: string;
  email: string | null;
  full_name: string | null;
  role: "patient" | "doctor" | "hospital" | "hospital_admin" | "admin";
  hospital_id: string | null;
  hospital_name: string | null;
  is_active: boolean;
  organization: string | null;
  specialty: string | null;
};

type Hospital = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  address: string | null;
  phone: string | null;
  emergency: boolean;
  trauma: boolean;
  ambulance: boolean;
  open_24h: boolean;
};

type HospitalFields = Omit<Hospital, "id">;

function AdminPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const logs = useQuery({
    queryKey: ["admin-logs", user?.id],
    enabled: !!user,
    queryFn: () => carekeyRequest<Array<{ id: string; action: string; provider_name: string | null; hospital_name: string | null; success: boolean; created_at: string }>>("/audit/admin", user!),
  });
  const users = useQuery({
    queryKey: ["admin-users", user?.id],
    enabled: !!user,
    queryFn: () => carekeyRequest<AdminUser[]>("/admin/users", user!),
  });
  const hospitals = useQuery({
    queryKey: ["admin-hospitals", user?.id],
    enabled: !!user,
    queryFn: () => carekeyRequest<Hospital[]>("/hospitals", user!),
  });

  async function saveUser(id: string, values: { role: "patient" | "doctor" | "hospital" | "hospital_admin"; hospital_id: string | null; full_name: string; organization: string; specialty: string }): Promise<boolean> {
    try {
      await carekeyRequest<AdminUser>(`/admin/users/${id}`, user!, {
        method: "PATCH",
        body: JSON.stringify({
          role: values.role,
          hospital_id: values.hospital_id,
          full_name: values.full_name.trim() || undefined,
          organization: values.organization.trim() || null,
          specialty: values.specialty.trim() || null,
        }),
      });
      toast.success("User updated");
      await qc.invalidateQueries({ queryKey: ["admin-users"] });
      await qc.invalidateQueries({ queryKey: ["doctors"] });
      return true;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update user");
      return false;
    }
  }

  async function setDoctorActive(account: AdminUser, isActive: boolean) {
    if (!user) return;
    if (!window.confirm(`${isActive ? "Reactivate" : "Deactivate"} doctor access for ${account.email ?? account.full_name ?? "this account"}?`)) return;
    try {
      await carekeyRequest(`/admin/users/${account.id}/status`, user, {
        method: "PATCH",
        body: JSON.stringify({ is_active: isActive }),
      });
      toast.success(isActive ? "Doctor access reactivated" : "Doctor access deactivated");
      await qc.invalidateQueries({ queryKey: ["admin-users"] });
      await qc.invalidateQueries({ queryKey: ["doctors"] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update doctor access");
    }
  }

  async function addHospital(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload = {
      name: String(form.get("name") || "").trim(),
      latitude: Number(form.get("latitude")),
      longitude: Number(form.get("longitude")),
      address: String(form.get("address") || "").trim() || null,
      phone: String(form.get("phone") || "").trim() || null,
      emergency: form.get("emergency") === "on",
      trauma: form.get("trauma") === "on",
      ambulance: form.get("ambulance") === "on",
      open_24h: form.get("open_24h") === "on",
    };
    try {
      await carekeyRequest("/hospitals", user, { method: "POST", body: JSON.stringify(payload) });
      toast.success("Hospital added to the directory");
      formElement.reset();
      await qc.invalidateQueries({ queryKey: ["admin-hospitals"] });
      await qc.invalidateQueries({ queryKey: ["hospitals"] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not add hospital");
    }
  }

  async function updateHospital(id: string, payload: HospitalFields): Promise<boolean> {
    if (!user) return false;
    try {
      await carekeyRequest(`/hospitals/${id}`, user, { method: "PATCH", body: JSON.stringify(payload) });
      toast.success("Hospital updated");
      await qc.invalidateQueries({ queryKey: ["admin-hospitals"] });
      await qc.invalidateQueries({ queryKey: ["hospitals"] });
      return true;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update hospital");
      return false;
    }
  }

  async function deleteHospital(hospital: Hospital) {
    if (!user || !window.confirm(`Delete ${hospital.name} from the hospital directory?`)) return;
    try {
      await carekeyRequest(`/hospitals/${hospital.id}`, user, { method: "DELETE" });
      toast.success("Hospital deleted from the directory");
      await qc.invalidateQueries({ queryKey: ["admin-hospitals"] });
      await qc.invalidateQueries({ queryKey: ["hospitals"] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete hospital");
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="mt-1 text-sm text-muted-foreground">Manage demo accounts and hospital directory entries. Use synthetic data only.</p>
      </header>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Users</h2>
          <p className="text-sm text-muted-foreground">A user must sign up and sign in once before they appear here. Assign every doctor and hospital administrator to a hospital.</p>
        </div>
        {users.isLoading ? <p className="text-sm text-muted-foreground">Loading users…</p> : null}
        {users.error ? <p role="alert" className="text-sm text-destructive">Could not load users: {users.error.message}</p> : null}
        <div className="space-y-3">
          {(users.data ?? []).map((account) => (
            <AdminUserRow key={account.id} account={account} hospitals={hospitals.data ?? []} onSave={saveUser} onSetActive={setDoctorActive} />
          ))}
          {!users.isLoading && !users.error && !users.data?.length ? (
            <div className="card-surface p-4 text-sm text-muted-foreground">No registered users yet.</div>
          ) : null}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <form className="card-surface space-y-4 p-5" onSubmit={addHospital}>
          <div>
            <h2 className="text-lg font-semibold">Add hospital</h2>
            <p className="text-sm text-muted-foreground">Use fictional demo facilities and coordinates.</p>
          </div>
          <div className="space-y-1.5"><Label htmlFor="hospital-name">Name</Label><Input id="hospital-name" name="name" required maxLength={200} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5"><Label htmlFor="hospital-lat">Latitude</Label><Input id="hospital-lat" name="latitude" type="number" min="-90" max="90" step="any" required /></div>
            <div className="space-y-1.5"><Label htmlFor="hospital-lon">Longitude</Label><Input id="hospital-lon" name="longitude" type="number" min="-180" max="180" step="any" required /></div>
          </div>
          <div className="space-y-1.5"><Label htmlFor="hospital-address">Address</Label><Input id="hospital-address" name="address" /></div>
          <div className="space-y-1.5"><Label htmlFor="hospital-phone">Phone</Label><Input id="hospital-phone" name="phone" type="tel" maxLength={32} /></div>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" name="emergency" defaultChecked />Emergency</label>
            <label className="flex items-center gap-2"><input type="checkbox" name="trauma" />Trauma</label>
            <label className="flex items-center gap-2"><input type="checkbox" name="ambulance" defaultChecked />Ambulance</label>
            <label className="flex items-center gap-2"><input type="checkbox" name="open_24h" defaultChecked />Open 24 hours</label>
          </div>
          <Button type="submit">Add hospital</Button>
        </form>
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Hospital directory ({hospitals.data?.length ?? 0})</h2>
          {hospitals.error ? <p role="alert" className="text-sm text-destructive">Could not load hospitals: {hospitals.error.message}</p> : null}
          {(hospitals.data ?? []).map((hospital) => (
            <HospitalRow key={hospital.id} hospital={hospital} onSave={updateHospital} onDelete={deleteHospital} />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Recent access activity</h2>
          <p className="text-sm text-muted-foreground">Emergency and consented access attempts recorded by the backend.</p>
        </div>
        {logs.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading activity…</p>
        ) : !logs.data?.length ? (
          <div className="card-surface p-5 text-sm text-muted-foreground">No activity yet.</div>
        ) : (
          <ul className="space-y-2">
            {logs.data.map((log) => (
              <li key={log.id} className="card-surface p-3 text-sm">
                <p className="font-medium">{log.action}</p>
                <p className="text-xs text-muted-foreground">{log.provider_name ?? "—"}{log.hospital_name ? ` · ${log.hospital_name}` : ""} · {formatDateTime(log.created_at)} · {log.success ? "success" : "failed"}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function AdminUserRow({ account, hospitals, onSave, onSetActive }: {
  account: AdminUser;
  hospitals: Hospital[];
  onSave: (id: string, values: { role: "patient" | "doctor" | "hospital" | "hospital_admin"; hospital_id: string | null; full_name: string; organization: string; specialty: string }) => Promise<boolean>;
  onSetActive: (account: AdminUser, isActive: boolean) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [role, setRole] = useState<"patient" | "doctor" | "hospital" | "hospital_admin">(account.role === "doctor" || account.role === "hospital" || account.role === "hospital_admin" ? account.role : "patient");
  const [hospitalId, setHospitalId] = useState(account.hospital_id ?? "");
  const [fullName, setFullName] = useState(account.full_name ?? "");
  const [organization, setOrganization] = useState(account.organization ?? "");
  const [specialty, setSpecialty] = useState(account.specialty ?? "");
  if (account.role === "admin") {
    return (
      <div className="card-surface p-4">
        <p className="font-medium">{account.email ?? "No email"}</p>
        <p className="text-xs text-muted-foreground">Administrator · role changes require trusted database access.</p>
      </div>
    );
  }
  return (
    <div className="card-surface grid gap-3 p-4 md:grid-cols-2">
      <div className="md:col-span-2">
        <p className="font-medium">{account.email ?? "No email"}</p>
        <p className="text-xs text-muted-foreground">Current role: {account.role}{account.hospital_name ? ` · ${account.hospital_name}` : ""}{account.is_active ? " · active" : " · deactivated"}</p>
      </div>
      {editing ? <>
        <div className="space-y-1.5"><Label>Name</Label><Input value={fullName} maxLength={100} onChange={(event) => setFullName(event.target.value)} /></div>
        <div className="space-y-1.5"><Label>Role</Label><select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={role} onChange={(event) => setRole(event.target.value as "patient" | "doctor" | "hospital" | "hospital_admin")}><option value="patient">Patient</option><option value="doctor">Doctor</option><option value="hospital">Hospital account</option><option value="hospital_admin">Hospital administrator (legacy)</option></select></div>
        {role !== "patient" ? <div className="space-y-1.5"><Label>Hospital (required)</Label><select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={hospitalId} onChange={(event) => setHospitalId(event.target.value)} required><option value="">Choose a hospital</option>{hospitals.map((hospital) => <option key={hospital.id} value={hospital.id}>{hospital.name}</option>)}</select></div> : null}
        {role === "doctor" ? <div className="space-y-1.5"><Label>Organization</Label><Input value={organization} maxLength={120} onChange={(event) => setOrganization(event.target.value)} /></div> : null}
        <div className="space-y-1.5"><Label>Specialty</Label><Input value={specialty} maxLength={120} onChange={(event) => setSpecialty(event.target.value)} /></div>
        <div className="flex gap-2 md:col-span-2">
        <Button size="sm" onClick={() => { void onSave(account.id, { role, hospital_id: role === "patient" ? null : hospitalId || null, full_name: fullName, organization, specialty }).then((saved) => { if (saved) setEditing(false); }); }}>Save changes</Button>
          <Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
        </div>
      </> : <div className="flex flex-wrap gap-2 md:col-span-2">
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>Edit {account.role === "doctor" ? "doctor" : "user"}</Button>
        {account.role === "doctor" ? <Button size="sm" variant="outline" onClick={() => void onSetActive(account, !account.is_active)}>{account.is_active ? "Deactivate doctor" : "Reactivate doctor"}</Button> : null}
      </div>}
    </div>
  );
}

function HospitalRow({ hospital, onSave, onDelete }: {
  hospital: Hospital;
  onSave: (id: string, values: HospitalFields) => Promise<boolean>;
  onDelete: (hospital: Hospital) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const saved = await onSave(hospital.id, {
      name: String(form.get("name") || "").trim(),
      latitude: Number(form.get("latitude")),
      longitude: Number(form.get("longitude")),
      address: String(form.get("address") || "").trim() || null,
      phone: String(form.get("phone") || "").trim() || null,
      emergency: form.get("emergency") === "on",
      trauma: form.get("trauma") === "on",
      ambulance: form.get("ambulance") === "on",
      open_24h: form.get("open_24h") === "on",
    });
    if (saved) setEditing(false);
  }
  return editing ? (
    <form className="card-surface space-y-3 p-4" onSubmit={(event) => void submit(event)}>
      <div className="space-y-1.5"><Label>Name</Label><Input name="name" defaultValue={hospital.name} required maxLength={200} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5"><Label>Latitude</Label><Input name="latitude" type="number" min="-90" max="90" step="any" defaultValue={hospital.latitude} required /></div>
        <div className="space-y-1.5"><Label>Longitude</Label><Input name="longitude" type="number" min="-180" max="180" step="any" defaultValue={hospital.longitude} required /></div>
      </div>
      <div className="space-y-1.5"><Label>Address</Label><Input name="address" defaultValue={hospital.address ?? ""} /></div>
      <div className="space-y-1.5"><Label>Phone</Label><Input name="phone" type="tel" maxLength={32} defaultValue={hospital.phone ?? ""} /></div>
      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" name="emergency" defaultChecked={hospital.emergency} />Emergency</label>
        <label className="flex items-center gap-2"><input type="checkbox" name="trauma" defaultChecked={hospital.trauma} />Trauma</label>
        <label className="flex items-center gap-2"><input type="checkbox" name="ambulance" defaultChecked={hospital.ambulance} />Ambulance</label>
        <label className="flex items-center gap-2"><input type="checkbox" name="open_24h" defaultChecked={hospital.open_24h} />Open 24 hours</label>
      </div>
      <div className="flex gap-2"><Button size="sm" type="submit">Save changes</Button><Button size="sm" type="button" variant="outline" onClick={() => setEditing(false)}>Cancel</Button></div>
    </form>
  ) : (
    <div className="card-surface flex flex-wrap items-start justify-between gap-3 p-4">
      <div><p className="font-medium">{hospital.name}</p><p className="text-sm text-muted-foreground">{hospital.address || `${hospital.latitude}, ${hospital.longitude}`}</p></div>
      <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setEditing(true)}>Edit</Button><Button size="sm" variant="destructive" onClick={() => void onDelete(hospital)}>Delete</Button></div>
    </div>
  );
}
