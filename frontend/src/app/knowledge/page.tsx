"use client";

import { FileText, RefreshCw, Search, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge,
  type BadgeTone,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorNote,
  PageHeader,
} from "@/components/ui";
import { api, API_URL, type KnowledgeDocument, type Source } from "@/lib/api";
import { formatRelative } from "@/lib/utils";

const STATUS_TONE: Record<KnowledgeDocument["status"], BadgeTone> = {
  indexed: "success",
  indexing: "accent",
  pending: "neutral",
  failed: "danger",
};

export default function KnowledgePage() {
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Source[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setDocs(await api<KnowledgeDocument[]>("/api/knowledge"));
    } catch {
      setError("Could not load documents. Is the backend running?");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data fetch
    load();
  }, [load]);

  useEffect(() => {
    if (!docs.some((d) => d.status === "indexing" || d.status === "pending")) return;
    const timer = setInterval(load, 1500);
    return () => clearInterval(timer);
  }, [docs, load]);

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${API_URL}/api/knowledge`, { method: "POST", body });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Upload failed");
      setTimeout(load, 300);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function reindex() {
    await api("/api/knowledge/reindex", { method: "POST" });
    setTimeout(load, 300);
  }

  async function search(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    try {
      setResults(await api<Source[]>(`/api/knowledge/search?q=${encodeURIComponent(query)}`));
    } catch {
      setError("Search failed. Is the backend running?");
    } finally {
      setSearching(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Knowledge base"
        description="PDFs the agent retrieves from. Chunked, embedded locally with FastEmbed and stored in Qdrant."
        action={
          <div className="flex gap-2">
            <Button onClick={reindex}>
              <RefreshCw className="size-4" /> Re-index all
            </Button>
            <Button variant="primary" onClick={() => fileInput.current?.click()} disabled={uploading}>
              <Upload className="size-4" /> {uploading ? "Uploading..." : "Upload PDF"}
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
          </div>
        }
      />
      {error && (
        <div className="mb-6">
          <ErrorNote error={error} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Documents" description={`${docs.length} files indexed`} />
          {docs.length === 0 ? (
            <EmptyState>No documents yet. Upload a PDF or run the ingest script.</EmptyState>
          ) : (
            <ul className="divide-y divide-panel-border">
              {docs.map((doc) => (
                <li key={doc.id} className="flex items-start gap-3 px-5 py-4">
                  <FileText className="mt-0.5 size-4 text-violet-300" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{doc.title}</p>
                    <p className="text-xs text-muted">
                      {doc.filename} · {doc.pages} pages · {doc.chunks} chunks
                      {doc.indexed_at && ` · indexed ${formatRelative(doc.indexed_at)}`}
                    </p>
                    {doc.error && <p className="mt-1 text-xs text-red-300">{doc.error}</p>}
                  </div>
                  <Badge tone={STATUS_TONE[doc.status]}>{doc.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Test retrieval"
            description="See exactly which chunks the agent would receive for a question."
          />
          <form onSubmit={search} className="flex gap-2 px-5 pt-4">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Is there a late payment fee?"
              className="flex-1 rounded-lg border border-panel-border bg-black/20 px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent"
            />
            <Button type="submit" disabled={searching} aria-label="Search knowledge base">
              <Search className="size-4" />
            </Button>
          </form>
          <div className="space-y-3 px-5 py-4">
            {results?.length === 0 && <EmptyState>No matching chunks.</EmptyState>}
            {results?.map((r, i) => (
              <div key={i} className="rounded-lg bg-white/[0.03] p-3 text-xs">
                <div className="mb-1.5 flex items-center gap-2 text-muted">
                  <span className="font-medium text-foreground">#{i + 1}</span>
                  <span>
                    {r.source} · page {r.page}
                  </span>
                  <span className="ml-auto font-mono">{r.score.toFixed(3)}</span>
                </div>
                <p className="line-clamp-6 whitespace-pre-line leading-relaxed text-foreground/80">
                  {r.content.split("\n\n").slice(1).join("\n\n") || r.content}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
