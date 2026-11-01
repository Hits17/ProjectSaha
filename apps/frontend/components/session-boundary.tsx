"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { shouldSyncSession } from "@/lib/session-controller";
import { initializeSession, reloadSessionFromStorage, retrySession } from "@/lib/session";

export function SessionBoundary({ children }: { children: React.ReactNode }) {
  const status = useAuthStore(s => s.status);
  const path = usePathname();
  useEffect(() => {
    void initializeSession();
    const sync = (event: StorageEvent) => {
      if ((event.key === "saha-auth" || event.key === null) && shouldSyncSession(useAuthStore.getState(), event.newValue))
        void reloadSessionFromStorage();
    };
    const online = () => { if (useAuthStore.getState().status === "unavailable") void retrySession(); };
    window.addEventListener("storage", sync);
    window.addEventListener("online", online);
    return () => { window.removeEventListener("storage", sync); window.removeEventListener("online", online); };
  }, []);
  const publicContent = path === "/" || path === "/guide";
  if (status === "unavailable") return <><div role="alert" className="border-b border-line bg-warning-soft p-4 text-center text-sm">We couldn’t verify your session. Your saved sign-in has been kept. <button type="button" onClick={() => void retrySession()} className="font-semibold text-accent underline">Try again</button></div>{publicContent ? children : <p className="p-8 text-center text-muted">Reconnect to open your account safely.</p>}</>;
  if (status === "loading" && !publicContent) return <div role="status" className="p-12 text-center text-sm text-muted">Restoring your Saha session…</div>;
  return children;
}
