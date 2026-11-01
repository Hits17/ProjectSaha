# Saha architecture references

Updated 2026-11-01. Every current artifact is regenerated from the checked-out
source and current implementation notes by `python3 scripts/update-architecture-docs.py`.
The previous five artifacts are retained in [archive](archive/README.md).

| Artifact | Content |
| --- | --- |
| [System architecture](SAHA_ARCHITECTURE.html) | Product journey, service mapping, privacy, media, projects, chat and release boundaries |
| [Backend](SAHA_BACKEND.html) | Searchable handler inventory, model tables/columns, guards and service behavior |
| [Frontend](SAHA_FRONTEND.html) | Shared UI, project/feed interactions, all public/admin application routes |
| [System diagram](saha-system-architecture.drawio) | Trust boundaries and external references/chat |
| [Deployment diagram](saha-deployment-topology.drawio) | Existing nginx/Cloudflare/systemd mapping and separate local chat stack |

Open HTML directly in a browser: it uses local CSS/JavaScript, searchable sections,
expandable inventories and no external CDN. Open draw.io XML in diagrams.net.
The pages are documentation, not running application demos. For live evidence see
[Current status](../CURRENT-STATUS.md); for deployment use [Hosting](../HOSTING.md).

Regenerate after router/model/page changes. Keep historical findings in the archive;
do not interpret older planned integrations as implemented or deployed features.
