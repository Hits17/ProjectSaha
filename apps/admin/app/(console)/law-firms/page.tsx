"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, LawFirm } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Btn, EmptyRow, fmtDate, Section, Td, Th } from "@/components/ui";

export default function LawFirmsPage() {
  const { accessToken } = useAuthStore();
  const [firms, setFirms] = useState<LawFirm[]>([]);
  const [name, setName] = useState("");
  const [jurisdictions, setJurisdictions] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    if (!accessToken) return;
    api.lawFirms.list(accessToken).then(setFirms).catch((e) => setError(e.message));
  }, [accessToken]);

  useEffect(() => { load(); }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.lawFirms.create(accessToken!, {
        name: name.trim(),
        jurisdictions: jurisdictions.split(",").map((j) => j.trim()).filter(Boolean),
        contact_email: email.trim() || null,
      });
      setName(""); setJurisdictions(""); setEmail("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Create failed");
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (f: LawFirm) => {
    setError(null);
    try { await api.lawFirms.update(accessToken!, f.id, { is_active: !f.is_active }); load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Update failed"); }
  };

  const edit = async (f: LawFirm) => {
    const newName = prompt("Firm name:", f.name);
    if (!newName) return;
    const newJur = prompt("Jurisdictions (comma-separated):", f.jurisdictions.join(", "));
    if (newJur === null) return;
    const newEmail = prompt("Contact email:", f.contact_email ?? "");
    if (newEmail === null) return;
    setError(null);
    try {
      await api.lawFirms.update(accessToken!, f.id, {
        name: newName.trim(),
        jurisdictions: newJur.split(",").map((j) => j.trim()).filter(Boolean),
        contact_email: newEmail.trim() || null,
      });
      load();
    } catch (e) { setError(e instanceof ApiError ? e.message : "Update failed"); }
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Law Firm Partners</h1>
      <p className="text-sm text-slate-500">
        Firms listed here are offered to deal parties during the legal phase and receive the 3% legal fee on disbursement.
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <Section title="Add partner firm">
        <form onSubmit={create} className="flex flex-wrap gap-2 items-end">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-56" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Jurisdictions (comma-separated)</label>
            <input value={jurisdictions} onChange={(e) => setJurisdictions(e.target.value)} placeholder="US-DE, US-CA, EU"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-56" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Contact email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-56" />
          </div>
          <button type="submit" disabled={saving}
            className="bg-slate-900 text-white rounded-lg px-4 py-1.5 text-sm font-medium hover:bg-slate-700 disabled:opacity-50">
            {saving ? "Adding…" : "Add firm"}
          </button>
        </form>
      </Section>

      <Section title={`${firms.length} partner firms`}>
        <table className="w-full">
          <thead><tr><Th>Name</Th><Th>Jurisdictions</Th><Th>Contact</Th><Th>Status</Th><Th>Added</Th><Th>Actions</Th></tr></thead>
          <tbody>
            {firms.length === 0 && <EmptyRow cols={6} text="No partner firms yet." />}
            {firms.map((f) => (
              <tr key={f.id} className="hover:bg-slate-50">
                <Td className="font-medium text-slate-900">{f.name}</Td>
                <Td>{f.jurisdictions.length ? f.jurisdictions.join(", ") : "—"}</Td>
                <Td>{f.contact_email ?? "—"}</Td>
                <Td>{f.is_active
                  ? <span className="text-xs font-medium text-green-700">active</span>
                  : <span className="text-xs font-medium text-slate-400">inactive</span>}</Td>
                <Td>{fmtDate(f.created_at)}</Td>
                <Td>
                  <div className="flex gap-1.5">
                    <Btn onClick={() => edit(f)}>Edit</Btn>
                    <Btn variant={f.is_active ? "danger" : "primary"} onClick={() => toggle(f)}>
                      {f.is_active ? "Deactivate" : "Activate"}
                    </Btn>
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}
