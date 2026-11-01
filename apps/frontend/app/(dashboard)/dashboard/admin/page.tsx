"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import {
  api, ApiError, AdminTransactionRow, AdminUserRow, AuditLogRow, PlatformStats,
} from "@/lib/api";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="bg-white border border-line rounded-xl p-4">
      <p className="text-xs text-muted uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-ink mt-1">{value}</p>
      {hint && <p className="text-xs text-muted mt-1">{hint}</p>}
    </div>
  );
}

function Breakdown({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return <span className="text-xs text-gray-300">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5 mt-1">
      {entries.map(([k, v]) => (
        <span key={k} className="text-xs bg-surface-2 text-ink-soft rounded px-1.5 py-0.5 capitalize">{k}: {v}</span>
      ))}
    </div>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const { accessToken, user } = useAuthStore();
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [txns, setTxns] = useState<AdminTransactionRow[]>([]);
  const [logs, setLogs] = useState<AuditLogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyUser, setBusyUser] = useState<string | null>(null);

  useEffect(() => {
    if (user && user.role !== "admin") { router.push("/dashboard"); return; }
    if (!accessToken) return;
    Promise.all([
      api.admin.stats(accessToken),
      api.admin.users(accessToken, 25),
      api.admin.transactions(accessToken, 15),
      api.admin.auditLogs(accessToken, 20),
    ])
      .then(([s, u, t, l]) => { setStats(s); setUsers(u); setTxns(t); setLogs(l); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load admin data"))
      .finally(() => setLoading(false));
  }, [accessToken, user, router]);

  const toggleActive = async (u: AdminUserRow) => {
    if (!accessToken) return;
    setBusyUser(u.id);
    try {
      const updated = await api.admin.setUserActive(accessToken, u.id, !u.is_active);
      setUsers((prev) => prev.map((x) => (x.id === u.id ? updated : x)));
    } catch (e) { setError(e instanceof ApiError ? e.message : "Update failed"); }
    finally { setBusyUser(null); }
  };

  if (loading) return <p className="text-sm text-muted">Loading…</p>;
  if (error) return <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink">Admin Console</h1>
        <p className="text-sm text-muted mt-0.5">Platform oversight — users, deals, and activity.</p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="Users" value={stats.users_total} />
          <Stat label="Listings" value={stats.listings_total} />
          <Stat label="Transactions" value={stats.transactions_total} />
          <Stat label="Reviews" value={stats.reviews_total} />
          <Stat label="Disbursed" value={`$${stats.total_disbursed_usd.toLocaleString()}`} hint="To IP holders" />
          <Stat label="Commission" value={`$${stats.total_commission_usd.toLocaleString()}`} hint="Saha revenue" />
          <div className="bg-white border border-line rounded-xl p-4 col-span-2">
            <p className="text-xs text-muted uppercase tracking-wide">Transactions by status</p>
            <Breakdown data={stats.transactions_by_status} />
            <p className="text-xs text-muted uppercase tracking-wide mt-3">Users by role</p>
            <Breakdown data={stats.users_by_role} />
          </div>
        </div>
      )}

      {/* Users */}
      <div className="bg-white border border-line rounded-xl p-5">
        <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Users</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="pb-2 font-medium">Email</th>
                <th className="pb-2 font-medium">Role</th>
                <th className="pb-2 font-medium">KYC</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-line last:border-0">
                  <td className="py-2 text-ink">{u.email}</td>
                  <td className="py-2 text-muted capitalize">{u.role}</td>
                  <td className="py-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${u.kyc_status === "verified" ? "bg-green-100 text-green-700" : "bg-surface-2 text-muted"}`}>{u.kyc_status}</span>
                  </td>
                  <td className="py-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${u.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{u.is_active ? "active" : "disabled"}</span>
                  </td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => toggleActive(u)}
                      disabled={busyUser === u.id || u.role === "admin"}
                      className="text-xs font-medium text-ink hover:underline disabled:opacity-30 disabled:no-underline"
                    >
                      {u.role === "admin" ? "—" : u.is_active ? "Disable" : "Enable"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Recent transactions */}
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Recent Transactions</h2>
          <div className="space-y-2">
            {txns.length === 0 ? <p className="text-sm text-muted">None yet.</p> : txns.map((t) => (
              <div key={t.id} className="flex items-center justify-between text-sm py-1.5 border-b border-line last:border-0">
                <span className="text-muted capitalize">{t.status.replace(/_/g, " ")}</span>
                <span className="font-medium text-ink">${Number(t.deal_value_usd).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Audit log */}
        <div className="bg-white border border-line rounded-xl p-5">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Activity Log</h2>
          <div className="space-y-1.5">
            {logs.length === 0 ? <p className="text-sm text-muted">No activity.</p> : logs.map((l) => (
              <div key={l.id} className="flex items-center justify-between text-xs py-1 border-b border-line last:border-0">
                <span className="text-ink-soft font-mono">{l.action}</span>
                <span className="text-muted">{new Date(l.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
