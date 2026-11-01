import { useAuthStore } from "@/store/auth";
// Hosted browsers reach the API through the same nginx/Cloudflare origin.
// A developer's .env.local must never bake localhost into the production app.
export const BASE_URL = process.env.NODE_ENV === "production"
  ? ""
  : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

export type ListingStatus = "draft" | "ai_generating" | "review" | "published" | "archived";

export interface BOMItem {
  id: string;
  material_name: string;
  specification: string | null;
  quantity_per_unit: string;
  unit_of_measure: string;
  shelf_life_days: number | null;
  procurement_cadence: string | null;
  is_critical: boolean;
  notes: string | null;
  created_at: string;
}

export interface VaultAsset {
  id: string;
  original_filename: string;
  file_size_bytes: number;
  content_type: string | null;
  created_at: string;
}

/** Teaser tier (T0) — what any caller, including anonymous ones, may see.
 *
 *  Mirrors PublicListingResponse. The confidential fields (private description,
 *  bill of materials, vault asset inventory) are deliberately absent: they were
 *  previously returned on the public browse endpoints, which handed over the
 *  manufacturing recipe for every listing to unauthenticated callers
 *  (security/AUDIT.md SAHA-003). */
export interface PublicListing {
  id: string;
  creator_id: string;
  title: string;
  product_category: string | null;
  tags: string[];
  public_description: string | null;
  status: ListingStatus;
  created_at: string;
}

/** Full tier (T2) — returned only to the listing's creator.
 *  Mirrors OwnerListingResponse. */
export interface Listing extends PublicListing {
  description: string | null;
  equipment_requirements: string[];
  batch_size_definition: string | null;
  view_count: number;
  bom_items: BOMItem[];
  vault_assets: VaultAsset[];
  updated_at: string;
}

export interface DialogueResponse {
  reply: string;
  messages: { role: string; content: string }[];
}

export interface FinalizeBOMResponse {
  bom_items: BOMItem[];
  listing: Listing;
}

export interface ParsedIntent {
  product_type: string | null;
  industry: string | null;
  keywords: string[];
  refined_query: string;
}

export interface SignatureStatus {
  contract_sha256: string | null;
  buyer_signed: boolean;
  seller_signed: boolean;
  fully_executed: boolean;
  signatures: { signer_id: string; signed_at: string }[];
}

/** Narrows a listing response to the owner tier.
 *
 *  `bom_items` is the discriminator because it is the field the API adds only
 *  for the creator — presence of it means the whole owner tier is present. */
export function isOwnerListing(l: PublicListing | Listing): l is Listing {
  return Array.isArray((l as Listing).bom_items);
}

export interface SearchResult {
  /** Teaser tier — search is reachable unauthenticated. */
  listing: PublicListing;
  score: number;
}

export interface SearchResponse {
  intent: ParsedIntent;
  results: SearchResult[];
  total: number;
  /** Open-library resources offered when listings are scarce ("build it yourself"). */
  open_resource_suggestions: OpenResource[];
}

export type ProposalStatus =
  | "draft" | "submitted" | "nda_pending" | "nda_signed"
  | "negotiating" | "accepted" | "rejected" | "withdrawn";

export interface ProposalVersion {
  id: string;
  version: number;
  offer_amount_usd: string | null;
  license_type: string | null;
  territory: string | null;
  duration_months: number | null;
  proposed_by_id: string;
  notes: string | null;
  created_at: string;
}

export interface ProposalMessage {
  id: string;
  sender_id: string;
  content: string;
  is_blocked: boolean;
  block_reason: string | null;
  created_at: string;
}

export interface LawFirm {
  id: string;
  name: string;
  jurisdictions: string[];
  contact_email: string | null;
}

export type TransactionStatus =
  | "pending_legal" | "contract_drafting" | "contract_review"
  | "signing_pending" | "signed" | "escrow_pending" | "escrow_funded"
  | "disbursement_pending" | "completed" | "disputed" | "cancelled";

export interface Disbursement {
  id: string;
  ip_holder_amount_usd: string;
  saha_commission_usd: string;
  legal_fee_usd: string;
  escrow_fee_usd: string;
  executed_at: string | null;
  created_at: string;
}

