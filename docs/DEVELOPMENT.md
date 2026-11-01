# Develop and validate Saha

Updated 2026-11-01. Read [Current status](CURRENT-STATUS.md),
[architecture](architecture/README.md) and [history](DEVELOPMENT-HISTORY.md) first.

## Repository

- `apps/frontend`: Next.js member/public interface, shared shell and social/projects UI.
- `apps/admin`: separate Next.js private control plane.
- `apps/backend`: FastAPI, SQLAlchemy services/models, storage/Matrix adapters.
- `saha-dev-infra`: existing infrastructure, explicit SQL migrations, isolated tests/chat.
- `bin/saha`, `deploy/host`, `scripts`: existing-host mapping, schema/build/release gates.

The original host checkout contains a separate frontend Git repository tracked as
a gitlink without `.gitmodules`. Preserve that working copy. The prepared ProjectSaha
publication checkout flattens the frontend into ordinary tracked files, making all
three apps available from one clone. See [repository publishing](REPOSITORY-PUBLISHING.md)
for preparation, upload status and commands; repository publication does not deploy
the running services.

## Dependencies and local development

Validated local toolchain: Node 20.20.2, pnpm 9.15.4, Python 3.11.15. Each web app
pins pnpm in package.json. Run commands from that app directory, not an unrelated
home directory that selects a different Corepack version. `pnpm install --frozen-lockfile`
and backend `uv sync --all-extras --frozen` reproduce lockfile dependencies when
network/package caches are available. No new package is needed for this release.

Run `pnpm dev` in frontend (port 3000), `pnpm dev` in admin (configured port 3002),
and `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000` in backend for a
separate local development setup. Do not collide with active production listeners.
Use the checked-in example environment, private credentials and an isolated DB.
Production API URLs are same-origin; development may use NEXT_PUBLIC_API_URL.
Fonts are bundled locally. Never commit `.env` files, tokens or generated secrets.

## Verification

From repository root:

```sh
node scripts/verify-js-dependencies.cjs
node scripts/test-ux-navigation.cjs
node scripts/test-social-mentions.cjs
node scripts/test-session-lifecycle.cjs
```

From backend:

```sh
.venv/bin/pytest -q -m 'not requires_db'
```

Non-database tests do not probe the application DB. Database fixtures only target
`saha_test`; CI requires database/Redis prerequisites before running all tests.
Use [isolated local checks](../saha-dev-infra/local-checks/README.md) for request-level
integration tests, including project invitations/references and membership revocation.
Schema order is in [collaboration deployment](OPEN-COLLABORATION-DEPLOYMENT.md).
Do not run fixtures or a seed against the real application database.

Run `pnpm exec tsc --noEmit --incremental false` in each web app. Production builds
must be staged separately or run via `saha build` after apps are stopped. The CLI
adds identity receipts and validates current routes; a raw `pnpm build` is not the
complete host release process. Verify navigation, forms, media playback, mentions,
keyboard/focus, errors, mobile layouts and screen-reader labels in a real browser.

## Documentation and contribution conventions

Regenerate all three interactive pages and both diagrams using
`python3 scripts/update-architecture-docs.py`. Update the relevant user/security/
operations guide, `CHANGELOG.md`, and append actual evidence to development history.
Keep historical audit findings dated. Do not call a feature deployed from a build
result, or E2EE certified from mocked Matrix tests. See [Documentation audit](DOCUMENTATION-AUDIT.md).

Use server-side membership/ownership checks, bounded uploads, allowlisted URL
schemes and escaped text. Keep external files on their providers; reference cards
must not cause server-side remote URL fetching. Use identity-safe authenticated
media requests and revoke temporary blob URLs. Tests should cover behavior and
cross-user boundaries, not mirror JSX implementation details.

Session architecture, review findings and manual acceptance are in [Session consistency](SESSION-CONSISTENCY.md). Backend refresh/logout concurrency cases require the isolated test database.
