import { useAuthStore } from "@/store/auth";
// Production admin traffic follows the private nginx origin on port 8080.
const BASE_URL = process.env.NODE_ENV === "production"
  ? ""
  : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

// ── Types (mirror app/api/schemas/admin.py) ─────────────────────────────────

export type UserRole = "creator" | "manufacturer" | "legal" | "admin";
export type KYCStatus = "pending" | "in_review" | "verified" | "rejected";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  kyc_status: KYCStatus;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface PlatformStats {
  users_total: number;
  users_by_role: Record<string, number>;
  listings_total: number;
  listings_by_status: Record<string, number>;
  proposals_total: number;
  proposals_by_status: Record<string, number>;
  transactions_total: number;
  transactions_by_status: Record<string, number>;
  reviews_total: number;
  total_disbursed_usd: number;
  total_commission_usd: number;
  pipeline_value_usd: number;
}

export interface AuditLogRow {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  created_at: string;
}

export interface UserDetail {
  user: User;
  listings_count: number;
  proposals_count: number;
  transactions_count: number;
  average_rating: number | null;
  review_count: number;
  recent_audit: AuditLogRow[];
}

export interface ListingRow {
  id: string;
  title: string;
  status: string;
  product_category: string | null;
  view_count: number;
  creator_id: string;
  creator_email: string;
  created_at: string;
  updated_at: string;
}

export interface ProposalRow {
  id: string;
  listing_id: string;
  listing_title: string;
  buyer_id: string;
  seller_id: string;
  status: string;
  offer_amount_usd: number | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TransactionRow {
  id: string;
  status: string;
  deal_value_usd: number;
  saha_commission_usd: number | null;
  buyer_id: string;
  seller_id: string;
  listing_id: string | null;
  escrow_funded_at: string | null;
  disbursed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewRow {
  id: string;
  transaction_id: string;
  reviewer_id: string;
  reviewee_id: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface LawFirm {
  id: string;
  name: string;
  jurisdictions: string[];
  contact_email: string | null;
  is_active: boolean;
  created_at: string;
}

export interface DisbursementRow {
  id: string;
  transaction_id: string;
  ip_holder_amount_usd: string;
  saha_commission_usd: string;
  legal_fee_usd: string;
  escrow_fee_usd: string;
  executed_at: string | null;
  created_at: string;
}

export interface QueryStat { query: string; count: number; avg_results: number; }
export interface GapStat { query: string; count: number; }
export interface LabelStat { label: string; count: number; }

export interface DemandOverview {
  window_days: number;
  total_searches: number;
  unique_searchers: number;
  unmet_searches: number;
  top_queries: QueryStat[];
  demand_gaps: GapStat[];
  top_industries: LabelStat[];
  top_product_types: LabelStat[];
}

export type OpenResourceType = "patent" | "research_paper" | "trademark";
export type OpenResourceStatus = "pending" | "approved" | "rejected";

export interface OpenResource {
  rights_evidence_url?: string | null;
  rights_note?: string | null;
  jurisdiction?: string | null;
  id: string;
  resource_type: OpenResourceType;
  title: string;
  summary: string | null;
  authors: string | null;
  organization: string | null;
  identifier: string | null;
  source_url: string;
  license: string;
  category: string | null;
  tags: string[];
  published_year: number | null;
  status: OpenResourceStatus;
  is_active: boolean;
  view_count: number;
  build_count: number;
  is_building: boolean;
  created_at: string;
  updated_at: string;
}

export interface OpenResourceInput {
  rights_evidence_url?: string | null;
  rights_note?: string | null;
  jurisdiction?: string | null;
  resource_type: OpenResourceType;
  title: string;
  summary?: string | null;
  authors?: string | null;
  organization?: string | null;
  identifier?: string | null;
  source_url: string;
  license: string;
  category?: string | null;
  tags?: string[];
  published_year?: number | null;
}

// Mirror OPEN_LICENSES / COMMUNITY_TOPICS in the backend schemas.
export const OPEN_LICENSES = [
  "public_domain", "cc0", "cc_by", "cc_by_sa", "mit", "apache_2_0",
  "gpl_3_0", "open_patent_pledge", "defensive_publication",
] as const;

export const RESOURCE_CATEGORIES = [
  "biotech_pharma", "clean_energy", "materials_science", "software_ai",
  "hardware_electronics", "consumer_products", "agritech_food",
  "medical_devices", "industrial_manufacturing", "general",
] as const;

export interface ReviewMedia { id: string; content_type: string; byte_size: number; alt_text: string; url: string }

export interface ModerationRow {
  media: ReviewMedia[];
  id: string;
  author_id: string;
  author_name: string;
  title: string | null;
  body: string;
  visibility: "public" | "members" | "community";
  moderation_status: "published" | "flagged" | "held" | "approved" | "rejected" | "removed";
  safety_categories: string[];
  safety_reason: string | null;
  report_count: number;
  held_at: string | null;
  created_at: string;
}

export interface HealthReport {
  status: string;
  checks: Record<string, string | { active: string; status: string; model: string }>;
}

// ── Client ──────────────────────────────────────────────────────────────────

class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map(item => item && typeof item === "object" && "msg" in item ? String(item.msg) : "Invalid input").join("; ")
      : detail && typeof detail === "object" && "message" in detail ? String(detail.message)
      : "Request failed");
  }
}

