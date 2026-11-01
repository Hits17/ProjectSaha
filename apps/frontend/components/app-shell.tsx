"use client";

import { Suspense, useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { Brand } from "@/components/brand";
import { NotificationBell } from "@/components/notification-bell";
import { ProfileMenu } from "@/components/profile-menu";
import * as Icon from "@/components/ui/icons";
import { breadcrumbs, primaryNavigation, routeIsActive, safeReturnTo, signInHref, workspaceNavigation } from "@/lib/navigation";

const subscribe = () => () => {};
export function useClientReady() {
  return useSyncExternalStore(subscribe, () => true, () => false);
}

function WorkspaceLinks({ path, admin, onNavigate }: { path: string; admin: boolean; onNavigate?: () => void }) {
  return <>
    {workspaceNavigation.map(group => {
      const links = <div className="mt-2 space-y-1">{group.items.map(item => {
        const Glyph = Icon[item.icon];
        const active = routeIsActive(path, item.href);
        return <Link key={item.href} href={item.href} onClick={onNavigate} aria-current={active ? "page" : undefined}
          className={`flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${active ? "bg-accent-soft text-accent font-semibold" : "text-ink-soft hover:bg-surface-2 hover:text-ink"}`}>
          <Glyph className="size-4 shrink-0" />{item.label}
        </Link>;
      })}</div>;
      return group.label === "IP & marketplace"
        ? <details key={`${group.label}:${path}`} open={group.items.some(i => routeIsActive(path, i.href))} className="border-t border-line pt-4"><summary className="cursor-pointer px-3 text-xs font-semibold text-muted">{group.label}</summary>{links}</details>
        : <section key={group.label}><h2 className="px-3 text-[11px] font-semibold uppercase tracking-widest text-muted">{group.label}</h2>{links}</section>;
    })}
    <div className="border-t border-line pt-3 space-y-1">
      {admin && <Link aria-current={path === "/dashboard/admin" ? "page" : undefined} className="nav-utility" href="/dashboard/admin" onClick={onNavigate}><Icon.Shield className="size-4" />Administration</Link>}
      <Link aria-current={path === "/guide" ? "page" : undefined} className="nav-utility" href="/guide" onClick={onNavigate}><Icon.Info className="size-4" />Getting started</Link>
      <Link aria-current={path === "/dashboard/security" ? "page" : undefined} className="nav-utility" href="/dashboard/security" onClick={onNavigate}><Icon.Lock className="size-4" />Account & security</Link>
    </div>
  </>;
}

function AuthenticationLinks({ path, mobile = false, onNavigate }: { path: string; mobile?: boolean; onNavigate?: () => void }) {
  const params = useSearchParams();
  const accountPage = ["/login", "/register", "/verify-email"].includes(path);
  const destination = accountPage ? safeReturnTo(params.get("next")) : path === "/" ? "/dashboard" : path + (params.size ? `?${params}` : "");
  return <><Link href={signInHref(destination)} onClick={onNavigate} className={mobile ? "nav-utility" : "hidden sm:inline-flex text-sm font-medium text-ink-soft"}>Sign in</Link>{!mobile && <Link href={`/register?next=${encodeURIComponent(destination)}`} className="inline-flex min-h-10 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-hover">Join Saha</Link>}</>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const ready = useClientReady();
  const { user, accessToken, status } = useAuthStore();
  const signedIn = ready && status === "authenticated" && !!accessToken && !!user;
  const checking = !ready || status === "loading" || status === "unavailable";
  const [menuPath, setMenuPath] = useState<string | null>(null);
  const menuOpen = menuPath === path;
  const trigger = useRef<HTMLButtonElement>(null);
  const header = useRef<HTMLElement>(null);
  const authPage = ["/login", "/register", "/verify-email"].includes(path);
  const workspace = signedIn && path !== "/" && !authPage;
  const crumbs = breadcrumbs(path);

  useEffect(() => {
    if (!menuOpen) return;
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") { setMenuPath(null); trigger.current?.focus(); } };
    const click = (e: PointerEvent) => { if (!header.current?.contains(e.target as Node)) setMenuPath(null); };
    document.addEventListener("keydown", key);
    document.addEventListener("pointerdown", click);
    return () => { document.removeEventListener("keydown", key); document.removeEventListener("pointerdown", click); };
  }, [menuOpen]);

  return <div className="min-h-screen">
    <a href="#main-content" className="skip-link">Skip to content</a>
    <header ref={header} onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setMenuPath(null); }} className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur-xl">
      <div className="mx-auto flex h-[72px] max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-10"><Brand /><nav aria-label="Main navigation" className="hidden lg:flex items-center gap-1">
          {primaryNavigation.map(item => <Link key={item.href} href={item.href} aria-current={routeIsActive(path, item.href) ? "page" : undefined} className={`rounded-lg px-4 py-2.5 text-sm font-medium ${routeIsActive(path, item.href) ? "bg-accent-soft text-accent" : "text-ink-soft hover:bg-surface-2"}`}>{item.label}</Link>)}
        </nav></div>
        <div className="flex items-center gap-3">
          {checking ? <span role="status" className="text-xs text-muted">{status === "unavailable" ? "Session unavailable" : "Checking session…"}</span> : signedIn ? <><Link href="/dashboard" className="hidden sm:inline-flex text-sm font-medium text-ink-soft hover:text-accent">My workspace</Link><NotificationBell /><ProfileMenu /></> : <Suspense fallback={<><Link href="/login" className="hidden sm:inline-flex text-sm font-medium text-ink-soft">Sign in</Link><Link href="/register" className="inline-flex min-h-10 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-white">Join Saha</Link></>}><AuthenticationLinks path={path} /></Suspense>}
          <button ref={trigger} type="button" aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuPath(menuOpen ? null : path)} className="grid size-10 place-items-center rounded-lg border border-line lg:hidden">{menuOpen ? <Icon.X className="size-5" /> : <Icon.Menu className="size-5" />}</button>
        </div>
      </div>
      {menuOpen && <nav id="mobile-navigation" aria-label="Mobile navigation" className="lg:hidden max-h-[calc(100dvh-72px)] overflow-y-auto border-t border-line bg-surface p-4 space-y-5">
        <div className="grid grid-cols-2 gap-2">{[{ href: "/", label: "Home" }, ...primaryNavigation].map(item => <Link key={item.href} href={item.href} onClick={() => setMenuPath(null)} className="rounded-lg bg-surface-2 px-3 py-3 text-sm font-medium">{item.label}</Link>)}</div>
        {checking ? <p className="text-sm text-muted">Checking your session…</p> : signedIn ? <WorkspaceLinks path={path} admin={user?.role === "admin"} onNavigate={() => setMenuPath(null)} /> : <div className="flex gap-5"><Suspense fallback={<Link href="/login" className="nav-utility">Sign in</Link>}><AuthenticationLinks path={path} mobile onNavigate={() => setMenuPath(null)} /></Suspense><Link href="/guide" onClick={() => setMenuPath(null)} className="nav-utility">Getting started</Link></div>}
      </nav>}
    </header>
    <div className={`mx-auto max-w-[1440px] ${workspace ? "lg:grid lg:grid-cols-[240px_minmax(0,1fr)]" : ""}`}>
      {workspace && <aside className="hidden lg:block border-r border-line"><nav aria-label="Workspace navigation" className="sticky top-[72px] max-h-[calc(100dvh-72px)] overflow-y-auto p-5 space-y-6"><WorkspaceLinks path={path} admin={user?.role === "admin"} /></nav></aside>}
      <div className="min-w-0">
        <main id="main-content" tabIndex={-1} className={`mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-10 ${path === "/" ? "py-8 sm:py-12" : "py-6 sm:py-8"}`}>
          {path !== "/" && !authPage && <nav aria-label="Breadcrumb" className="mb-7"><ol className="flex flex-wrap items-center gap-2 text-xs text-muted">{crumbs.map((crumb, index) => <li key={index} className="flex items-center gap-2">{index > 0 && <Icon.ChevronRight className="size-3" />}{crumb.href ? <Link href={crumb.href} className="hover:text-accent">{crumb.label}</Link> : <span aria-current="page" className="font-medium text-ink-soft">{crumb.label}</span>}</li>)}</ol></nav>}
          {children}
        </main>
        <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 border-t border-line px-4 py-7 text-xs text-muted sm:px-6 lg:px-10"><span>Saha · Open ideas. Shared progress.</span><div className="flex gap-5"><Link href="/guide" className="hover:text-accent">Getting started</Link><Link href="/explore" className="hover:text-accent">Explore research</Link><Link href="/dashboard/marketplace" className="hover:text-accent">IP tools</Link></div></footer>
      </div>
    </div>
  </div>;
}
