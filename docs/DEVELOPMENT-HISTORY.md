# Saha development history

## Current objective — 2026-10-31

The owner has changed the primary product direction: Saha is a non-monetized open innovation platform for discovering openly usable patents and collaboratively developing projects. Preserve existing IP transaction features, but do not prioritize their expansion. Build excellent discovery, institutions, spaces, social collaboration and genuine end-to-end encrypted chat.

User clarification: “tag numbers” means **private internal space references**, not tax/registration IDs. Only space administrators and Saha platform administrators may see them. Institutions need public pages with posts/comments and administrator-controlled verification approval.

## Working rules

- Work in `/home/hitarth/Downloads/saha`. Marketplace is a separate Git working tree; preserve its pre-existing edits in four listing/API files. No clean/reset/checkout of user changes.
- Do not migrate the live database, restart services or rebuild the live `.next` tree during development. Deliver migrations and runbook with isolated tests first.
- Never label encryption at rest as E2EE. E2EE requires client-held keys and an established protocol, with explicit membership/revocation/device/recovery handling.
- Patent publication is not an open license. Preserve source, jurisdiction, rights evidence and review status; do not promise exhaustive internet coverage or unrestricted reuse.
- Keep this file current at each milestone and before stopping. An account rate-limit reset does not itself guarantee this agent automatically resumes; resume by reading this file.

## Baseline

- Prior architecture/review: `docs/REVIEW-2026-10-31.md` (transaction-heavy priorities superseded by the product direction above).
- Existing backend baseline: 379 passed with 15 DB tests and four async upload-read tests excluded; both Next applications typecheck. Details in prior review.
- Existing community chat is plaintext; proposal chat is server-encrypted. Neither is E2EE.
- Existing institutions absent. Communities, social posts/comments, library submissions/build declarations and admin moderation already exist.

## Plan and progress

1. [implemented; testing] Institutions as public community-backed pages; separate private reference/evidence storage; verification policy/request/review API and admin UI; public posts/comments and membership. New migrations are NOT applied to the running application database.
2. [implemented; testing] Saved-post visibility filtering, edit reclassification, vote/report target visibility, private-space post checks. Collaboration guards now accept confirmed email or legacy verified KYC; transactions unchanged.
3. [implemented; setup pending] Matrix/Element E2EE transport; dedicated keyless membership service account; encrypted-only rooms, verified account linking, room reconciliation, leave/remove revocation; old plaintext/server-decrypted transports return 410. No Matrix service configured or live E2EE test completed. Do NOT claim operational E2EE until deployed and tested.
4. [implemented; testing] Public homepage/Explore, curated discovery plus external database links, rights-evidence UI/API, public source-linked projects/task boards and project stage controls. Main dashboard now prioritizes open innovation; previous dashboard preserved at `/dashboard/marketplace`. Ten-feature roadmap in `OPEN-INNOVATION-PLAN.md`.
5. [implemented; testing] Private research collections, non-destructive source re-saving, private notes, saved searches and restored search URLs. No automatic alerts yet. Fifth migration: `2026-10-31-research-collections.sql`.
6. [validated offline; deployment gates pending] Latest backend run: **423 passed, 23 deselected, 5 warnings**. Only database-dependent tests were deselected. The four previously hanging upload tests now use realistic in-memory spooled multipart files and pass, with an actual bounded-read assertion. Frontend/admin production builds passed in isolated temporary directories, alongside TypeScript checks, Python compilation, CI/Compose parsing and both working-tree whitespace checks. Request integration cases require a dedicated `saha_test` DB; CI provisions Postgres/Redis and ordered schema, but that CI job has not been executed here. Local server execution is blocked by the socket sandbox.

## Resume checklist

Read this file and `git status` in both the root and `apps/frontend`. Read any most recent completion entries below. Continue the pending stage, preserve user edits, and update validation results. Do not assume migrations have been applied or external services configured.

## Milestone log

