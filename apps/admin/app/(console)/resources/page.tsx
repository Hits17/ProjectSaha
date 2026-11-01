"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api, ApiError, OPEN_LICENSES, RESOURCE_CATEGORIES,
  OpenResource, OpenResourceInput, OpenResourceType,
} from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Badge, Btn, EmptyRow, fmtDate, Section, Td, Th } from "@/components/ui";

const EMPTY_FORM: OpenResourceInput = {
  resource_type: "patent",
  title: "",
  summary: "",
  authors: "",
  organization: "",
  identifier: "",
  source_url: "",
  license: "public_domain",
  category: "general",
  tags: [],
  published_year: null,
};

function label(v: string): string {
  return v.replace(/_/g, " ");
}

export default function OpenLibraryPage() {
  const { accessToken } = useAuthStore();
  const [rows, setRows] = useState<OpenResource[]>([]);
  const [form, setForm] = useState<OpenResourceInput>(EMPTY_FORM);
  const [tagsText, setTagsText] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    if (!accessToken) return;
    api.resources.list(accessToken, { limit: 200 }).then(setRows).catch((e) => setError(e.message));
  }, [accessToken]);

  useEffect(() => { load(); }, [load]);

  const set = <K extends keyof OpenResourceInput>(k: K, v: OpenResourceInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const startEdit = (r: OpenResource) => {
    setEditingId(r.id);
    setForm({
      resource_type: r.resource_type,
      title: r.title,
      summary: r.summary ?? "",
      authors: r.authors ?? "",
      organization: r.organization ?? "",
      identifier: r.identifier ?? "",
      source_url: r.source_url,
      rights_evidence_url: r.rights_evidence_url || "",
      rights_note: r.rights_note || "",
      jurisdiction: r.jurisdiction || "",
      license: r.license,
      category: r.category ?? "general",
      tags: r.tags,
      published_year: r.published_year,
    });
    setTagsText(r.tags.join(", "));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setTagsText("");
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    const body: OpenResourceInput = {
      ...form,
      title: form.title.trim(),
      summary: form.summary?.toString().trim() || null,
      authors: form.authors?.toString().trim() || null,
      organization: form.organization?.toString().trim() || null,
      identifier: form.identifier?.toString().trim() || null,
      source_url: form.source_url.trim(),
      rights_evidence_url: form.rights_evidence_url?.trim() || null,
      rights_note: form.rights_note?.trim() || null,
      jurisdiction: form.jurisdiction?.trim() || null,
      tags: tagsText.split(",").map((t) => t.trim()).filter(Boolean),
    };
    try {
      if (editingId) await api.resources.update(accessToken!, editingId, body);
      else await api.resources.create(accessToken!, body);
      cancelEdit();
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (r: OpenResource) => {
    setError(null);
    try { await api.resources.update(accessToken!, r.id, { is_active: !r.is_active }); load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Update failed"); }
  };

  const approve = async (r: OpenResource) => {
    setError(null);
    try { await api.resources.approve(accessToken!, r.id); load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Approve failed"); }
  };

  const reject = async (r: OpenResource) => {
    const reason = prompt("Reason for declining (sent to the submitter, optional):", "");
    if (reason === null) return;
    setError(null);
    try { await api.resources.reject(accessToken!, r.id, reason.trim() || undefined); load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Reject failed"); }
  };

  const pending = rows.filter((r) => r.status === "pending");

  const inputCls = "border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-full";

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Open Innovation Library</h1>
      <p className="text-sm text-slate-500">
        Curate sources with documented reuse conditions. Record rights evidence, relevant
        jurisdictions and attribution requirements. Public availability or a copyright
        license does not by itself establish patent permission.
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {pending.length > 0 && (
        <Section title={`${pending.length} pending member submission${pending.length === 1 ? "" : "s"}`}>
          <div className="space-y-3">
            {pending.map((r) => (
              <div key={r.id} className="flex items-start justify-between gap-4 border border-amber-200 bg-amber-50/50 rounded-lg p-3">
                <div className="min-w-0">
                  <a href={r.source_url} target="_blank" rel="noopener noreferrer"
                    className="font-medium text-slate-900 hover:underline">{r.title}</a>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {r.resource_type.replace(/_/g, " ")} · {label(r.license)}
                    {r.identifier ? ` · ${r.identifier}` : ""}{r.category ? ` · ${label(r.category)}` : ""}
                  </p>
                  {r.summary && <p className="text-sm text-slate-600 mt-1 line-clamp-2">{r.summary}</p>}
                </div>
                <div className="flex gap-1.5 shrink-0">
                  <Btn variant="primary" onClick={() => approve(r)}>Approve</Btn>
                  <Btn variant="danger" onClick={() => reject(r)}>Reject</Btn>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title={editingId ? "Edit resource" : "Add resource"}
        actions={editingId ? <Btn onClick={cancelEdit}>Cancel edit</Btn> : undefined}>
        <form onSubmit={save} className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Type</label>
            <select value={form.resource_type}
              onChange={(e) => set("resource_type", e.target.value as OpenResourceType)}
              className={inputCls}>
              <option value="patent">Patent</option>
              <option value="research_paper">Research paper</option>
              <option value="trademark">Trademark</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs text-slate-400 mb-1">Title</label>
            <input value={form.title} onChange={(e) => set("title", e.target.value)}
              required minLength={5} maxLength={300} className={inputCls} />
          </div>
          <div className="md:col-span-3">
            <label className="block text-xs text-slate-400 mb-1">Summary — what it is and what someone could build with it</label>
            <textarea value={form.summary ?? ""} onChange={(e) => set("summary", e.target.value)}
              rows={3} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Authors / inventors</label>
            <input value={form.authors ?? ""} onChange={(e) => set("authors", e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Organization</label>
            <input value={form.organization ?? ""} onChange={(e) => set("organization", e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Patent № / DOI / USPTO reg. №</label>
            <input value={form.identifier ?? ""} onChange={(e) => set("identifier", e.target.value)}
              placeholder="US7614507B2, 10.1000/xyz, or USPTO 0123456" className={inputCls} />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs text-slate-400 mb-1">Source URL</label>
            <input type="url" value={form.source_url} onChange={(e) => set("source_url", e.target.value)}
              required placeholder="https://patents.google.com/…" className={inputCls} />
          </div>
          <label className="block text-xs text-slate-500">Rights evidence URL
            <input className={inputCls} type="url" value={form.rights_evidence_url || ""} onChange={e => set("rights_evidence_url", e.target.value)} placeholder="https://" maxLength={1000} />
          </label>
          <label className="block text-xs text-slate-500">Relevant jurisdiction
            <input className={inputCls} value={form.jurisdiction || ""} onChange={e => set("jurisdiction", e.target.value)} maxLength={120} />
          </label>
          <label className="block text-xs text-slate-500 md:col-span-3">Rights and attribution notes
            <textarea className={inputCls} value={form.rights_note || ""} onChange={e => set("rights_note", e.target.value)} maxLength={3000} rows={3} />
          </label>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Published year</label>
            <input type="number" min={1800} max={2100} value={form.published_year ?? ""}
              onChange={(e) => set("published_year", e.target.value ? Number(e.target.value) : null)}
              className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">License</label>
            <select value={form.license} onChange={(e) => set("license", e.target.value)} className={inputCls}>
              {OPEN_LICENSES.map((l) => <option key={l} value={l}>{label(l)}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Category</label>
            <select value={form.category ?? "general"} onChange={(e) => set("category", e.target.value)} className={inputCls}>
              {RESOURCE_CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Tags (comma-separated, max 10)</label>
            <input value={tagsText} onChange={(e) => setTagsText(e.target.value)}
              placeholder="filtration, membrane, water" className={inputCls} />
          </div>
          <div className="md:col-span-3">
            <button type="submit" disabled={saving}
              className="bg-slate-900 text-white rounded-lg px-4 py-1.5 text-sm font-medium hover:bg-slate-700 disabled:opacity-50">
              {saving ? "Saving…" : editingId ? "Save changes" : "Add to library"}
            </button>
          </div>
        </form>
      </Section>

      <Section title={`${rows.length} resources`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>Title</Th><Th>Type</Th><Th>License</Th><Th>Category</Th><Th>Views</Th><Th>Building</Th><Th>Review</Th><Th>Status</Th><Th>Added</Th><Th>Actions</Th></tr></thead>
            <tbody>
              {rows.length === 0 && <EmptyRow cols={10} text="No resources yet — add the first one above." />}
              {rows.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50">
                  <Td className="font-medium text-slate-900 max-w-xs">
                    <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      {r.title}
                    </a>
                    {r.identifier && <span className="block text-xs text-slate-400">{r.identifier}</span>}
                  </Td>
                  <Td><Badge value={r.resource_type} /></Td>
                  <Td className="whitespace-nowrap">{label(r.license)}</Td>
                  <Td className="whitespace-nowrap">{r.category ? label(r.category) : "—"}</Td>
                  <Td>{r.view_count}</Td>
                  <Td>{r.build_count}</Td>
                  <Td><Badge value={r.status} /></Td>
                  <Td>{r.is_active
                    ? <span className="text-xs font-medium text-green-700">active</span>
                    : <span className="text-xs font-medium text-slate-400">archived</span>}</Td>
                  <Td>{fmtDate(r.created_at)}</Td>
                  <Td>
                    <div className="flex gap-1.5">
                      <Btn onClick={() => startEdit(r)}>Edit</Btn>
                      {r.status === "rejected" && (
                        <Btn variant="primary" onClick={() => approve(r)}>Approve</Btn>
                      )}
                      <Btn variant={r.is_active ? "danger" : "primary"} onClick={() => toggleActive(r)}>
                        {r.is_active ? "Archive" : "Restore"}
                      </Btn>
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
