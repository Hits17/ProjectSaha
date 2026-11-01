"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, ReviewRow } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Btn, EmptyRow, fmtDate, Section, shortId, Td, Th } from "@/components/ui";

export default function ReviewsPage() {
  const { accessToken } = useAuthStore();
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    api.reviews.list(accessToken, { limit: 100 }).then(setRows).catch((e) => setError(e.message));
  }, [accessToken]);

  useEffect(() => { load(); }, [load]);

  const remove = async (r: ReviewRow) => {
    if (!confirm("Delete this review? This is permanent and affects the reviewee's reputation score.")) return;
    setError(null);
    try { await api.reviews.remove(accessToken!, r.id); load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Delete failed"); }
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Reviews</h1>
      <p className="text-sm text-slate-500">Moderation: remove abusive or fraudulent reviews. Deletions are audited.</p>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <Section title={`${rows.length} reviews`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Rating</Th><Th>Comment</Th><Th>Reviewer</Th><Th>Reviewee</Th><Th>Transaction</Th><Th>When</Th><Th></Th></tr></thead>
            <tbody>
              {rows.length === 0 && <EmptyRow cols={7} text="No reviews yet." />}
              {rows.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50">
                  <Td className="font-medium text-amber-600">{"★".repeat(r.rating)}<span className="text-slate-200">{"★".repeat(5 - r.rating)}</span></Td>
                  <Td className="max-w-md"><p className="truncate">{r.comment ?? "—"}</p></Td>
                  <Td className="font-mono text-xs">{shortId(r.reviewer_id)}</Td>
                  <Td className="font-mono text-xs">{shortId(r.reviewee_id)}</Td>
                  <Td className="font-mono text-xs">{shortId(r.transaction_id)}</Td>
                  <Td>{fmtDate(r.created_at)}</Td>
                  <Td><Btn variant="danger" onClick={() => remove(r)}>Delete</Btn></Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
