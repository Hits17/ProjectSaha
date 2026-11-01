"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { safeReturnTo } from "@/lib/navigation";
import { LoadingRow } from "@/components/ui";

export function GuestOnly({ children }: { children: React.ReactNode }) {
  const status = useAuthStore(s => s.status);
  const router = useRouter();
  useEffect(() => {
    if (status === "authenticated") router.replace(safeReturnTo(new URLSearchParams(window.location.search).get("next")));
  }, [status, router]);
  return status === "anonymous" ? children : <LoadingRow label="Opening your workspace…" />;
}
