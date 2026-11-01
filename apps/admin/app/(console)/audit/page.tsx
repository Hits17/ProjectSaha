"use client";

import { useCallback, useEffect, useState } from "react";
import { api, AuditLogRow } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { EmptyRow, Section, shortId, Td, Th } from "@/components/ui";

const PAGE_SIZE = 50;

export default function AuditPage() {
  const { accessToken } = useAuthStore();
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [action, setAction] = useState("");
  const [userId, setUserId] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    api.auditLogs.list(accessToken, {
      limit: PAGE_SIZE, offset,
      action: action || undefined,
      user_id: userId.trim() || undefined,
    }).then(setRows).catch((e) => setError(e.message));
  }, [accessToken, action, userId, offset]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Audit Log</h1>
      <p className="text-sm text-slate-500">Every security-relevant event on the platform, including all admin actions taken in this console.</p>

      <div className="flex flex-wrap gap-2">
        <input value={action} onChange={(e) => { setAction(e.target.value); setOffset(0); }}
          placeholder="Filter by action prefix (e.g. admin., user., settlement.)"
          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-80" />
        <input value={userId} onChange={(e) => { setUserId(e.target.value); setOffset(0); }}
          placeholder="Filter by user UUID"
          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-72 font-mono" />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <Section title="Events"
        actions={
          <div className="flex gap-2 items-center">
            <button onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} disabled={offset === 0}
              className="text-sm text-slate-600 disabled:opacity-30">← Newer</button>
            <span className="text-xs text-slate-400">{offset + 1}–{offset + rows.length}</span>
            <button onClick={() => setOffset(offset + PAGE_SIZE)} disabled={rows.length < PAGE_SIZE}
              className="text-sm text-slate-600 disabled:opacity-30">Older →</button>
          </div>
        }>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Action</Th><Th>Resource</Th><Th>Resource ID</Th><Th>Actor</Th><Th>When</Th></tr></thead>
            <tbody>
              {rows.length === 0 && <EmptyRow cols={5} text="No events match." />}
              {rows.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50">
                  <Td className="font-medium text-slate-900">{a.action}</Td>
                  <Td>{a.resource_type ?? "—"}</Td>
                  <Td className="font-mono text-xs">{a.resource_id ? shortId(a.resource_id) : "—"}</Td>
                  <Td className="font-mono text-xs">{a.user_id ? shortId(a.user_id) : "system"}</Td>
                  <Td>{new Date(a.created_at).toLocaleString()}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
