"use client";

import { useAuthStore } from "@/store/auth";
import { useTransactions } from "@/lib/hooks";
import { ApiError, TransactionStatus } from "@/lib/api";
import {
  Badge,
  CardLink,
  EmptyState,
  ErrorBanner,
  PageHeader,
  SkeletonList,
  type Tone,
} from "@/components/ui";
import * as Icon from "@/components/ui/icons";

const STATUS: Record<TransactionStatus, { label: string; tone: Tone }> = {
  pending_legal: { label: "Pending Legal", tone: "neutral" },
  contract_drafting: { label: "Drafting Contract", tone: "info" },
  contract_review: { label: "Review Contract", tone: "warning" },
  signing_pending: { label: "Signing", tone: "warning" },
  signed: { label: "Signed", tone: "info" },
  escrow_pending: { label: "Escrow Pending", tone: "accent" },
  escrow_funded: { label: "Escrow Funded", tone: "accent" },
  disbursement_pending: { label: "Disbursing", tone: "accent" },
  completed: { label: "Completed", tone: "success" },
  disputed: { label: "Disputed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export default function TransactionsPage() {
  const { user } = useAuthStore();
  const { data: transactions = [], isLoading, error } = useTransactions();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Transactions"
        description="Your active deals through legal, signing, escrow, and disbursement."
      />

      {isLoading && <SkeletonList rows={3} />}
      {error && (
        <ErrorBanner>{error instanceof ApiError ? error.message : "Failed to load"}</ErrorBanner>
      )}

      {!isLoading && !error && transactions.length === 0 && (
        <EmptyState
          icon={<Icon.Shield className="w-5 h-5" />}
          title="No transactions yet"
          description="A transaction is created automatically when a proposal is accepted."
        />
      )}

      <div className="space-y-3">
        {transactions.map((txn) => {
          const isBuyer = txn.buyer_id === user?.id;
          const badge = STATUS[txn.status] ?? STATUS.pending_legal;
          const ds = txn.deal_summary;
          return (
            <CardLink key={txn.id} href={`/dashboard/transactions/${txn.id}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-muted font-medium uppercase tracking-wide">
                      {isBuyer ? "Buying" : "Selling"}
                    </span>
                    <Badge tone={badge.tone} dot>
                      {badge.label}
                    </Badge>
                  </div>
                  <p className="text-sm font-semibold text-ink truncate">
                    {ds?.listing_title ?? `Transaction ${txn.id.slice(0, 8)}…`}
                  </p>
                  <p className="text-sm text-muted mt-0.5 tabular-nums">
                    ${Number(txn.deal_value_usd).toLocaleString()}
                    {txn.law_firm && ` · ${txn.law_firm.name}`}
                  </p>
                </div>
                <p className="text-xs text-muted shrink-0">
                  {new Date(txn.updated_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </p>
              </div>
            </CardLink>
          );
        })}
      </div>
    </div>
  );
}
