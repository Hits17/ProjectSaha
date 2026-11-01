"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function AdminLoginPage() {
  const router = useRouter();
  const { setAuth, clearAuth, status, user } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (status === "authenticated" && user?.role === "admin") router.replace("/");
  }, [status, user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const revision = useAuthStore.getState().revision;
    try {
      const tokens = await api.auth.login(email, password, mfaCode || undefined);
      const me = await api.auth.me(tokens.access_token, true);
      if (useAuthStore.getState().revision !== revision) return;
      if (me.role !== "admin") {
        clearAuth();
        setError("This console is restricted to administrators.");
        return;
      }
      setAuth(me, tokens.access_token, tokens.refresh_token);
      router.replace("/");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Login failed";
      if (err instanceof ApiError && message === "MFA code required") {
        // Password verified — reveal the second-factor field instead of erroring.
        setMfaRequired(true);
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  if (status === "loading" || (status === "authenticated" && user?.role === "admin")) return <p role="status" className="p-12 text-center">Opening administration…</p>;

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Saha <span className="text-indigo-400">Admin</span></h1>
          <p className="text-sm text-slate-400 mt-1">Platform administration console</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
          <div>
            <label htmlFor="admin-email" className="block text-xs font-medium text-slate-600 mb-1">Email</label>
            <input id="admin-email" autoComplete="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:border-indigo-500" />
          </div>
          <div>
            <label htmlFor="admin-password" className="block text-xs font-medium text-slate-600 mb-1">Password</label>
            <input id="admin-password" autoComplete="current-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:border-indigo-500" />
          </div>
          {mfaRequired && (
            <div>
              <label htmlFor="admin-mfa" className="block text-xs font-medium text-slate-600 mb-1">Authenticator code</label>
              <input id="admin-mfa" type="text" inputMode="numeric" autoComplete="one-time-code" value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)} required autoFocus placeholder="6-digit code"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:border-indigo-500" />
            </div>
          )}
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <button type="submit" disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50">
            {loading ? "Signing in…" : "Sign in"}
          </button>
          <p className="text-xs text-slate-500 text-center">Administrator accounts only. All actions are audited.</p>
        </form>
      </div>
    </div>
  );
}
