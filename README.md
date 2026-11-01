# Saha — Open Innovation & Collaborative Development

Latest patch: [session consistency fixes](docs/SESSION-CONSISTENCY.md) remove signup prompts for signed-in users, unify restoration and harden refresh/logout races. This patch needs coordinated app builds/restarts but **no additional database migration**. See [release evidence](docs/CURRENT-STATUS.md).

The current development release adds multimedia posts, mentions/reactions, independent invite-only projects and reference shortcuts with platform/type badges. It requires `2026-11-01-social-media.sql` and `2026-11-01-project-workspaces.sql`; use [Hosting](docs/HOSTING.md) for the existing system. See [User guide](docs/USER-GUIDE.md) and [Current status](docs/CURRENT-STATUS.md) for implementation limits and publication evidence.

Saha brings research discovery, institutions and collaborative projects into one
platform. Its primary direction is non-monetized open collaboration. Existing IP
marketplace, materials, proposal and transaction tools remain available.

**Current state:** the collaboration release was confirmed online by the owner.
The subsequent unified UI release has passed offline builds and checks, but its
publication is not yet confirmed. Private Matrix/Element chat is prepared for
local testing only and has not passed live two-device acceptance.
See [current status](docs/CURRENT-STATUS.md) for exact build identities and evidence.

## Documentation

- [Documentation index](docs/README.md) and [user guide](docs/USER-GUIDE.md)
- [Interactive architecture, backend and frontend references](docs/architecture/README.md)
- [UX principles, page map and navigation](docs/UX-NAVIGATION.md)
- [Local development and testing](docs/DEVELOPMENT.md)
- [Saha CLI, nginx, systemd and Cloudflare hosting](docs/HOSTING.md)
- [Schema migrations and collaboration cutover](docs/OPEN-COLLABORATION-DEPLOYMENT.md)
- [Encrypted chat setup and acceptance](docs/ENCRYPTED-CHAT.md)
- [Open innovation roadmap](docs/OPEN-INNOVATION-PLAN.md)
- [Security boundaries](security/CURRENT-SECURITY.md)
- [Development history and continuation notes](docs/DEVELOPMENT-HISTORY.md)
- [Changelog](CHANGELOG.md)

## Capabilities

| Area | Current behavior |
| --- | --- |
| Explore | Curated patents/research with source and rights context; separate links to Google Patents, Espacenet and WIPO |
| Projects | Public source-linked spaces, contribution guides, repository links, project stages and versioned task boards |
| Institutions | Public pages, member posts/comments and an optional administrator-reviewed verification workflow |
| Research workspace | Private collections, saved resources, personal notes and saved searches |
| Communities | Interest groups, social feed, posts/comments/votes/follows and separate social/transaction reputation |
| Private references | Internal space identifiers restricted to owners and MFA-qualified platform admins |
| Private conversations | Matrix/Element integration; clients hold keys; old message transports return 410 |
| IP tools | Retained listings, AI-assisted documentation, semantic IP discovery, materials, proposals, legal/settlement workflows |
| Administration | Private console for members, institutions, resources, moderation, transactions, audit and operations |

Discovery is not an exhaustive internet patent index. Public readability and a
curated rights label do not guarantee reuse permission. Saved-search alerts,
notebooks, contributor matching and other roadmap items remain planned.

Collaboration uses confirmed email (or existing verified KYC); financial workflows
keep their KYC requirements. Public posts, project tasks and institution updates
are public. Collections/notes are server-side private records, not E2EE messages.

## Repository and stack

| Location | Purpose |
| --- | --- |
| `apps/backend` | FastAPI, Pydantic, async SQLAlchemy/asyncpg; loopback :8000 |
| `apps/frontend` | Next.js 15 / React 19, Tailwind 4, Zustand, TanStack Query; loopback :3000 |
| `apps/admin` | Separate Next.js administration application; loopback :3002 |
| `saha-dev-infra` | Compose dependencies, SQL baseline/migrations, isolated validation/chat templates |
| `bin/saha`, `scripts`, `deploy/host` | Host CLI, validation/installation and service/proxy configuration |
| `docs`, `security` | User, developer, operational, interactive architecture and security references |

The existing host uses native PostgreSQL plus Docker Redis, MinIO, Qdrant and
observability/mail services. AI and financial integrations remain configuration-
dependent. The UI uses local Geist/Fraunces fonts and a shared forest/sage/paper
palette; no hosted-font fetch is needed to build.

The original host checkout has a nested frontend Git repository. The prepared
ProjectSaha publication checkout includes the frontend as ordinary files so a
single clone contains all three applications. See [repository publishing](docs/REPOSITORY-PUBLISHING.md)
for the checkout distinction and upload status.
Saha's application source license has not yet been selected. Font licenses are
included in each application's `public/fonts` directory.

## Run the existing host

From a normal terminal with the installed service mapping:

```sh
cd ~/Downloads/saha
saha status
saha versions
```

For the October-migrated host, deploy the new social/project release through the existing setup:

```sh
bash scripts/migrate-social-workspaces.sh && saha versions --local
# After local feature acceptance:
saha online && saha versions
```

Both November migrations are required; the helper backs up, migrates, builds and starts locally. Stop on failure. Do not run
`next build` over a served `.next` directory. New hosts and older databases must
follow the [hosting runbook](docs/HOSTING.md) and explicit migration order first.
For local development, use [Development](docs/DEVELOPMENT.md), not the production
service ports while those services are active.
