import { notFound } from "next/navigation";
import Link from "next/link";
import { publicListing } from "@/lib/server-listings";
import { ListingCTA } from "@/components/listing-cta";

export const dynamic = "force-dynamic";

// Anonymous callers receive the teaser tier — no bill of materials, no private
// description, no vault inventory (security/AUDIT.md SAHA-003). This page renders
// only what a stranger is entitled to see; the deal flow discloses the rest.
export default async function PublicListingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const listing = await publicListing(id);
  if (!listing || listing.status !== "published") notFound();

  return (
    <div className="space-y-6">


      <div className="max-w-3xl mx-auto space-y-6">
        <div>
          {listing.product_category && (
            <p className="text-xs text-muted uppercase tracking-wide mb-2">{listing.product_category}</p>
          )}
          <h1 className="text-3xl font-bold text-ink">{listing.title}</h1>
          {listing.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {listing.tags.map((t) => (
                <span key={t} className="text-xs bg-surface-2 text-ink-soft px-2.5 py-1 rounded-full">{t}</span>
              ))}
            </div>
          )}
        </div>

        {listing.public_description && (
          <div className="bg-surface border border-line rounded-xl p-6">
            <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">About this IP</h2>
            <p className="text-ink-soft leading-relaxed">{listing.public_description}</p>
          </div>
        )}

        {/* The bill of materials and equipment list used to render here. They
            are the manufacturing recipe, and this page is reachable by anyone
            on the internet — so the API no longer sends them to non-owners and
            this page no longer asks for them. Material detail is disclosed
            inside a deal, not on a public page. */}
        <div className="bg-surface border border-line rounded-xl p-6">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">
            Technical detail
          </h2>
          <p className="text-sm text-ink-soft">
            The bill of materials, equipment requirements and supporting documents
            for this listing are shared with verified buyers during a deal. Sign in
            and make an offer to begin.
          </p>
        </div>

        <ListingCTA listingId={id} />

        <p className="text-center text-xs text-muted">Published on Saha</p>
      </div>
    </div>
  );
}
