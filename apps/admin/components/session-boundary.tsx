"use client";
import { useEffect } from "react";
import { useAuthStore } from "@/store/auth";
import { shouldSyncSession } from "@/lib/session-controller";
import { initializeSession, reloadSessionFromStorage, retrySession } from "@/lib/session";

export function SessionBoundary({ children }: { children: React.ReactNode }) {
  const status = useAuthStore(s => s.status);
  useEffect(() => {
    void initializeSession();
    const sync = (event: StorageEvent) => {
      if ((event.key === "saha-admin-auth" || event.key === null) && shouldSyncSession(useAuthStore.getState(), event.newValue))
        void reloadSessionFromStorage();
    };
    const online = () => { if (useAuthStore.getState().status === "unavailable") void retrySession(); };
    window.addEventListener("storage", sync);
    window.addEventListener("online", online);
    return () => { window.removeEventListener("storage", sync); window.removeEventListener("online", online); };
  }, []);
  const publicContent = false;
  if (status === "unavailable") return <><div role="alert" className="border-b border-slate-200 bg-amber-50 p-4 text-center text-sm">We couldn’t verify your session. Your saved sign-in has been kept. <button type="button" onClick={() => void retrySession()} className="font-semibold text-indigo-700 underline">Try again</button></div>{publicContent ? children : <p className="p-8 text-center text-slate-500">Reconnect to open your account safely.</p>}</>;
  if (status === "loading" && !publicContent) return <div role="status" className="p-12 text-center text-sm text-slate-500">Restoring your Saha session…</div>;
  return children;
}
