import { request, type Community, type FeedPost } from "./api";

export interface Institution extends Community {
  is_institution: boolean;
  website_url: string | null;
  verification_status: "unverified" | "pending" | "verified" | "rejected";
}
export interface PrivateSpaceRecord {
  community_id: string; reference: string; request_note: string | null;
  evidence_url: string | null; review_note: string | null;
  requested_at: string | null; reviewed_at: string | null;
}
export const institutions = {
  browse: (token: string | null, q = "", offset = 0) =>
    request<Institution[]>(`/api/v1/institutions?q=${encodeURIComponent(q)}&limit=24&offset=${offset}`, { token: token ?? undefined }),
  get: (token: string | null, id: string) => request<Institution>(`/api/v1/institutions/${id}`, { token: token ?? undefined }),
  create: (token: string, input: { name: string; description: string; topic: string; website_url: string | null }) =>
    request<Institution>("/api/v1/institutions", { method: "POST", token, body: JSON.stringify(input) }),
  update: (token: string, id: string, input: { name: string; description: string; topic: string; website_url: string | null }) =>
    request<Institution>(`/api/v1/institutions/${id}`, { method: "PATCH", token, body: JSON.stringify(input) }),
  private: (token: string, id: string) => request<PrivateSpaceRecord>(`/api/v1/spaces/${id}/private`, { token }),
  policy: () => request<{ institution_verification_enabled: boolean }>("/api/v1/institutions/policy"),
  verify: (token: string, id: string, note: string, evidence_url: string | null) =>
    request<PrivateSpaceRecord>(`/api/v1/institutions/${id}/verification`, { method: "POST", token, body: JSON.stringify({ note, evidence_url }) }),
  posts: (token: string | null, id: string, offset = 0) =>
    request<FeedPost[]>(`/api/v1/social/feed?community_id=${encodeURIComponent(id)}&sort=new&limit=20&offset=${offset}`, { token: token ?? undefined }),
};
