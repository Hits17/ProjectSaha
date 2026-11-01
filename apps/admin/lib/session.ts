"use client";
import { BASE_URL } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { createSessionController } from "./session-controller";
import type { User } from "@/lib/api";

const controller = createSessionController<User>({
  snapshot: () => useAuthStore.getState(), base: BASE_URL,
  fetch: (...args) => fetch(...args),
  accept: (user, tokens) => useAuthStore.getState().setAuth(user, tokens.access_token, tokens.refresh_token),
  profile: user => useAuthStore.getState().setUser(user),
  tokens: tokens => useAuthStore.getState().setTokens(tokens.access_token, tokens.refresh_token),
  anonymous: () => useAuthStore.getState().clearAuth(),
  unavailable: () => useAuthStore.getState().unavailable(),
  lock: async action => {
    if (typeof navigator !== "undefined" && navigator.locks)
      return await navigator.locks.request("saha-session-refresh", action);
    return await action();
  },
});
let initialization: Promise<void> | null = null;
export function initializeSession() {
  if (!initialization) initialization = (async () => {
    await useAuthStore.persist.rehydrate();
    useAuthStore.getState().beginCheck();
    await controller.restore();
  })();
  return initialization;
}
export async function reloadSessionFromStorage() {
  // Rehydrate BEFORE writing state, otherwise an old tab can overwrite a new login.
  controller.invalidate();
  await useAuthStore.persist.rehydrate();
  useAuthStore.getState().beginCheck();
  await controller.restore();
}
export async function retrySession() {
  controller.invalidate();
  useAuthStore.getState().beginCheck();
  await controller.restore();
}
export const refreshSession = controller.refresh;
