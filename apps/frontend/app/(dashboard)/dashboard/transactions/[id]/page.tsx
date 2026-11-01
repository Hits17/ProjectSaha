"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { StepUpPrompt, useStepUp } from "@/components/step-up-prompt";
import { api, ApiError, ContractDraftResponse, LawFirm, Review, Transaction, VaultAccessFile } from "@/lib/api";

const STATUS_STEPS = [
  { key: "pending_legal",        label: "Pending Legal" },
  { key: "contract_drafting",    label: "Drafting" },
  { key: "contract_review",      label: "Review" },
  { key: "signing_pending",      label: "Signing" },
  { key: "signed",               label: "Signed" },
  { key: "escrow_pending",       label: "Escrow" },
  { key: "escrow_funded",        label: "Funded" },
  { key: "disbursement_pending", label: "Disbursing" },
  { key: "completed",            label: "Complete" },
];

function StatusTracker({ status }: { status: string }) {
  const currentIdx = STATUS_STEPS.findIndex((s) => s.key === status);
  if (status === "cancelled" || status === "disputed") {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-red-700 text-sm font-medium capitalize">
        {status}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1">
      {STATUS_STEPS.map((step, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;
        return (
          <div key={step.key} className="flex items-center gap-1 shrink-0">
            <div className={`text-xs px-2 py-1 rounded-full font-medium ${
              active ? "bg-accent text-white"
              : done ? "bg-green-100 text-green-700"
              : "bg-surface-2 text-muted"
            }`}>
              {step.label}
            </div>
            {i < STATUS_STEPS.length - 1 && (
              <span className={`text-xs ${done ? "text-green-400" : "text-gray-200"}`}>›</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function TransactionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { accessToken, user } = useAuthStore();
  const [txn, setTxn] = useState<Transaction | null>(null);
  const [lawFirms, setLawFirms] = useState<LawFirm[]>([]);
  const [contractText, setContractText] = useState<string | null>(null);
  const [vaultFiles, setVaultFiles] = useState<VaultAccessFile[] | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [ratingInput, setRatingInput] = useState(5);
  const [commentInput, setCommentInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");

  const reload = async () => {
    if (!accessToken) return;
    const t = await api.transactions.get(accessToken, id);
    setTxn(t);
    if (t.status === "pending_legal") {
      const firms = await api.transactions.lawFirms(accessToken);
      setLawFirms(firms);
    }
    if (t.status === "completed") {
      const rv = await api.transactions.listReviews(accessToken, id).catch(() => []);
      setReviews(rv);
    }
  };

  useEffect(() => {
    if (!accessToken) return;
    reload()
      .catch((e) => setError(e instanceof ApiError ? e.message : "Not found"))
      .finally(() => setLoading(false));
  }, [accessToken, id]);

  const handleAssignFirm = async (firmId: string) => {
    if (!accessToken) return;
    setActionLoading(true);
    try {
      const updated = await api.transactions.assignLawFirm(accessToken, id, firmId);
      setTxn(updated);
      setLawFirms([]);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Failed"); }
    finally { setActionLoading(false); }
  };

  const stepUp = useStepUp();

  const handleDraftContract = async () => {
    if (!accessToken) return;
    setActionLoading(true);
    setError("");
    try {
      const resp: ContractDraftResponse = await api.transactions.draftContract(accessToken, id);
      setTxn(resp.transaction);
      setContractText(resp.contract_text);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Draft failed"); }
    finally { setActionLoading(false); }
  };

  // Signing records THIS party's signature; the deal executes only once both
  // parties have signed the same contract bytes (security/AUDIT.md SAHA-008).
  const handleSign = async () => {
    if (!accessToken) return;
    const stepUpToken = await stepUp.require();
    if (!stepUpToken) return;
    setActionLoading(true);
    try {
      const updated = await api.transactions.sign(accessToken, id, stepUpToken);
      setTxn(updated);
      setContractText(null);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Sign failed"); }
    finally { setActionLoading(false); }
  };

  const runSettlement = async (fn: () => Promise<Transaction>, failMsg: string) => {
    if (!accessToken) return;
    setActionLoading(true);
    setError("");
    try {
      const updated = await fn();
      setTxn(updated);
    } catch (e) { setError(e instanceof ApiError ? e.message : failMsg); }
    finally { setActionLoading(false); }
  };

  const handleCreateEscrow = () =>
    runSettlement(() => api.transactions.createEscrow(accessToken!, id), "Failed to create escrow");
  const handleConfirmEscrow = () =>
    runSettlement(() => api.transactions.confirmEscrow(accessToken!, id), "Failed to confirm payment");
  // Buyer-only: releasing escrow is the payer's decision about the payer's
  // money (security/AUDIT.md SAHA-007).
  const handleDisburse = async () => {
    const stepUpToken = await stepUp.require();
    if (!stepUpToken) return;
    runSettlement(
      () => api.transactions.disburse(accessToken!, id, stepUpToken),
      "Disbursement failed",
    );
  };

  const handleViewVault = async () => {
    if (!accessToken) return;
    setActionLoading(true);
    setError("");
    try {
      const files = await api.transactions.vaultAccess(accessToken, id);
      setVaultFiles(files);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Vault access denied"); }
    finally { setActionLoading(false); }
  };

  const handleSubmitReview = async () => {
    if (!accessToken) return;
    setActionLoading(true);
    setError("");
    try {
      const review = await api.transactions.createReview(accessToken, id, {
        rating: ratingInput,
        comment: commentInput.trim() || undefined,
      });
      setReviews((prev) => [review, ...prev]);
      setCommentInput("");
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not submit review"); }
    finally { setActionLoading(false); }
  };

  if (loading) return <p className="text-sm text-muted">Loading…</p>;
  if (!txn) return <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{error || "Not found"}</div>;

  const ds = txn.deal_summary;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard/transactions" className="text-xs text-muted hover:text-ink-soft mb-1 inline-block">← Transactions</Link>
        <h1 className="text-xl font-bold text-ink">{ds?.listing_title ?? "Transaction"}</h1>
        <div className="mt-3">
          <StatusTracker status={txn.status} />
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>}

      {/* Deal Summary */}
      <div className="bg-white border border-line rounded-xl p-5">
        <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">Deal Summary</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
          {[
            { label: "Deal Value", value: `$${Number(txn.deal_value_usd).toLocaleString()}` },
            { label: "License", value: ds?.license_type ?? "—" },
            { label: "Territory", value: ds?.territory ?? "—" },
            { label: "Duration", value: ds?.duration_months ? `${ds.duration_months} months` : "—" },
            { label: "Saha Fee (5%)", value: txn.saha_commission_usd ? `$${Number(txn.saha_commission_usd).toLocaleString()}` : "—" },
            { label: "Legal Fee (3%)", value: txn.legal_fee_usd ? `$${Number(txn.legal_fee_usd).toLocaleString()}` : "—" },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs text-muted">{label}</p>
              <p className="font-medium text-ink mt-0.5">{value}</p>
            </div>
          ))}
        </div>
        {txn.law_firm && (
          <div className="mt-4 pt-4 border-t border-line flex items-center gap-3">
            <div>
              <p className="text-xs text-muted">Assigned Law Firm</p>
              <p className="text-sm font-medium text-ink">{txn.law_firm.name}</p>
              <p className="text-xs text-muted">{txn.law_firm.jurisdictions.join(", ")}</p>
            </div>
          </div>
        )}
      </div>

      {/* Action Panel */}
      {txn.status === "pending_legal" && lawFirms.length > 0 && (
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">Select Law Firm</h2>
          <div className="space-y-2">
            {lawFirms.map((firm) => (
              <div key={firm.id} className="flex items-center justify-between p-3 border border-line rounded-lg">
                <div>
                  <p className="text-sm font-medium text-ink">{firm.name}</p>
                  <p className="text-xs text-muted">{firm.jurisdictions.join(", ")}</p>
                </div>
                <button
                  onClick={() => handleAssignFirm(firm.id)}
                  disabled={actionLoading}
                  className="text-sm bg-accent text-white px-3 py-1.5 rounded-lg hover:bg-accent-hover disabled:opacity-50"
                >
                  Select
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {txn.status === "contract_drafting" && (
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Contract</h2>
          <p className="text-sm text-muted mb-4">AI will draft a license agreement based on your deal terms using Anthropic Claude.</p>
          <button
            onClick={handleDraftContract}
            disabled={actionLoading}
            className="bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50"
          >
            {actionLoading ? "Drafting with AI…" : "Draft Contract"}
          </button>
        </div>
      )}

      {txn.status === "contract_review" && (
        <div className="bg-white border border-line rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold text-muted uppercase tracking-wide">Contract Review</h2>
            <button
              onClick={handleSign}
              disabled={actionLoading}
              className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              {actionLoading ? "Signing…" : "Sign Contract"}
            </button>
          </div>
          {contractText ? (
            <pre className="bg-canvas border border-line rounded-lg p-4 text-xs text-ink-soft overflow-auto max-h-96 whitespace-pre-wrap">
              {contractText}
            </pre>
          ) : (
            <button
              onClick={handleDraftContract}
              disabled={actionLoading}
              className="text-sm text-ink font-medium hover:underline"
            >
              {actionLoading ? "Loading…" : "Reload contract text"}
            </button>
          )}
        </div>
      )}

      {/* Settlement Panel */}
      {["signed", "escrow_pending", "escrow_funded", "disbursement_pending", "completed"].includes(txn.status) && (
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">Settlement</h2>

          {/* Payout breakdown */}
          {(() => {
            const deal = Number(txn.deal_value_usd);
            const commission = Number(txn.saha_commission_usd ?? 0);
            const legal = Number(txn.legal_fee_usd ?? 0);
            const escrow = Number(txn.escrow_fee_usd ?? 0);
            const ipHolder = deal - commission - legal - escrow;
            const fmt = (n: number) => `$${n.toLocaleString()}`;
            return (
              <div className="bg-canvas border border-line rounded-lg p-4 mb-4 space-y-1.5 text-sm">
                <div className="flex justify-between"><span className="text-muted">Escrow amount</span><span className="font-medium text-ink">{fmt(deal)}</span></div>
                <div className="flex justify-between"><span className="text-muted">— Saha commission (5%)</span><span className="text-ink-soft">−{fmt(commission)}</span></div>
                <div className="flex justify-between"><span className="text-muted">— Legal fee (3%)</span><span className="text-ink-soft">−{fmt(legal)}</span></div>
                <div className="flex justify-between"><span className="text-muted">— Escrow fee (1%)</span><span className="text-ink-soft">−{fmt(escrow)}</span></div>
                <div className="flex justify-between pt-1.5 mt-1.5 border-t border-line"><span className="font-medium text-ink">IP holder net payout</span><span className="font-semibold text-green-700">{fmt(ipHolder)}</span></div>
              </div>
            );
          })()}

          {/* Status-driven actions */}
          {txn.status === "signed" && (
            <div>
              <p className="text-sm text-muted mb-3">Contract signed. The buyer initiates the Stripe escrow to lock funds.</p>
              {user?.id === txn.buyer_id ? (
                <button onClick={handleCreateEscrow} disabled={actionLoading}
                  className="bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50">
                  {actionLoading ? "Initiating…" : "Initiate Escrow"}
                </button>
              ) : (
                <p className="text-sm text-muted">Waiting for the buyer to initiate escrow.</p>
              )}
            </div>
          )}

          {txn.status === "escrow_pending" && (
            <div>
              <p className="text-sm text-muted mb-3">
                Escrow PaymentIntent created. In production the buyer completes payment via Stripe; in this environment, the buyer confirms funding directly.
              </p>
              {user?.id === txn.buyer_id ? (
                <button onClick={handleConfirmEscrow} disabled={actionLoading}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
                  {actionLoading ? "Confirming…" : "Confirm Escrow Funded"}
                </button>
              ) : (
                <p className="text-sm text-muted">Waiting for the buyer to fund escrow.</p>
              )}
            </div>
          )}

          {txn.status === "escrow_funded" && (
            <div>
              <p className="text-sm text-muted mb-1">
                Funded {txn.escrow_funded_at ? new Date(txn.escrow_funded_at).toLocaleString() : ""}. Vault access is now released to the buyer.
              </p>
              <p className="text-sm text-muted mb-3">Disburse to release funds to the IP holder and law firm, completing the transaction.</p>
              <button onClick={handleDisburse} disabled={actionLoading}
                className="bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50">
                {actionLoading ? "Disbursing…" : "Disburse Funds"}
              </button>
            </div>
          )}

          {txn.status === "completed" && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800">
              ✓ Transaction complete. Disbursed {txn.disbursed_at ? new Date(txn.disbursed_at).toLocaleString() : ""}.
              {user?.id === txn.buyer_id && (
                <span className="block mt-1">
                  Ready to produce? <a href="/dashboard/materials" className="font-medium underline hover:no-underline">Source raw materials in your region →</a>
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Vault Access — available to parties once escrow is funded */}
      {["escrow_funded", "disbursement_pending", "completed"].includes(txn.status) && (
        <div className="bg-white border border-line rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-muted uppercase tracking-wide">Vault Access</h2>
            <button onClick={handleViewVault} disabled={actionLoading}
              className="text-sm text-ink font-medium hover:underline disabled:opacity-50">
              {actionLoading ? "Loading…" : vaultFiles ? "Refresh" : "Load files"}
            </button>
          </div>
          {vaultFiles === null ? (
            <p className="text-sm text-muted">Released to the buyer after escrow funding. Click “Load files” to list the decrypted downloads.</p>
          ) : vaultFiles.length === 0 ? (
            <p className="text-sm text-muted">No vault files attached to this listing.</p>
          ) : (
            <div className="space-y-2">
              {vaultFiles.map((f) => (
                <button key={f.asset_id} type="button"
                  onClick={async () => {
                    if (!accessToken) return;
                    const stepUpToken = await stepUp.require();
                    if (!stepUpToken) return;
                    api.transactions
                      .downloadVaultFile(accessToken, f, stepUpToken)
                      .catch((e) => setError(e.message));
                  }}
                  className="w-full flex items-center justify-between p-3 border border-line rounded-lg hover:bg-canvas text-left">
                  <div>
                    <p className="text-sm font-medium text-ink">{f.filename}</p>
                    <p className="text-xs text-muted">{(f.file_size_bytes / 1024).toFixed(1)} KB · decrypted on download</p>
                  </div>
                  <span className="text-sm text-ink font-medium">Download ↓</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Reviews — available once the transaction is completed */}
      {txn.status === "completed" && (() => {
        const myReview = reviews.find((r) => r.reviewer_id === user?.id);
        const counterpartyReview = reviews.find((r) => r.reviewer_id !== user?.id);
        return (
          <div className="bg-white border border-line rounded-xl p-5">
            <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">Reviews</h2>

            {!myReview ? (
              <div className="mb-4">
                <p className="text-sm text-muted mb-3">Rate your counterparty on this completed deal.</p>
                <div className="flex items-center gap-1 mb-3">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} type="button" onClick={() => setRatingInput(n)}
                      className={`text-2xl leading-none ${n <= ratingInput ? "text-amber-400" : "text-gray-200"} hover:text-amber-400`}>
                      ★
                    </button>
                  ))}
                  <span className="ml-2 text-sm text-muted">{ratingInput}/5</span>
                </div>
                <textarea
                  value={commentInput}
                  onChange={(e) => setCommentInput(e.target.value)}
                  placeholder="Optional comment…"
                  rows={2}
                  maxLength={2000}
                  className="w-full border border-line rounded-lg p-2.5 text-sm focus:ring-1 focus:ring-accent mb-3"
                />
                <button onClick={handleSubmitReview} disabled={actionLoading}
                  className="bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50">
                  {actionLoading ? "Submitting…" : "Submit Review"}
                </button>
              </div>
            ) : (
              <div className="mb-4 bg-canvas border border-line rounded-lg p-3">
                <p className="text-xs text-muted mb-1">Your review</p>
                <p className="text-amber-400 text-sm">{"★".repeat(myReview.rating)}<span className="text-gray-200">{"★".repeat(5 - myReview.rating)}</span></p>
                {myReview.comment && <p className="text-sm text-ink-soft mt-1">{myReview.comment}</p>}
              </div>
            )}

            <div className="pt-3 border-t border-line">
              <p className="text-xs text-muted mb-2">Review from counterparty</p>
              {counterpartyReview ? (
                <div>
                  <p className="text-amber-400 text-sm">{"★".repeat(counterpartyReview.rating)}<span className="text-gray-200">{"★".repeat(5 - counterpartyReview.rating)}</span></p>
                  {counterpartyReview.comment && <p className="text-sm text-ink-soft mt-1">{counterpartyReview.comment}</p>}
                </div>
              ) : (
                <p className="text-sm text-muted">No review yet.</p>
              )}
            </div>
          </div>
        );
      })()}

      <StepUpPrompt
        isOpen={stepUp.isOpen}
        onSubmit={stepUp.submit}
        onCancel={stepUp.cancel}
        action="This action"
      />
    </div>
  );
}
