"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api, ApiError, BOMItem, Listing, VaultAsset, isOwnerListing } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  draft:         "Draft",
  ai_generating: "AI Documenting",
  review:        "Ready to Publish",
  published:     "Published",
  archived:      "Archived",
};

function BOMTable({ items }: { items: BOMItem[] }) {
  if (items.length === 0) return <p className="text-sm text-muted">No BOM items yet. Finalize the AI dialogue to generate them.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left">
            <th className="pb-2 font-medium text-muted text-xs uppercase tracking-wide">Material</th>
            <th className="pb-2 font-medium text-muted text-xs uppercase tracking-wide">Qty / Unit</th>
            <th className="pb-2 font-medium text-muted text-xs uppercase tracking-wide">Cadence</th>
            <th className="pb-2 font-medium text-muted text-xs uppercase tracking-wide">Critical</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {items.map((item) => (
            <tr key={item.id}>
              <td className="py-2.5 pr-4">
                <p className="font-medium text-ink">{item.material_name}</p>
                {item.specification && <p className="text-xs text-muted">{item.specification}</p>}
              </td>
              <td className="py-2.5 pr-4 text-ink-soft">{item.quantity_per_unit} {item.unit_of_measure}</td>
              <td className="py-2.5 pr-4 text-muted capitalize">{item.procurement_cadence ?? "—"}</td>
              <td className="py-2.5">
                {item.is_critical
                  ? <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">Critical</span>
                  : <span className="text-xs text-muted">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FileRow({ asset }: { asset: VaultAsset }) {
  const mb = (asset.file_size_bytes / 1024 / 1024).toFixed(2);
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-line last:border-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink truncate">{asset.original_filename}</p>
        <p className="text-xs text-muted">{mb} MB · {asset.content_type ?? "unknown"}</p>
      </div>
      <span className="text-xs text-muted bg-green-50 text-green-700 px-2 py-0.5 rounded-full ml-4 shrink-0">Encrypted</span>
    </div>
  );
}

export default function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { accessToken } = useAuthStore();
  const [listing, setListing] = useState<Listing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    if (!accessToken) return;
    api.listings.get(accessToken, id)
      .then((l) => {
        // The API returns the owner tier only to the creator. Anything else is
        // the teaser, which means this isn't your listing — this page manages
        // BOM, vault files and publishing, none of which apply.
        if (!isOwnerListing(l)) {
          setError("This isn't your listing. Open it from Discover to view the public page.");
          return;
        }
        setListing(l);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Not found"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [accessToken, id]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !accessToken) return;
    setUploading(true);
    setUploadError("");
    try {
      await api.listings.uploadFile(accessToken, id, file);
      load();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handlePublish = async () => {
    if (!accessToken || !listing) return;
    setPublishing(true);
    try {
      const updated = await api.listings.publish(accessToken, id, listing.public_description ?? undefined);
      setListing(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Publish failed");
    } finally {
      setPublishing(false);
    }
  };

  if (loading) return <p className="text-sm text-muted">Loading…</p>;
  if (error) return <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{error}</div>;
  if (!listing) return null;

  const canDialogue = listing.status === "draft" || listing.status === "ai_generating";
  const canPublish = listing.status === "review";
  const isPublished = listing.status === "published";

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/dashboard/listings" className="text-xs text-muted hover:text-ink-soft mb-1 inline-block">← My Listings</Link>
          <h1 className="text-2xl font-bold text-ink">{listing.title}</h1>
          <p className="text-sm text-muted mt-0.5">
            {listing.product_category ?? "No category"}
            {" · "}
            <span className="font-medium">{STATUS_LABEL[listing.status] ?? listing.status}</span>
            {isPublished && (
              <Link href={`/listings/${id}`} className="ml-3 text-blue-600 hover:underline text-xs">View public page →</Link>
            )}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          {canDialogue && (
            <Link
              href={`/dashboard/listings/${id}/dialogue`}
              className="px-3 py-1.5 border border-line-strong rounded-lg text-sm text-ink-soft hover:border-line-strong transition-colors"
            >
              Continue Dialogue
            </Link>
          )}
          {canPublish && (
            <button
              onClick={handlePublish}
              disabled={publishing}
              className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {publishing ? "Publishing…" : "Publish Listing"}
            </button>
          )}
        </div>
      </div>

      {listing.public_description && (
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Public Description</h2>
          <p className="text-sm text-ink-soft">{listing.public_description}</p>
          {listing.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {listing.tags.map((t) => (
                <span key={t} className="text-xs bg-surface-2 text-ink-soft px-2 py-0.5 rounded-full">{t}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="bg-white border border-line rounded-xl p-5">
        <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">Bill of Materials</h2>
        <BOMTable items={listing.bom_items} />
      </div>

      <div className="bg-white border border-line rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide">IP Vault Files</h2>
          {!isPublished && (
            <label className={`cursor-pointer text-sm text-ink font-medium hover:underline ${uploading ? "opacity-50 cursor-not-allowed" : ""}`}>
              {uploading ? "Uploading…" : "+ Upload File"}
              <input ref={fileRef} type="file" className="hidden" onChange={handleFileUpload} disabled={uploading} />
            </label>
          )}
        </div>
        {uploadError && <p className="text-red-600 text-xs mb-3">{uploadError}</p>}
        {listing.vault_assets.length === 0
          ? <p className="text-sm text-muted">No files uploaded. Files are AES-256 encrypted at rest.</p>
          : listing.vault_assets.map((a) => <FileRow key={a.id} asset={a} />)
        }
      </div>

      {listing.equipment_requirements.length > 0 && (
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Equipment Requirements</h2>
          <ul className="space-y-1">
            {listing.equipment_requirements.map((eq, i) => (
              <li key={i} className="text-sm text-ink-soft">· {eq}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
