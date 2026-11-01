/** One route map for navigation, breadcrumbs and sign-in continuation. */
export const primaryNavigation = [
  { href: "/explore", label: "Explore" },
  { href: "/projects", label: "Projects" },
  { href: "/institutions", label: "Institutions" },
];

export const workspaceNavigation = [
  { label: "Workspace", items: [
    { href: "/dashboard", label: "Overview", icon: "Compass" },
    { href: "/explore", label: "Explore research", icon: "Search" },
    { href: "/projects", label: "Projects", icon: "Package" },
    { href: "/dashboard/collections", label: "My collections", icon: "BookOpen" },
  ] },
  { label: "Community", items: [
    { href: "/dashboard/feed", label: "Community feed", icon: "FileText" },
    { href: "/dashboard/community", label: "Interest groups", icon: "Users" },
    { href: "/institutions", label: "Institutions", icon: "Building" },
    { href: "/dashboard/library", label: "Contribute resources", icon: "Plus" },
  ] },
  { label: "IP & marketplace", items: [
    { href: "/dashboard/marketplace", label: "Marketplace overview", icon: "Compass" },
    { href: "/dashboard/discover", label: "Find IP listings", icon: "Search" },
    { href: "/dashboard/listings", label: "My listings", icon: "FileText" },
    { href: "/dashboard/materials", label: "Materials", icon: "Package" },
    { href: "/dashboard/demand", label: "Demand signals", icon: "TrendingUp" },
    { href: "/dashboard/proposals", label: "Proposals", icon: "Handshake" },
    { href: "/dashboard/transactions", label: "Transactions", icon: "Shield" },
  ] },
] as const;

export function routeIsActive(path: string, href: string) {
  return path === href || (href !== "/" && href !== "/dashboard" && path.startsWith(href + "/"));
}

const labels: Record<string, string> = {
  ...Object.fromEntries([...primaryNavigation, ...workspaceNavigation.flatMap(g => [...g.items])].map(i => [i.href, i.label])),
  "/": "Home", "/dashboard": "Workspace", "/dashboard/profile": "Account settings",
  "/dashboard/security": "Security", "/dashboard/admin": "Administration",
  "/dashboard/members": "Member profile", "/listings": "IP listings",
  "/guide": "Getting started", "/login": "Sign in", "/register": "Join Saha",
  "/verify-email": "Verify email",
};

export function breadcrumbs(path: string): { href?: string; label: string }[] {
  const parts = path.split("/").filter(Boolean);
  const result: { href?: string; label: string }[] = [{ href: "/", label: "Home" }];
  parts.forEach((part, index) => {
    const href = "/" + parts.slice(0, index + 1).join("/");
    const label = labels[href] || ({ new: "Create listing", dialogue: "Listing assistant" }[part]) || "Details";
    // /listings and /dashboard/members are not index routes.
    const target = href === "/listings" ? "/dashboard/discover" : href === "/dashboard/members" ? undefined : href;
    result.push({ href: index === parts.length - 1 ? undefined : target, label });
  });
  return result;
}

/** Only known local application routes may receive a post-auth redirect. */
export function safeReturnTo(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\s\u0000-\u001f]/.test(value)) return "/dashboard";
  try {
    const url = new URL(value, "https://saha.invalid");
    if (url.origin !== "https://saha.invalid") return "/dashboard";
    const allowed = ["/dashboard", "/explore", "/projects", "/institutions", "/listings", "/guide"];
    if (url.pathname !== "/" && !allowed.some(p => url.pathname === p || url.pathname.startsWith(p + "/"))) return "/dashboard";
    return url.pathname + url.search + url.hash;
  } catch { return "/dashboard"; }
}

export function signInHref(destination: string) {
  return "/login?next=" + encodeURIComponent(safeReturnTo(destination));
}
