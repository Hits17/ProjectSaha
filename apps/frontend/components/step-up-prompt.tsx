"use client";

import { useCallback, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

/**
 * Re-authentication prompt for irreversible or high-value actions.
 *
 * Escrow release, contract execution and confidential document egress each
 * require a freshly minted step-up token in addition to the access token, so a
 * stolen session alone cannot trigger them (security/AUDIT.md SAHA-015).
 *
 * `useStepUp` keeps the token in memory for its short lifetime and never
 * persists it — the whole point is that it is not recoverable from storage.
 */

const STEP_UP_LIFETIME_MS = 10 * 60 * 1000;

interface CachedToken {
  token: string;
  expiresAt: number;
}

export function useStepUp() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [cached, setCached] = useState<CachedToken | null>(null);
  const [pending, setPending] = useState<null | ((token: string | null) => void)>(null);

  /** Returns a valid step-up token, prompting the user if one is needed. */
  const require = useCallback((): Promise<string | null> => {
    if (cached && cached.expiresAt > Date.now() + 30_000) {
      return Promise.resolve(cached.token);
    }
    return new Promise((resolve) => setPending(() => resolve));
  }, [cached]);

  const submit = useCallback(
    async (password: string, mfaCode: string) => {
      if (!accessToken) return { error: "Not signed in" };
      try {
        const res = await api.auth.stepUp(accessToken, password, mfaCode || undefined);
        const token = res.step_up_token;
        setCached({ token, expiresAt: Date.now() + STEP_UP_LIFETIME_MS });
        pending?.(token);
        setPending(null);
        return {};
      } catch (e) {
        return { error: e instanceof ApiError ? e.message : "Re-authentication failed" };
      }
    },
    [accessToken, pending]
  );

  const cancel = useCallback(() => {
    pending?.(null);
    setPending(null);
  }, [pending]);

  return { require, submit, cancel, isOpen: pending !== null };
}

export function StepUpPrompt({
  isOpen,
  onSubmit,
  onCancel,
  action,
}: {
  isOpen: boolean;
  onSubmit: (password: string, mfaCode: string) => Promise<{ error?: string }>;
  onCancel: () => void;
  action: string;
}) {
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!isOpen) return null;

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const result = await onSubmit(password, mfaCode);
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setPassword("");
    setMfaCode("");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <form
        onSubmit={handle}
        className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl space-y-4"
      >
        <div>
          <h2 className="text-base font-semibold text-ink">Confirm it&rsquo;s you</h2>
          <p className="mt-1 text-sm text-muted">
            {action} is irreversible, so we ask for your password again before going ahead.
          </p>
        </div>

        <label className="block">
          <span className="text-sm font-medium text-ink-soft">Password</span>
          <input
            type="password"
            autoFocus
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-ink-soft">
            Authenticator code <span className="text-muted">(if enabled)</span>
          </span>
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm tracking-widest"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 rounded-lg border border-line-strong px-4 py-2 text-sm font-medium text-ink-soft"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="flex-1 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy ? "Verifying…" : "Confirm"}
          </button>
        </div>
      </form>
    </div>
  );
}
