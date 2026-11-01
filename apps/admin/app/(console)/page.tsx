"use client";

import { useEffect, useState } from "react";
import { api, AuditLogRow, PlatformStats } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Badge, EmptyRow, fmtUsd, Section, StatCard, Td, Th } from "@/components/ui";

export default function OverviewPage() {
  const { accessToken } = useAuthStore();
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [audit, setAudit] = useState<AuditLogRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    api.stats(accessToken).then(setStats).catch((e) => setError(e.message));
    api.auditLogs.list(accessToken, { limit: 10 }).then(setAudit).catch(() => {});
  }, [accessToken]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!stats) return <p className="text-sm text-slate-400">Loading platform stats…</p>;

  const breakdown = (m: Record<string, number>) =>
    Object.entries(m).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-slate-900">Platform Overview</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Users" value={stats.users_total} />
        <StatCard label="Listings" value={stats.listings_total} />
        <StatCard label="Proposals" value={stats.proposals_total} />
        <StatCard label="Transactions" value={stats.transactions_total} />
        <StatCard label="GMV disbursed" value={fmtUsd(stats.total_disbursed_usd)} hint="paid to IP holders" />
        <StatCard label="Saha commission" value={fmtUsd(stats.total_commission_usd)} hint="lifetime revenue" />
        <StatCard label="Pipeline value" value={fmtUsd(stats.pipeline_value_usd)} hint="open transactions" />
        <StatCard label="Reviews" value={stats.reviews_total} />
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {([
          ["Users by role", stats.users_by_role],
          ["Listings by status", stats.listings_by_status],
          ["Transactions by status", stats.transactions_by_status],
        ] as const).map(([title, map]) => (
          <Section key={title} title={title}>
            <div className="space-y-2">
              {breakdown(map).length === 0 && <p className="text-sm text-slate-400">No data yet.</p>}
              {breakdown(map).map(([k, n]) => (
                <div key={k} className="flex items-center justify-between">
                  <Badge value={k} />
                  <span className="text-sm font-semibold text-slate-700">{n}</span>
                </div>
              ))}
            </div>
          </Section>
        ))}
      </div>

      <Section title="Recent activity">
        <table className="w-full">
          <thead><tr><Th>Action</Th><Th>Resource</Th><Th>User</Th><Th>When</Th></tr></thead>
          <tbody>
            {audit.length === 0 && <EmptyRow cols={4} text="No audit events yet." />}
            {audit.map((a) => (
              <tr key={a.id}>
                <Td className="font-medium text-slate-900">{a.action}</Td>
                <Td>{a.resource_type ?? "—"}</Td>
                <Td className="font-mono text-xs">{a.user_id?.slice(0, 8) ?? "—"}</Td>
                <Td>{new Date(a.created_at).toLocaleString()}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}
