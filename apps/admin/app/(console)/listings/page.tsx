"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, ListingRow } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Badge, Btn, EmptyRow, fmtDate, Section, Td, Th } from "@/components/ui";

const STATUSES = ["draft", "ai_generating", "review", "published", "archived"];

export default function ListingsPage() {
  const { accessToken } = useAuthStore();
  const [rows, setRows] = useState<ListingRow[]>([]);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    api.listings.list(accessToken, { limit: 100, status: status || undefined, search: search || undefined })
      .then(setRows).catch((e) => setError(e.message));
  }, [accessToken, status, search]);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Action failed"); }
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Listings</h1>
      <p className="text-sm text-slate-500">
        Moderation: archiving removes a listing from the marketplace and the search index. Restoring returns it to
        “review” so the creator can re-publish.
      </p>

      <div className="flex flex-wrap gap-2">
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search title…"
          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-64" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Section title={`${rows.length} listings`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Title</Th><Th>Creator</Th><Th>Status</Th><Th>Category</Th><Th>Views</Th><Th>Created</Th><Th>Actions</Th></tr></thead>
            <tbody>
              {rows.length === 0 && <EmptyRow cols={7} text="No listings match." />}
              {rows.map((l) => (
                <tr key={l.id} className="hover:bg-slate-50">
                  <Td className="font-medium text-slate-900 max-w-xs truncate">{l.title}</Td>
                  <Td className="text-xs">{l.creator_email}</Td>
                  <Td><Badge value={l.status} /></Td>
                  <Td>{l.product_category ?? "—"}</Td>
                  <Td>{l.view_count}</Td>
                  <Td>{fmtDate(l.created_at)}</Td>
                  <Td>
                    {l.status !== "archived" ? (
                      <Btn variant="danger" onClick={() => {
                        if (confirm(`Archive "${l.title}"? It will be removed from the marketplace and search.`))
                          act(() => api.listings.archive(accessToken!, l.id));
                      }}>Archive</Btn>
                    ) : (
                      <Btn onClick={() => act(() => api.listings.restore(accessToken!, l.id))}>Restore</Btn>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
