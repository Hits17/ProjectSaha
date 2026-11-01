"use client";

import { useState } from "react";
import { api, ApiError, type KYCStatus } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

const STATUS_CONFIG: Record<KYCStatus, { label: string; color: string; bg: string }> = {
  pending:   { label: "Not Started",   color: "text-ink-soft",  bg: "bg-surface-2"  },
  in_review: { label: "In Review",     color: "text-amber-700", bg: "bg-amber-50"  },
  verified:  { label: "Verified",      color: "text-green-700", bg: "bg-green-50"  },
  rejected:  { label: "Rejected",      color: "text-red-700",   bg: "bg-red-50"    },
};

export function KYCStatusBadge({ status }: { status: KYCStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${cfg.bg} ${cfg.color}`}>
      {status === "verified" && <span>✓</span>}
      {status === "in_review" && <span>⏳</span>}
      {status === "rejected" && <span>✕</span>}
      {cfg.label}
    </span>
  );
}

export function KYCFlow() {
  const { user, accessToken, setUser } = useAuthStore();
  const [loading, setLoading] = useState<"initiate" | "complete" | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  if (!user || !accessToken) return null;

  const kyc_status = user.kyc_status;

  if (kyc_status === "verified") {
    return (
      <div className="bg-green-50 border border-green-200 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center text-white font-bold">✓</div>
          <div>
            <p className="font-medium text-green-900">Identity Verified</p>
            <p className="text-sm text-green-700">You can now create listings and submit proposals.</p>
          </div>
        </div>
      </div>
    );
  }

  const handleInitiate = async () => {
    setLoading("initiate");
    setError("");
    setMessage("");
    try {
      const res = await api.users.initiateKyc(accessToken);
      setMessage(res.message);
      const updated = await api.users.me(accessToken);
      setUser(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to start KYC");
    } finally {
      setLoading(null);
    }
  };

  const handleMockComplete = async () => {
    setLoading("complete");
    setError("");
    try {
      await api.users.completeKycMock(accessToken);
      const updated = await api.users.me(accessToken);
      setUser(updated);
      setMessage("Identity verified successfully!");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to complete KYC");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="border border-amber-200 bg-amber-50 rounded-xl p-4 space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 bg-amber-400 rounded-full flex items-center justify-center text-white font-bold flex-shrink-0">!</div>
        <div>
          <p className="font-medium text-amber-900">Identity Verification Required</p>
          <p className="text-sm text-amber-700 mt-0.5">
            {kyc_status === "pending"
              ? "Verify your identity to list IP, submit proposals, and transact on Saha."
              : "Your verification is being reviewed. In dev mode you can simulate approval below."}
          </p>
        </div>
      </div>

      {message && (
        <div className="bg-white border border-amber-200 rounded-lg p-2 text-sm text-amber-800">
          {message}
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        {kyc_status === "pending" && (
          <button
            onClick={handleInitiate}
            disabled={loading !== null}
            className="bg-amber-500 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors"
          >
            {loading === "initiate" ? "Starting…" : "Start Verification"}
          </button>
        )}

        {kyc_status === "in_review" && (
          <button
            onClick={handleMockComplete}
            disabled={loading !== null}
            className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {loading === "complete" ? "Verifying…" : "Simulate Approval (dev only)"}
          </button>
        )}
      </div>
    </div>
  );
}
