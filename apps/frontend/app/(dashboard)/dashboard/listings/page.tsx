"use client";

import { useMyListings } from "@/lib/hooks";
import { ApiError, ListingStatus } from "@/lib/api";
import {
  Badge,
  Button,
  CardLink,
  EmptyState,
  ErrorBanner,
  PageHeader,
  SkeletonList,
  type Tone,
} from "@/components/ui";
import * as Icon from "@/components/ui/icons";

const STATUS: Record<ListingStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  ai_generating: { label: "AI Working", tone: "info" },
  review: { label: "Review", tone: "warning" },
  published: { label: "Published", tone: "success" },
  archived: { label: "Archived", tone: "danger" },
};

export default function ListingsPage() {
  const { data: listings, isLoading, error } = useMyListings();

  return (
    <div className="space-y-6">
      <PageHeader
        title="My IP Listings"
        description="Document your intellectual property and publish it to the marketplace."
        actions={
          <Button href="/dashboard/listings/new" size="sm">
            <Icon.Plus className="w-4 h-4" />
            New Listing
          </Button>
        }
      />

      {isLoading && <SkeletonList rows={3} />}

      {error && (
        <ErrorBanner>
          {error instanceof ApiError ? error.message : "Failed to load listings"}
        </ErrorBanner>
      )}

      {!isLoading && !error && listings?.length === 0 && (
        <EmptyState
          icon={<Icon.FileText className="w-5 h-5" />}
          title="No listings yet"
          description="Create your first IP listing and let AI help you document it."
          action={
            <Button href="/dashboard/listings/new">
              <Icon.Plus className="w-4 h-4" />
              Create a listing
            </Button>
          }
        />
      )}

      <div className="space-y-3">
        {listings?.map((l) => {
          const badge = STATUS[l.status] ?? STATUS.draft;
          return (
            <CardLink key={l.id} href={`/dashboard/listings/${l.id}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-semibold text-ink truncate">{l.title}</p>
                  <p className="text-xs text-muted mt-0.5">
                    {l.product_category ?? "No category"} · {l.bom_items.length} BOM items ·{" "}
                    {l.vault_assets.length} files
                  </p>
                </div>
                <Badge tone={badge.tone} dot>
                  {badge.label}
                </Badge>
              </div>
              {l.public_description && (
                <p className="text-sm text-ink-soft mt-2 line-clamp-2">{l.public_description}</p>
              )}
            </CardLink>
          );
        })}
      </div>
    </div>
  );
}
