# Open collaboration release preparation

Updated 2026-11-01. The owner previously confirmed deployment of the October release.
The subsequent social/workspace release has not been published from this coding
sandbox. On that existing host use `bash scripts/migrate-social-workspaces.sh`;
it performs backup, the two November migrations, build and local startup. Existing
projects become private and associated posts become community-only; memberships
remain. Source selection becomes nullable. No old messages or financial records
are rewritten. See [Hosting](HOSTING.md) and [Current status](CURRENT-STATUS.md).

No live migrations, service restarts, chat account provisioning or deployment were performed during development. Existing services continue to run their existing build until an operator deploys this release.

## Schema order

For a fresh test database, the initial schema already contains communities, notifications and the open library. Do not blindly reapply every historic migration by alphabetical order. This release was checked offline against the initial schema followed by:

1. `2026-08-05-security-hardening.sql`
2. `2026-08-06-social-feed.sql`
3. `2026-08-06-content-moderation.sql`
4. `2026-10-31-open-collaboration.sql`
5. `2026-10-31-encrypted-chat.sql`
6. `2026-10-31-resource-provenance.sql`
7. `2026-10-31-open-projects.sql`
8. `2026-10-31-research-collections.sql`
9. `2026-11-01-social-media.sql`
10. `2026-11-01-project-workspaces.sql`

For an existing database already through August's hardening/social migrations, apply the five October migrations, then both November migrations in the order above, after a verified backup. They add columns/tables and do not rewrite old messages or financial records. They assume the existing application role `saha`; adapt grants deliberately if your deployment uses a different role.

The five October and both November SQL migrations were executed and reapplied successfully in a temporary PostgreSQL 14 single-user database. The sandbox prohibits socket creation, so this is real schema/idempotency validation, not a live ASGI/PostgreSQL integration test. The production database was not contacted.

## Chat cutover

The new release deliberately disables legacy community/proposal chat reads and writes with HTTP 410. Configure Matrix/Element and complete the real-client acceptance tests in `ENCRYPTED-CHAT.md` **before** deploying this release to ordinary users. Otherwise the UI honestly reports encrypted chat unavailable; it does not fall back to plaintext.

If existing users need old message records, establish a participant-authorized archival/export process separately. Never relabel historical plaintext/server-decrypted messages as end-to-end encrypted or copy them into an open public feed.

## Institution policy

Institution pages are public, but verification is not automatic. New pages start unverified. In the admin portal, Institutions & Spaces lets a platform administrator enable verification requests, inspect private references/evidence, and approve/reject/revoke with a meaningful reason. Owners cannot approve their own institutions. Changing the institution name or official URL invalidates the badge and requires review again.

Private reference numbers are available only to the space owner and MFA-qualified platform administrators (the existing `admin` role). A community moderator is not a platform administrator and does not get reference access.

## Application rollout and smoke checks

- Deploy backend and frontend together after migrations. Preserve existing user edits and build a separate release artifact; do not build over the currently served `.next` directory.
- Confirm anonymous home/Explore/institution browsing; project detail/tasks/references must be hidden from nonmembers; an unconfirmed user cannot create/post/contribute, while a confirmed-email user can without financial KYC.
- Confirm transaction endpoints still use verified-KYC guards and remain reachable through the marketplace/transaction navigation.
- Inspect a public institution response, feed, project response and discovery result: none may contain a private reference, request evidence or review note.
- From a different ordinary member and community moderator, private-reference endpoint must return 403. From the owner and an MFA-qualified platform admin, it must work.
- Toggle verification requests off/on, request review, review as a different platform admin, and edit name/domain to prove the badge is invalidated.
- Create independent and source-linked projects; reject outsider self-join and public visibility changes; invite existing users, add references/manager pins and assign tasks and test stale task updates return 409. Test unauthorized task changes are rejected.
- Test post edits and saved posts after revocation/moderation; public/private space boundaries must hold.
- Perform Matrix's two-client encryption, membership revocation, outage and recovery checks before launch. Never infer E2EE success from a green mocked test suite.

## Known delivery constraint

The parent repository currently stores `apps/frontend` as a Git gitlink with no `.gitmodules` and no frontend remote configured. This development session did not rewrite the repository layout or discard that working tree. Before pushing/deploying via a clean CI checkout, either import the frontend into the monorepo or configure an accessible frontend repository/submodule with recursive checkout. A local typecheck is not proof that a clean checkout contains these new UI files.

Current tests, unresolved items and resume instructions are recorded in `DEVELOPMENT-HISTORY.md`.

## Local validation environment

The owner selected local testing only. `saha-dev-infra/local-checks/README.md`
contains the prepared isolated PostgreSQL/Redis integration runner and localhost
Matrix/Element HTTPS setup. Generated secrets and local certificates are ignored
by Git; do not reuse the test server identity for production.

Both full web production builds now pass in separate temporary directories from
fresh offline frozen-lockfile installs. The frontend bundles the existing fonts
locally, removing Google Fonts DNS access from compilation. The running builds
were untouched. Live services and browser/E2EE acceptance remain unverified:
this agent sandbox denies Docker access and socket creation.