- 2026-10-31: Recorded changed direction and private-reference clarification before implementation. No live changes deployed.
- 2026-10-31: Implemented initial institutions/social/Matrix slices. Files primarily new routers/services, new frontend/admin pages; existing four user-edited listing/API files preserved. New legacy-chat cutover is a breaking deployment change: apply migrations and configure Matrix/Element before restarting. Keep documenting setup and regression checks.
- 2026-10-31: Executed base + August dependencies + four new October migrations in an isolated PostgreSQL 14 single-user database; reapplied all four successfully. Added collections migration and executed/reapplied it successfully too. No live database contacted. Temporary data directory: `/tmp/saha-collaboration-pg.RIqhmf` (not the application DB).
- 2026-10-31: Hardened email verification to bind the current address; old unbound links must be reissued. Existing MFA can no longer be silently reset by calling setup. Chat identity linking always requires a recent step-up token without financial KYC. Fixed step-up CORS, isolated account query caches, server logout, refresh single-flight and stale refresh guards. Latest validations still pending below.
- 2026-10-31: Owner said “Continue the development” while work was ongoing; objective unchanged. Optional question about licensing Saha's own code remains unanswered; no license selected or added.

- 2026-10-31: Compared all ORM metadata columns with the isolated PostgreSQL schema: **38 tables, 357 columns matched**. No live application database mutation.
- 2026-10-31: Added private collections/notes and saved searches, owner-scoped APIs and account-keyed UI state. Source re-saving preserves notes; withdrawn source metadata is hidden. Alerts remain future work.
- 2026-10-31: Notification streams now support owner-validated replay cursors and stable timestamp/ID ordering. Frontend uses bounded reconnect, fresh tickets and polling fallback; institution reviews and task assignments generate best-effort notices. A durable transactional notification outbox remains future work.
- 2026-10-31: Runtime Matrix policy now checks the service account remains keyless; personal identity linking always requires fresh step-up. Signup text emphasizes research/creation and prototyping. Added registration field limits and safe rejection of oversized bcrypt login input.
- 2026-10-31: Final milestone validation: 419 backend tests passed / 27 deselected / 3 warnings in 13.35s; frontend/admin `tsc --noEmit --incremental false` passed; `compileall`, YAML syntax and root/frontend `git diff --check` passed. No browser acceptance run at that milestone; later isolated production builds passed (see below). No deployments, service restarts or live chat calls.

## Next work and release gates

1. Run dedicated database integration tests on a host/CI runner that allows PostgreSQL/Redis sockets. The current CI configuration is prepared, not yet verified by a remote run.
2. Configure isolated Matrix/Element, use a keyless service account and complete every two-device acceptance check in `ENCRYPTED-CHAT.md`. Until then chat is an implemented integration, not operationally verified E2EE. Legacy message routes return 410 in this release.
3. Resolve the frontend Git delivery layout without losing the existing dirty working tree: root tracks a gitlink, but no `.gitmodules` or frontend remote exists. A clean checkout cannot deliver these local UI changes yet.
4. Follow the deployment runbook for backups, five ordered migrations and coordinated backend/frontend rollout. Do not build over the served `.next` directory.
5. Next product work: reproducibility notebooks, project milestones/contributor matching, moderation/governance and official-source ingestion with provenance. Search currently covers curated resources plus external links, not all internet patents. Saved-search automatic alerts and the remaining roadmap slices are unfinished.
6. Source-code licensing question remains unanswered; do not add a license without the owner's choice.

## Dependency and local validation follow-up — 2026-11-01

Owner requested completion of pending dependency/runtime checks and selected **local testing only** for chat. No permanent domain was chosen.

