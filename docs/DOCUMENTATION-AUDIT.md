# Documentation refresh inventory

Reviewed 2026-11-01. All files in the current documentation directory were inventoried,
including three interactive HTML pages and two editable diagrams. Original architecture
artifacts remain in `architecture/archive` as historical evidence. Security histories
retain original findings; current guidance is linked rather than rewriting past events.

| File | Treatment |
| --- | --- |
| `README.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `CHANGELOG.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/CURRENT-STATUS.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/DEPLOYMENT.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/DEVELOPMENT-HISTORY.md` | Append-only progress, validation, rollout limits and resume notes |
| `docs/DEVELOPMENT.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/ENCRYPTED-CHAT.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/HOST-AUDIT-2026-11-01.md` | Historical body retained; current-status/supersession context added |
| `docs/HOSTING.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/OPEN-COLLABORATION-DEPLOYMENT.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/OPEN-INNOVATION-PLAN.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/README.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/REVIEW-2026-10-31.md` | Historical body retained; current-status/supersession context added |
| `docs/SOCIAL-FEED-DESIGN.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/USER-GUIDE.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/UX-NAVIGATION.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/architecture/README.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `docs/architecture/SAHA_ARCHITECTURE.html` | Regenerated current interactive reference/diagram; prior artifact archived |
| `docs/architecture/SAHA_BACKEND.html` | Regenerated current interactive reference/diagram; prior artifact archived |
| `docs/architecture/SAHA_FRONTEND.html` | Regenerated current interactive reference/diagram; prior artifact archived |
| `docs/architecture/saha-deployment-topology.drawio` | Regenerated current interactive reference/diagram; prior artifact archived |
| `docs/architecture/saha-system-architecture.drawio` | Regenerated current interactive reference/diagram; prior artifact archived |
| `security/ARCHITECTURE-TARGET.md` | Historical body retained; current-status/supersession context added |
| `security/AUDIT.md` | Historical body retained; current-status/supersession context added |
| `security/CURRENT-SECURITY.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `security/DEPLOY-2026-08-05.md` | Historical body retained; current-status/supersession context added |
| `security/README.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `security/RECON.md` | Historical body retained; current-status/supersession context added |
| `security/REMEDIATION-PLAN.md` | Historical body retained; current-status/supersession context added |
| `security/ROADMAP.md` | Historical body retained; current-status/supersession context added |
| `security/THREAT-MODEL.md` | Historical body retained; current-status/supersession context added |
| `apps/admin/README.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `apps/frontend/README.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `saha-dev-infra/chat/README.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `saha-dev-infra/local-checks/README.md` | Reviewed/refreshed for current behavior, operations and evidence |
| `saha-dev-infra/seed/README.md` | Reviewed/refreshed for current behavior, operations and evidence |

The generated backend inventory includes 177 source-declared HTTP handlers and 42
mapped tables. Frontend/admin routes are discovered from actual page files. HTML
search, expandable inventories and links use no external CDN. Diagram XML is
uncompressed and editable. The generator is `scripts/update-architecture-docs.py`.

Validation checks current HTML syntax/IDs/anchors, inline JavaScript parsing,
diagram IDs/edges and local Markdown links. These are offline checks, not browser
interaction certification. Current application release identity and remaining
host/E2EE/integration gates are in [Current status](CURRENT-STATUS.md).

Font copyright/OFL notices were inspected as third-party license material and
preserved verbatim. Source-code licensing remains undecided; documentation updates
do not imply a license grant. Archive documents retain older terminology and counts
and must not be used as current deployment instructions.


## Session-consistency follow-up

Added [Session review](SESSION-CONSISTENCY.md), refreshed current status/hosting,
user/developer/security guidance, app READMEs, changelog and the interactive system/
backend/frontend descriptions. This patch adds no migration; older migration
procedures are explicitly labeled for hosts missing the social/workspace schema.
