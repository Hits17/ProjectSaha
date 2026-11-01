# Session consistency review and fixes

Updated 2026-11-01. Trigger: a signed-in member still saw an account-creation call
to action on Home. Review covered both web stores, hydration, providers/layouts,
login/register/logout, request retries, binary uploads/downloads, backend token
rotation, cookie settings and existing authorization guards.

## Findings and implemented fixes

| Finding | Resulting behavior |
| --- | --- |
| Home signup CTA was hard-coded | Signed-in members see “Continue to your workspace”; confirmed guests see “Join the community”. |
| Hydration/readiness checks differed between components | One explicit loading/authenticated/anonymous/unavailable lifecycle drives header, home and route guards. |
| Cached profile/token was treated as sufficient UI state | Restore validates `/users/me`; account-dependent screens wait until validation completes. Home/guide retain their public content. |
| Cookie-only session could not recover without a cached user | Bootstrap can exchange the httpOnly refresh cookie and load the authoritative profile. |
| Signed-in members could revisit signup/login forms | Guest-only guard redirects to a validated `next` destination; email verification remains accessible while signed in. |
| Any refresh HTTP failure cleared authentication | Invalid-session 401 clears it; network failures, 403 edge denials, 429 and 5xx retain credentials for retry. |
| Shared cookie could supply another account's refresh token | Profile identity is checked before publishing a rotated token or retrying the original operation. Mismatch signs out locally. |
| Delayed response could update a later session | Revision checks reject responses after logout/account change, including after JSON/blob body reads. Login/logout completion also respects newer sessions. |
| A late 401 could reject a token another request had already rotated | Same-session requests reuse the newer credential; concurrent refresh is single-flight. |
| Binary uploads/downloads bypassed normal refresh handling | Avatar, listing uploads, social/admin media and vault downloads now share the session-aware client; multipart boundaries remain browser-generated and vault step-up is retained. |
| API helper accepted an arbitrary URL | It rejects external/protocol-relative/control-character paths before attaching credentials; vault paths are constrained to their API family. |
| Separate tabs could retain obsolete login/logout state | Same-origin storage events reconcile login/logout/account changes. Same-account token rotations do not unmount forms or erase drafts. |
| Browser storage denial could interrupt state writes | In-memory fallback keeps this tab usable; persisted fields are allowlisted, legacy refresh-token fields are discarded. |
| Refresh and logout could race on a token family | Backend serializes family operations, rechecks the token under a row lock, invalidates replayed families and revokes all descendants on logout. |

## Session lifecycle

Both applications explicitly hydrate their own store, mark it as checking, then
validate a cached bearer or recover through the refresh cookie. Only a server
profile makes the UI authenticated. A known invalid session becomes anonymous;
uncertain availability becomes a retry state rather than a misleading signup CTA.
An explicit local sign-out marker suppresses automatic cookie restoration after a
failed logout request. Long-lived refresh tokens are not persisted in localStorage;
short-lived access tokens and profile hints retain the existing persistence model.

Same-tab refresh callers share one exchange; browsers with Web Locks also serialize
same-origin exchanges across tabs. Backend locking remains authoritative. Public
and private admin origins have separate stores and authorization requirements;
this is not cross-origin SSO. The server remains the authority for every action.

On storage account changes, protected content is unmounted before accepting the new
profile. Public frontend query caches and component state are scoped to account
identity. A refresh for the same account updates credentials/profile without
unmounting the current form. Invalid or malformed token expiry hints are treated
as expired; client decoding never grants server authorization.

## Verification

- `node scripts/test-session-lifecycle.cjs`: 44 checks cover both app controllers,
  actual home CTA rendering, cookie-only recovery, expiry, failed refresh, concurrent
  callers, cross-account cookie mismatch, delayed responses, binary reads, step-up
  failures, external URL rejection, persisted-field filtering and blocked storage.
- Existing navigation/server-fetch and mention-editor checks remain passing.
- Backend non-database suite: 473 passed, 26 database cases deselected. New branch
  tests verify rechecking after lock acquisition, replay invalidation and family logout.
- Two new PostgreSQL concurrency cases are included in the isolated DB suite:
  simultaneous refresh, and logout racing rotation. They still require execution
  against `saha_test`; mocked tests do not prove live database scheduling.
- Full frontend/admin production builds passed. Exact identities and deployment
  evidence are recorded in [Current status](CURRENT-STATUS.md).

## Browser acceptance on the host

1. Sign in and return Home: workspace CTA/account menu agree; no signup flash during reload.
2. Open `/login?next=/projects` and `/register` while signed in: redirect without showing a form.
3. Reload with an expired access token and a valid cookie: recover the same account.
4. Open two tabs; sign out or change account in one: the other clears old private content.
5. Rotate a same-account token while composing: preserve the draft and retry requests correctly.
6. Simulate offline/503/429 during restore or refresh: keep a retry path without claiming the account is invalid.
7. Upload an avatar/post image and download an authorized vault file after token expiry; retain step-up rules.
8. Test storage-disabled/private browsing, keyboard navigation and mobile layouts.

## Limits

This work is not a zero-bug or enterprise-certification claim. Browser acceptance,
real DB concurrency and remote CI remain unverified here. Stateless access tokens
already issued can remain usable until expiry; family logout revokes refresh
capability, not every already-issued bearer instantly. If storage is blocked and
logout cannot reach the server, a local sign-out cannot guarantee revocation across
future reloads/devices. HTTPS/cookie policy still applies; do not weaken production
cookies to make private plain-HTTP access persistent. Browsers without Web Locks
may hit safe replay rejection during simultaneous cross-tab rotation.

No new package or schema migration is required for this patch. Deploy backend,
frontend and admin together using the stopped-build/local-verification sequence
in [Hosting](HOSTING.md). No existing live build was overwritten during validation.
