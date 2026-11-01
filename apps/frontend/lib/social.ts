import { request, type SocialMedia } from "@/lib/api";

export interface MentionMember { user_id: string; full_name: string; headline: string | null; has_avatar: boolean }
export const REACTIONS = [
  { key: "like", label: "Like", symbol: "👍" },
  { key: "celebrate", label: "Celebrate", symbol: "👏" },
  { key: "support", label: "Support", symbol: "🤝" },
  { key: "love", label: "Love", symbol: "💚" },
  { key: "insightful", label: "Insightful", symbol: "💡" },
  { key: "curious", label: "Curious", symbol: "🤔" },
] as const;

export const social = {
  members: (token: string, q: string) => request<MentionMember[]>(`/api/v1/social/members/search?q=${encodeURIComponent(q)}`, { token }),
  upload: (token: string, file: File, alt: string) => { const body = new FormData(); body.set("file", file); body.set("alt_text", alt); return request<SocialMedia>("/api/v1/social/media", { method: "POST", token, body }); },
  removeDraft: (token: string, id: string) => request<void>(`/api/v1/social/media/${id}`, { method: "DELETE", token }),
  react: (token: string, postId: string, kind: string | null) => request<{ reactions: Record<string, number>; my_reaction: string | null }>(`/api/v1/social/posts/${postId}/reaction`, { method: "PUT", token, body: JSON.stringify({ kind }) }),
};

/** No bearer tokens in media URLs. Blob callers revoke their object URL on cleanup. */
export async function socialBlob(path: string, token: string | null, signal: AbortSignal): Promise<Blob> {
  return request<Blob>(path, { token: token ?? undefined, signal, responseType: "blob", cache: "no-store" });
}
