# Saha documentation

Updated 2026-11-01. Start with [current implementation and release status](CURRENT-STATUS.md).

## Use and develop Saha

| Guide | Contents |
| --- | --- |
| [Session consistency](SESSION-CONSISTENCY.md) | Login restoration, home CTA, request races, token rotation and verification |
| [User guide](USER-GUIDE.md) | Discover research, join projects/institutions, collections, account settings |
| [UX and navigation](UX-NAVIGATION.md) | Page map, shared design, navigation and browser acceptance |
| [Development](DEVELOPMENT.md) | Local setup, dependencies, tests and contribution constraints |
| [Repository publishing](REPOSITORY-PUBLISHING.md) | Complete source checkout, exclusions and GitHub upload status |
| [Product roadmap](OPEN-INNOVATION-PLAN.md) | Open collaboration direction and ten additional features |
| [Social feed design](SOCIAL-FEED-DESIGN.md) | Ranking/reputation rationale with current access-policy corrections |

## Operate the service

| Guide | Contents |
| --- | --- |
| [Hosting](HOSTING.md) | Authoritative CLI/systemd/nginx/Cloudflare runbook |
| [Deployment overview](DEPLOYMENT.md) | Topology, current rollout and troubleshooting entry point |
| [Schema and collaboration cutover](OPEN-COLLABORATION-DEPLOYMENT.md) | Fresh/existing DB migration order and feature acceptance |
| [Encrypted chat](ENCRYPTED-CHAT.md) | Matrix/Element trust boundary and required two-device checks |
| [Local validation](../saha-dev-infra/local-checks/README.md) | Isolated Postgres/Redis and local-only HTTPS chat stack |
| [Current security boundaries](../security/CURRENT-SECURITY.md) | Public, private, encrypted and privileged data/access boundaries |

## Interactive technical references

The [architecture index](architecture/README.md) links all three updated interactive
HTML pages and both draw.io diagrams. They cover the system, backend and frontend;
current inventories come from the source tree. Open the HTML files directly in a
browser. They work without a documentation server or external diagram CDN.

See the [documentation refresh inventory](DOCUMENTATION-AUDIT.md) for per-file coverage.

## Historical evidence

- [Development history](DEVELOPMENT-HISTORY.md): chronological decisions, validations and resumable work.
- [2026-10-31 code review](REVIEW-2026-10-31.md): findings at that point, not a current unresolved-issue list.
- [2026-11-01 host audit](HOST-AUDIT-2026-11-01.md): earlier stale-build diagnosis; later rollout recorded separately.
- [Changelog](../CHANGELOG.md): dated implementation milestones, not a live deployment guarantee.
- [Security evidence index](../security/README.md): original audits, remediation plans and target architecture.
- [Archived interactive references](architecture/archive/README.md): earlier transaction-centric diagrams, retained for history.

When changing behavior, update the relevant guide and interactive page, append to
the development history, and update current status only when new evidence supports
it. A successful build is not a successful deployment or an encryption acceptance test.
