"use client";

import { useEffect, useState } from "react";
import { api, DisbursementRow, PlatformStats } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { EmptyRow, fmtUsd, Section, shortId, StatCard, Td, Th } from "@/components/ui";

export default function RevenuePage() {
  const { accessToken } = useAuthStore();
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [rows, setRows] = useState<DisbursementRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    api.stats(accessToken).then(setStats).catch((e) => setError(e.message));
    api.disbursements.list(accessToken, { limit: 100 }).then(setRows).catch((e) => setError(e.message));
  }, [accessToken]);

  const totalLegal = rows.reduce((s, r) => s + Number(r.legal_fee_usd), 0);
  const totalEscrow = rows.reduce((s, r) => s + Number(r.escrow_fee_usd), 0);

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Revenue</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Saha commission" value={fmtUsd(stats?.total_commission_usd ?? 0)} hint="lifetime (5% of deals)" />
        <StatCard label="Disbursed to IP holders" value={fmtUsd(stats?.total_disbursed_usd ?? 0)} />
        <StatCard label="Legal fees routed" value={fmtUsd(totalLegal)} hint="paid to law firm partners" />
        <StatCard label="Escrow fees retained" value={fmtUsd(totalEscrow)} />
      </div>

      <Section title={`Disbursement ledger (${rows.length})`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Transaction</Th><Th>IP holder</Th><Th>Commission</Th><Th>Legal</Th><Th>Escrow</Th><Th>Executed</Th></tr></thead>
            <tbody>
              {rows.length === 0 && <EmptyRow cols={6} text="No disbursements yet." />}
              {rows.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50">
                  <Td className="font-mono text-xs">{shortId(d.transaction_id)}</Td>
                  <Td className="font-medium text-green-700">{fmtUsd(d.ip_holder_amount_usd)}</Td>
                  <Td>{fmtUsd(d.saha_commission_usd)}</Td>
                  <Td>{fmtUsd(d.legal_fee_usd)}</Td>
                  <Td>{fmtUsd(d.escrow_fee_usd)}</Td>
                  <Td>{d.executed_at ? new Date(d.executed_at).toLocaleString() : "—"}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
