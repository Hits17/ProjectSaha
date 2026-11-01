"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, KYCStatus, User, UserDetail, UserRole } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Badge, Btn, EmptyRow, fmtDate, Section, Td, Th } from "@/components/ui";

const ROLES: UserRole[] = ["creator", "manufacturer", "legal", "admin"];

export default function UsersPage() {
  const { accessToken, user: me } = useAuthStore();
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [kyc, setKyc] = useState("");
  const [active, setActive] = useState("");
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    api.users.list(accessToken, {
      limit: 100, search: search || undefined, role: role || undefined,
      kyc_status: kyc || undefined,
      is_active: active === "" ? undefined : active === "true",
    }).then(setUsers).catch((e) => setError(e.message));
  }, [accessToken, search, role, kyc, active]);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); load(); if (detail) openDetail(detail.user.id); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Action failed"); }
  };

  const openDetail = async (id: string) => {
    if (!accessToken) return;
    try { setDetail(await api.users.detail(accessToken, id)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Failed to load user"); }
  };

  const changeRole = (u: User) => {
    const next = prompt(`New role for ${u.email} (${ROLES.join(" | ")}):`, u.role);
    if (!next || next === u.role) return;
    if (!ROLES.includes(next as UserRole)) { setError(`Invalid role: ${next}`); return; }
    act(() => api.users.setRole(accessToken!, u.id, next as UserRole));
  };

  const overrideKyc = (u: User, status: KYCStatus) => {
    const reason = prompt(`Reason for setting KYC of ${u.email} to "${status}" (audited):`);
    if (!reason) return;
    act(() => api.users.setKyc(accessToken!, u.id, status, reason));
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">Users</h1>

      <div className="flex flex-wrap gap-2">
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search email or name…"
          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-64" />
        <select value={role} onChange={(e) => setRole(e.target.value)} className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm">
          <option value="">All roles</option>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <select value={kyc} onChange={(e) => setKyc(e.target.value)} className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm">
          <option value="">All KYC</option>
          {["pending", "in_review", "verified", "rejected"].map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <select value={active} onChange={(e) => setActive(e.target.value)} className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm">
          <option value="">Active + disabled</option>
          <option value="true">Active only</option>
          <option value="false">Disabled only</option>
        </select>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Section title={`${users.length} users`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><Th>User</Th><Th>Role</Th><Th>KYC</Th><Th>Status</Th><Th>Joined</Th><Th>Actions</Th></tr></thead>
            <tbody>
              {users.length === 0 && <EmptyRow cols={6} text="No users match." />}
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <Td>
                    <button onClick={() => openDetail(u.id)} className="text-left hover:underline">
                      <p className="font-medium text-slate-900">{u.full_name}</p>
                      <p className="text-xs text-slate-400">{u.email}</p>
                    </button>
                  </Td>
                  <Td><Badge value={u.role} /></Td>
                  <Td><Badge value={u.kyc_status} /></Td>
                  <Td>{u.is_active
                    ? <span className="text-xs font-medium text-green-700">active</span>
                    : <span className="text-xs font-medium text-red-600">disabled</span>}</Td>
                  <Td>{fmtDate(u.created_at)}</Td>
                  <Td>
                    <div className="flex flex-wrap gap-1.5">
                      {u.id !== me?.id && (
                        <Btn variant={u.is_active ? "danger" : "primary"}
                          onClick={() => act(() => api.users.setActive(accessToken!, u.id, !u.is_active))}>
                          {u.is_active ? "Disable" : "Enable"}
                        </Btn>
                      )}
                      <Btn onClick={() => changeRole(u)}>Role</Btn>
                      {u.kyc_status !== "verified" && (
                        <Btn onClick={() => overrideKyc(u, "verified")}>Verify KYC</Btn>
                      )}
                      {u.kyc_status !== "rejected" && (
                        <Btn variant="danger" onClick={() => overrideKyc(u, "rejected")}>Reject KYC</Btn>
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {detail && (
        <Section title={`User detail — ${detail.user.email}`}
          actions={<Btn onClick={() => setDetail(null)}>Close</Btn>}>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            <div><p className="text-xs text-slate-400">Listings</p><p className="text-lg font-bold">{detail.listings_count}</p></div>
            <div><p className="text-xs text-slate-400">Proposals</p><p className="text-lg font-bold">{detail.proposals_count}</p></div>
            <div><p className="text-xs text-slate-400">Transactions</p><p className="text-lg font-bold">{detail.transactions_count}</p></div>
            <div><p className="text-xs text-slate-400">Avg rating</p><p className="text-lg font-bold">{detail.average_rating ?? "—"}</p></div>
            <div><p className="text-xs text-slate-400">Reviews</p><p className="text-lg font-bold">{detail.review_count}</p></div>
          </div>
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Recent activity</p>
          <table className="w-full">
            <thead><tr><Th>Action</Th><Th>Resource</Th><Th>When</Th></tr></thead>
            <tbody>
              {detail.recent_audit.length === 0 && <EmptyRow cols={3} text="No activity recorded." />}
              {detail.recent_audit.map((a) => (
                <tr key={a.id}>
                  <Td className="font-medium">{a.action}</Td>
                  <Td>{a.resource_type ?? "—"}</Td>
                  <Td>{new Date(a.created_at).toLocaleString()}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
    </div>
  );
}
