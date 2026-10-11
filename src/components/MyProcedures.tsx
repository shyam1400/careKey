import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/hooks/useAuth";
import { carekeyRequest } from "@/lib/carekey-api";
import { formatDateTime } from "@/lib/carekey";
import { Badge } from "@/components/ui/badge";

type Procedure = {
  id: string;
  patient_name: string;
  doctor_name: string;
  hospital_name: string;
  name: string;
  status: "planned" | "in_progress" | "completed" | "cancelled";
  notes: string | null;
  started_at: string;
  ended_at: string | null;
};

export function MyProcedures({ audience }: { audience: "patient" | "doctor" }) {
  const { user } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["my-procedures", user?.id],
    enabled: !!user,
    queryFn: () => carekeyRequest<Procedure[]>("/procedures/me", user!),
  });

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">{audience === "patient" ? "Your procedures" : "Tracked procedures"}</h2>
        <p className="text-sm text-muted-foreground">Hospital procedure tracking linked to your account.</p>
      </div>
      {isLoading ? <p className="text-sm text-muted-foreground">Loading procedures…</p> : null}
      {error ? <p role="alert" className="text-sm text-destructive">Could not load procedures: {error.message}</p> : null}
      {!isLoading && !error && !data?.length ? <p className="card-surface p-4 text-sm text-muted-foreground">No procedures are linked to your account yet.</p> : null}
      {data?.map((procedure) => (
        <article key={procedure.id} className="card-surface space-y-2 p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 className="font-medium">{procedure.name}</h3>
              <p className="text-sm text-muted-foreground">
                {audience === "patient" ? `Dr. ${procedure.doctor_name}` : `Patient: ${procedure.patient_name}`}
                {` · ${procedure.hospital_name}`}
              </p>
            </div>
            <Badge variant="secondary">{procedure.status.replace("_", " ")}</Badge>
          </div>
          {procedure.notes ? <p className="text-sm">{procedure.notes}</p> : null}
          <p className="text-xs text-muted-foreground">Started {formatDateTime(procedure.started_at)}{procedure.ended_at ? ` · ended ${formatDateTime(procedure.ended_at)}` : ""}</p>
        </article>
      ))}
    </section>
  );
}
