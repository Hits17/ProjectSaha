"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ProposalRow } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Badge, EmptyRow, fmtDate, fmtUsd, Section, shortId, Td, Th } from "@/components/ui";

const STATUSES = ["draft", "submitted", "nda_pending", "nda_signed", "negotiating", "accepted", "rejected", "withdrawn"];

export default function ProposalsPage() {
  const { accessToken } = useAuthStore();
  const [rows, setRows] = useState<ProposalRow[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    api.proposals.list(accessToken, { limit: 100, status: status || undefined })
      .then(setRows).catch((e) => setError(e.message));
  }, [accessToken, status]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Proposals</h1>
      <p className="text-sm text-slate-500">Read-only negotiation oversight. Message contents stay encrypted and are never shown here.</p>

      <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm">
        <option value="">All statuses</option>
        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Section title={`${rows.length} proposals`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Listing</Th><Th>Status</Th><Th>Offer</Th><Th>Round</Th><Th>Buyer</Th><Th>Seller</Th><Th>Updated</Th></tr></thead>
            <tbody>
              {rows.length === 0 && <EmptyRow cols={7} text="No proposals match." />}
              {rows.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <Td className="font-medium text-slate-900 max-w-xs truncate">{p.listing_title}</Td>
                  <Td><Badge value={p.status} /></Td>
                  <Td>{fmtUsd(p.offer_amount_usd)}</Td>
                  <Td>v{p.version}</Td>
                  <Td className="font-mono text-xs">{shortId(p.buyer_id)}</Td>
                  <Td className="font-mono text-xs">{shortId(p.seller_id)}</Td>
                  <Td>{fmtDate(p.updated_at)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
