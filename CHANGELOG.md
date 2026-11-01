# Changelog

## 2026-11-01 — session consistency follow-up

- Fixed logged-in home CTA and signup/login routing; centralized validated session restoration in both apps.
- Preserved sessions on temporary refresh failures; guarded account changes, cookie identity mismatches, cross-tab state and delayed responses.
- Unified authenticated JSON/multipart/blob handling, retained vault step-up, and rejected external credential-bearing request paths.
- Serialized refresh/logout by token family and revoked descendants; added client and backend regression/concurrency cases.
- No new dependency/schema migration. Publication and browser/DB acceptance remain separate release gates.

## 2026-11-01 — collaboration UX and social/workspace release

- Unified public/workspace navigation, home journey, route mapping, account continuation and admin styling.
- Shared social composer/cards with bounded multimedia uploads, member mentions, expressive reactions, followed/saved feeds and threaded discussion.
- Independent invite-only projects; optional library source; private reference links with platform/type badges, search, manager pins and versioned edits. Existing tasks/stages and Matrix/Element handoff retained.
- Two November migrations; protected media access, reference permissions and isolated regression checks. The release requires DB migration and coordinated backend/web builds.
- All current interactive architecture pages/diagrams regenerated; user/developer/security/operations guides refreshed; historical audit evidence preserved and labeled.
- Publication, real browser acceptance, database request integration and two-device E2EE acceptance are tracked separately in [Current status](docs/CURRENT-STATUS.md).


## 2026-08-06 — Social feed, profile reputation, content safety

Design and rationale: [`docs/SOCIAL-FEED-DESIGN.md`](docs/SOCIAL-FEED-DESIGN.md).

### Feed and reputation

- **Posts, comments, votes, follows and saves.** Three post kinds (update /
  question / showcase), optional listing or library attachments, one level of
  comment threading.
- **Reddit's ranking algorithms, taken from their published `_sorts.pyx`**: hot
  ordering (`log10(score) + seconds/45000`) so early votes matter most and
  nothing stays on top forever, and the Wilson score lower bound at 80%
  confidence for comments so small confident samples can outrank large mediocre
  ones.
- **Two reputation tracks that are never summed.** *Standing* comes from posts
  and votes and gates social privileges (downvote at 50, community creation at
  250, flagging at 1000). *Track record* comes from completed deals and reviews
  and gates nothing — it is information shown to counterparties. Merging them
  would let someone farm engagement and arrive at a negotiation looking like a
  proven counterparty; a test asserts no combined-score column can be added.
- **Vote fuzzing deliberately not copied.** Reddit randomises displayed counts to
  deny bot operators a feedback signal — sound for an anonymous platform. Saha is
  KYC-verified with an append-only audit log, so fuzzing would only make the
  numbers untrustworthy.
- **Anti-gaming**: self-voting refused, one vote per member per item enforced by
  a unique constraint, reciprocal-vote rings decay at 1/n, editing after votes
  resets the score, deleting a downvoted post does not launder standing.
- **LinkedIn-style profiles** with platform-verified figures rendered above
  self-reported ones.

### Content safety

- **Disclosure guard** (advisory) — warns before a public post that reads like
  unpublished technical detail. Warns, never blocks.
- **Safety classifier** (restrictive) — detection is **intent × subject**, never
  subject alone, because this is a chemistry and manufacturing marketplace and a
  keyword blocklist would delete the platform's actual subject matter. Four
  outcomes: allow, flag, hold, block. Public visibility escalates ambiguity
  toward holding.
- **Only a human can release held content.** The classifier can take a post down;
  putting it back up requires an admin review. Enforced by an AST-walking test
  that fails if any function other than `review_post()` assigns the approved state.
- **Self-harm is met with support, not enforcement** — held rather than blocked,
  with a helpline rather than a policy citation.
- **Member reporting** that queues rather than removes: three independent reports
  pull a post, but a report alleging real-world harm pulls it immediately.
- **Admin moderation queue** (`/moderation` in the console), oldest-first, with
  every decision written to the append-only audit chain and the author notified
  either way.
