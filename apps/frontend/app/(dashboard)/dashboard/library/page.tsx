"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api, ApiError, OpenResource, OpenResourceSubmission, OpenResourceType } from "@/lib/api";
import * as Icon from "@/components/ui/icons";

const CATEGORIES: { value: string; label: string }[] = [
  { value: "", label: "All domains" },
  { value: "biotech_pharma", label: "Biotech & Pharma" },
  { value: "clean_energy", label: "Clean Energy" },
  { value: "materials_science", label: "Materials Science" },
  { value: "software_ai", label: "Software & AI" },
  { value: "hardware_electronics", label: "Hardware & Electronics" },
  { value: "consumer_products", label: "Consumer Products" },
  { value: "agritech_food", label: "AgriTech & Food" },
  { value: "medical_devices", label: "Medical Devices" },
  { value: "industrial_manufacturing", label: "Industrial Manufacturing" },
  { value: "general", label: "General" },
];

const LICENSES: { value: string; label: string }[] = [
  { value: "public_domain", label: "Public domain / expired patent" },
  { value: "cc0", label: "CC0" },
  { value: "cc_by", label: "CC BY" },
  { value: "cc_by_sa", label: "CC BY-SA" },
  { value: "mit", label: "MIT" },
  { value: "apache_2_0", label: "Apache 2.0" },
  { value: "gpl_3_0", label: "GPL 3.0" },
  { value: "open_patent_pledge", label: "Royalty-free patent pledge" },
  { value: "defensive_publication", label: "Defensive publication" },
];

const LICENSE_LABELS: Record<string, string> = Object.fromEntries(
  LICENSES.map((l) => [l.value, l.label.split(" / ")[0]])
);

// Resource-type badge: patent = indigo, research paper = teal, trademark = amber.
const TYPE_BADGES: Record<string, { label: string; className: string }> = {
  patent: { label: "Patent", className: "bg-indigo-50 text-indigo-700" },
  research_paper: { label: "Research paper", className: "bg-teal-50 text-teal-700" },
  trademark: { label: "Trademark", className: "bg-amber-50 text-amber-700" },
};

const categoryLabel = (v: string | null) =>
  CATEGORIES.find((c) => c.value === v)?.label ?? v ?? "General";

