# Saha private admin console

Separate Next.js application on loopback port 3002, behind private nginx :8080.
The public Cloudflare ingress excludes this listener. API access requires server-side
admin/MFA policy. Production API requests use the private nginx origin; development
may use NEXT_PUBLIC_API_URL.

Use `pnpm install --frozen-lockfile`, `pnpm dev`, and
`pnpm exec tsc --noEmit --incremental false` from this directory. The package scripts
set port 3002. Use `saha build` with apps stopped for host release builds.

Pages include overview, users, listings, proposals, transactions, revenue, reviews,
law firms, demand, audit, system health, library resources, moderation and
Institutions & Spaces. The latter controls optional verification requests, review,
badges and private space references. Moderation now loads protected social image/
video attachments using authenticated requests; text classification does not scan
visual media. Private reference visibility does not extend to community moderators.

See [interactive route inventory](../../docs/architecture/SAHA_FRONTEND.html),
[current security](../../security/CURRENT-SECURITY.md), [development](../../docs/DEVELOPMENT.md)
and [host operations](../../docs/HOSTING.md). Do not expose the console through the
public tunnel or treat a successful local build as a deployed release.

Login restoration and session-aware API behavior are documented in [Session consistency](../../docs/SESSION-CONSISTENCY.md). The current patch adds no package or schema migration.