- Both classifiers run in-process — member content never leaves the trust
  boundary to be classified, and neither module encodes any harmful procedure.

### Testing

385 tests (up from 276). The safety suite's false-positive cases outnumber its
detection cases on purpose: over-blocking would make the platform unusable for
exactly the members it is built for.

### Migrations

`2026-08-06-social-feed.sql` and `2026-08-06-content-moderation.sql` — both
additive and idempotent, both require `postgres`.

## 2026-08-05 — Security audit + hardening pass

A full security review (`security/`) produced 38 findings; this change addresses
all of them. **Staged, not deployed** — the schema migration needs `postgres`
credentials. See [`security/DEPLOY-2026-08-05.md`](security/DEPLOY-2026-08-05.md)
for the sequence and rollback.

### Live on the host

- **Data-plane services bound to loopback.** MinIO, Redis, Qdrant, Mailpit,
  Grafana, Prometheus and Loki published on `0.0.0.0` with default or absent
  credentials, on a shared network. Anyone on that network reached the vault
  bucket (`minioadmin`/`minioadmin`), every platform email including
  verification tokens, and the AI session cache holding creators' invention
  descriptions in plaintext — with no account and no application interaction.
  This was the cheapest total-compromise path in the audit. Grafana's
  `admin`/`admin` rotated. *(SAHA-002, 006, 012, 028)*

### Confidentiality

- **Tiered disclosure.** `ListingResponse` served both the owner view and the
  public browse endpoints, so `GET /api/v1/listings/public` returned the private
  description, the complete bill of materials and confidential vault filenames
  to unauthenticated callers through an internet-facing proxy. For most listed
  assets the BOM *is* the invention. Split into `PublicListingResponse` (T0) and
  `OwnerListingResponse` (T2); search results carry the teaser tier; `offset`
  bounded. *(SAHA-003)*
- **Vault key versioning.** The encryption key was the placeholder committed in
  `.env.example` — every object and every negotiation message was decryptable by
  anyone who had read the repository, with no rotation mechanism. Objects now
  record the key version that encrypted them, `scripts/rotate_vault_key.py`
  backfills, and placeholder key material is rejected in *every* environment.
  *(SAHA-001)*
- **Negotiation plaintext no longer leaves the trust boundary.** The contact-info
  classifier POSTed every message to a third-party inference API to answer a
  yes/no question. Replaced with deterministic in-process detection; a data-tier
  policy routes confidential and trade-secret AI functions to self-hosted
  inference and fails closed for unclassified ones. *(SAHA-013)*
- **Contracts encrypted and digest-verified**; bulk member emails removed from
  list responses. *(SAHA-021, 016)*

### Transaction integrity

- **Escrow release is buyer-only.** `/disburse` used the either-party predicate,
  so the seller could transfer the escrow to themselves the moment the buyer
  funded it — no approval, inspection period or dispute window. Release is now
  attributed and requires step-up re-authentication. *(SAHA-007)*
- **Contracts require both signatures.** `/sign` executed on one party's call,
  recorded nothing about who signed, and left the DocuSign envelope permanently
  null. New `contract_signatures` table binds each signature to the contract's
  SHA-256; redrafting clears prior signatures. *(SAHA-008)*
- **One executed deal per listing**, enforced by a row lock and a partial unique
  index; concurrent disbursement closed by `SELECT … FOR UPDATE`. *(SAHA-037, 032)*
- **Mock payments are development-only** — mock mode marked escrow funded with no
  money moving, and escrow funding releases the seller's vault. *(SAHA-036)*

### Evidentiary integrity

- **`audit_logs` is now a hash chain** over an RFC 8785-style canonical
  serialisation, with an append-only trigger. Altering, deleting or reordering
  any row breaks every subsequent hash. Only pseudonymous identifiers and content
  digests are hashed, so erasure rights and immutability coexist. *(SAHA-014)*

### Identity and session

- **KYC mock mode gated on `APP_ENV is development`** — the flag alone was true
  on the public deployment, letting any anonymous registrant self-approve to
  VERIFIED, the status gating listings, proposals, transactions and vault
  download. The Persona webhook signature check no longer passes unconditionally.
  *(SAHA-004)*