- Backend: `uv pip check --python .venv/bin/python` verified **102 packages**, all compatible. A manifest check confirmed every direct runtime and dev requirement is installed and within range. `uv lock --check --offline` passed. A pip-less uv environment is expected; installing pip is unnecessary.
- Frontend/admin: pnpm **9.15.4**, Node **20.20.2**. Frozen lockfile checks passed. Fresh isolated offline installs succeeded (58 frontend / 52 admin installed packages). `pnpm store status` passed integrity verification.
- Added `scripts/verify-js-dependencies.cjs` and a CI step: actual runtime/development roots, transitive runtime dependencies, peer ranges and Node engine constraints all pass (131 frontend / 122 admin dependency/peer checks). Missing optional packages include other platform binaries and opt-in integrations; these are not missing required dependencies. Recursive `npm ls` had been inspecting third-party development manifests in pnpm links, producing misleading missing-tool/version warnings.
- Native ARM64 Next.js bindings and PostCSS load successfully. Both **full production builds passed** using fresh temporary installs under `/tmp/saha-release-check-w0blpqfg`; served `.next` trees untouched. Frontend originally failed Google Fonts DNS: bundled the existing unchanged Geist/Fraunces WOFF2 subsets, original unicode ranges/fallback metrics, embedded copyright attribution and SIL OFL notice. No third-party font request is needed for build/runtime. Application source licensing is unchanged.
- Corrected upload test representations to use `SpooledTemporaryFile` as multipart uploads do. Previously excluded four tests now run; the oversized-input case proves the read stops before the whole payload is consumed. Latest complete non-DB suite: **423 passed, 23 DB tests deselected, 5 warnings in 12.88s**. Existing warnings concern deprecated status/constants and a deliberately short forged JWT test key; no test failures.
- Prepared `saha-dev-infra/local-checks/`: dedicated Postgres/Redis integration services, separate Synapse database, Synapse/Element, loopback-only HTTPS proxy, explicit schema order, fresh secrets and local CA/certificate. Generated files are ignored; secret permissions are 0600. Compose parsing, shell syntax, localhost certificate chain/hostname and registration-disabled configuration passed. Generator refuses to overwrite existing secrets.
- Local runner `python3 saha-dev-infra/local-checks/run_tests.py` fails explicitly when Docker is inaccessible, instead of marking skipped integration tests as successful. Database prerequisite checker now requires database name `saha_test`, new tables and Redis. No normal application `.env` or running service was changed.
- **Observed external blockers:** Docker API socket access denied; both AF_INET and AF_UNIX socket creation return EPERM. Image pulls/ARM64 container manifests, live DB/Redis connections, Matrix provisioning and two-device crypto/revocation/recovery checks cannot execute inside this session. Local setup is prepared and statically checked, not a running or certified E2EE deployment. Follow `saha-dev-infra/local-checks/README.md` from a normal terminal with Docker access. No network vulnerability database audit or remote CI run was completed.

Resume with the local test runner on a socket-enabled host; then follow the local chat acceptance steps. Do not repeat dependency installs or production builds unless package/source changes justify it. Frontend gitlink delivery layout remains a separate unresolved release constraint; preserve both working trees.

## Existing-host service mapping — 2026-11-01

Owner requested all features map to the existing `saha` CLI/service, nginx and Cloudflare setup.

- Inspected `/usr/local/bin/saha`, existing backend/frontend/admin systemd units, nginx sites, and `/etc/cloudflared/config.yml`. Actual public chain: `sahasolutions.com` + `www` → existing tunnel → nginx :80 → web :3000 / API :8000. Private admin: nginx :8080 → admin :3002 / API :8000. Existing tunnel denies all other hostnames. Did not read tunnel credential JSON or copy secrets.
- Fixed both web API base URLs: production uses same-origin `/api/` despite a developer `.env.local` containing localhost:8000. Development retains the configurable direct API URL. Preserved earlier user changes in frontend/lib/api.ts.
- Added `deploy/host/` with explicit mappings, five systemd units (`saha`, `saha-infra`, backend/frontend/admin), nginx sites, sanitized forwarded headers/edge trust, HTTPS forwarding for local tunnel peers, unbuffered SSE and query-free access logs. Existing native PostgreSQL and original Docker Compose project/volumes are retained. Infrastructure startup does not pull or recreate images. No public chat/admin routes added.
- Added repository `bin/saha`: compatible start/stop/online/offline/status plus routes/doctor/build and local-only startup. Grouped service starts local dependencies/apps; CLI gates tunnel startup on nginx readiness. Startup refuses missing/localhost browser builds; backend `ExecStartPre` performs a read-only model/schema check. Build requires both web services confirmed stopped, backs up old outputs, restores both on failure and never automatically starts services or migrates DB.
- `scripts/install-host.py` stages/verifies reviewable config, backs up current system files on apply, installs the global CLI and service mapping, tests nginx and reloads systemd definitions. It never starts/restarts services, enables boot startup, changes Cloudflare ingress or rewrites application secrets. Current host root files were **not** modified: this sandbox cannot write /etc or /usr/local and denies socket creation. The existing global CLI remains unchanged until applying the prepared installer from a normal terminal.
- Validation: both full production builds passed again in isolated temporary directories with deliberately hostile `NEXT_PUBLIC_API_URL=http://localhost:8000`; browser bundles contain no localhost:8000 API URL. systemd unit verification passed. Existing Cloudflare ingress validation passed. nginx reported staged syntax OK, then failed its socket-opening step with EPERM, so full nginx/runtime verification remains blocked. Prior complete non-DB suite: **431 passed, 23 deselected, 5 warnings in 12.02s**, with eight new hosting tests; subsequent tunnel-readiness retry test added (focused results below).
- Operator runbook: `docs/HOSTING.md`. From a normal sudo-enabled host terminal, validate/apply the installer, back up/apply missing migrations, stop apps, build, start locally, smoke test, then bring the existing tunnel online. Never overwrite served .next outputs or silently run additive migrations. Account-level Cloudflare cache rules were not inspected. Existing secure domain-cookie settings are preserved; plain LAN admin HTTP does not provide equivalent HTTPS cookie sessions.

