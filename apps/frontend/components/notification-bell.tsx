"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import {
  api,
  isTokenExpired,
  notificationsStreamUrl,
  refreshAccessToken,
  type Notification,
} from "@/lib/api";
import { cn } from "@/components/ui";
import * as Icon from "@/components/ui/icons";
import { safeReturnTo } from "@/lib/navigation";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function NotificationBell() {
  const identity = useAuthStore(s => s.user?.id ?? "anonymous");
  return <NotificationBellContent key={identity} />;
}

function NotificationBellContent() {
  const router = useRouter();
  const token = useAuthStore((s) => s.accessToken);
  const [items, setItems] = useState<Notification[]>([]);
  // Bumped when a stream ends, to re-run the effect and mint a fresh ticket.
  const [streamEpoch, setStreamEpoch] = useState(0);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const lastEvent = useRef<string | null>(null);
  const retryAttempt = useRef(0);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [list, count] = await Promise.all([
        api.notifications.list(token, 20),
        api.notifications.unreadCount(token),
      ]);
      setItems(list);
      setUnread(count.unread);
    } catch {
      /* transient — the SSE stream or next poll will refresh */
    }
  }, [token]);

  // Real fallback: reconcile server state even when the event stream is down.
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 30_000);
    return () => clearInterval(timer);
  }, [load]);

  // Real-time updates via SSE. Prepend new notifications and bump the badge.
  useEffect(() => {
    if (!token) return;
    if (isTokenExpired(token)) {
      refreshAccessToken();
      return;
    }

    // EventSource can't send an Authorization header, so the handshake
    // credential rides in the URL — where nginx logs it and the browser keeps
    // it in history. It must therefore not be the access token, which is what
    // this used to pass (security/AUDIT.md SAHA-017). Exchange it for a
    // 60-second, stream-scoped ticket instead: one recovered from a log has
    // expired, and grants nothing beyond this feed even before it does.
    let es: EventSource | null = null;
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let refreshTimer: ReturnType<typeof setTimeout> | null = null;
    const reconcileSoon = () => {
      if (closed || refreshTimer) return;
      refreshTimer = setTimeout(() => { refreshTimer = null; if (!closed) void load(); }, 150);
    };
    const retry = () => {
      if (closed) return;
      const delay = Math.min(30_000, 1_000 * 2 ** Math.min(retryAttempt.current++, 5));
      retryTimer = setTimeout(() => { if (!closed) setStreamEpoch(n => n + 1); }, delay);
    };

    (async () => {
      let ticket: string;
      try {
        ticket = (await api.auth.streamTicket(token)).ticket;
      } catch {
        retry();
        return;
      }
      if (closed) return;

      es = new EventSource(notificationsStreamUrl(ticket, lastEvent.current));
      es.onopen = () => { void load(); };
      es.onmessage = (e) => {
        try {
          const event: Notification = JSON.parse(e.data);
          lastEvent.current = e.lastEventId || event.id;
          retryAttempt.current = 0;
          // Treat an event as an invalidation, not an increment: replay and the
          // initial REST/stream overlap must not duplicate cards or unread counts.
          reconcileSoon();
        } catch { /* malformed frame; polling still reconciles */ }
      };
      es.onerror = () => {
        // The ticket is short-lived by design, so the browser's auto-reconnect
        // will eventually fail. Close and let the effect re-run, which mints a
        // fresh ticket — refreshing the access token first if it has expired.
        es?.close();
        es = null;
        if (isTokenExpired(token)) refreshAccessToken();
        else retry();
      };
    })();

    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (refreshTimer) clearTimeout(refreshTimer);
      es?.close();
    };
  }, [token, streamEpoch, load]);

  // Close on outside click / Escape.
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

  const openPanel = async () => {
    setOpen((o) => !o);
    if (!open && unread > 0 && token) {
      // Optimistically clear the badge; persist in the background.
      setUnread(0);
      try {
        await api.notifications.markAllRead(token);
        setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      } catch {
        /* will reconcile on next load */
      }
    }
  };

  const onItemClick = (n: Notification) => {
    setOpen(false);
    if (n.link) router.push(safeReturnTo(n.link));
  };

  if (!token) return null;

  return (
    <div className="relative" ref={panelRef} onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false); }}>
      <button
        ref={triggerRef}
        onClick={openPanel}
        className="relative grid place-items-center w-9 h-9 rounded-md text-ink-soft hover:text-ink hover:bg-surface-2 transition-colors"
        aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}
        aria-controls={panelId}
        aria-expanded={open}
      >
        <Icon.Bell className="w-5 h-5" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 grid place-items-center rounded-full bg-danger text-white text-[10px] font-semibold">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          id={panelId}
          role="region"
          aria-label="Notifications"
          className="fixed inset-x-4 top-20 sm:absolute sm:inset-x-auto sm:top-auto sm:right-0 sm:mt-2 sm:w-80 max-h-[70vh] overflow-y-auto bg-surface border border-line rounded-xl shadow-lg z-30 animate-[saha-fade-in_120ms_ease-out]"
        >
          <div className="px-4 py-3 border-b border-line flex items-center justify-between">
            <span className="text-sm font-semibold text-ink">Notifications</span>
          </div>
          {items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-muted">You&apos;re all caught up.</p>
          ) : (
            <ul>
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => onItemClick(n)}
                    className={cn(
                      "w-full text-left px-4 py-3 border-b border-line last:border-0 hover:bg-surface-2 transition-colors",
                      !n.is_read && "bg-accent-soft/40",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      {!n.is_read && (
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-accent shrink-0" aria-hidden />
                      )}
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink">{n.title}</p>
                        {n.body && <p className="text-xs text-muted mt-0.5 line-clamp-2">{n.body}</p>}
                        <p className="text-[11px] text-muted mt-1">{timeAgo(n.created_at)}</p>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
