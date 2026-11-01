/** Session lifecycle, independent of React so races can be tested deterministically. */
export type SessionStatus = "loading" | "authenticated" | "anonymous" | "unavailable";
export interface SessionSnapshot { user: { id: string } | null; accessToken: string | null; refreshToken: string | null; revision: number; signedOut: boolean }
interface Tokens { access_token: string; refresh_token: string }
interface Options<User extends { id: string }> {
  snapshot: () => SessionSnapshot;
  fetch: typeof fetch;
  base: string;
  accept: (user: User, tokens: Tokens) => void;
  tokens: (tokens: Tokens) => void;
  profile: (user: User) => void;
  anonymous: () => void;
  unavailable: () => void;
  lock?: <T>(action: () => Promise<T>) => Promise<T>;
}
export function createSessionController<User extends { id: string }>(options: Options<User>) {
  let restoring: Promise<void> | null = null;
  let refreshing: Promise<string | null> | null = null;
  const current = (snapshot: SessionSnapshot) => options.snapshot().revision === snapshot.revision;
  const runLocked = options.lock ?? (async <T>(action: () => Promise<T>) => action());
  async function exchange(start: SessionSnapshot): Promise<Tokens | null> {
    const response = await options.fetch(`${options.base}/api/v1/auth/refresh`, {
      method: "POST", credentials: "include", cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(start.refreshToken ? { refresh_token: start.refreshToken } : {}),
      signal: AbortSignal.timeout(15000),
    });
    if (!current(start)) return null;
    if (response.status === 401) { options.anonymous(); return null; }
    if (!response.ok) throw new Error("Session service temporarily unavailable");
    const tokens = await response.json() as Tokens;
    if (!tokens.access_token || !tokens.refresh_token) throw new Error("Invalid session response");
    return current(start) ? tokens : null;
  }
  async function restore() {
    if (restoring) return restoring;
    const start = options.snapshot();
    const task = (async () => {
      if (start.signedOut) { if (current(start)) options.anonymous(); return; }
      try {
        let tokens: Tokens = { access_token: start.accessToken ?? "", refresh_token: start.refreshToken ?? "" };
        const profile = (token: string) => options.fetch(`${options.base}/api/v1/users/me`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(15000) });
        let response = tokens.access_token ? await profile(tokens.access_token) : null;
        if (!current(start)) return;
        if (!response || response.status === 401) {
          const rotated = await runLocked(async () => current(start) ? exchange(start) : null);
          if (!rotated || !current(start)) return;
          tokens = rotated;
          // Keep a rotated in-memory fallback if the subsequent profile request fails.
          options.tokens(tokens);
          response = await profile(tokens.access_token);
        }
        if (!current(start)) return;
        if (response.status === 401) { options.anonymous(); return; }
        if (!response.ok) throw new Error("Could not verify session");
        const user = await response.json() as User;
        if (!user || typeof user.id !== "string" || !user.id) throw new Error("Invalid profile response");
        if (!current(start)) return;
        if (start.user && start.user.id !== user.id) { options.anonymous(); return; }
        options.accept(user, tokens);
      } catch { if (current(start)) options.unavailable(); }
    })();
    restoring = task;
    try { await task; } finally { if (restoring === task) restoring = null; }
  }
  async function refresh(): Promise<string | null> {
    if (refreshing) return refreshing;
    const start = options.snapshot();
    if (!start.user || !start.accessToken || start.signedOut) return null;
    const task = runLocked(async () => {
      if (!current(start)) return null;
      // Another tab/request may have already rotated this token while we waited.
      if (options.snapshot().accessToken !== start.accessToken) return options.snapshot().accessToken;
      try {
        const tokens = await exchange(start);
        if (!tokens || !current(start)) return null;
        const response = await options.fetch(`${options.base}/api/v1/users/me`, {
          headers: { Authorization: `Bearer ${tokens.access_token}` }, cache: "no-store", signal: AbortSignal.timeout(15000),
        });
        if (!current(start)) return null;
        if (response.status === 401) { options.anonymous(); return null; }
        if (!response.ok) return null;
        const user = await response.json() as User;
        if (!current(start)) return null;
        // A shared cookie can belong to another login; never retry an old user's
        // mutation with that account's token.
        if (!user || user.id !== start.user?.id) { options.anonymous(); return null; }
        options.tokens(tokens);
        options.profile(user);
        return tokens.access_token;
      } catch { return null; } // Network/429/5xx must not log a user out.
    });
    refreshing = task;
    try { return await task; } finally { if (refreshing === task) refreshing = null; }
  }
  function invalidate() { restoring = null; refreshing = null; }
  return { restore, refresh, invalidate };
}


/** Same-account token rotation must not unmount a tab's unsaved form/draft. */
export function shouldSyncSession(current: { status: SessionStatus; user: { id: string } | null }, raw: string | null): boolean {
  if (current.status !== "authenticated" || !current.user || !raw) return true;
  try {
    const cached = JSON.parse(raw)?.state;
    return cached?.signedOut === true || cached?.user?.id !== current.user.id || !cached?.accessToken;
  } catch { return true; }
}