- **`APP_ENV` is a closed enum.** The deployed value was `staging`, which matched
  neither `production` nor `prod`, so every production guard was a silent no-op
  on a public host. Staging is now hardened exactly like production. *(SAHA-005)*
- **Step-up re-authentication** for escrow release, contract execution and vault
  egress; **MFA mandatory for administrators**. *(SAHA-015)*
- **TOTP codes are single-use** — an intercepted code was replayable for up to 90
  seconds. *(SAHA-030)*
- **`python-jose` → `PyJWT`** behind one module, with issuer/audience assertion
  and a `jti` on every token. *(SAHA-026)*
- **Admin console no longer persists the refresh token** to `localStorage` — the
  control plane had weaker token storage than the marketplace. *(SAHA-009)*
- **SSE stream takes a 60-second scoped ticket**, not the access token, which was
  landing in nginx access logs. *(SAHA-017)*
- Secure cookie flags, plaintext CORS origins rejected. *(SAHA-010)*

### Infrastructure and input handling

- **Client IPs resolve through a trusted-proxy chain.** nginx appends to
  `X-Forwarded-For` and the backend read element `[0]` — the client-supplied one
  — so rate limits were bypassable by header rotation and audit attribution was
  forgeable. *(SAHA-011)*
- **Uploads identified by magic bytes**, read in bounded chunks aborting at the
  cap rather than after buffering the whole body; filenames normalised; storage
  keys are opaque UUID paths. *(SAHA-018, 031)*
- **Deep `/health` is admin-only** and no longer echoes exception text.
  *(SAHA-019)*
- Rate limits on KYC, vault download and anonymous browse; SMTP TLS
  configurable; listing view counts deduplicated. *(SAHA-020, 027, 038)*

### Testing and CI

- **Test suite 141 → 274.** Added `tests/conftest.py` — there was no integration
  harness at all, which is why a response-model leak (SAHA-003) and a
  wrong-authorization-helper bug (SAHA-007) survived the previous suite: both are
  invisible to unit tests.
- **Deny-by-default routing test** walks the live route table and fails on any
  route without an authentication dependency.
- **CI pipeline** (`.github/workflows/ci.yml`) — pytest, ruff, bandit, pip-audit,
  semgrep, gitleaks over full history, plus six audit-derived invariants that
  generic scanners would miss (no `0.0.0.0` container ports, no credentials in
  query parameters, no placeholder key material, message service never imports
  the LLM client, admin store never persists a refresh token).
- `tests/test_persona_webhook.py` previously **asserted the vulnerability** as
  intended behaviour; inverted.

### Migration

`saha-dev-infra/migrations/2026-08-05-security-hardening.sql` — additive and
idempotent. Adds `contract_signatures`, audit-chain columns and trigger, vault
key/digest columns, escrow release attribution, TOTP counter, and the
single-executed-deal index. **Requires `postgres`** (six tables are
postgres-owned).

## 2026-07-03 — User profile page + account menu

**Profile page** (`/dashboard/profile`) — every member's account home.

- **Identity lock**: name and email are editable only until KYC verifies the
  identity (`PATCH /api/v1/users/me`; per-field 403 once verified — the
  marketplace trades on verified identity). Changing the email pre-KYC resets
  `email_verified` and re-sends the verification link.
- **Profile pictures**: `POST /api/v1/users/me/avatar` (JPEG/PNG/WebP ≤ 2 MB;
  SVG/GIF rejected), stored plain in MinIO under `avatars/<user_id>/…` and
  served through authenticated `GET /api/v1/users/me/avatar` +
  `GET /api/v1/users/{id}/avatar` — never raw storage URLs. New `users.avatar_key`
  column (`saha-dev-infra/migrations/2026-07-02-user-avatars.sql`; ALTER needs
  the table owner, `sudo -u postgres`). `UserResponse` gains `has_avatar`.
