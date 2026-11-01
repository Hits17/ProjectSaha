"use client";

import { Fragment, useEffect, useMemo } from "react";
import { useAuthStore } from "@/store/auth";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionBoundary } from "@/components/session-boundary";
import { ToastProvider } from "@/components/ui";

/** App-wide client providers: React Query (data cache) + Toast (notifications).
 *  Each account gets a separate QueryClient; private caches cannot survive account switches. */
export function Providers({ children }: { children: React.ReactNode }) {
  const userId = useAuthStore(s => s.user?.id ?? null);
  const client = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
    [userId],
  );
  useEffect(() => () => { void client.cancelQueries(); client.clear(); }, [client]);

  return (
    <QueryClientProvider client={client}>
      <ToastProvider><SessionBoundary><Fragment key={userId ?? "anonymous"}>{children}</Fragment></SessionBoundary></ToastProvider>
    </QueryClientProvider>
  );
}
