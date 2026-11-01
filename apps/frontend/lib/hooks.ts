"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import type { CommunityInput, MaterialInput, MaterialStatus } from "@/lib/api";

/** The current access token, or null. Queries below are disabled without it. */
export function useToken(): string | null {
  return useAuthStore((s) => s.accessToken);
}

// ── Query hooks ───────────────────────────────────────────────────────────────
// Each is disabled until a token exists, so they don't fire on the login screen.

export function useMe() {
  const token = useToken();
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.users.me(token!),
    enabled: !!token,
  });
}

export function useMyListings() {
  const token = useToken();
  return useQuery({
    queryKey: ["listings", "me"],
    queryFn: () => api.listings.myListings(token!),
    enabled: !!token,
  });
}

export function usePublicListings(limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["listings", "public", limit, offset],
    queryFn: () => api.listings.publicListings(limit, offset),
  });
}

export function useListing(id: string | undefined) {
  const token = useToken();
  return useQuery({
    queryKey: ["listing", id],
    queryFn: () => api.listings.get(token, id!),
    enabled: !!id,
  });
}

export function useProposals() {
  const token = useToken();
  return useQuery({
    queryKey: ["proposals"],
    queryFn: () => api.proposals.list(token!),
    enabled: !!token,
  });
}

export function useProposal(id: string | undefined) {
  const token = useToken();
  return useQuery({
    queryKey: ["proposal", id],
    queryFn: () => api.proposals.get(token!, id!),
    enabled: !!token && !!id,
  });
}

export function useTransactions() {
  const token = useToken();
  return useQuery({
    queryKey: ["transactions"],
    queryFn: () => api.transactions.list(token!),
    enabled: !!token,
  });
}

export function useTransaction(id: string | undefined) {
  const token = useToken();
  return useQuery({
    queryKey: ["transaction", id],
    queryFn: () => api.transactions.get(token!, id!),
    enabled: !!token && !!id,
  });
}

export function useMyMaterials() {
  const token = useToken();
  return useQuery({
    queryKey: ["materials", "me"],
    queryFn: () => api.materials.mine(token!),
    enabled: !!token,
  });
}

export function useBrowseMaterials(filters: {
  q?: string;
  category?: string;
  region?: string;
  country?: string;
} = {}) {
  const token = useToken();
  return useQuery({
    queryKey: ["materials", "browse", filters],
    queryFn: () => api.materials.browse(token!, filters),
    enabled: !!token,
  });
}

export function useMyCommunities() {
  const token = useToken();
  return useQuery({
    queryKey: ["communities", "me"],
    queryFn: () => api.communities.mine(token!),
    enabled: !!token,
  });
}

export function useBrowseCommunities(filters: { q?: string; topic?: string } = {}) {
  const token = useToken();
  return useQuery({
    queryKey: ["communities", "browse", filters],
    queryFn: () => api.communities.browse(token!, filters),
    enabled: !!token,
  });
}

export function useDemandOverview(days = 30) {
  const token = useToken();
  return useQuery({
    queryKey: ["demand", days],
    queryFn: () => api.demand.overview(token!, days),
    enabled: !!token,
  });
}

export function useAdminStats() {
  const token = useToken();
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => api.admin.stats(token!),
    enabled: !!token,
  });
}

// ── Mutation hooks ─────────────────────────────────────────────────────────────

export function useCreateMaterial() {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MaterialInput) => api.materials.create(token!, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["materials"] }),
  });
}

export function useUpdateMaterial(id: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<MaterialInput> & { status?: MaterialStatus }) =>
      api.materials.update(token!, id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["materials"] }),
  });
}

export function useCreateCommunity() {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CommunityInput) => api.communities.create(token!, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["communities"] }),
  });
}

export function useCreateListing() {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; product_category?: string; description?: string }) =>
      api.listings.create(token!, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["listings"] }),
  });
}