- **Password change**: `POST /api/v1/users/me/password` (current + new, policy
  enforced) revokes every *other* session's refresh token — the session making
  the change keeps its cookie.
- **Header account menu**: the nav's Security item, the email text, and the
  standalone sign-out button are replaced by an avatar dropdown (picture or
  initials) with Profile / Security / Sign out.
- Tests: 121 → **138 passing**. Versions: backend 0.4.0, frontend 0.3.0.

## 2026-07-02 — Open Innovation Library + settlement/auth hardening

**New feature: Open Innovation Library** — admin-curated open-source patents and
research papers members can build on royalty-free (engagement driver: free R&D
raw material that feeds communities and future listings).

- Schema: `open_resources` table + `open_resource_type` enum
  (`saha-dev-infra/migrations/2026-07-02-open-resources.sql`).
- Backend: `GET /api/v1/open-resources[/{id}]` (any logged-in member; view-count
  tracked) + admin-only, audited curation CRUD under `/api/v1/admin/open-resources`.
  License field restricted to a vetted open-license vocabulary (public domain, CC,
  MIT/Apache/GPL, royalty-free pledge, defensive publication); categories mirror
  community topics so resources map to R&D communities.
- Marketplace app: `/dashboard/library` browse page (search, type/domain filters,
  outbound source links) + "Open Library" nav item.
- Admin console: `/resources` curation page (create/edit/archive/restore).
- **Member submissions with admin approval**: verified members submit resources via
  `POST /api/v1/open-resources/submissions`; entries land as `status='pending'`
  (new `open_resource_status` enum — pending/approved/rejected; schema in
  `saha-dev-infra/migrations/2026-07-02-open-library-v2.sql`). Admins get an
  in-app notification and work a pending queue on the admin `/resources` page;
  `POST /api/v1/admin/open-resources/{id}/approve` or `/reject` notifies the
  submitter either way (rejection can carry a reason).
- **"I'm building this" declarations**: verified members publicly declare they're
  developing a resource (`open_resource_builds` table, unique per user+resource,
  optional 500-char note) via `POST`/`DELETE /api/v1/open-resources/{id}/build`
  and `GET /{id}/builders`. Build counts surface on library cards and the admin
  table — the engagement funnel is now resources → active builds → listings.
- **Discuss in community deep link**: each library card links to
  `/dashboard/community?topic=<category>`; the community page now seeds its
  topic filter from that query param, routing readers straight into the
  matching R&D community.
- **Weekly digest**: an in-process scheduler (started in the FastAPI lifespan;
  multi-worker-safe via a Postgres advisory lock) notifies every active member in-app plus
  best-effort email ("N new open resources this week — Clean Energy (5), …")
  once `LIBRARY_DIGEST_INTERVAL_DAYS` (default 7) have passed and new approved
  resources exist since the last run; idempotency rides on the newest
  `library.digest` notification. New settings `LIBRARY_DIGEST_ENABLED` (default
  true) and `LIBRARY_DIGEST_INTERVAL_DAYS` (default 7), documented in
  `apps/backend/.env.example`.
- **Demand-gap cross-link**: `POST /api/v1/search` now returns
  `open_resource_suggestions` (up to 3 open resources matched on intent
  keywords) whenever fewer than 3 listings match; the Discover page renders a
  "No listings yet — build it yourself" section linking into the library.
- Tests: 97 → 114 → **121 passing** (validation + route-protection wiring, then
  submissions/approval, build declarations, and digest/search cross-link
  coverage). Backend API version bumped 0.2.0 → 0.3.0.

**Fixes**

- **Stripe live-mode escrow**: `confirm_escrow_funded` no longer re-confirms the
  PaymentIntent when the `payment_intent.succeeded` webhook fires (re-confirming a
  succeeded intent errors and would have wedged funding in retry loops), and the
  manual buyer `/escrow/confirm` endpoint now refuses to mark escrow funded in live
  mode — funding proof comes only from the signature-verified webhook. (Mock-mode
  dev flow unchanged.)
- **Disbursement guard**: refuse disbursement when fees exceed the deal value
  instead of silently completing with no seller transfer.
