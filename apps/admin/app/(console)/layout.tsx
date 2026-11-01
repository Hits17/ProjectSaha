"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

const GROUPS = [
  { label: "Community & research", items: [
    { href: "/", label: "Overview" }, { href: "/institutions", label: "Institutions & spaces" },
    { href: "/users", label: "Members" }, { href: "/resources", label: "Research library" },
    { href: "/moderation", label: "Moderation" }, { href: "/reviews", label: "Reviews" },
  ] },
  { label: "IP & marketplace", items: [
    { href: "/listings", label: "Listings" }, { href: "/proposals", label: "Proposals" },
    { href: "/transactions", label: "Transactions" }, { href: "/demand", label: "Demand signals" },
    { href: "/revenue", label: "Revenue" }, { href: "/law-firms", label: "Law firms" },
  ] },
  { label: "Platform", items: [{ href: "/audit", label: "Audit log" }, { href: "/system", label: "System" }] },
];

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, accessToken, refreshToken, clearAuth, status } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);
  const [menuPath, setMenuPath] = useState<string | null>(null);
  const menuOpen = menuPath === pathname;
  useEffect(() => setHydrated(true), []);
  useEffect(() => {
    if (hydrated && (status === "anonymous" || (status === "authenticated" && user?.role !== "admin"))) router.replace("/login");
  }, [hydrated, status, user, router]);
  if (!hydrated || status !== "authenticated" || !accessToken || user?.role !== "admin") return <div role="status" className="min-h-screen flex items-center justify-center text-slate-500 text-sm">Opening Saha administration…</div>;

  const signOut = async () => {
    const revision = useAuthStore.getState().revision;
    try { await api.auth.logout(accessToken, refreshToken ?? undefined); } catch { /* best effort */ }
    if (useAuthStore.getState().revision === revision) { clearAuth(); router.replace("/login"); }
  };
  const current = GROUPS.flatMap(g => g.items).find(i => i.href === pathname)?.label ?? "Details";
  const navigation = <>{GROUPS.map(group => <section key={group.label} className="mb-6"><h2 className="px-3 text-[11px] font-semibold uppercase tracking-widest text-slate-500">{group.label}</h2><div className="mt-2 space-y-1">{group.items.map(item => {
    const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href + "/"));
    return <Link key={item.href} href={item.href} onClick={() => setMenuPath(null)} aria-current={active ? "page" : undefined} className={`block rounded-lg px-3 py-2.5 text-sm ${active ? "bg-indigo-100 text-indigo-700 font-semibold" : "text-slate-600 hover:bg-slate-100"}`}>{item.label}</Link>;
  })}</div></section>)}</>;

  return <div className="min-h-screen">
    <a href="#admin-content" className="skip-link">Skip to content</a>
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur"><div className="mx-auto flex h-[72px] max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6"><Link href="/" aria-label="Saha administration home" className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl bg-indigo-600 font-semibold text-white">S</span><span className="text-2xl font-semibold tracking-tight">saha<span className="text-indigo-600">.</span></span><span className="hidden rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 sm:inline">Administration</span></Link><div className="flex items-center gap-4"><a href="https://sahasolutions.com" target="_blank" rel="noopener noreferrer" className="hidden text-sm text-indigo-700 sm:block">Open Saha ↗</a><button onClick={signOut} className="text-sm text-slate-600">Sign out</button><button className="rounded-lg border border-slate-300 px-3 text-sm lg:hidden" aria-expanded={menuOpen} aria-controls="admin-mobile-nav" onClick={() => setMenuPath(menuOpen ? null : pathname)}>Menu</button></div></div>
    {menuOpen && <nav id="admin-mobile-nav" aria-label="Administration mobile navigation" className="max-h-[calc(100dvh-72px)] overflow-y-auto border-t border-slate-200 p-4 lg:hidden">{navigation}</nav>}</header>
    <div className="mx-auto max-w-[1440px] lg:grid lg:grid-cols-[240px_minmax(0,1fr)]"><aside className="hidden border-r border-slate-200 lg:block"><nav aria-label="Administration navigation" className="sticky top-[72px] max-h-[calc(100dvh-72px)] overflow-y-auto p-5">{navigation}<p className="border-t border-slate-200 px-3 pt-4 text-xs text-slate-500 break-all">{user.email}</p></nav></aside><main id="admin-content" tabIndex={-1} className="min-w-0 p-4 sm:p-6 lg:p-8"><nav aria-label="Breadcrumb" className="mb-6 flex gap-2 text-xs text-slate-500"><Link href="/">Administration</Link><span aria-hidden="true">/</span><span aria-current="page">{current}</span></nav>{children}</main></div>
  </div>;
}