Resume: read `docs/HOSTING.md`; complete privileged installation and socket-enabled checks outside this sandbox. Preserve the running service and both dirty Git working trees until rollout. Earlier local-test Matrix and frontend Git delivery constraints still apply.

- Final focused hosting validation: **9 passed** (including delayed tunnel readiness, fail-closed exposure, local startup, failed-build restoration and forwarded-IP/protocol handling). Syntax/whitespace checks passed after final edits.

## Privileged setup attempt — 2026-11-01

Owner explicitly authorized the required privileged host setup. A non-interactive sudo capability check failed because this execution environment sets `no new privileges`; sudo also reports that its system configuration is not owned by root in this sandbox. This is an execution-policy restriction, not missing authorization or an incorrect password. No supplied credential was stored in files or passed to a command. No privileged installer, migrations, service changes or public deployment could be executed. Continue from a normal host terminal, or a session whose permissions actually permit privileged host setup, using docs/HOSTING.md. Do not retry through alternate privilege-escalation routes in this sandbox.

## Host installer completed by owner — 2026-11-01

Owner supplied successful terminal output from `sudo python3 scripts/install-host.py --apply`: systemd verification, staged and installed nginx tests, and existing Cloudflare ingress validation all passed. Original host files are backed up at `/var/backups/saha-host-backup-kxzm1bx5`. Installer explicitly did not restart/start services or reload nginx. Next host actions: stop apps/tunnel, make a private PostgreSQL custom-format backup of the configured native `saha` database, apply only five October migrations in documented order, rebuild stopped apps, start locally and smoke test, then optionally bring the tunnel online. Agent sandbox restrictions still prevent executing those host actions here.

## Public HTTP 403 investigation — 2026-11-01

Owner reported all nine services active, local nginx ready, public readiness HTTP 403. No origin-versus-edge cause is proven yet. External browser-tool requests could not retrieve the site, and this sandbox cannot open network sockets. Added `saha diagnose` to compare direct backend, nginx with actual public Host, and public HTTPS; report server/CF-Mitigated/Ray ID and readiness-JSON validity without response bodies or secrets. Added explicit Saha user agent and reject HTML login/challenge HTTP 200 as readiness. Confirmed no suitable connected Cloudflare account tool is available. Focused hosting suite: 13 passed; syntax/whitespace checks passed. Next required evidence: owner runs `saha diagnose` from the normal terminal and supplies output; then inspect the specific edge rule/Access route or origin response indicated. No global Cloudflare security changes made or requested.

## Confirmed stale configured builds — 2026-11-01

Owner requested all host settings and tunnel-to-build mapping be checked. Re-read installed units/CLI/nginx/tunnel and validated ingress rules for apex, www and admin catch-all. All installed wiring matches repository; backend production configuration validates without issues. Found **actual source build directories still contain August 6 artifacts**: frontend `Fl0C7dCiYjFHCQO__LEax`, admin `aMwp6PvMGepI_QuOiySjC`, with all new collaboration routes absent. This is separate from public HTTP 403; runtime processes/public traffic cannot be inspected in socket-restricted agent session.

