"use client";

import { useCallback, useEffect, useState } from "react";
import { request } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

interface SpaceRow {
  space: { id: string; name: string; is_institution: boolean; verification_status: string; website_url: string | null };
  private: { reference: string; request_note: string | null; evidence_url: string | null; review_note: string | null };
}
export default function InstitutionsAdmin() {
  const token = useAuthStore(s => s.accessToken);
  const [enabled, setEnabled] = useState(false);
  const [rows, setRows] = useState<SpaceRow[]>([]);
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [reason, setReason] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [policy, list] = await Promise.all([
        request<{ institution_verification_enabled: boolean }>("/api/v1/institutions/policy", { token }),
        request<SpaceRow[]>(`/api/v1/admin/spaces?limit=30&offset=${offset}${status ? `&verification_status=${status}` : ""}`, { token }),
      ]); setEnabled(policy.institution_verification_enabled); setRows(list);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load spaces"); }
  }, [token, status, offset]);
  useEffect(() => { void load(); }, [load]);
  async function toggle() {
    if (!token) return; setBusy(true); setError("");
    try { const p = await request<{ institution_verification_enabled: boolean }>("/api/v1/admin/institutions/policy", { method: "PUT", token, body: JSON.stringify({ institution_verification_enabled: !enabled }) }); setEnabled(p.institution_verification_enabled); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not update policy"); } finally { setBusy(false); }
  }
  async function review(id: string, decision: string) {
    if (!token) return; setBusy(true); setError("");
    try { await request(`/api/v1/admin/institutions/${id}/review`, { method: "POST", token, body: JSON.stringify({ decision, reason: reason[id] || "" }) }); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Review failed"); } finally { setBusy(false); }
  }
  return <div className="space-y-6"><h1 className="text-2xl font-bold">Institutions & spaces</h1><p className="text-sm text-slate-500">Internal references and verification evidence are restricted to space owners and Saha administrators. A badge confirms institutional identity, not patent ownership or scientific validity.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <section className="bg-white border rounded-xl p-5 flex justify-between gap-4 items-center"><div><h2 className="font-semibold">Institution verification requests</h2><p className="text-sm text-slate-500">Turning this on lets institution owners request human verification. Turning it off does not auto-verify or revoke existing badges.</p></div><button type="button" role="switch" aria-checked={enabled} disabled={busy || !token} onClick={toggle} className={`rounded px-4 py-2 text-white ${enabled ? "bg-emerald-700" : "bg-slate-700"}`}>{enabled ? "Enabled" : "Disabled"}</button></section>
    <label className="flex gap-3 items-center text-sm">Verification status<select value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }} className="border rounded p-2"><option value="">All spaces</option>{["pending", "verified", "rejected", "unverified"].map(s => <option key={s}>{s}</option>)}</select></label>
    <div className="space-y-4">{rows.map(row => <article key={row.space.id} className="bg-white border rounded-xl p-5 space-y-3"><div className="flex justify-between"><h2 className="font-semibold">{row.space.name}</h2><span className="text-xs">{row.space.is_institution ? "Institution" : "Community"} · {row.space.verification_status}</span></div><p className="text-sm">Internal reference: <code>{row.private.reference}</code></p>{row.space.website_url && <a href={row.space.website_url} target="_blank" rel="noopener noreferrer" className="text-indigo-700 text-sm underline">Website ↗</a>}{row.private.request_note && <p className="text-sm whitespace-pre-wrap">Request: {row.private.request_note}</p>}{row.private.evidence_url && <a href={row.private.evidence_url} target="_blank" rel="noopener noreferrer" className="text-indigo-700 text-sm underline">Owner-provided evidence ↗</a>}{row.private.review_note && <p className="text-sm">Previous review: {row.private.review_note}</p>}
      {row.space.is_institution && ["pending", "verified"].includes(row.space.verification_status) && <div className="space-y-2"><label className="block text-sm">Reason for decision<textarea aria-label={`Review reason for ${row.space.name}`} value={reason[row.space.id] || ""} onChange={e => setReason(v => ({ ...v, [row.space.id]: e.target.value }))} minLength={10} maxLength={2000} className="block border rounded p-2 w-full mt-1" /></label><div className="flex gap-2">{(row.space.verification_status === "pending" ? [["verified", "Approve"], ["rejected", "Reject"]] : [["unverified", "Revoke badge"]]).map(([decision, label]) => <button key={decision} disabled={busy || (reason[row.space.id]?.trim().length || 0) < 10} onClick={() => void review(row.space.id, decision)} className="rounded bg-slate-800 text-white px-3 py-2 disabled:opacity-40 text-sm">{label}</button>)}</div></div>}
    </article>)}</div><div className="flex justify-between"><button disabled={!offset || busy} onClick={() => setOffset(v => Math.max(0, v - 30))}>Previous</button><button disabled={rows.length < 30 || busy} onClick={() => setOffset(v => v + 30)}>Next</button></div>
  </div>;
}
