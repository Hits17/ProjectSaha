"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth";
import { api, ApiError, Material, MaterialInput } from "@/lib/api";

const CATEGORIES: { value: string; label: string }[] = [
  { value: "metals", label: "Metals" },
  { value: "polymers_plastics", label: "Polymers & Plastics" },
  { value: "textiles", label: "Textiles" },
  { value: "wood_paper", label: "Wood & Paper" },
  { value: "chemicals", label: "Chemicals" },
  { value: "electronics_components", label: "Electronics Components" },
  { value: "ceramics_glass", label: "Ceramics & Glass" },
  { value: "packaging", label: "Packaging" },
  { value: "agricultural", label: "Agricultural" },
  { value: "other", label: "Other" },
];

const categoryLabel = (value: string) =>
  CATEGORIES.find((c) => c.value === value)?.label ?? value;

const STATUS_BADGE: Record<string, string> = {
  active: "text-green-700 bg-green-50",
  paused: "text-amber-700 bg-amber-50",
  archived: "text-muted bg-surface-2",
};

function MaterialCard({
  material,
  isMine,
  onEdit,
  onPauseResume,
  onArchive,
}: {
  material: Material;
  isMine: boolean;
  onEdit?: (m: Material) => void;
  onPauseResume?: (m: Material) => void;
  onArchive?: (m: Material) => void;
}) {
  return (
    <div className="bg-white border border-line rounded-xl p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs text-muted uppercase tracking-wide mb-1">
            {categoryLabel(material.category)} · {material.region}, {material.country}
          </p>
          <p className="font-semibold text-ink truncate">{material.title}</p>
          {material.description && (
            <p className="text-sm text-muted mt-1 line-clamp-2">{material.description}</p>
          )}
        </div>
        <div className="shrink-0 text-right">
          <p className="font-semibold text-ink">
            {material.currency} {Number(material.price_per_unit).toLocaleString()}
            <span className="text-xs text-muted font-normal"> / {material.unit}</span>
          </p>
          {isMine && (
            <span className={`inline-block mt-1 text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_BADGE[material.status]}`}>
              {material.status}
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs text-muted">
        {material.min_order_quantity && <span>Min. order: {Number(material.min_order_quantity).toLocaleString()} {material.unit}</span>}
        {material.monthly_capacity && <span>Capacity: {material.monthly_capacity}</span>}
        {material.lead_time_days !== null && <span>Lead time: {material.lead_time_days} days</span>}
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-line">
        {isMine ? (
          <div className="flex gap-3 text-xs font-medium">
            <button onClick={() => onEdit?.(material)} className="text-ink hover:underline">Edit</button>
            {material.status !== "archived" && (
              <>
                <button onClick={() => onPauseResume?.(material)} className="text-ink hover:underline">
                  {material.status === "active" ? "Pause" : "Resume"}
                </button>
                <button onClick={() => onArchive?.(material)} className="text-red-600 hover:underline">Archive</button>
              </>
            )}
          </div>
        ) : (
          <>
            <p className="text-xs text-muted">
              Seller: <span className="font-medium text-ink-soft">{material.seller_name}</span>
            </p>
            {material.seller_email && (
              <a
                href={`mailto:${material.seller_email}?subject=${encodeURIComponent(`Saha material inquiry: ${material.title}`)}`}
                className="text-xs font-medium bg-accent text-white px-3 py-1.5 rounded-lg hover:bg-accent-hover transition-colors"
              >
                Contact Seller
              </a>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const EMPTY_FORM = {
  title: "",
  description: "",
  category: "other",
  region: "",
  country: "",
  unit: "kg",
  price_per_unit: "",
  currency: "USD",
  min_order_quantity: "",
  monthly_capacity: "",
  lead_time_days: "",
};

function MaterialForm({
  initial,
  onCancel,
  onSaved,
}: {
  initial: Material | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const { accessToken } = useAuthStore();
  const [form, setForm] = useState(() =>
    initial
      ? {
          title: initial.title,
          description: initial.description ?? "",
          category: initial.category,
          region: initial.region,
          country: initial.country,
          unit: initial.unit,
          price_per_unit: String(initial.price_per_unit),
          currency: initial.currency,
          min_order_quantity: initial.min_order_quantity ? String(initial.min_order_quantity) : "",
          monthly_capacity: initial.monthly_capacity ?? "",
          lead_time_days: initial.lead_time_days !== null ? String(initial.lead_time_days) : "",
        }
      : EMPTY_FORM
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (field: keyof typeof EMPTY_FORM) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken) return;
    setSaving(true);
    setError("");
    const body: MaterialInput = {
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      category: form.category,
      region: form.region.trim(),
      country: form.country.trim(),
      unit: form.unit.trim(),
      price_per_unit: Number(form.price_per_unit),
      currency: form.currency.trim().toUpperCase() || "USD",
      min_order_quantity: form.min_order_quantity ? Number(form.min_order_quantity) : undefined,
      monthly_capacity: form.monthly_capacity.trim() || undefined,
      lead_time_days: form.lead_time_days ? Number(form.lead_time_days) : undefined,
    };
    try {
      if (initial) await api.materials.update(accessToken, initial.id, body);
      else await api.materials.create(accessToken, body);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save material");
      setSaving(false);
    }
  };

  const inputCls =
    "w-full px-3 py-2 border border-line-strong rounded-lg text-sm focus:ring-2 focus:ring-accent focus:border-transparent";
  const labelCls = "block text-sm font-medium text-ink-soft mb-1";

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-line rounded-xl p-5 space-y-4">
      <h3 className="font-semibold text-ink">{initial ? "Edit material" : "List a raw material"}</h3>

      <div>
        <label className={labelCls}>Material name</label>
        <input value={form.title} onChange={set("title")} required minLength={3} className={inputCls} placeholder="e.g. Recycled HDPE pellets, food-grade" />
      </div>

      <div>
        <label className={labelCls}>Description</label>
        <textarea value={form.description} onChange={set("description")} rows={3} className={inputCls} placeholder="Grades, certifications, processing notes…" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Category</label>
          <select value={form.category} onChange={set("category")} className={inputCls}>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Unit</label>
          <input value={form.unit} onChange={set("unit")} required className={inputCls} placeholder="kg, ton, litre, m²…" />
        </div>
        <div>
          <label className={labelCls}>Region</label>
          <input value={form.region} onChange={set("region")} required minLength={2} className={inputCls} placeholder="e.g. Gujarat" />
        </div>
        <div>
          <label className={labelCls}>Country</label>
          <input value={form.country} onChange={set("country")} required minLength={2} className={inputCls} placeholder="e.g. India" />
        </div>
        <div>
          <label className={labelCls}>Price per unit</label>
          <input value={form.price_per_unit} onChange={set("price_per_unit")} required type="number" min="0.01" step="0.01" className={inputCls} placeholder="1.85" />
        </div>
        <div>
          <label className={labelCls}>Currency</label>
          <input value={form.currency} onChange={set("currency")} required maxLength={3} className={inputCls} placeholder="USD" />
        </div>
        <div>
          <label className={labelCls}>Min. order quantity <span className="text-muted">(optional)</span></label>
          <input value={form.min_order_quantity} onChange={set("min_order_quantity")} type="number" min="0.01" step="0.01" className={inputCls} placeholder="500" />
        </div>
        <div>
          <label className={labelCls}>Lead time, days <span className="text-muted">(optional)</span></label>
          <input value={form.lead_time_days} onChange={set("lead_time_days")} type="number" min="0" max="365" className={inputCls} placeholder="14" />
        </div>
      </div>

      <div>
        <label className={labelCls}>Monthly capacity <span className="text-muted">(optional)</span></label>
        <input value={form.monthly_capacity} onChange={set("monthly_capacity")} className={inputCls} placeholder="e.g. 20 tons/month" />
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>}

      <div className="flex gap-2">
        <button type="submit" disabled={saving} className="bg-accent text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
          {saving ? "Saving…" : initial ? "Save changes" : "Publish material"}
        </button>
        <button type="button" onClick={onCancel} className="px-5 py-2.5 rounded-lg text-sm font-medium text-ink-soft border border-line hover:border-line-strong transition-colors">
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function MaterialsPage() {
  const { accessToken, user } = useAuthStore();
  const [tab, setTab] = useState<"browse" | "mine">("browse");

  // Browse state
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [region, setRegion] = useState("");
  const [results, setResults] = useState<Material[] | null>(null);

  // My listings state
  const [mine, setMine] = useState<Material[] | null>(null);
  const [editing, setEditing] = useState<Material | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const runBrowse = useCallback(async (filters: { q?: string; category?: string; region?: string }) => {
    if (!accessToken) return;
    setLoading(true);
    setError("");
    try {
      setResults(await api.materials.browse(accessToken, { ...filters, limit: 50 }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load materials");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  const loadMine = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError("");
    try {
      setMine(await api.materials.mine(accessToken));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load your materials");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    if (tab === "browse") runBrowse({});
    else loadMine();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, accessToken]);

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault();
    runBrowse({ q: q.trim() || undefined, category: category || undefined, region: region.trim() || undefined });
  };

  const handlePauseResume = async (m: Material) => {
    if (!accessToken) return;
    try {
      await api.materials.update(accessToken, m.id, { status: m.status === "active" ? "paused" : "active" });
      loadMine();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Update failed");
    }
  };

  const handleArchive = async (m: Material) => {
    if (!accessToken) return;
    if (!window.confirm(`Archive "${m.title}"? It will disappear from the marketplace.`)) return;
    try {
      await api.materials.archive(accessToken, m.id);
      loadMine();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Archive failed");
    }
  };

  const isVerified = user?.kyc_status === "verified";
  const inputCls =
    "px-3 py-2 border border-line-strong rounded-lg text-sm focus:ring-2 focus:ring-accent focus:border-transparent";

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Raw Materials</h1>
          <p className="text-sm text-muted mt-0.5">
            Source production inputs near you — or list materials you can supply. Regional sourcing cuts costs and gives every buyer a backup supplier.
          </p>
        </div>
        {tab === "mine" && isVerified && !showForm && (
          <button
            onClick={() => { setEditing(null); setShowForm(true); }}
            className="shrink-0 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            + List material
          </button>
        )}
      </div>

      <div className="flex gap-1 bg-surface-2 rounded-lg p-1 w-fit">
        {([["browse", "Browse"], ["mine", "My Materials"]] as const).map(([value, label]) => (
          <button
            key={value}
            onClick={() => { setTab(value); setShowForm(false); setEditing(null); }}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === value ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink-soft"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>}

      {tab === "browse" && (
        <>
          <form onSubmit={handleFilter} className="flex flex-wrap gap-2">
            <input value={q} onChange={(e) => setQ(e.target.value)} className={`${inputCls} flex-1 min-w-48`} placeholder="Search materials…" />
            <select value={category} onChange={(e) => setCategory(e.target.value)} className={inputCls}>
              <option value="">All categories</option>
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
            <input value={region} onChange={(e) => setRegion(e.target.value)} className={`${inputCls} w-40`} placeholder="Region" />
            <button type="submit" disabled={loading} className="bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
              Filter
            </button>
          </form>

          {loading && <p className="text-sm text-muted">Loading…</p>}
          {!loading && results !== null && results.length === 0 && (
            <div className="bg-white border border-dashed border-line-strong rounded-xl p-12 text-center">
              <p className="text-muted text-sm">No materials match yet. Be the first to list one from your region.</p>
            </div>
          )}
          <div className="space-y-3">
            {results?.map((m) => (
              <MaterialCard key={m.id} material={m} isMine={m.seller_id === user?.id} onEdit={(mat) => { setTab("mine"); setEditing(mat); setShowForm(true); }} />
            ))}
          </div>
        </>
      )}

      {tab === "mine" && (
        <>
          {!isVerified && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-amber-800 text-sm">
              Complete KYC verification to list materials.
            </div>
          )}

          {showForm && (
            <MaterialForm
              initial={editing}
              onCancel={() => { setShowForm(false); setEditing(null); }}
              onSaved={() => { setShowForm(false); setEditing(null); loadMine(); }}
            />
          )}

          {loading && <p className="text-sm text-muted">Loading…</p>}
          {!loading && mine !== null && mine.length === 0 && !showForm && (
            <div className="bg-white border border-dashed border-line-strong rounded-xl p-12 text-center">
              <p className="text-muted text-sm">You haven't listed any materials yet.</p>
            </div>
          )}
          <div className="space-y-3">
            {mine?.map((m) => (
              <MaterialCard
                key={m.id}
                material={m}
                isMine
                onEdit={(mat) => { setEditing(mat); setShowForm(true); }}
                onPauseResume={handlePauseResume}
                onArchive={handleArchive}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