Corrected doctor's false-positive logic: require current collaboration routes and matching source build receipts. Added source fingerprint helper excluding secrets/generated output, CLI build receipts, compiled Next `X-Saha-Build` headers and startup-fixed backend header. Added `saha versions [--local]` for expected-versus-served identities; local and public version gates now apply to publication. Both updated production builds passed in isolated temporary directories and their compiled IDs/response headers/new route manifests were verified. Focused hosting tests: 17 passed; complete suite result follows. No live .next directories overwritten or services changed. Exact findings in `docs/HOST-AUDIT-2026-11-01.md`; rollout/version commands in `docs/HOSTING.md`. Owner must run the prepared commands on a normal host terminal because this sandbox cannot stop/restart services. Do not claim the live tunnel serves the new version until runtime identity checks pass.

- Final build-identity milestone validation: **440 backend tests passed, 23 database tests deselected, 5 warnings in 12.17s**. Both isolated production builds passed with compiled response IDs and required routes verified. Existing live build directories remain untouched and stale.

## Backend 502 root cause confirmed — 2026-11-01

Owner's local version output confirms updated frontend `frontend-f11c2343641ed5a11fce` and admin `admin-02394647a4d6b24fef32` are served; backend returns 502. Read actual `journalctl -u saha-backend`: ExecStartPre repeatedly fails because **all five October migrations remain unapplied**, listing nine new tables and six new columns. Existing schema objects passed the model comparison. This is not a wrong nginx upstream or a stale web build.

Prepared `scripts/migrate-open-collaboration.sh` for the owner's normal terminal: restrict to configured native PostgreSQL localhost:5432/saha, stop apps/tunnel, create a private pg_dump archive and check readability, apply only five additive October SQL files with ON_ERROR_STOP, run schema gate, start locally and check served versions. Never disables schema checks or runs the initial baseline. Leaves public tunnel stopped until `saha online`. `bash -n` and the non-mutating `--check` passed. No live SQL or service actions were executed in the agent sandbox. No web rebuild is necessary for this fix. Public 403 remains a separate outstanding check after local backend recovery.

## Public rollout verified by owner — 2026-11-01

Owner supplied successful `saha online` output. Local web, backend and private admin all return HTTP 200 with matching expected/served identities. Public web and backend through the existing tunnel also return HTTP 200 with matching identities:

- Frontend: `frontend-f11c2343641ed5a11fce`
- Backend: `backend-681d53a4ea28292a2775`
- Private admin: `admin-02394647a4d6b24fef32`

CLI confirmed `https://sahasolutions.com` online with readiness HTTP 200. Thus the former backend schema-startup failure and public 403 are no longer present in this verified operator run; the cause of the former 403 was not independently established. Tunnel-to-current-build mapping is now verified by response identity, not just active service state. No further rebuild/restart is required for this milestone. Matrix/Element two-device acceptance, broader feature browser tests, database integration suite/remote CI and frontend Git delivery layout remain separately outstanding; this result does not establish E2EE operation or completion of those tests.


## Unified UX and navigation — 2026-11-01 (in progress)

Owner requested a complete coherence/navigation pass and publication after code
changes. Replaced independent public/dashboard/auth framing with one root Saha
shell, a shared forest/sage/paper palette, stable primary navigation, grouped
workspace sidebar and explicit mobile menu. Redesigned home, workspace and auth
screens; added a getting-started page, route map, breadcrumbs and recovery pages.
Applied semantic colors to legacy screens while retaining their functionality.
Private admin now shares the palette/font and has grouped responsive navigation.

Fixed lost sign-in destinations (validated local next URLs, source selection,
registration continuation, hydration-aware guard), canonical institution routing,
KYC links now pointing to the actual marketplace verification flow, disabled-link
buttons, popover semantics/focus and narrow notification positioning. Public
listing SSR now uses an anonymous server-only absolute API URL; origin failures
reach retry UI rather than being silently treated as 404. Browser requests remain
same-origin; no changes to backend/database or host/tunnel mapping.

