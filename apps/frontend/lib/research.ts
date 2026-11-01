import { request } from "./api";
export interface ResearchCollection { id: string; name: string; description: string | null; created_at: string }
export interface CollectionItem { resource_id: string; resource_title: string | null; source_url: string | null; note: string | null; created_at: string }
export interface SavedSearch { id: string; label: string; query: string; resource_type: string; created_at: string }
export const research = {
  collections: (token: string, offset = 0) => request<ResearchCollection[]>(`/api/v1/research/collections?offset=${offset}`, { token }),
  create: (token: string, name: string, description: string | null) => request<ResearchCollection>("/api/v1/research/collections", { method: "POST", token, body: JSON.stringify({ name, description }) }),
  remove: (token: string, id: string) => request<void>(`/api/v1/research/collections/${id}`, { method: "DELETE", token }),
  items: (token: string, id: string, offset = 0) => request<CollectionItem[]>(`/api/v1/research/collections/${id}/items?offset=${offset}`, { token }),
  save: (token: string, collection: string, resource: string) => request<void>(`/api/v1/research/collections/${collection}/items/${resource}`, { method: "PUT", token, body: "{}" }),
  note: (token: string, collection: string, resource: string, note: string | null) => request<void>(`/api/v1/research/collections/${collection}/items/${resource}`, { method: "PUT", token, body: JSON.stringify({ note }) }),
  removeItem: (token: string, collection: string, resource: string) => request<void>(`/api/v1/research/collections/${collection}/items/${resource}`, { method: "DELETE", token }),
  searches: (token: string, offset = 0) => request<SavedSearch[]>(`/api/v1/research/searches?offset=${offset}`, { token }),
  saveSearch: (token: string, query: string, resource_type: string) => request<void>("/api/v1/research/searches", { method: "POST", token, body: JSON.stringify({ label: query.slice(0, 120), query, resource_type }) }),
  removeSearch: (token: string, id: string) => request<void>(`/api/v1/research/searches/${id}`, { method: "DELETE", token }),
};