function ResourceCard({
  resource,
  onToggleBuild,
}: {
  resource: OpenResource;
  onToggleBuild?: (r: OpenResource) => void;
}) {
  const typeBadge = TYPE_BADGES[resource.resource_type] ?? TYPE_BADGES.patent;
  return (
    <div className="bg-white border border-line rounded-xl p-5 flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${typeBadge.className}`}
        >
          {typeBadge.label}
        </span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-700 font-medium">
          {LICENSE_LABELS[resource.license] ?? resource.license}
        </span>
      </div>

      <p className="font-semibold text-ink">{resource.title}</p>
      <p className="text-xs text-muted uppercase tracking-wide mt-1">
        {categoryLabel(resource.category)}
        {resource.published_year ? ` · ${resource.published_year}` : ""}
        {resource.identifier ? ` · ${resource.identifier}` : ""}
      </p>
      {resource.summary && (
        <p className="text-sm text-muted mt-2 line-clamp-3">{resource.summary}</p>
      )}
      {(resource.authors || resource.organization) && (
        <p className="text-xs text-muted mt-2">
          {resource.authors}
          {resource.authors && resource.organization ? " — " : ""}
          {resource.organization}
        </p>
      )}
      {resource.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {resource.tags.map((t) => (
            <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-surface-2 text-muted">
              {t}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-line">
        <div className="flex items-center gap-3 text-xs text-muted min-w-0">
          <span className="shrink-0">{resource.view_count} views</span>
          {resource.build_count > 0 && (
            <span className="inline-flex items-center gap-1 text-emerald-700 font-medium shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              {resource.build_count} building
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {onToggleBuild && (
            <button
              onClick={() => onToggleBuild(resource)}
              className={`text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors ${
                resource.is_building
                  ? "bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100"
                  : "bg-white border-line text-ink-soft hover:border-line-strong"
              }`}
              title={resource.is_building ? "You're building this — click to withdraw" : "Tell the community you're developing this"}
            >
              {resource.is_building ? "Building ✓" : "I'm building this"}
            </button>
          )}
          <Link
            href={`/dashboard/community?topic=${encodeURIComponent(resource.category || "general")}`}
            className="text-xs font-medium px-2.5 py-1.5 rounded-lg border border-line text-ink-soft hover:border-line-strong transition-colors"
            title="Discuss this resource in the matching R&D community"
          >
            Discuss
          </Link>
          <a
            href={resource.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium bg-accent text-white px-2.5 py-1.5 rounded-lg hover:bg-accent-hover transition-colors"
          >
            Source ↗
          </a>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------- submission dialog ------- */

const EMPTY_SUBMISSION: OpenResourceSubmission = {
  resource_type: "patent",
  title: "",
  summary: "",
  identifier: "",
  source_url: "",
  license: "public_domain",
  category: "general",
};

function SubmitModal({ onClose, onSubmitted }: { onClose: () => void; onSubmitted: () => void }) {
  const token = useAuthStore((s) => s.accessToken);
  const [form, setForm] = useState<OpenResourceSubmission>(EMPTY_SUBMISSION);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = <K extends keyof OpenResourceSubmission>(k: K, v: OpenResourceSubmission[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setSaving(true);
    setError("");
    try {
      await api.openResources.submit(token, {
        ...form,
        title: form.title.trim(),
        summary: form.summary?.toString().trim() || null,
        identifier: form.identifier?.toString().trim() || null,
        source_url: form.source_url.trim(),
        rights_evidence_url: form.rights_evidence_url?.trim() || null,
        rights_note: form.rights_note?.trim() || null,
        jurisdiction: form.jurisdiction?.trim() || null,
      });
      onSubmitted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Submission failed");
    } finally {
      setSaving(false);
    }
  };

  const inputCls =
    "w-full border border-line-strong rounded-lg px-3 py-2 text-sm focus:border-line-strong";

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-ink">Suggest a resource</h2>
        <p className="text-sm text-muted mt-1 mb-4">
          Suggest a source with evidence about its reuse conditions. A public patent document is not automatically free to use; administrators review submissions before publication.
        </p>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-muted mb-1">Type</label>
              <select value={form.resource_type}
                onChange={(e) => set("resource_type", e.target.value as OpenResourceType)}
                className={inputCls}>
                <option value="patent">Patent</option>
                <option value="research_paper">Research paper</option>
                <option value="trademark">Trademark</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted mb-1">Patent № / DOI / USPTO reg. № (optional)</label>
              <input value={form.identifier ?? ""} onChange={(e) => set("identifier", e.target.value)}
                placeholder="US7614507B2" className={inputCls} />
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Title</label>
            <input value={form.title} onChange={(e) => set("title", e.target.value)}
              required minLength={5} maxLength={300} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Source URL</label>
            <input type="url" value={form.source_url} onChange={(e) => set("source_url", e.target.value)}
              required placeholder="https://patents.google.com/…" className={inputCls} />
          </div>
          <label className="block text-xs text-muted">Rights evidence URL (optional)
            <input type="url" value={form.rights_evidence_url || ""} onChange={e => set("rights_evidence_url", e.target.value)} placeholder="https:// — license, pledge or official legal status" maxLength={1000} className={inputCls} />
          </label>
          <label className="block text-xs text-muted">Relevant jurisdiction (optional)
            <input value={form.jurisdiction || ""} onChange={e => set("jurisdiction", e.target.value)} placeholder="For example, United States" maxLength={120} className={inputCls} />
          </label>
          <label className="block text-xs text-muted">Rights and attribution notes (optional)
            <textarea value={form.rights_note || ""} onChange={e => set("rights_note", e.target.value)} maxLength={3000} rows={3} className={inputCls} />
          </label>
          <div>
            <label className="block text-xs text-muted mb-1">Why it&apos;s worth building on (optional)</label>
            <textarea value={form.summary ?? ""} onChange={(e) => set("summary", e.target.value)}
              rows={3} className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-muted mb-1">License</label>
              <select value={form.license} onChange={(e) => set("license", e.target.value)} className={inputCls}>
                {LICENSES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted mb-1">Domain</label>
              <select value={form.category ?? "general"} onChange={(e) => set("category", e.target.value)} className={inputCls}>
                {CATEGORIES.filter((c) => c.value).map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={saving}
              className="flex-1 bg-accent text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-accent-hover disabled:opacity-40 transition-colors">
              {saving ? "Submitting…" : "Submit for review"}
            </button>
            <button type="button" onClick={onClose}
              className="px-5 py-2.5 rounded-xl text-sm font-medium text-ink-soft border border-line hover:bg-canvas transition">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- page ------ */

export default function OpenLibraryPage() {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const [resources, setResources] = useState<OpenResource[]>([]);
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSubmit, setShowSubmit] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const isVerified = (user?.email_verified || user?.kyc_status === "verified");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const rows = await api.openResources.browse(token, {
        q: q.trim() || undefined,
        resource_type: type || undefined,
        category: category || undefined,
        limit: 60,
      });
      setResources(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load the library");
    } finally {
      setLoading(false);
    }
  }, [token, q, type, category]);

  // Load on mount and whenever filters change (search debounced).
  useEffect(() => {
    const t = setTimeout(load, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  const toggleBuild = async (r: OpenResource) => {
    if (!token) return;
    if (!isVerified) {
      setNotice("Confirm your email to declare you're building on a resource.");
      return;
    }
    // Optimistic flip; reconcile with the server's count.
    setResources((prev) =>
      prev.map((x) =>
        x.id === r.id
          ? { ...x, is_building: !r.is_building, build_count: r.build_count + (r.is_building ? -1 : 1) }
          : x
      )
    );
    try {
      const status = r.is_building
        ? await api.openResources.withdrawBuild(token, r.id)
        : await api.openResources.declareBuild(token, r.id);
      setResources((prev) =>
        prev.map((x) =>
          x.id === r.id ? { ...x, is_building: status.is_building, build_count: status.build_count } : x
        )
      );
    } catch (e) {
      setResources((prev) => prev.map((x) => (x.id === r.id ? r : x)));
      setError(e instanceof ApiError ? e.message : "Could not update your build status");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-ink">Open Innovation Library</h1>
          <p className="text-sm text-muted mt-1 max-w-2xl">
            Open-source patents, research papers, and free-to-use trademarks — expired or
            pledged patents, openly licensed research, and genericized marks you can freely
            build on. Develop it, improve it, and share what you make with the world.
          </p>
        </div>
        {isVerified && (
          <button
            onClick={() => setShowSubmit(true)}
            className="shrink-0 bg-accent text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            + Suggest a resource
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-56">
          <Icon.Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search titles, abstracts, authors, patent numbers…"
            className="w-full bg-white border border-line rounded-lg pl-9 pr-3 py-2 text-sm focus:border-line-strong"
          />
        </div>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="bg-white border border-line rounded-lg px-3 py-2 text-sm"
        >
          <option value="">All types</option>
          <option value="patent">Patents</option>
          <option value="research_paper">Research papers</option>
          <option value="trademark">Trademarks</option>
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="bg-white border border-line rounded-lg px-3 py-2 text-sm"
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      {notice && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-amber-800 text-sm flex items-center justify-between">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)} className="text-amber-600 hover:text-amber-800 ml-3">✕</button>
        </div>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-muted text-sm">
          <Icon.Spinner className="w-4 h-4 mr-2 animate-spin" /> Loading the library…
        </div>
      ) : resources.length === 0 ? (
        <div className="bg-white border border-line rounded-xl p-10 text-center">
          <Icon.BookOpen className="w-8 h-8 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-muted">
            {q || type || category
              ? "Nothing matches these filters yet."
              : "The library is being stocked — check back soon."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {resources.map((r) => (
            <ResourceCard key={r.id} resource={r} onToggleBuild={toggleBuild} />
          ))}
        </div>
      )}

      {showSubmit && (
        <SubmitModal
          onClose={() => setShowSubmit(false)}
          onSubmitted={() => {
            setShowSubmit(false);
            setNotice("Thanks! Your suggestion is in the review queue — you'll get a notification once an admin approves it.");
          }}
        />
      )}
    </div>
  );
}