async function tryRefresh(): Promise<string | null> {
  const { refreshSession } = await import("@/lib/session");
  return refreshSession();
}

export const refreshAccessToken = tryRefresh;

async function request<T>(
  path: string,
  options: RequestInit & { token?: string; responseType?: "blob"; sessionIndependent?: boolean } = {}
): Promise<T> {
  const { token: suppliedToken, responseType, sessionIndependent, ...fetchOptions } = options;
  if (!path.startsWith("/") || path.startsWith("//") || /[\\\u0000-\u0020]/.test(path))
    throw new ApiError(400, "API requests must use a local application path.");
  const started = useAuthStore.getState();
  let token = suppliedToken;
  const managed = !!token && !sessionIndependent;
  if (managed && token !== started.accessToken) {
    // An earlier closure may hold a token rotated for the same account. Bind the
    // operation to that identity before using the newer credential.
    let subject: unknown;
    try { subject = JSON.parse(atob(token!.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).sub; } catch { /* invalid token */ }
    if (!started.user || !started.accessToken || subject !== started.user.id)
      throw new ApiError(409, "Your session changed. Please try again.");
    token = started.accessToken;
  }
  const assertSession = () => {
    if (managed && useAuthStore.getState().revision !== started.revision)
      throw new ApiError(409, "Your session changed. Please try again.");
  };
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...fetchOptions, headers });
  assertSession();
  if (res.status === 204) return undefined as T;

  if (res.status === 401 && token && !res.headers.get("X-Step-Up-Required")) {
    const active = useAuthStore.getState();
    const newToken = managed && active.revision === started.revision
      ? active.accessToken !== token ? active.accessToken : await tryRefresh()
      : null;
    assertSession();
    if (newToken) {
      const retry = await fetch(`${BASE_URL}${path}`, {
        ...fetchOptions,
        headers: { ...headers, Authorization: `Bearer ${newToken}` },
      });
      assertSession();
      if (retry.status === 204) return undefined as T;
      if (retry.ok && responseType === "blob") {
        const blob = await retry.blob(); assertSession(); return blob as T;
      }
      const retryData = await retry.json().catch(() => ({ detail: "Request failed" }));
      assertSession();
      if (retry.status === 401 && managed && !retry.headers.get("X-Step-Up-Required")) useAuthStore.getState().clearAuth();
      if (!retry.ok) throw new ApiError(retry.status, retryData.detail || "Request failed");
      return retryData as T;
    }
  }

  if (res.ok && responseType === "blob") {
    const blob = await res.blob(); assertSession(); return blob as T;
  }
  const data = await res.json().catch(() => ({ detail: "Request failed" }));
  assertSession();
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    throw new ApiError(res.status, detail || "Request failed");
  }
  return data as T;
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export const api = {
  auth: {
    // credentials:"include" lets the browser store and return the httpOnly
    // refresh cookie, which is where the long-lived token lives.
    login: (email: string, password: string, mfa_code?: string) =>
      request<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        credentials: "include",
        body: JSON.stringify(mfa_code ? { email, password, mfa_code } : { email, password }),
      }),
    logout: (token: string, refresh_token?: string) =>
      request<void>("/api/v1/auth/logout", {
        method: "POST", token, credentials: "include",
        body: JSON.stringify(refresh_token ? { refresh_token } : {}),
      }),
    stepUp: (token: string, password: string, mfa_code?: string) =>
      request<{ step_up_token: string; expires_in_seconds: number }>("/api/v1/auth/step-up", {
        method: "POST", token,
        body: JSON.stringify(mfa_code ? { password, mfa_code } : { password }),
      }),
    me: (token: string, sessionIndependent = false) => request<User>("/api/v1/users/me", { token, sessionIndependent }),
  },

  stats: (token: string) => request<PlatformStats>("/api/v1/admin/stats", { token }),

  demand: (token: string, days = 30) =>
    request<DemandOverview>(`/api/v1/admin/demand?days=${days}`, { token }),

  users: {
    list: (token: string, p: { limit?: number; offset?: number; search?: string; role?: string; kyc_status?: string; is_active?: boolean } = {}) =>
      request<User[]>(`/api/v1/admin/users${qs(p)}`, { token }),
    detail: (token: string, id: string) =>
      request<UserDetail>(`/api/v1/admin/users/${id}`, { token }),
    setActive: (token: string, id: string, is_active: boolean) =>
      request<User>(`/api/v1/admin/users/${id}/active`, {
        method: "POST", token, body: JSON.stringify({ is_active }),
      }),
    setRole: (token: string, id: string, role: UserRole) =>
      request<User>(`/api/v1/admin/users/${id}/role`, {
        method: "POST", token, body: JSON.stringify({ role }),
      }),
    setKyc: (token: string, id: string, kyc_status: KYCStatus, reason: string) =>
      request<User>(`/api/v1/admin/users/${id}/kyc`, {
        method: "POST", token, body: JSON.stringify({ kyc_status, reason }),
      }),
  },

  listings: {
    list: (token: string, p: { limit?: number; offset?: number; status?: string; search?: string } = {}) =>
      request<ListingRow[]>(`/api/v1/admin/listings${qs(p)}`, { token }),
    archive: (token: string, id: string) =>
      request<ListingRow>(`/api/v1/admin/listings/${id}/archive`, { method: "POST", token }),
    restore: (token: string, id: string) =>
      request<ListingRow>(`/api/v1/admin/listings/${id}/restore`, { method: "POST", token }),
  },

  proposals: {
    list: (token: string, p: { limit?: number; offset?: number; status?: string } = {}) =>
      request<ProposalRow[]>(`/api/v1/admin/proposals${qs(p)}`, { token }),
  },

  transactions: {
    list: (token: string, p: { limit?: number; offset?: number; status?: string } = {}) =>
      request<TransactionRow[]>(`/api/v1/admin/transactions${qs(p)}`, { token }),
    dispute: (token: string, id: string) =>
      request<TransactionRow>(`/api/v1/admin/transactions/${id}/dispute`, { method: "POST", token }),
    resolve: (token: string, id: string, resolution: "complete" | "cancel", reason: string) =>
      request<TransactionRow>(`/api/v1/admin/transactions/${id}/resolve`, {
        method: "POST", token, body: JSON.stringify({ resolution, reason }),
      }),
  },

  reviews: {
    list: (token: string, p: { limit?: number; offset?: number } = {}) =>
      request<ReviewRow[]>(`/api/v1/admin/reviews${qs(p)}`, { token }),
    remove: (token: string, id: string) =>
      request<void>(`/api/v1/admin/reviews/${id}`, { method: "DELETE", token }),
  },

  lawFirms: {
    list: (token: string) => request<LawFirm[]>("/api/v1/admin/law-firms", { token }),
    create: (token: string, body: { name: string; jurisdictions: string[]; contact_email?: string | null }) =>
      request<LawFirm>("/api/v1/admin/law-firms", {
        method: "POST", token, body: JSON.stringify(body),
      }),
    update: (token: string, id: string, body: Partial<{ name: string; jurisdictions: string[]; contact_email: string | null; is_active: boolean }>) =>
      request<LawFirm>(`/api/v1/admin/law-firms/${id}`, {
        method: "PATCH", token, body: JSON.stringify(body),
      }),
  },

  resources: {
    list: (token: string, p: { limit?: number; offset?: number; q?: string; resource_type?: string; status?: string } = {}) =>
      request<OpenResource[]>(`/api/v1/admin/open-resources${qs(p)}`, { token }),
    create: (token: string, body: OpenResourceInput) =>
      request<OpenResource>("/api/v1/admin/open-resources", {
        method: "POST", token, body: JSON.stringify(body),
      }),
    update: (token: string, id: string, body: Partial<OpenResourceInput> & { is_active?: boolean }) =>
      request<OpenResource>(`/api/v1/admin/open-resources/${id}`, {
        method: "PATCH", token, body: JSON.stringify(body),
      }),
    approve: (token: string, id: string) =>
      request<OpenResource>(`/api/v1/admin/open-resources/${id}/approve`, { method: "POST", token }),
    reject: (token: string, id: string, reason?: string) =>
      request<OpenResource>(`/api/v1/admin/open-resources/${id}/reject`, {
        method: "POST", token, body: JSON.stringify(reason ? { reason } : {}),
      }),
  },

  disbursements: {
    list: (token: string, p: { limit?: number; offset?: number } = {}) =>
      request<DisbursementRow[]>(`/api/v1/admin/disbursements${qs(p)}`, { token }),
  },

  auditLogs: {
    list: (token: string, p: { limit?: number; offset?: number; action?: string; user_id?: string } = {}) =>
      request<AuditLogRow[]>(`/api/v1/admin/audit-logs${qs(p)}`, { token }),
  },

  // /health is admin-gated now: it enumerates every backend component,
  // which is a map of the internal architecture (security/AUDIT.md SAHA-019).
  health: (token: string) => request<HealthReport>("/health", { token }),

  // ── Content moderation ────────────────────────────────────────────────────
  // Held posts are invisible to members until approved here. The classifier can
  // take content down; only this path puts it back up.
  moderationQueue: (token: string, status?: string) =>
    request<ModerationRow[]>(
      `/api/v1/social/moderation/queue${status ? `?status=${status}` : ""}`, { token }),

  reviewPost: (token: string, postId: string, approve: boolean, note?: string) =>
    request<ModerationRow>(`/api/v1/social/moderation/posts/${postId}/review`, {
      method: "POST", token, body: JSON.stringify({ approve, note: note ?? null }),
    }),
};

export { ApiError, BASE_URL, request };


export async function reviewMediaBlob(path: string, token: string, signal: AbortSignal): Promise<Blob> {
  return request<Blob>(path, { token, signal, responseType: "blob", cache: "no-store" });
}
