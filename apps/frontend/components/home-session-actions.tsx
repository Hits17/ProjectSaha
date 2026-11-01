"use client";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";

export function HomeSessionActions({ hint = false }: { hint?: boolean }) {
  const status = useAuthStore(s => s.status);
  if (status === "loading" || status === "unavailable") return <span role="status" className={hint ? "text-xs text-muted" : "text-sm text-white/75"}>{status === "loading" ? "Checking your session…" : "Reconnect to continue with your account."}</span>;
  const signedIn = status === "authenticated";
  if (hint) return <span className="text-xs text-muted">{signedIn ? "Your research, collaborators and projects are in your workspace." : "Explore freely. Join when you’re ready to contribute."}</span>;
  return <Link href={signedIn ? "/dashboard" : "/register"} className="inline-flex min-h-12 shrink-0 items-center justify-center rounded-lg bg-white px-6 text-sm font-semibold text-ink hover:bg-accent-soft">{signedIn ? "Continue to your workspace →" : "Join the community →"}</Link>;
}
