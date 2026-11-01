"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { useClientReady } from "@/components/app-shell";
import { LoadingRow } from "@/components/ui";
import { signInHref } from "@/lib/navigation";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const ready = useClientReady();
  const { accessToken, user, status } = useAuthStore();
  useEffect(() => {
    if (ready && status === "anonymous") router.replace(signInHref(window.location.pathname + window.location.search));
  }, [ready, status, router]);
  if (!ready || status !== "authenticated" || !accessToken || !user) return <LoadingRow label="Opening your workspace…" />;
  return <>{children}</>;
}
