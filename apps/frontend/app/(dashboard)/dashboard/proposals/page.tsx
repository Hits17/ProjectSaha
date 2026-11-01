"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { useProposals, useToken } from "@/lib/hooks";
import { api, ApiError, Proposal, ProposalStatus } from "@/lib/api";
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

const STATUS: Record<ProposalStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  submitted: { label: "Submitted", tone: "info" },
  nda_pending: { label: "NDA Pending", tone: "warning" },
  nda_signed: { label: "NDA Signed", tone: "info" },
  negotiating: { label: "Negotiating", tone: "accent" },
  accepted: { label: "Accepted", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
};

function ProposalRow({
  proposal,
  userId,
  listingTitle,
}: {
  proposal: Proposal;
  userId: string;
  listingTitle?: string;
}) {
  const isBuyer = proposal.buyer_id === userId;
  const badge = STATUS[proposal.status] ?? STATUS.draft;

  return (
    <CardLink href={`/dashboard/proposals/${proposal.id}`}>
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-muted uppercase tracking-wide">
              {isBuyer ? "Sent" : "Received"}
            </span>
            <Badge tone={badge.tone} dot>
              {badge.label}
            </Badge>
          </div>
          <p className="text-sm font-semibold text-ink truncate">
            {listingTitle ?? `Listing ${proposal.listing_id.slice(0, 8)}…`}
          </p>
          {proposal.offer_amount_usd && (
            <p className="text-sm text-muted mt-0.5 tabular-nums">
              ${Number(proposal.offer_amount_usd).toLocaleString()} · {proposal.license_type} · v
              {proposal.version}
            </p>
          )}
        </div>
        <p className="text-xs text-muted shrink-0">
          {new Date(proposal.updated_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
        </p>
      </div>
    </CardLink>
  );
}

export default function ProposalsPage() {
  const { user } = useAuthStore();
  const token = useToken();
  const { data: proposals = [], isLoading, error } = useProposals();
  const [listingTitles, setListingTitles] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!token || proposals.length === 0) return;
    const uniqueIds = [...new Set(proposals.map((p) => p.listing_id))];
    (async () => {
      const titles: Record<string, string> = {};
      await Promise.allSettled(
        uniqueIds.map(async (id) => {
          try {
            const l = await api.listings.get(token, id);
            titles[id] = l.title;
          } catch {}
        }),
      );
      setListingTitles(titles);
    })();
  }, [token, proposals]);

  const received = proposals.filter((p) => p.seller_id === user?.id);
  const sent = proposals.filter((p) => p.buyer_id === user?.id);

  return (
    <div className="space-y-6">
      <PageHeader title="Proposals" description="Offers you've sent and offers on your listings." />

      {isLoading && <SkeletonList rows={3} />}
      {error && (
        <ErrorBanner>{error instanceof ApiError ? error.message : "Failed to load"}</ErrorBanner>
      )}

      {!isLoading && !error && proposals.length === 0 && (
        <EmptyState
          icon={<Icon.Handshake className="w-5 h-5" />}
          title="No proposals yet"
          description="Discover published IP and make your first offer."
          action={
            <Button href="/dashboard/discover">
              <Icon.Compass className="w-4 h-4" />
              Discover IP
            </Button>
          }
        />
      )}

      {received.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide font-sans">
            Received ({received.length})
          </h2>
          {received.map((p) => (
            <ProposalRow key={p.id} proposal={p} userId={user?.id ?? ""} listingTitle={listingTitles[p.listing_id]} />
          ))}
        </div>
      )}

      {sent.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide font-sans">
            Sent ({sent.length})
          </h2>
          {sent.map((p) => (
            <ProposalRow key={p.id} proposal={p} userId={user?.id ?? ""} listingTitle={listingTitles[p.listing_id]} />
          ))}
        </div>
      )}
    </div>
  );
}