- **MFA brute-force**: wrong TOTP codes now count toward account lockout like
  wrong passwords.
- **Realtime notifications**: the SSE stream now refreshes the access token when it
  expires instead of letting `EventSource` retry a stale URL in a 401 loop.
- **Admin console MFA**: login page reveals an authenticator-code field when the
  account has MFA enabled (previously an MFA-enabled admin could not sign in).

## 2026-07 — Enterprise upgrade (pre-public-launch)

A three-phase hardening and feature pass to bring every layer to enterprise grade.
Backend test suite grew 73 → **97 passing**; frontend `tsc` clean and `next build`
green across 21 routes.

### Phase 1 — Foundation

**Backend security**
- Universal rate limiting: `SlowAPIMiddleware` `default_limits` protects **every**
  route; stricter per-route tiers on money-movement (settlement) and AI/upload
  (listing dialogue, contract drafting, file upload). Tiers centralized in
  `app/core/ratelimit.py`.
- Request body-size guard middleware (1 MB JSON / 50 MB multipart) → 413.
- Security headers: Content-Security-Policy, Permissions-Policy,
  Cross-Origin-Opener-Policy (added to the existing nosniff / frame-deny / HSTS set).
- Account lockout after repeated failed logins (configurable threshold + cooldown, 429).
- Schema: `failed_login_attempts`, `locked_until`, `email_verified`,
  `email_verified_at`, `mfa_enabled`, `mfa_secret` on `users`.

**Frontend design system** (`apps/frontend/components/ui/`, zero UI-library deps)
- Institutional-trust tokens (warm-neutral surfaces, navy ink, gold accent,
  Fraunces serif display) via Tailwind v4 `@theme`.
- Component library: Button, Card, Badge, StatTile, PageHeader, form fields,
  Skeleton/EmptyState/ErrorBanner, sortable Table, accessible Dialog/ConfirmDialog
  (focus trap), Toast system, inline SVG icons, charts.
- React Query provider + typed hooks over the API client.
- Shell, dashboard, listings, proposals, transactions, login, and register
  refactored onto the system.

### Phase 2 — Security depth

- **TOTP two-factor auth** (RFC 6238, dependency-free; secrets AES-256-GCM-encrypted)
  with setup/enable/disable/status endpoints and a login MFA gate.
- **Password policy** (`app/core/passwords.py`): ≥12 chars, letters+numbers,
  common-password denylist.
- **Email verification**: signed-token issue on register + resend + confirm; opt-in
  `require_email_verified` gate.
- **httpOnly, SameSite refresh cookie** on login/refresh/logout — the long-lived
  refresh token is no longer stored in JS-accessible storage; the frontend keeps
  only the short-lived access token.
- Content-Disposition header-injection fix on vault downloads (RFC 5987 encoding).
- IDOR sweep (clean) and XSS review (no dangerous sinks).
- New pages: `/dashboard/security` (MFA + email verification) and `/verify-email`.

### Phase 3 — Features

- **Real-time notifications**: `notifications` table + service + REST endpoints and
  a Server-Sent Events stream. Raised on proposal submit/counter/accept/message,
  escrow funding, and disbursement. Web app shows a live notification bell.
- **Analytics charts**: zero-dependency SVG chart set (bar/sparkline/donut) applied
  to the demand-intelligence dashboard.
- **Onboarding checklist** on the dashboard (email → KYC → first listing → MFA).

### Migrations

Apply in date order (existing DBs):
`saha-dev-infra/migrations/2026-07-01-auth-hardening.sql`,
`saha-dev-infra/migrations/2026-07-01-notifications.sql`. Both are folded into
`init-scripts/01-schema.sql` for fresh installs. Note: the auth-hardening
`ALTER TABLE users` requires the table owner (`sudo -u postgres psql`).

### Remaining roadmap

Saved searches + demand alerts; AI buyer↔listing match recommendations and
valuation hints; a browser end-to-end pass on the cookie-auth cutover; and
refactoring the remaining pages (discover, materials, community, admin, detail
views) onto the design system (they inherit the global tokens today).
