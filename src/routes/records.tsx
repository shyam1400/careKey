import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { carekeyRequest } from "@/lib/carekey-api";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import { RequireRole } from "@/components/RequireRole";
import { PageHeading } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DOC_TYPES, formatDate } from "@/lib/carekey";

export const Route = createFileRoute("/records")({
  head: () => ({
    meta: [
      { title: "Medical records — CareKey" },
      {
        name: "description",
        content: "Upload and view prescriptions, lab reports, discharge summaries and imaging reports.",
      },
      { property: "og:title", content: "Medical records — CareKey" },
      {
        property: "og:description",
        content: "Store your medical documents privately and share them only with consent.",
      },
    ],
  }),
  component: () => (
    <RequireRole roles={["patient"]}>
      <RecordsPage />
    </RequireRole>
  ),
});

export async function openDocument(documentId: string, user: NonNullable<ReturnType<typeof useAuth>["user"]>) {
  try {
    const { url } = await carekeyRequest<{ url: string }>(`/records/documents/${documentId}/download-url`, user, { method: "POST" });
    window.open(url, "_blank", "noopener");
  } catch (error) {
    toast.error(error instanceof Error ? error.message : "Could not open file");
  }
}

function RecordsPage() {
  const { user, profile } = useAuth();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("prescription");
  const [busy, setBusy] = useState(false);

  const { data } = useQuery({
    queryKey: ["documents", user?.id],
    enabled: !!user,
    queryFn: async () => {
      return carekeyRequest<Array<{ id: string; file_name: string; doc_type: string; storage_path: string | null; created_at: string }>>("/records/documents", user!);
    },
  });

  async function upload() {
    if (!user || !file) return toast.error("Choose a file first");
    if (file.size > 10 * 1024 * 1024) return toast.error("Max file size is 10 MB");
    setBusy(true);
    let path: string | null = null;
    try {
      const signed = await carekeyRequest<{ path: string; token: string }>("/records/documents/upload-token", user, {
        method: "POST",
        body: JSON.stringify({ file_name: file.name, content_type: file.type }),
      });
      path = signed.path;
      const { error: uploadError } = await supabase.storage
        .from("medical-documents")
        .uploadToSignedUrl(signed.path, signed.token, file, { contentType: file.type });
      if (uploadError) throw uploadError;
      await carekeyRequest("/records/documents", user, {
        method: "POST",
        body: JSON.stringify({ file_name: file.name.slice(0, 150), doc_type: docType, storage_path: path }),
      });
    } catch (error) {
      if (path) {
        try {
          await carekeyRequest("/records/documents/storage-object", user, {
            method: "DELETE",
            body: JSON.stringify({ path }),
          });
        } catch { /* best-effort cleanup */ }
      }
      setBusy(false);
      return toast.error(error instanceof Error ? error.message : "Upload failed");
    }
    setBusy(false);
    setFile(null);
    toast.success("Document uploaded");
    await qc.invalidateQueries({ queryKey: ["documents", user.id] });
  }

  async function remove(id: string) {
    try {
      await carekeyRequest(`/records/documents/${id}`, user!, { method: "DELETE" });
    } catch (error) {
      return toast.error(error instanceof Error ? error.message : "Could not delete document");
    }
    await qc.invalidateQueries({ queryKey: ["documents", user?.id] });
  }

  return (
    <>
      <PageHeading title="Medical records" description="Documents are private unless you share them." />
      <div className="grid gap-6 md:grid-cols-[340px_1fr]">
        <div className="card-surface h-fit space-y-4 p-6">
          <h2 className="font-semibold">Upload document</h2>
          <div className="space-y-1.5">
            <Label>Type</Label>
            <Select value={docType} onValueChange={setDocType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DOC_TYPES.map((d) => (
                  <SelectItem key={d.key} value={d.key}>
                    {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="file">File (PDF or image, max 10 MB)</Label>
            <Input
              id="file"
              type="file"
              accept=".pdf,image/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <Button className="w-full" onClick={upload} disabled={busy || !file}>
            {busy ? "Uploading…" : "Upload"}
          </Button>
        </div>

        <div className="card-surface overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">File</th>
                <th className="p-3">Type</th>
                <th className="p-3">Uploaded</th>
                <th className="p-3">Owner</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {(data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-6 text-muted-foreground">
                    No documents yet.
                  </td>
                </tr>
              ) : (
                data!.map((d) => (
                  <tr key={d.id}>
                    <td className="p-3 font-medium">{d.file_name}</td>
                    <td className="p-3">
                      <Badge variant="secondary">
                        {DOC_TYPES.find((t) => t.key === d.doc_type)?.label ?? d.doc_type}
                      </Badge>
                    </td>
                    <td className="p-3">{formatDate(d.created_at)}</td>
                    <td className="p-3">{profile?.full_name}</td>
                    <td className="space-x-1 whitespace-nowrap p-3 text-right">
                      <Button size="sm" variant="outline" onClick={() => openDocument(d.id, user!)}>
                        View
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => remove(d.id)}>
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
