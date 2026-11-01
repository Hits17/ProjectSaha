"use client";

import { SecureChat } from "@/components/secure-chat";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuthStore } from "@/store/auth";
import { api, ApiError, Proposal, ProposalMessage } from "@/lib/api";

const offerSchema = z.object({
  offer_amount_usd: z.number().positive("Must be positive"),
  license_type: z.string().min(1, "Required"),
  territory: z.string().min(1, "Required"),
  duration_months: z.number().int().positive("Must be positive"),
  notes: z.string().optional(),
});
type OfferForm = z.infer<typeof offerSchema>;

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft", submitted: "Submitted", nda_pending: "NDA Pending",
  nda_signed: "NDA Signed", negotiating: "Negotiating",
  accepted: "Accepted", rejected: "Rejected", withdrawn: "Withdrawn",
};
const STATUS_COLOR: Record<string, string> = {
  draft: "text-muted", submitted: "text-blue-600", nda_pending: "text-yellow-600",
  nda_signed: "text-teal-600", negotiating: "text-purple-600",
  accepted: "text-green-600", rejected: "text-red-600", withdrawn: "text-muted",
};

function OfferPanel({ proposal, isBuyer, onAction }: {
  proposal: Proposal;
  isBuyer: boolean;
  onAction: (action: "submit" | "counter" | "accept" | "reject" | "withdraw", body?: OfferForm) => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [formType, setFormType] = useState<"submit" | "counter">("submit");
  const { register, handleSubmit, formState: { errors } } = useForm<OfferForm>({
    resolver: zodResolver(offerSchema),
    defaultValues: {
      offer_amount_usd: Number(proposal.offer_amount_usd) || undefined,
      license_type: proposal.license_type ?? "",
      territory: proposal.territory ?? "",
      duration_months: proposal.duration_months ?? undefined,
    },
  });

  const st = proposal.status;
  const canSubmit = isBuyer && st === "draft";
  const canCounter = st === "submitted" || st === "negotiating" || st === "nda_signed";
  const canAccept = (st === "submitted" || st === "negotiating" || st === "nda_signed") && !isBuyer;
  const canReject = canAccept;
  const canWithdraw = isBuyer && !["accepted","rejected","withdrawn"].includes(st);
  const isClosed = ["accepted","rejected","withdrawn"].includes(st);

  if (isClosed) {
    return (
      <div className={`text-sm font-semibold ${STATUS_COLOR[st]}`}>
        Proposal {STATUS_LABEL[st]}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {!showForm && (
        <div className="flex flex-wrap gap-2">
          {canSubmit && (
            <button onClick={() => { setFormType("submit"); setShowForm(true); }}
              className="bg-accent text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-accent-hover">
              Submit Offer
            </button>
          )}
          {canCounter && (
            <button onClick={() => { setFormType("counter"); setShowForm(true); }}
              className="bg-accent text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-accent-hover">
              Counter Offer
            </button>
          )}
          {canAccept && (
            <button onClick={() => onAction("accept")}
              className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-green-700">
              Accept
            </button>
          )}
          {canReject && (
            <button onClick={() => onAction("reject")}
              className="border border-red-300 text-red-600 px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-red-50">
              Reject
            </button>
          )}
          {canWithdraw && (
            <button onClick={() => onAction("withdraw")}
              className="border border-line-strong text-muted px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-canvas">
              Withdraw
            </button>
          )}
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit((d) => { onAction(formType, d); setShowForm(false); })}
          className="bg-canvas border border-line rounded-xl p-4 space-y-3">
          <p className="text-sm font-semibold text-ink-soft">{formType === "submit" ? "Submit Offer" : "Counter Offer"}</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-muted mb-1">Amount (USD)</label>
              <input {...register("offer_amount_usd", { valueAsNumber: true })} type="number" step="0.01"
                className="w-full px-2 py-1.5 border border-line-strong rounded-lg text-sm" />
              {errors.offer_amount_usd && <p className="text-red-500 text-xs mt-0.5">{errors.offer_amount_usd.message}</p>}
            </div>
            <div>
              <label className="block text-xs text-muted mb-1">Duration (months)</label>
              <input {...register("duration_months", { valueAsNumber: true })} type="number"
                className="w-full px-2 py-1.5 border border-line-strong rounded-lg text-sm" />
              {errors.duration_months && <p className="text-red-500 text-xs mt-0.5">{errors.duration_months.message}</p>}
            </div>
            <div>
              <label className="block text-xs text-muted mb-1">License Type</label>
              <input {...register("license_type")} placeholder="Exclusive, Non-exclusive…"
                className="w-full px-2 py-1.5 border border-line-strong rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-xs text-muted mb-1">Territory</label>
              <input {...register("territory")} placeholder="Global, US, EU…"
                className="w-full px-2 py-1.5 border border-line-strong rounded-lg text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Notes (optional)</label>
            <textarea {...register("notes")} rows={2}
              className="w-full px-2 py-1.5 border border-line-strong rounded-lg text-sm resize-none" />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="bg-accent text-white px-4 py-1.5 rounded-lg text-sm font-medium">
              Confirm
            </button>
            <button type="button" onClick={() => setShowForm(false)}
              className="border border-line-strong px-4 py-1.5 rounded-lg text-sm text-ink-soft">
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default function ProposalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { accessToken, user } = useAuthStore();
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    if (!accessToken) return;
    try {
      setProposal(await api.proposals.get(accessToken, id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Not found");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [accessToken, id]);

  const handleAction = async (action: "submit" | "counter" | "accept" | "reject" | "withdraw", body?: OfferForm) => {
    if (!accessToken) return;
    try {
      let updated: Proposal;
      if (action === "submit" && body) updated = await api.proposals.submit(accessToken, id, body);
      else if (action === "counter" && body) updated = await api.proposals.counter(accessToken, id, body);
      else if (action === "accept") updated = await api.proposals.accept(accessToken, id);
      else if (action === "reject") updated = await api.proposals.reject(accessToken, id);
      else if (action === "withdraw") updated = await api.proposals.withdraw(accessToken, id);
      else return;
      setProposal(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed");
    }
  };

  if (loading) return <p className="text-sm text-muted">Loading…</p>;
  if (error && !proposal) return <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{error}</div>;
  if (!proposal || !user) return null;

  const isBuyer = proposal.buyer_id === user.id;
  const latestVersion = proposal.versions[proposal.versions.length - 1];

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard/proposals" className="text-xs text-muted hover:text-ink-soft mb-1 inline-block">← Proposals</Link>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-ink">
              {isBuyer ? "Your Proposal" : "Incoming Proposal"}
            </h1>
            <p className={`text-sm font-medium mt-0.5 ${STATUS_COLOR[proposal.status]}`}>
              {STATUS_LABEL[proposal.status]} · Version {proposal.version}
            </p>
          </div>
          <OfferPanel proposal={proposal} isBuyer={isBuyer} onAction={handleAction} />
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>}

      {latestVersion && (
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">Current Terms</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Offer", value: latestVersion.offer_amount_usd ? `$${Number(latestVersion.offer_amount_usd).toLocaleString()}` : "—" },
              { label: "License", value: latestVersion.license_type ?? "—" },
              { label: "Territory", value: latestVersion.territory ?? "—" },
              { label: "Duration", value: latestVersion.duration_months ? `${latestVersion.duration_months} mo` : "—" },
            ].map((item) => (
              <div key={item.label}>
                <p className="text-xs text-muted">{item.label}</p>
                <p className="text-sm font-semibold text-ink mt-0.5">{item.value}</p>
              </div>
            ))}
          </div>
          {latestVersion.notes && (
            <p className="text-sm text-muted mt-3 border-t border-line pt-3">{latestVersion.notes}</p>
          )}
        </div>
      )}

      <SecureChat scope="proposal" scopeId={id} />

      {proposal.versions.length > 1 && (
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">Negotiation History</h2>
          <div className="space-y-3">
            {[...proposal.versions].reverse().map((v) => (
              <div key={v.id} className="flex items-start justify-between text-sm border-b border-line pb-3 last:border-0 last:pb-0">
                <div>
                  <span className="font-medium text-ink-soft">v{v.version}</span>
                  <span className="text-muted mx-2">·</span>
                  <span className="text-ink-soft">${Number(v.offer_amount_usd).toLocaleString()} · {v.license_type} · {v.duration_months}mo</span>
                  {v.notes && <p className="text-xs text-muted mt-0.5">{v.notes}</p>}
                </div>
                <span className="text-xs text-muted shrink-0">
                  {new Date(v.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
