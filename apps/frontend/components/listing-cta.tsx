"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api, ApiError } from "@/lib/api";

export function ListingCTA({ listingId }: { listingId: string }) {
  const { isAuthenticated, user, accessToken } = useAuthStore();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handlePropose = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError("");
    try {
      const proposal = await api.proposals.create(accessToken, listingId);
      router.push(`/dashboard/proposals/${proposal.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to create proposal");
      setLoading(false);
    }
  };

  if (isAuthenticated()) {
    // Open-roles model: any verified member can propose (the API rejects
    // proposing on your own listing).
    const isVerified = user?.kyc_status === "verified";

    return (
      <div className="bg-accent text-white rounded-xl p-6 text-center">
        <p className="font-semibold text-lg">Interested in this IP?</p>
        {isVerified ? (
          <>
            <p className="text-slate-300 text-sm mt-1 mb-4">
              Submit a proposal to start negotiations with the creator.
            </p>
            {error && <p className="text-red-400 text-xs mb-3">{error}</p>}
            <button
              onClick={handlePropose}
              disabled={loading}
              className="inline-block bg-white text-ink font-semibold px-6 py-2.5 rounded-lg text-sm hover:bg-surface-2 disabled:opacity-50 transition-colors"
            >
              {loading ? "Creating proposal…" : "Make a Proposal"}
            </button>
          </>
        ) : (
          <>
            <p className="text-slate-300 text-sm mt-1 mb-4">Complete KYC verification to submit proposals.</p>
            <Link href="/dashboard/marketplace#verification" className="inline-block bg-white text-ink font-semibold px-6 py-2.5 rounded-lg text-sm hover:bg-surface-2 transition-colors">
              Complete Verification
            </Link>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="bg-accent text-white rounded-xl p-6 text-center">
      <p className="font-semibold text-lg">Interested in this IP?</p>
      <p className="text-slate-300 text-sm mt-1 mb-4">
        Create a Saha account to submit a proposal, access vault documents, and start negotiations.
      </p>
      <Link
        href={`/register?next=${encodeURIComponent(`/listings/${listingId}`)}`}
        className="inline-block bg-white text-ink font-semibold px-6 py-2.5 rounded-lg text-sm hover:bg-surface-2 transition-colors"
      >
        Get Started
      </Link>
    </div>
  );
}
