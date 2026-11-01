"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Button, LoadingRow } from "@/components/ui";
import * as Icon from "@/components/ui/icons";

function VerifyEmailInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("Missing verification token.");
      return;
    }
    api.auth
      .confirmEmail(token)
      .then(() => setState("ok"))
      .catch((e) => {
        setState("error");
        setMessage(e instanceof ApiError ? e.message : "Verification failed.");
      });
  }, [token]);

  return (
    <div className="grid place-items-center py-16">
      <div className="bg-surface border border-line rounded-2xl shadow-md p-8 max-w-md w-full text-center">
        {state === "loading" && <LoadingRow label="Verifying your email…" />}
        {state === "ok" && (
          <>
            <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-success-soft text-success grid place-items-center">
              <Icon.Check className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-semibold text-ink">Email verified</h1>
            <p className="text-sm text-muted mt-1">Your account email is now confirmed.</p>
            <Button href="/dashboard" className="mt-6">
              Go to dashboard
            </Button>
          </>
        )}
        {state === "error" && (
          <>
            <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-danger-soft text-danger grid place-items-center">
              <Icon.AlertTriangle className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-semibold text-ink">Verification failed</h1>
            <p className="text-sm text-muted mt-1">{message}</p>
            <Link
              href="/dashboard/security"
              className="mt-6 inline-block text-ink font-medium hover:text-accent hover:underline text-sm"
            >
              Request a new link →
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<LoadingRow label="Loading…" />}>
      <VerifyEmailInner />
    </Suspense>
  );
}
