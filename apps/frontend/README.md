# Saha public and member application

Next.js 15 / React 19 / Tailwind 4, with a shared shell for Home, Explore,
Institutions, Projects and the signed-in workspace. The social feed supports
multimedia and mentions; projects are invite-only with optional source selection,
tasks, external reference cards and an Element chat handoff.

From this directory use `pnpm install --frozen-lockfile`, `pnpm dev`, and
`pnpm exec tsc --noEmit --incremental false`. pnpm is pinned to 9.15.4. Fonts are
bundled locally. Production browser requests use same-origin nginx `/api`; local
development may set `NEXT_PUBLIC_API_URL`.

Do not run a build over the active production `.next`. The host release command is
`saha build` with both apps stopped, followed by local readiness/version checks.
The November schema migrations must precede this release's backend startup.

Read [Development](../../docs/DEVELOPMENT.md), [User guide](../../docs/USER-GUIDE.md),
[UX map](../../docs/UX-NAVIGATION.md), [interactive frontend reference](../../docs/architecture/SAHA_FRONTEND.html)
and [Hosting](../../docs/HOSTING.md). The parent repository's frontend gitlink lacks
a configured submodule remote; preserve this working tree and resolve delivery
before assuming CI receives it.

Login restoration and session-aware API behavior are documented in [Session consistency](../../docs/SESSION-CONSISTENCY.md). The current patch adds no package or schema migration.