Seven navigation/server-fetch regression checks passed. Both TypeScript checks
passed before the final small accessibility refinements; production builds and
final checks in progress in `/tmp/saha-ux-release-xplxxt38`. No live `.next` has
been replaced. `systemctl is-active saha-frontend` still fails with "Failed to
connect to bus: Operation not permitted" in this session. Publication cannot be
performed from this environment; no alternative privilege bypass was attempted.
See `docs/UX-NAVIGATION.md` for route mapping and browser/release checklist.


### UX final review follow-up

Owner reiterated completion, code review and publishing/restarting the new build.
Both initial production builds passed; all 17 host-wiring checks passed (one
existing deprecation warning). Static HTML checks confirmed one header/main,
unique IDs and skip targets on home, sign-in, registration, guide and institutions.
All literal internal frontend links resolve to existing page routes.

Final review additionally removed conflicting focus-outline suppression, retained
header search parameters through sign-in, avoided tablet header crowding, linked
form errors/hints to inputs, fixed Shift+Tab from the initial dialog focus, and
constrained notification navigation to validated local application routes. Final
source-synchronized builds are being regenerated in the same isolated staging
folder. No new dependency or database migration is required.


### UX release validation complete — publication pending host execution

Final production builds succeeded, including TypeScript validity checks:

- Frontend: `frontend-b6715659bc2071fffdc5` (35 application routes plus not-found).
- Admin: `admin-3222fc3a4db4255ae339` (15 application routes plus not-found).

Final staged files exactly match application source fingerprints. Compiled
X-Saha-Build headers, build IDs, required route manifests and absence of localhost
API URLs in production browser bundles passed. Staged receipts are written under
`/tmp/saha-ux-release-xplxxt38/{frontend,admin}/.next/saha-build.json`.
Seven navigation/server-fetch regression tests and 17 host-wiring tests passed;
installed dependency ranges/peers/engines and both working-tree whitespace checks
passed. Final generated HTML checks confirmed one main/header, unique IDs, skip
links and labelled sign-in/registration inputs. New navigation tests are wired
into the frontend CI job; remote CI was not run.

No live build artifacts were overwritten and no host service was stopped or
restarted. Current sandbox cannot access the system service manager (EPERM).
Therefore the redesigned release is built and verified offline, **not published**.
Real browser interaction/mobile/screen-reader acceptance and live served-version
checks remain unverified. Run the gated stop/build/start-local/online/version
sequence in `docs/UX-NAVIGATION.md` from a normal terminal. No DB migration is
required for this UI release. Preserve the earlier frontend Git-layout and local
Matrix/Element acceptance follow-ups; neither was resolved by this UI pass.


### 2026-11-01 — social feed and standalone project expansion in progress

Owner added multimedia posts/member tagging and standalone invite-only projects with
external reference links. Implementing real attachment storage with post ACLs,
expressive reactions, mention editing and shared feed cards. Project source selection
is optional; new and existing projects become private, preserving memberships.
Reference links use stored platform/type metadata and bundled icons, with member-only
access and owner/author management. Matrix chat reuses the project's community scope.
Two new additive migrations are required: `2026-11-01-social-media.sql` and
`2026-11-01-project-workspaces.sql`. The earlier UX-only build fingerprints above are
now superseded; new builds and full verification are pending. Documentation refresh
includes the three interactive architecture pages and both drawio files, not just Markdown.
No host services have been changed; publication remains restricted by this sandbox.


### 2026-11-01 — social/workspace release verified offline; host rollout pending

Implemented shared feed/institution multimedia composer and cards, bounded protected
media storage, member mentions, expressive reactions, following/saved/search views,
threaded comments, link sharing and admin attachment review. Fixed counter updates
and rendering of replies whose parent was removed/outside the result window.

Projects can start without a resource and are invite-only. Both project API reads
and generic community settings enforce privacy; the migration converts older project
spaces/posts while preserving members. Added reference records with HTTPS URL,
platform/type badges, descriptions, filters, copy links, manager pins, ownership
rules, 200-reference limit and stale-edit protection. Project chat reuses the
existing Matrix community scope. Existing-user invitations grant membership
immediately; pending acceptance remains a future feature.

