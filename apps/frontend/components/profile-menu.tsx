"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import * as Icon from "@/components/ui/icons";

/** Fired (window event) after an avatar upload so the header refreshes. */
export const AVATAR_UPDATED_EVENT = "saha:avatar-updated";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

/** Circular avatar: the user's picture when set, else their initials. */
export function Avatar({ src, name, className = "w-8 h-8 text-xs" }: {
  src: string | null;
  name: string;
  className?: string;
}) {
  return src ? (
    // eslint-disable-next-line @next/next/no-img-element -- blob object URL, next/image can't optimize it
    <img src={src} alt="" className={`${className} rounded-full object-cover`} />
  ) : (
    <span
      aria-hidden
      className={`${className} rounded-full bg-ink text-white grid place-items-center font-semibold select-none`}
    >
      {initials(name)}
    </span>
  );
}

/** Loads the signed-in user's avatar as an object URL; re-fetches on upload. */
export function useMyAvatar(): string | null {
  const token = useAuthStore((s) => s.accessToken);
  const hasAvatar = useAuthStore((s) => s.user?.has_avatar ?? false);
  const [url, setUrl] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    window.addEventListener(AVATAR_UPDATED_EVENT, bump);
    return () => window.removeEventListener(AVATAR_UPDATED_EVENT, bump);
  }, []);

  useEffect(() => {
    if (!token || !hasAvatar) {
      setUrl(null);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    api.users.fetchAvatarUrl(token).then((u) => {
      if (cancelled) {
        if (u) URL.revokeObjectURL(u);
        return;
      }
      objectUrl = u;
      setUrl(u);
    }).catch(() => { if (!cancelled) setUrl(null); });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [token, hasAvatar, version]);

  return url;
}

export function ProfileMenu() {
  const router = useRouter();
  const { user, accessToken, clearAuth } = useAuthStore();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const avatarUrl = useMyAvatar();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); triggerRef.current?.focus(); } };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;

  const signOut = async () => {
    const revision = useAuthStore.getState().revision;
    setOpen(false);
    try { if (accessToken) await api.auth.logout(accessToken); }
    catch { /* Server may be unavailable; always clear the local session. */ }
    finally { if (useAuthStore.getState().revision === revision) { clearAuth(); router.push("/login"); } }
  };

  const itemCls =
    "flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-ink-soft hover:text-ink hover:bg-surface-2 transition-colors";

  return (
    <div className="relative" ref={panelRef} onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false); }}>
      <button
        ref={triggerRef}
        onClick={() => setOpen((o) => !o)}
        className="grid size-10 place-items-center rounded-full ring-offset-2 hover:ring-2 hover:ring-line transition-shadow"
        aria-label="Account menu"
        aria-controls={panelId}
        aria-expanded={open}
      >
        <Avatar src={avatarUrl} name={user.full_name} />
      </button>

      {open && (
        <div
          id={panelId}
          aria-label="Account options"
          className="absolute right-0 mt-2 w-60 bg-surface border border-line rounded-xl shadow-lg z-30 py-1.5 animate-[saha-fade-in_120ms_ease-out]"
        >
          <div className="px-4 py-2.5 border-b border-line mb-1">
            <p className="text-sm font-semibold text-ink truncate">{user.full_name}</p>
            <p className="text-xs text-muted truncate">{user.email}</p>
          </div>
          {/* The public-facing profile other members see — distinct from the
              account settings below it. */}
          <Link
            href={`/dashboard/members/${user.id}`}

            onClick={() => setOpen(false)}
            className={itemCls}
          >
            <Icon.UserCircle className="w-4 h-4" />
            My profile
          </Link>
          <Link href="/dashboard/profile" onClick={() => setOpen(false)} className={itemCls}>
            <Icon.Sparkles className="w-4 h-4" />
            Account settings
          </Link>
          <Link href="/dashboard/security" onClick={() => setOpen(false)} className={itemCls}>
            <Icon.Lock className="w-4 h-4" />
            Security
          </Link>
          <div className="border-t border-line my-1" />
          <button onClick={signOut} className={itemCls}>
            <Icon.LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
