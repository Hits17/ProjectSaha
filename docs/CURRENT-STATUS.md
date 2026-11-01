# Current implementation and release status

Updated 2026-11-01. This distinguishes source implementation, offline validation
and operator-confirmed deployment. Historical audits retain their original context.

## Implemented in the current source

| Area | Implementation | Limit |
| --- | --- | --- |
| Shared UX | Common home/workspace navigation, page map, breadcrumbs, account continuation, design tokens, local fonts and responsive admin | Real browser/mobile/screen-reader acceptance outstanding |
| Social feed and institution posts | Shared multimedia composer/cards, member mentions, hashtags/search, six reactions, comments/replies, follows, saved feeds, link sharing | No polls, scheduling, document attachments, native repost counters, media scanning or transcoding |
| Media security | Owner-only drafts, bounded MIME/signature checks, atomic single-use attachment, current post ACL before download, protected admin review | Signature checking is not complete validation/scanning; cleanup is lazy, no storage purge job |
| Projects | Standalone invite-only spaces; optional approved library source; member directory, contribution guide, stage and versioned tasks | Existing-user invitation grants membership immediately; pending invite acceptance is future work |
| Project references | HTTPS shortcuts, selected platform/file type, bundled badges, notes, filters/search, manager pins, author/manager edits, version conflicts | 200 per project; files remain on their provider; no remote fetch/indexing or E2EE for metadata |
| Institutions | Public pages/updates, membership and admin-controlled reviewed verification | Badge is platform review, not proof of patent rights |
| Private internal space references | Separate records; owner and MFA-qualified Saha admin only | Not available to members or community moderators |
| Discovery | Curated library, provenance/rights evidence and external search links | No internet-wide ingestion or guarantee of reuse rights |
| Collections | Account-private collections, notes and saved searches | No automated saved-search alerts; not E2EE |
| Chat | Matrix/Element identity proof, password/MFA step-up, keyless membership bot, encrypted room policy and revocation | Local testing only; operational two-device acceptance not completed |
| Legacy chat | Historical plaintext/server-decrypted routes return 410 | Old records unchanged; no fallback or retroactive E2EE |
| IP workflows | Existing listing/materials/proposal/transaction tools preserved | Secondary to collaboration; financial guards retained |

Saha is intended as a non-monetized open innovation platform. Its own source-code
license has not yet been selected. Third-party font notices/licenses are preserved.

## Session consistency follow-up

The latest source fixes the signed-in Home signup prompt and audits the full session
path. Both apps now validate restoration centrally, distinguish unavailable from
anonymous, synchronize account changes across tabs, guard signup/login pages and
reject stale or cross-account retries. Uploads/downloads use the same client.
Backend refresh/logout now serialize by token family and revoke descendants.
See [Session review](SESSION-CONSISTENCY.md) for findings, behavior and limits.

## Release artifacts and deployment evidence

The owner confirmed the prior social/workspace release locally through nginx.
The new session patch has been built and validated offline but not activated by
this coding session:

| Component | Last operator-confirmed local served | Session-patch candidate |
| --- | --- | --- |
| Frontend | `frontend-b5504d0f93177e951687` | `frontend-80c073dfbf82b9edccda` |
| Backend | `backend-0fce8b086b4eba972cc8` | `backend-d639a4f8ebfc8705c1a1` |
| Private admin | `admin-be777f81ae21acad88b3` | `admin-e2b402ab5214fd3cecdf` |

Candidate web builds and receipts are in `/tmp/saha-session-release-mij_akxy`.
Source fingerprints, BUILD_ID, compiled X-Saha-Build, required routes and production
browser API origins match. The backend candidate is its source identity. Earlier
social builds under `/tmp/saha-social-release-uxbxevwp` remain historical artifacts.

**Activation/public verification of the session patch is pending.** The latest
`systemctl is-active saha` again failed with bus access `Operation not permitted`.
No live builds, migrations, tunnel configuration or services were changed here.
The user's prior authorization to publish remains sufficient; the sandbox cannot
perform host operations. Local version evidence for the previous release does
not certify the new patch or browser/encryption behavior.

Existing mapping is preserved: public domains → Cloudflare → nginx :80 → frontend
:3000 / backend :8000; private nginx :8080 → admin :3002 / API :8000. Local test
chat is separate and is not added to public ingress.

## Validation

- 473 backend non-database tests passed; 26 database tests deselected. The final
  expiry-recheck adjustment also passed its four targeted rotation/logout cases.
  Real PostgreSQL concurrency cases are added but have not run here.
- 44 client session/CTA/request/storage checks, seven navigation/server-fetch
  checks and five mention-editor checks passed (56 client checks total).
- Both full production web builds passed with TypeScript validation.
- Installed JS ranges/peers/Node engines passed; all 102 backend packages compatible.
  No new dependency was introduced.
- Both November migrations applied and reapplied on isolated PostgreSQL 14.24 using
  single-user mode; all 42 model tables / 389 columns and the nullable project source matched. No application database connection was made.
- Three current interactive HTML references and both draw.io diagrams regenerated
  from source. Earlier artifacts archived; user/developer/security/operations docs updated.

Still required on a normal host: dedicated PostgreSQL/Redis request integration,
real browser interaction/accessibility, public tunnel version
checks, and Matrix two-device acceptance before enabling production encrypted chat.
Remote CI has not run. The separate frontend gitlink lacks a submodule mapping/
remote, so clean-checkout delivery needs a deliberate repository-layout resolution.

## Activate the session patch on the already-migrated host

No new package or database migration is required. Backend and both web apps must
be restarted together after building while the apps are stopped:

```sh
cd ~/Downloads/saha
saha stop && saha build && saha start --local && saha versions --local
# Complete the session/browser acceptance checks, then:
saha online && saha versions
```

Stop on failure. Do not rerun collaboration migrations just for this session patch.
The earlier local version output only establishes the baseline served release.

## Initial deployment procedure (retained for other hosts)

Read [Hosting](HOSTING.md) and [schema order](OPEN-COLLABORATION-DEPLOYMENT.md).
Both `2026-11-01-social-media.sql` and `2026-11-01-project-workspaces.sql` are required.
The latter makes existing projects private while preserving members and source links.

```sh
cd ~/Downloads/saha
bash scripts/migrate-social-workspaces.sh --check
bash scripts/migrate-social-workspaces.sh
saha versions --local
# Complete local feature checks before opening public access:
saha online
saha versions
```

Stop on any failure. The helper backs up the configured native database, stops
apps, applies the migrations, builds and starts locally. It leaves the tunnel
stopped. It does not establish external file permissions or certify chat encryption.
Markdown/HTML/draw.io documentation changes do not alter application fingerprints.