Validation:
- 469 backend non-DB tests passed; 24 DB-dependent cases deselected. The new 29-case
  unit suite covers URLs, private project loads, pin/edit permissions, media limits,
  access/ownership, canonical mentions and reaction authorization.
- 7 navigation/server-fetch and 5 mention-editor tests passed.
- Full frontend/admin production builds passed in `/tmp/saha-social-release-uxbxevwp`:
  frontend-b5504d0f93177e951687; admin-be777f81ae21acad88b3.
- Source hashes, BUILD_ID, compiled X-Saha-Build, required routes and absence of
  localhost API URLs in production browser bundles passed. Receipts written only
  to isolated staging builds. Backend source: backend-0fce8b086b4eba972cc8.
- JS required ranges/peers/engines passed; all 102 backend packages compatible.
- Both November migrations applied/reapplied on isolated PostgreSQL 14.24; 42
  model tables / 389 columns and optional source nullability matched. The first
  single-user invocation lacked `-j` and rolled back on line-splitting syntax
  errors; corrected invocations and repeat/schema checks passed. No live DB touched.
- Fixed test harness so non-DB tests do not probe the configured database; DB
  fixtures refuse anything except saha_test. A hung early unit check was stopped;
  the final complete non-DB run finished normally in 12.60 seconds.
- Three interactive architecture pages and two drawio files regenerated with
  177 source-declared handlers / 42 model tables; previous artifacts archived.
  Documentation index, user/developer/security guides, deployment instructions,
  roadmap, app/infra READMEs and changelog refreshed. Historical audits labeled.
- Current HTML IDs/anchors/JavaScript syntax and drawio references parsed; local
  documentation links checked. Whitespace checks passed in root and frontend.

Release helper: `bash scripts/migrate-social-workspaces.sh --check` passes without
mutating host state. The non-check form stops apps, backs up the configured native
DB, applies only both November migrations, builds, checks schema, and starts locally.
The older October helper now includes both November migrations and builds too.
Both scripts stop on failures and leave the tunnel stopped until `saha online`.

Latest `systemctl is-active saha` still returns bus access EPERM. User already
allows publication, but sandbox restrictions prevent it. No live build was replaced,
no service restarted, no tunnel changed. Browser/mobile/screen-reader acceptance,
isolated request integration, Matrix two-device acceptance and live served-version
checks remain outstanding. Frontend gitlink delivery remains unresolved. Current
instructions and exact versions are in docs/CURRENT-STATUS.md and docs/HOSTING.md.


### Owner-confirmed local social/workspace release

The owner supplied `saha versions --local` with HTTP 200 and matching served/expected
identities for frontend-b5504d0f93177e951687, backend-0fce8b086b4eba972cc8 and
admin-be777f81ae21acad88b3. All three current components are now confirmed served
through local/private nginx. This supersedes the earlier local-activation-pending
status; activation was performed outside the restricted coding session.

No public version output or migration/backup transcript accompanied this result.
Public tunnel confirmation remains pending via `saha online` and `saha versions`.
Do not rebuild or repeat migrations solely in response to this successful check.
Local workflow/browser and Matrix two-device acceptance remain distinct gates.


### Session consistency audit — implementation and validation in progress

Owner reported the signed-in homepage still advertises account creation and
requested a deeper session/bug review. Confirmed hard-coded homepage registration
CTA, independent hydration checks, no centralized profile validation, missing
login/register guest guard, and refresh treating 429/5xx as logout.

Implementing shared tested session lifecycle in frontend/admin: explicit restoration
status, cookie-only restoration, /users/me verification, retryable outage state,
cross-tab storage synchronization, same-origin refresh locking where supported,
account identity checks before refresh retry, late-response/session revision guards,
and account-scoped UI/cache cleanup. Home CTA/header/route guards now use the same
state. Media, avatar and vault operations use the shared authenticated request path;
external API paths are rejected and vault step-up remains intact. Auth form replies
cannot overwrite a later login/logout. Legacy persisted refresh-token fields are
excluded during hydration and rewritten from the safe allowlist.