export interface Transaction {
  id: string;
  proposal_id: string;
  listing_id: string;
  buyer_id: string;
  seller_id: string;
  status: TransactionStatus;
  deal_value_usd: string;
  saha_commission_usd: string | null;
  legal_fee_usd: string | null;
  escrow_fee_usd: string | null;
  deal_summary: Record<string, string | number | null> | null;
  /** Digest of the contract bytes, so a client can verify what was signed.
   *  The storage key is no longer exposed — it leaked the internal object
   *  layout while serving no purpose (security/AUDIT.md SAHA-021). */
  contract_sha256: string | null;
  law_firm: LawFirm | null;
  disbursements: Disbursement[];
  escrow_funded_at: string | null;
  disbursed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContractDraftResponse {
  contract_text: string;
  transaction: Transaction;
}

export interface VaultAccessFile {
  asset_id: string;
  filename: string;
  file_size_bytes: number;
  content_type: string | null;
  download_path: string;
}

export interface Proposal {
  id: string;
  listing_id: string;
  buyer_id: string;
  seller_id: string;
  status: ProposalStatus;
  offer_amount_usd: string | null;
  license_type: string | null;
  territory: string | null;
  duration_months: number | null;
  nda_signed_at: string | null;
  version: number;
  versions: ProposalVersion[];
  created_at: string;
  updated_at: string;
}

export interface Review {
  id: string;
  transaction_id: string;
  reviewer_id: string;
  reviewee_id: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface Reputation {
  user_id: string;
  average_rating: number | null;
  review_count: number;
  reviews: Review[];
}

export type MaterialStatus = "active" | "paused" | "archived";

export interface Material {
  id: string;
  seller_id: string;
  title: string;
  description: string | null;
  category: string;
  region: string;
  country: string;
  unit: string;
  price_per_unit: string;
  currency: string;
  min_order_quantity: string | null;
  monthly_capacity: string | null;
  lead_time_days: number | null;
  status: MaterialStatus;
  created_at: string;
  updated_at: string;
  seller_name: string | null;
  seller_email: string | null;
}

export interface MaterialInput {
  title: string;
  description?: string;
  category: string;
  region: string;
  country: string;
  unit: string;
  price_per_unit: number;
  currency?: string;
  min_order_quantity?: number;
  monthly_capacity?: string;
  lead_time_days?: number;
}

// --- Social: communities ---
export type CommunityVisibility = "public" | "private";
export type MembershipRole = "owner" | "moderator" | "member";

export interface Community {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  topic: string;
  visibility: CommunityVisibility;
  created_by: string;
  created_at: string;
  updated_at: string;
  member_count: number;
  is_member: boolean;
  my_role: MembershipRole | null;
}

export interface CommunityInput {
  name: string;
  description?: string;
  topic: string;
  visibility?: CommunityVisibility;
}

export interface CommunityMember {
  user_id: string;
  full_name: string;
  email: string;
  role: MembershipRole;
  joined_at: string;
}

export interface CommunityMessage {
  id: string;
  community_id: string;
  sender_id: string;
  sender_name: string;
  content: string;
  created_at: string;
}

// --- Open Innovation Library ---
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

export interface OpenResourceSubmission {
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

export interface BuildStatus {
  resource_id: string;
  build_count: number;
  is_building: boolean;
}

export interface BuilderRow {
  user_id: string;
  full_name: string;
  note: string | null;
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

export interface AdminUserRow {
  id: string;
  email: string;
  full_name: string;
  role: string;
  kyc_status: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminTransactionRow {
  id: string;
  status: string;
  deal_value_usd: number;
  buyer_id: string;
  seller_id: string;
  created_at: string;
  updated_at: string;
}

export interface AuditLogRow {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  created_at: string;
}

export type UserRole = "creator" | "manufacturer" | "legal" | "admin";
export type KYCStatus = "pending" | "in_review" | "verified" | "rejected";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  kyc_status: KYCStatus;
  is_active: boolean;
  email_verified: boolean;
  mfa_enabled: boolean;
  has_avatar: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface KYCInitiateResponse {
  inquiry_id: string;
  session_token: string;
  mock: boolean;
  message: string;
}

export interface KYCCompleteResponse {
  kyc_status: KYCStatus;
  message: string;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

/** Absolute URL for the SSE notifications stream.
 *
 *  EventSource can't set headers, so the handshake credential has to travel in
 *  the URL — and anything in a URL is written to the reverse proxy's access log
 *  and the browser's history. It therefore must not be the access token, which
 *  is what this used to pass (security/AUDIT.md SAHA-017).
 *
 *  Call `api.auth.streamTicket()` first: it exchanges the bearer token for a
 *  60-second, stream-scoped ticket. A ticket recovered from a log has expired
 *  and grants nothing beyond this feed anyway. */
export function notificationsStreamUrl(ticket: string, after?: string | null): string {
  return `${BASE_URL}/api/v1/notifications/stream?ticket=${encodeURIComponent(ticket)}${after ? `&after=${encodeURIComponent(after)}` : ""}`;
}


// ── Social feed ─────────────────────────────────────────────────────────────

export type PostKind = "update" | "question" | "showcase";
export type PostVisibility = "public" | "members" | "community";

export interface AuthorSummary {
  user_id: string;
  full_name: string;
  headline: string | null;
  has_avatar: boolean;
  standing: number;
  tier: string;
}

export type ReportReason = "harmful" | "illegal" | "harassment" | "spam" | "confidential" | "other";
export type ModerationStatus = "published" | "flagged" | "held" | "approved" | "rejected" | "removed";

export interface SocialMedia {
  id: string; content_type: string; byte_size: number; alt_text: string; position: number; url: string;
}

export interface FeedPost {
  media?: SocialMedia[];
  reactions?: Record<string, number>;
  my_reaction?: string | null;
  is_following_author?: boolean;
  id: string;
  author: AuthorSummary;
  kind: PostKind;
  visibility: PostVisibility;
  community_id: string | null;
  title: string | null;
  body: string;
  link_url: string | null;
  listing_id: string | null;
  resource_id: string | null;
  score: number;
  up_count: number;
  down_count: number;
  comment_count: number;
  my_vote: number;
  is_saved: boolean;
  /** Only ever non-default on your OWN posts — held content is never sent to
   *  anyone else. Surfaced so a held post doesn't look like it vanished. */
  moderation_status: ModerationStatus;
  edited_at: string | null;
  created_at: string;
}

export interface PostComment {
  id: string;
  post_id: string;
  author: AuthorSummary;
  parent_id: string | null;
  body: string;
  score: number;
  confidence: number;
  my_vote: number;
  edited_at: string | null;
  created_at: string;
}

export interface DisclosureSignal { code: string; label: string; hint: string }
export interface DisclosureCheck {
  risk: "none" | "low" | "high";
  signals: DisclosureSignal[];
  warning: string | null;
}

/** Platform-derived. Nothing here can be self-reported. */
export interface VerifiedBlock {
  kyc_verified: boolean;
  member_since: string;
  completed_deals: number;
  average_rating: number | null;
  review_count: number;
  published_listings: number;
  library_contributions: number;
  communities: number;
}

/** Social standing. Deliberately never summed with the track record above. */
export interface StandingBlock {
  total_standing: number;
  post_standing: number;
  comment_standing: number;
  posts_count: number;
  comments_count: number;
  tier: string;
  next_tier: string | null;
  next_tier_at: number | null;
  can_downvote: boolean;
  can_create_community: boolean;
  can_flag: boolean;
}

export interface SelfAssertedBlock {
  headline: string | null;
  about: string | null;
  location: string | null;
  website_url: string | null;
  skills: string[];
  experience: { title: string; organization?: string; start?: string; end?: string; description?: string }[];
  featured: { kind: string; ref_id?: string; label: string; url?: string }[];
}

export interface MemberProfile {
  user_id: string;
  full_name: string;
  role: string;
  has_avatar: boolean;
  verified: VerifiedBlock;
  standing: StandingBlock;
  self_asserted: SelfAssertedBlock;
  recent_posts: FeedPost[];
  is_following: boolean;
  is_self: boolean;
}

class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map(item => item && typeof item === "object" && "msg" in item ? String(item.msg) : "Invalid input").join("; ")
      : detail && typeof detail === "object" && "message" in detail ? String(detail.message)
      : "Request failed");
  }
}

/** True when a JWT's exp claim is past (or within 30s of expiring). */
export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp !== "number" || !Number.isFinite(payload.exp) || payload.exp * 1000 <= Date.now() + 30_000;
  } catch {
    return true;
  }
}

async function tryRefresh(): Promise<string | null> {
  const { refreshSession } = await import("@/lib/session");
  return refreshSession();
}

export const refreshAccessToken = tryRefresh;

async function request<T>(
  path: string,
  options: RequestInit & { token?: string; stepUpToken?: string; responseType?: "blob"; sessionIndependent?: boolean } = {}
): Promise<T> {
  const { token: suppliedToken, stepUpToken, responseType, sessionIndependent, ...fetchOptions } = options;

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
    ...(typeof FormData !== "undefined" && fetchOptions.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(fetchOptions.headers as Record<string, string>),
  };

  if (token) headers["Authorization"] = `Bearer ${token}`;
  // Irreversible actions (escrow release, contract execution, vault egress)
  // require a freshly minted step-up token in addition to the access token, so
  // a stolen session alone cannot trigger them (security/AUDIT.md SAHA-015).
  if (stepUpToken) headers["X-Step-Up-Token"] = stepUpToken;

  const res = await fetch(`${BASE_URL}${path}`, { ...fetchOptions, headers });

  assertSession();
  if (res.status === 204) return undefined as T;

  // Auto-refresh on 401 then retry once
  if (res.status === 401 && token && !res.headers.get("X-Step-Up-Required")) {
    const active = useAuthStore.getState();
    const newToken = managed && active.revision === started.revision
      ? active.accessToken !== token ? active.accessToken : await tryRefresh()
      : null;
    assertSession();
    if (newToken) {
      const retryHeaders = { ...headers, Authorization: `Bearer ${newToken}` };
      const retry = await fetch(`${BASE_URL}${path}`, { ...fetchOptions, headers: retryHeaders });
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
    throw new ApiError(res.status, data.detail || "Request failed");
  }

  return data as T;
}

export const api = {
  auth: {
    register: (body: {
      email: string;
      password: string;
      full_name: string;
      role: UserRole;
    }) => request<User>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(body) }),

    // credentials:"include" lets the browser store the httpOnly refresh cookie.
    login: (body: { email: string; password: string; mfa_code?: string }) =>
      request<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        credentials: "include",
        body: JSON.stringify(body),
      }),

    /** Re-authenticate to obtain a short-lived token for a high-value action. */
    stepUp: (token: string, password: string, mfa_code?: string) =>
      request<{ step_up_token: string; expires_in_seconds: number }>("/api/v1/auth/step-up", {
        method: "POST", token,
        body: JSON.stringify(mfa_code ? { password, mfa_code } : { password }),
      }),

    /** Exchange the bearer token for a 60s ticket the EventSource can carry. */
    streamTicket: (token: string) =>
      request<{ ticket: string; expires_in_seconds: number }>("/api/v1/auth/stream-ticket", {
        method: "POST", token,
      }),

    refresh: (refresh_token?: string) =>
      request<TokenResponse>("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        body: JSON.stringify(refresh_token ? { refresh_token } : {}),
      }),

    logout: (token: string) =>
      request<void>("/api/v1/auth/logout", {
        method: "POST",
        token,
        credentials: "include",
        body: JSON.stringify({}),
      }),

    // MFA (TOTP)
    mfaStatus: (token: string) =>
      request<{ mfa_enabled: boolean }>("/api/v1/auth/mfa/status", { token }),
    mfaSetup: (token: string) =>
      request<{ secret: string; otpauth_uri: string }>("/api/v1/auth/mfa/setup", {
        method: "POST",
        token,
      }),
    mfaEnable: (token: string, code: string) =>
      request<{ mfa_enabled: boolean }>("/api/v1/auth/mfa/enable", {
        method: "POST",
        token,
        body: JSON.stringify({ code }),
      }),
    mfaDisable: (token: string, code: string) =>
      request<{ mfa_enabled: boolean }>("/api/v1/auth/mfa/disable", {
        method: "POST",
        token,
        body: JSON.stringify({ code }),
      }),

    // Email verification
    requestEmailVerification: (token: string) =>
      request<{ message: string }>("/api/v1/auth/verify-email/request", {
        method: "POST",
        token,
      }),
    confirmEmail: (verifyToken: string) =>
      request<{ message: string }>("/api/v1/auth/verify-email/confirm", {
        method: "POST",
        body: JSON.stringify({ token: verifyToken }),
      }),
  },

  users: {
    me: (token: string, sessionIndependent = false) => request<User>("/api/v1/users/me", { token, sessionIndependent }),

    updateProfile: (token: string, body: { full_name?: string; email?: string }) =>
      request<User>("/api/v1/users/me", { method: "PATCH", token, body: JSON.stringify(body) }),

    changePassword: (token: string, current_password: string, new_password: string) =>
      request<void>("/api/v1/users/me/password", {
        method: "POST", token, body: JSON.stringify({ current_password, new_password }),
      }),

    uploadAvatar: (token: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<User>("/api/v1/users/me/avatar", { method: "POST", token, body: form });
    },

    // Avatars are behind auth, so <img src> can't load them directly — fetch
    // with the token and hand back an object URL (caller revokes it).
    fetchAvatarUrl: async (token: string): Promise<string | null> => {
      try {
        return URL.createObjectURL(await request<Blob>("/api/v1/users/me/avatar", { token, responseType: "blob" }));
      } catch {
        return null;
      }
    },

    initiateKyc: (token: string) =>
      request<KYCInitiateResponse>("/api/v1/users/me/kyc/initiate", { method: "POST", token }),

    completeKycMock: (token: string) =>
      request<KYCCompleteResponse>("/api/v1/users/me/kyc/complete", { method: "POST", token }),
  },

  listings: {
    create: (token: string, body: { title: string; product_category?: string; description?: string }) =>
      request<Listing>("/api/v1/listings", { method: "POST", token, body: JSON.stringify(body) }),

    myListings: (token: string) => request<Listing[]>("/api/v1/listings/me", { token }),

    publicListings: (limit = 20, offset = 0) =>
      request<Listing[]>(`/api/v1/listings/public?limit=${limit}&offset=${offset}`),

    /** Returns the OWNER tier only when the caller owns the listing; everyone
     *  else — including authenticated non-owners — gets the teaser tier
     *  (security/AUDIT.md SAHA-003).
     *
     *  The union is deliberate. This previously claimed `Listing`, so the
     *  compiler happily allowed `listing.bom_items.length` on a response that
     *  no longer carries `bom_items`, and the public listing page threw at
     *  runtime. Narrow with `isOwnerListing()` before touching owner fields. */
    get: (token: string | null, id: string) =>
      request<PublicListing | Listing>(`/api/v1/listings/${id}`, token ? { token } : {}),

    startDialogue: (token: string, listingId: string) =>
      request<DialogueResponse>(`/api/v1/listings/${listingId}/dialogue/start`, { method: "POST", token }),

    sendDialogue: (token: string, listingId: string, message: string) =>
      request<DialogueResponse>(`/api/v1/listings/${listingId}/dialogue`, {
        method: "POST",
        token,
        body: JSON.stringify({ message }),
      }),

    getDialogue: (token: string, listingId: string) =>
      request<{ role: string; content: string }[]>(`/api/v1/listings/${listingId}/dialogue`, { token }),

    finalizeBOM: (token: string, listingId: string) =>
      request<FinalizeBOMResponse>(`/api/v1/listings/${listingId}/finalize-bom`, { method: "POST", token }),

    uploadFile: (token: string, listingId: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<VaultAsset>(`/api/v1/listings/${listingId}/files`, { method: "POST", token, body: form });
    },

    publish: (token: string, listingId: string, public_description?: string) =>
      request<Listing>(`/api/v1/listings/${listingId}/publish`, {
        method: "POST",
        token,
        body: JSON.stringify({ public_description }),
      }),
  },

  materials: {
    create: (token: string, body: MaterialInput) =>
      request<Material>("/api/v1/materials", { method: "POST", token, body: JSON.stringify(body) }),

    mine: (token: string) => request<Material[]>("/api/v1/materials/me", { token }),

    browse: (token: string, filters: { q?: string; category?: string; region?: string; country?: string; limit?: number; offset?: number } = {}) => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== "") params.set(k, String(v));
      });
      const qs = params.toString();
      return request<Material[]>(`/api/v1/materials${qs ? `?${qs}` : ""}`, { token });
    },

    get: (token: string, id: string) => request<Material>(`/api/v1/materials/${id}`, { token }),

    update: (token: string, id: string, body: Partial<MaterialInput> & { status?: MaterialStatus }) =>
      request<Material>(`/api/v1/materials/${id}`, { method: "PATCH", token, body: JSON.stringify(body) }),

    archive: (token: string, id: string) =>
      request<Material>(`/api/v1/materials/${id}`, { method: "DELETE", token }),
  },

  communities: {
    create: (token: string, body: CommunityInput) =>
      request<Community>("/api/v1/communities", { method: "POST", token, body: JSON.stringify(body) }),

    mine: (token: string) => request<Community[]>("/api/v1/communities/me", { token }),

    browse: (token: string, filters: { q?: string; topic?: string; limit?: number; offset?: number } = {}) => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== "") params.set(k, String(v));
      });
      const qs = params.toString();
      return request<Community[]>(`/api/v1/communities${qs ? `?${qs}` : ""}`, { token });
    },

    get: (token: string, id: string) => request<Community>(`/api/v1/communities/${id}`, { token }),

    update: (token: string, id: string, body: Partial<CommunityInput>) =>
      request<Community>(`/api/v1/communities/${id}`, { method: "PATCH", token, body: JSON.stringify(body) }),

    join: (token: string, id: string) =>
      request<Community>(`/api/v1/communities/${id}/join`, { method: "POST", token }),

    leave: (token: string, id: string) =>
      request<void>(`/api/v1/communities/${id}/leave`, { method: "POST", token }),

    members: (token: string, id: string) =>
      request<CommunityMember[]>(`/api/v1/communities/${id}/members`, { token }),

    addMember: (token: string, id: string, email: string) =>
      request<CommunityMember>(`/api/v1/communities/${id}/members`, {
        method: "POST", token, body: JSON.stringify({ email }),
      }),

    removeMember: (token: string, id: string, userId: string) =>
      request<void>(`/api/v1/communities/${id}/members/${userId}`, { method: "DELETE", token }),

    messages: (token: string, id: string, limit = 100) =>
      request<CommunityMessage[]>(`/api/v1/communities/${id}/messages?limit=${limit}`, { token }),

    postMessage: (token: string, id: string, content: string) =>
      request<CommunityMessage>(`/api/v1/communities/${id}/messages`, {
        method: "POST", token, body: JSON.stringify({ content }),
      }),
  },

  search: {
    query: (query: string, limit = 10, token?: string) =>
      request<SearchResponse>("/api/v1/search", {
        method: "POST",
        token,
        body: JSON.stringify({ query, limit }),
      }),
  },

  proposals: {
    create: (token: string, listing_id: string) =>
      request<Proposal>("/api/v1/proposals", {
        method: "POST", token, body: JSON.stringify({ listing_id }),
      }),

    list: (token: string) => request<Proposal[]>("/api/v1/proposals", { token }),

    get: (token: string, id: string) => request<Proposal>(`/api/v1/proposals/${id}`, { token }),

    submit: (token: string, id: string, body: {
      offer_amount_usd: number; license_type: string; territory: string; duration_months: number; notes?: string;
    }) => request<Proposal>(`/api/v1/proposals/${id}/submit`, { method: "POST", token, body: JSON.stringify(body) }),

    counter: (token: string, id: string, body: {
      offer_amount_usd: number; license_type: string; territory: string; duration_months: number; notes?: string;
    }) => request<Proposal>(`/api/v1/proposals/${id}/counter`, { method: "POST", token, body: JSON.stringify(body) }),

    accept: (token: string, id: string) =>
      request<Proposal>(`/api/v1/proposals/${id}/accept`, { method: "POST", token }),

    reject: (token: string, id: string) =>
      request<Proposal>(`/api/v1/proposals/${id}/reject`, { method: "POST", token }),

    withdraw: (token: string, id: string) =>
      request<Proposal>(`/api/v1/proposals/${id}/withdraw`, { method: "POST", token }),

    sendMessage: (token: string, id: string, content: string) =>
      request<ProposalMessage>(`/api/v1/proposals/${id}/messages`, {
        method: "POST", token, body: JSON.stringify({ content }),
      }),

    listMessages: (token: string, id: string) =>
      request<ProposalMessage[]>(`/api/v1/proposals/${id}/messages`, { token }),
  },

  social: {
    feed: (
      token: string | null,
      params: { sort?: string; kind?: PostKind; following_only?: boolean; limit?: number; offset?: number; q?: string } = {}
    ) => {
      const q = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)));
      return request<FeedPost[]>(`/api/v1/social/feed?${q}`, token ? { token } : {});
    },

    post: (token: string, id: string) => request<FeedPost>(`/api/v1/social/posts/${id}`, { token }),

    /** Advisory novelty-risk check. Runs server-side in-process — the draft
     *  never leaves the trust boundary. */
    checkDisclosure: (token: string, body: string, title: string | null, visibility: PostVisibility) =>
      request<DisclosureCheck>("/api/v1/social/disclosure-check", {
        method: "POST", token,
        body: JSON.stringify({ body, title, visibility }),
      }),

    create: (token: string, input: {
      body: string; title?: string | null; kind?: PostKind; visibility?: PostVisibility;
      community_id?: string | null; link_url?: string | null; listing_id?: string | null;
      acknowledged_disclosure?: boolean; media_ids?: string[];
    }) =>
      request<FeedPost>("/api/v1/social", { method: "POST", token, body: JSON.stringify(input) }),

    edit: (token: string, id: string, body: string, title?: string | null, acknowledged_disclosure = false) =>
      request<FeedPost>(`/api/v1/social/posts/${id}`, {
        method: "PATCH", token, body: JSON.stringify({ body, title, acknowledged_disclosure }),
      }),

    remove: (token: string, id: string) =>
      request<void>(`/api/v1/social/posts/${id}`, { method: "DELETE", token }),

    vote: (token: string, id: string, value: number) =>
      request<{ score: number; up_count: number; down_count: number; my_vote: number }>(
        `/api/v1/social/posts/${id}/vote`, { method: "POST", token, body: JSON.stringify({ value }) }),

    report: (token: string, id: string, reason: ReportReason, detail?: string) =>
      request<{ reported: boolean; already: boolean; held: boolean }>(
        `/api/v1/social/posts/${id}/report`, {
          method: "POST", token, body: JSON.stringify({ reason, detail: detail ?? null }),
        }),

    save: (token: string, id: string) =>
      request<{ saved: boolean }>(`/api/v1/social/posts/${id}/save`, { method: "POST", token }),

    saved: (token: string, offset = 0, limit = 20) => request<FeedPost[]>(`/api/v1/social/saved?offset=${offset}&limit=${limit}`, { token }),

    comments: (token: string | null, postId: string, sort = "best") =>
      request<PostComment[]>(`/api/v1/social/posts/${postId}/comments?sort=${sort}`,
        token ? { token } : {}),

    comment: (token: string, postId: string, body: string, parent_id?: string | null) =>
      request<PostComment>(`/api/v1/social/posts/${postId}/comments`, {
        method: "POST", token, body: JSON.stringify({ body, parent_id: parent_id ?? null }),
      }),

    voteComment: (token: string, id: string, value: number) =>
      request<{ score: number; up_count: number; down_count: number; my_vote: number }>(
        `/api/v1/social/comments/${id}/vote`, { method: "POST", token, body: JSON.stringify({ value }) }),

    deleteComment: (token: string, id: string) =>
      request<void>(`/api/v1/social/comments/${id}`, { method: "DELETE", token }),

    profile: (token: string, userId: string) =>
      request<MemberProfile>(`/api/v1/social/profiles/${userId}`, { token }),

    updateProfile: (token: string, changes: Partial<SelfAssertedBlock>) =>
      request<MemberProfile>("/api/v1/social/profiles/me", {
        method: "PATCH", token, body: JSON.stringify(changes),
      }),

    follow: (token: string, userId: string) =>
      request<{ following: boolean }>(`/api/v1/social/members/${userId}/follow`, { method: "POST", token }),

    unfollow: (token: string, userId: string) =>
      request<void>(`/api/v1/social/members/${userId}/follow`, { method: "DELETE", token }),
  },

  transactions: {
    list: (token: string) => request<Transaction[]>("/api/v1/transactions", { token }),

    get: (token: string, id: string) => request<Transaction>(`/api/v1/transactions/${id}`, { token }),

    lawFirms: (token: string) => request<LawFirm[]>("/api/v1/transactions/law-firms", { token }),

    assignLawFirm: (token: string, id: string, law_firm_id: string) =>
      request<Transaction>(`/api/v1/transactions/${id}/assign-law-firm`, {
        method: "POST", token, body: JSON.stringify({ law_firm_id }),
      }),

    draftContract: (token: string, id: string) =>
      request<ContractDraftResponse>(`/api/v1/transactions/${id}/draft-contract`, { method: "POST", token }),

    /** Records THIS party's signature. The transaction executes only once both
     *  parties have signed the same contract bytes (security/AUDIT.md SAHA-008). */
    sign: (token: string, id: string, stepUpToken: string) =>
      request<Transaction>(`/api/v1/transactions/${id}/sign`, { method: "POST", token, stepUpToken }),

    signatures: (token: string, id: string) =>
      request<SignatureStatus>(`/api/v1/transactions/${id}/signatures`, { token }),

    contract: (token: string, id: string) =>
      request<ContractDraftResponse>(`/api/v1/transactions/${id}/contract`, { token }),

    updateStatus: (token: string, id: string, new_status: TransactionStatus) =>
      request<Transaction>(`/api/v1/transactions/${id}/status?new_status=${new_status}`, { method: "POST", token }),

    // --- Settlement (Sprint 7) ---
    createEscrow: (token: string, id: string) =>
      request<Transaction>(`/api/v1/transactions/${id}/escrow/create`, { method: "POST", token }),

    confirmEscrow: (token: string, id: string) =>
      request<Transaction>(`/api/v1/transactions/${id}/escrow/confirm`, { method: "POST", token }),

    /** Release escrow to the seller. Buyer-only — this is the payer's decision
     *  about the payer's money (security/AUDIT.md SAHA-007). */
    disburse: (token: string, id: string, stepUpToken: string, reason?: string) =>
      request<Transaction>(`/api/v1/transactions/${id}/disburse`, {
        method: "POST", token, stepUpToken,
        body: JSON.stringify(reason ? { reason } : {}),
      }),

    vaultAccess: (token: string, id: string) =>
      request<VaultAccessFile[]>(`/api/v1/transactions/${id}/vault-access`, { token }),

    // Downloads the decrypted vault file via the authenticated endpoint and
    // triggers a browser save. Files are encrypted at rest, so a plain link
    // to storage would serve unreadable bytes.
    downloadVaultFile: async (token: string, file: VaultAccessFile, stepUpToken: string) => {
      if (!file.download_path.startsWith("/api/v1/transactions/")) throw new ApiError(400, "Invalid vault download path");
      const blob = await request<Blob>(file.download_path, { token, stepUpToken, responseType: "blob", cache: "no-store" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },

    // --- Reviews (Sprint 8) ---
    listReviews: (token: string, id: string) =>
      request<Review[]>(`/api/v1/transactions/${id}/reviews`, { token }),

    createReview: (token: string, id: string, body: { rating: number; comment?: string }) =>
      request<Review>(`/api/v1/transactions/${id}/reviews`, {
        method: "POST", token, body: JSON.stringify(body),
      }),
  },

  reviews: {
    reputation: (token: string, userId: string) =>
      request<Reputation>(`/api/v1/users/${userId}/reputation`, { token }),
  },

  demand: {
    overview: (token: string, days = 30) =>
      request<DemandOverview>(`/api/v1/demand/overview?days=${days}`, { token }),
  },

  openResources: {
    browse: (token: string, filters: { q?: string; resource_type?: string; category?: string; tag?: string; limit?: number; offset?: number } = {}) => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== "") params.set(k, String(v));
      });
      const qs = params.toString();
      return request<OpenResource[]>(`/api/v1/open-resources${qs ? `?${qs}` : ""}`, { token });
    },

    get: (token: string, id: string) =>
      request<OpenResource>(`/api/v1/open-resources/${id}`, { token }),

    submit: (token: string, body: OpenResourceSubmission) =>
      request<OpenResource>("/api/v1/open-resources/submissions", {
        method: "POST", token, body: JSON.stringify(body),
      }),

    declareBuild: (token: string, id: string, note?: string) =>
      request<BuildStatus>(`/api/v1/open-resources/${id}/build`, {
        method: "POST", token, body: JSON.stringify(note ? { note } : {}),
      }),

    withdrawBuild: (token: string, id: string) =>
      request<BuildStatus>(`/api/v1/open-resources/${id}/build`, { method: "DELETE", token }),

    builders: (token: string, id: string) =>
      request<BuilderRow[]>(`/api/v1/open-resources/${id}/builders`, { token }),
  },

  notifications: {
    list: (token: string, limit = 30) =>
      request<Notification[]>(`/api/v1/notifications?limit=${limit}`, { token }),
    unreadCount: (token: string) =>
      request<{ unread: number }>("/api/v1/notifications/unread-count", { token }),
    markRead: (token: string, id: string) =>
      request<void>(`/api/v1/notifications/${id}/read`, { method: "POST", token }),
    markAllRead: (token: string) =>
      request<void>("/api/v1/notifications/read-all", { method: "POST", token }),
  },

  admin: {
    stats: (token: string) => request<PlatformStats>("/api/v1/admin/stats", { token }),

    users: (token: string, limit = 50, offset = 0) =>
      request<AdminUserRow[]>(`/api/v1/admin/users?limit=${limit}&offset=${offset}`, { token }),

    transactions: (token: string, limit = 50, offset = 0) =>
      request<AdminTransactionRow[]>(`/api/v1/admin/transactions?limit=${limit}&offset=${offset}`, { token }),

    auditLogs: (token: string, limit = 50, offset = 0) =>
      request<AuditLogRow[]>(`/api/v1/admin/audit-logs?limit=${limit}&offset=${offset}`, { token }),

    setUserActive: (token: string, userId: string, is_active: boolean) =>
      request<AdminUserRow>(`/api/v1/admin/users/${userId}/active`, {
        method: "POST", token, body: JSON.stringify({ is_active }),
      }),
  },
};

export { ApiError, request };
