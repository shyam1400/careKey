import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { carekeyRequest } from "@/lib/carekey-api";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { formatDateTime } from "@/lib/carekey";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Admin — CareKey" },
      { name: "description", content: "CareKey administration: recent access activity across the prototype." },
      { property: "og:title", content: "Admin — CareKey" },
      { property: "og:description", content: "CareKey administration: recent access activity across the prototype." },
    ],
  }),
  component: () => (
    <RequireRole roles={["admin"]}>
      <AdminPage />
    </RequireRole>
  ),
});

function AdminPage() {
  const { user } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-logs", user?.id],
    enabled: !!user,
    queryFn: async () => {
      return carekeyRequest<Array<{ id: string; action: string; provider_name: string | null; success: boolean; created_at: string }>>("/audit/admin", user!);
    },
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Admin</h1>
      <h2 className="text-sm font-medium text-muted-foreground">Recent access activity</h2>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : !data?.length ? (
        <div className="card-surface p-6 text-sm text-muted-foreground">No activity yet.</div>
      ) : (
        <ul className="space-y-2">
          {data.map((l) => (
            <li key={l.id} className="card-surface p-3 text-sm">
              <p className="font-medium">{l.action}</p>
              <p className="text-xs text-muted-foreground">
                {l.provider_name ?? "—"} · {formatDateTime(l.created_at)} · {l.success ? "success" : "failed"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