First 30 session behavior tests pass (both app controllers, request races and actual
home CTA rendering); additional binary/step-up/URL tests and production builds are
pending. Earlier verified local social/workspace identities remain the served-release
evidence until this new session-fix release is built and activated. No DB migration
is expected. Keep docs and release status synchronized after final validation.


### Session review completed — verified artifacts, activation pending

Client fixes cover explicit hydration/restore states, authoritative /users/me,
cookie-only restore, guest-only forms, home/header agreement, transient failure
preservation, account identity checks before retry, late JSON/blob response guards,
same-origin login/logout synchronization without losing drafts on same-account
rotation, storage failure fallback and legacy persisted-field filtering. Shared
request handling now covers avatar/listing uploads and media/vault downloads,
keeps step-up headers, rejects external API paths and handles stale closures using
the current credential only for the same account.

Backend study also found refresh/logout races. Added advisory locking by refresh
family, fresh locked token/expiry recheck, replay invalidation and full family
logout (including rotated descendants). No schema migration or package added.
Existing stateless access tokens are still bounded by their expiry rather than
immediately revoked by family logout. Real concurrency tests are in the isolated
PostgreSQL suite and remain unexecuted here.

Validation:
- 44 client lifecycle/request/CTA/storage tests, 7 navigation/server-fetch and
  5 mention-editor tests pass. Session tests run against both app controllers.
- 473 backend non-DB tests pass; 26 DB cases deselected. Final expiry recheck
  passed the four targeted session-rotation cases after the full suite.
- Full frontend and admin production builds pass, with TypeScript checks.
- Candidate stage: /tmp/saha-session-release-mij_akxy. Frontend identity
  frontend-80c073dfbf82b9edccda; admin-e2b402ab5214fd3cecdf; backend source identity
  backend-d639a4f8ebfc8705c1a1. Source/receipt/BUILD_ID/header/routes and absence
  of localhost API URLs in browser bundles verified. Live .next outputs untouched.
- JS dependency/peer/engine checks pass; all 102 backend packages compatible.
- Session review/user/developer/security/hosting/status/changelog/app READMEs and
  interactive references updated. No new dependency or migration for this patch.

Latest systemctl probe still fails with bus EPERM. Previous social/workspace local
versions remain the last owner-confirmed served identities. Session patch activation
is pending normal-host execution of saha stop/build/start --local/versions --local,
then browser acceptance and saha online/versions. Do not rerun the November migrations
for this patch. Actual browser/mobile/accessibility, DB concurrency and Matrix device
checks remain distinct from the passing offline suites. No zero-bug claim is made.


### GitHub source publication prepared — network upload pending

Owner requested uploading all code to https://github.com/Hits17/ProjectSaha.git.
GitHub DNS resolution fails in this execution environment; no remote refs or
authentication could be verified and no upload is confirmed. Prepared a separate
source checkout at /home/hitarth/Downloads/ProjectSaha-publish on main with the
requested origin. Original host Git repositories and running builds are preserved.
Frontend source is included as ordinary files, resolving the otherwise incomplete
parent gitlink in the publication snapshot. A fresh snapshot avoids importing
unreviewed development history. Source, tests, migrations, lockfiles, deployment
templates and all documentation are included; local environments, dependencies,
compiled outputs and generated credentials are excluded. Pattern scans and
configured-secret comparison found only intentional example/test placeholders in
the candidate files. Publishing instructions are in docs/REPOSITORY-PUBLISHING.md.
Next step from a connected normal terminal: git -C
/home/hitarth/Downloads/ProjectSaha-publish push -u origin main. Never force push;
reconcile remote history if a normal push is rejected. This step publishes source
only and does not activate the pending session-consistency service release.

Publication validation: 422 files copied with matching content hashes before
strengthening the export-only ignore rules; all 422 are tracked, with no gitlinks
or missing application lockfiles/font notices. Staged whitespace checks and
git fsck passed. A source snapshot commit was created under the explicit
Saha source snapshot identity. The actual normal push to origin main also failed
with Could not resolve host: github.com; nothing was uploaded by this attempt.
