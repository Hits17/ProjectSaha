# Current security boundaries

Session follow-up: refresh/logout now serialize and revoke by token family;
web clients validate restored profiles, verify the refreshed account before retries,
reject stale session responses and prevent external credential-bearing API URLs.
See [session review and limits](../docs/SESSION-CONSISTENCY.md), including remaining
access-token lifetime, browser-storage and real DB concurrency acceptance limits.

Source review updated 2026-11-01. This supplements the dated audit; it is not a
penetration-test certificate or assertion that every historical risk is resolved.
[Release status](../docs/CURRENT-STATUS.md) records actual evidence.

| Surface | Boundary |
| --- | --- |
| Projects, tasks, reference links | Invited members; no public self-join, directory entry or generic visibility change. November migration makes prior projects private. |
| Reference editing/pinning | Author or manager edits/removes; only managers pin; optimistic version check; project quota; URL metadata never triggers remote fetch. |
| Social media draft | Owner only; opaque storage key, bounded reads and MIME signatures, six attachments/one video, serialized draft quota and single attachment ownership. |
| Published social media | Current post visibility/moderation/deletion checked before storage; private/no-store and nosniff; authenticated admin review requires MFA policy. |
| Mentions | Active account IDs, canonical labels, ten-account bound; notifications only to eligible viewers, no private content in notification text. |
| Space internal reference/evidence | Owner and MFA-qualified platform admin only; separate private records; absent from public response models. |
| Institution verification | Admin-controlled policy and explicit review; no self-approval; identity edits invalidate verification. |
| Collaboration | Confirmed email or existing verified KYC. Financial flows retain financial verification. |
| Collections/notes | Account-private authorization; not E2EE. |
| Chat | Matrix/Element device encryption; keyless membership bot, identity proof + fresh step-up; member removal revokes grants before success. |
| Legacy chat | HTTP 410; no server-decrypted/plaintext fallback; historical data unchanged. |
| Admin | Private nginx listener; server admin/MFA guards. No public tunnel route to admin. |

## Limits and next work

- Media signature checks are not complete decoding, malware scanning or image/video
  moderation. Current text rules cannot assess visual contents. Add reviewed media
  scanning/transcoding and storage lifecycle policy before high-volume operation.
- Draft cleanup is lazy on the owner's next upload; there is no background orphan
  garbage collector. Deleting a post denies media access but does not immediately
  purge its objects. A documented retention/purge job remains needed.
- Expressive reactions are not reputation votes. Email-confirmed collaboration has
  weaker Sybil resistance than financial KYC; retain rate limits and moderation.
- Platform/file-type badges are selected metadata, not verified provider identity.
  External file permissions remain outside Saha. Private reference URLs may contain
  provider sharing tokens: do not log them or expose them outside project access.
- Membership administration is trusted for Matrix invitations; only clients hold
  conversation keys. Device acceptance, key rotation/removal and recovery checks
  remain outstanding. Chat is local testing only; public chat is not certified live.
- Requests already authorized may finish during a concurrent membership change.
  Permission checks apply to subsequent reads; recipients can retain received data.
- Reference/task fields and feed content are not end-to-end encrypted. Financial
  vault encryption at rest is also a different boundary.
- Database integration, real browser acceptance, clean-checkout CI and external
  dependency/image security audits have not been completed in this sandbox.

## Evidence

The release includes offline schema apply/reapply, source/receipt checks, web
production builds and regression tests. Request-level integration tests need an
isolated `saha_test` database/Redis. Do not substitute unit test totals for their
results. Historical issues in [AUDIT](AUDIT.md), [RECON](RECON.md) and the
[threat model](THREAT-MODEL.md) remain preserved with their original dates.
