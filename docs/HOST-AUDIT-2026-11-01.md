# Saha host configuration and build audit — 2026-11-01

> **Historical evidence:** Findings below describe the stated review point. Subsequent fixes and owner-confirmed rollout are recorded in [Current status](CURRENT-STATUS.md) and [Development history](DEVELOPMENT-HISTORY.md). The new social/workspace release requires additional migrations and has separate rollout evidence.

## Confirmed from installed files

- Global CLI wrapper targets `/home/hitarth/Downloads/saha/bin/saha`.
- Grouped `saha.service`, native PostgreSQL, existing Docker infrastructure and app services have the expected paths/ports. Backend runs the schema precheck. Apps remain loopback-bound.
- Both public-domain Cloudflare ingress rules resolve to nginx `http://localhost:80`; the admin hostname resolves to the 404 catch-all. The service uses `/etc/cloudflared/config.yml`. `/usr/local/bin/cloudflared` points to the same `/usr/bin/cloudflared` used by the service.
- All four installed Saha nginx files match their repository versions, including SSE buffering, forwarded-header sanitization and public/private route separation.
- The loaded backend configuration file passes production validation. Public URL, both HTTPS CORS origins, allowed hosts, secure domain cookies and loopback proxy trust match the intended topology. No credentials were included in this report.

## Deployment mismatch found

The actual configured build directories contain these older artifacts:

| App | On-disk build ID | BUILD_ID timestamp | Missing new pages |
|---|---|---|---|
| frontend | `Fl0C7dCiYjFHCQO__LEax` | August 6, 2026 00:55 EDT | Explore, Projects, Institutions, Collections |
| admin | `aMwp6PvMGepI_QuOiySjC` | August 6, 2026 00:37 EDT | Institutions |

Thus configuration installation alone did not deploy the new web release.
The prior doctor check incorrectly accepted these builds because they had valid
BUILD_ID files and no localhost API URL. It now checks collaboration routes,
source fingerprints and build receipts as well.

## Changes and limits

Added `saha versions [--local]`, compiled web build headers, a startup-fixed
backend identity, source/receipt checks and publication version gates. Both
updated production builds passed in isolated temporary directories. Verified
that compiled route manifests include the new pages and `X-Saha-Build` matches
each Next build ID. Running host processes and public responses cannot be
inspected by this agent's socket-restricted session. No live build was replaced,
no host service restarted and no Cloudflare account rule changed.

Follow `HOSTING.md` to stop/build/start locally, verify local identities, then
publish and verify public identities. The reported public 403 remains a separate
unconfirmed edge-versus-origin issue; use `saha diagnose` and Cloudflare Ray IDs.
