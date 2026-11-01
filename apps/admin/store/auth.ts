"use client";
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { resilientSessionStorage } from "@/lib/session-storage";
import type { User } from "@/lib/api";
import type { SessionStatus } from "@/lib/session-controller";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  status: SessionStatus;
  revision: number;
  signedOut: boolean;
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clearAuth: () => void;
  beginCheck: () => void;
  unavailable: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(persist((set, get) => ({
  user: null, accessToken: null, refreshToken: null,
  status: "loading", revision: 0, signedOut: false,
  setAuth: (user, accessToken, refreshToken) => set(s => ({ user, accessToken, refreshToken, status: "authenticated", signedOut: false, revision: s.revision + 1 })),
  setUser: user => set({ user }),
  setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
  clearAuth: () => set(s => ({ user: null, accessToken: null, refreshToken: null, status: "anonymous", signedOut: true, revision: s.revision + 1 })),
  beginCheck: () => set(s => ({ status: "loading", revision: s.revision + 1 })),
  unavailable: () => set({ status: "unavailable" }),
  isAuthenticated: () => get().status === "authenticated" && !!get().user && !!get().accessToken,
}), {
  name: "saha-admin-auth",
  skipHydration: true,
  storage: createJSONStorage(() => resilientSessionStorage(() => window.localStorage)),
  // Only cached profile/access-token hints persist. Never trust them before /me.
  // Explicit logout suppresses cookie restoration if revocation could not reach the server.
  partialize: s => ({ user: s.user, accessToken: s.accessToken, signedOut: s.signedOut }),
  merge: (value, current) => {
    const cached = value as Partial<AuthState> | null;
    const user = cached?.user && typeof cached.user.id === "string" ? cached.user : null;
    return { ...current, status: "loading", revision: current.revision + 1, user, accessToken: typeof cached?.accessToken === "string" ? cached.accessToken : null,
      signedOut: cached?.signedOut === true, refreshToken: null };
  },
}));
