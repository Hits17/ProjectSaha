"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, TransactionRow } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Badge, Btn, EmptyRow, fmtDate, fmtUsd, Section, shortId, Td, Th } from "@/components/ui";

const STATUSES = [
  "pending_legal", "contract_drafting", "contract_review", "signing_pending", "signed",
  "escrow_pending", "escrow_funded", "disbursement_pending", "completed", "disputed", "cancelled",
];
const TERMINAL = new Set(["completed", "cancelled"]);

export default function TransactionsPage() {
  const { accessToken } = useAuthStore();
  const [rows, setRows] = useState<TransactionRow[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    api.transactions.list(accessToken, { limit: 100, status: status || undefined })
      .then(setRows).catch((e) => setError(e.message));
  }, [accessToken, status]);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Action failed"); }
  };

  const resolve = (t: TransactionRow, resolution: "complete" | "cancel") => {
    const reason = prompt(`Reason for resolving dispute as "${resolution}" (audited):`);
    if (!reason) return;
    act(() => api.transactions.resolve(accessToken!, t.id, resolution, reason));
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Transactions</h1>
      <p className="text-sm text-slate-500">
        Open a dispute to freeze an in-flight deal; resolve it to complete or cancel. Resolutions only settle the
        record — refunds are handled in Stripe.
      </p>

      <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm">
        <option value="">All statuses</option>
        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Section title={`${rows.length} transactions`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>ID</Th><Th>Status</Th><Th>Deal value</Th><Th>Commission</Th><Th>Buyer</Th><Th>Seller</Th><Th>Updated</Th><Th>Actions</Th></tr></thead>
            <tbody>
              {rows.length === 0 && <EmptyRow cols={8} text="No transactions match." />}
              {rows.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <Td className="font-mono text-xs">{shortId(t.id)}</Td>
                  <Td><Badge value={t.status} /></Td>
                  <Td className="font-medium">{fmtUsd(t.deal_value_usd)}</Td>
                  <Td>{fmtUsd(t.saha_commission_usd)}</Td>
                  <Td className="font-mono text-xs">{shortId(t.buyer_id)}</Td>
                  <Td className="font-mono text-xs">{shortId(t.seller_id)}</Td>
                  <Td>{fmtDate(t.updated_at)}</Td>
                  <Td>
                    <div className="flex gap-1.5">
                      {t.status === "disputed" ? (
                        <>
                          <Btn variant="primary" onClick={() => resolve(t, "complete")}>Complete</Btn>
                          <Btn variant="danger" onClick={() => resolve(t, "cancel")}>Cancel</Btn>
                        </>
                      ) : !TERMINAL.has(t.status) && (
                        <Btn variant="danger" onClick={() => {
                          if (confirm(`Open a dispute on ${shortId(t.id)}? The deal freezes until resolved.`))
                            act(() => api.transactions.dispute(accessToken!, t.id));
                        }}>Dispute</Btn>
                      )}
                    </div>
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
