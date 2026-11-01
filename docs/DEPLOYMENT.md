# Saha deployment overview

Latest patch: session consistency and backend token-family locking, with no new
migration. On the already-migrated host use the stopped-build/restart sequence in
[Hosting](HOSTING.md), then check [candidate versions](CURRENT-STATUS.md).
The social/workspace migration instructions below are retained for older hosts.

Updated 2026-11-01. [HOSTING.md](HOSTING.md) is the authoritative operational
runbook. This overview replaces the obsolete staging-era instructions for baked
LAN API URLs and building over running frontend artifacts.

## Existing topology

```text
sahasolutions.com + www
  → existing Cloudflare Tunnel (/etc/cloudflared/config.yml)
  → nginx :80
      /              → saha-frontend 127.0.0.1:3000
      /api/, /health → saha-backend  127.0.0.1:8000

Private LAN/VPN → nginx :8080
      /              → saha-admin   127.0.0.1:3002
      /api/          → saha-backend 127.0.0.1:8000

saha.service → native PostgreSQL + saha-infra + backend/frontend/admin + nginx
saha online  → readiness/version checks → cloudflared → public version checks
```

The public tunnel excludes admin and local test chat endpoints. Browser API calls
use the same nginx origin in production. Public listing Server Components use the
server-only `SAHA_INTERNAL_API_URL`, defaulting to `http://127.0.0.1:8000`; this is
not a browser setting. Development uses `NEXT_PUBLIC_API_URL` when configured.

## Release state

See [current status](CURRENT-STATUS.md). The installed mapping and prior
collaboration build were confirmed working by the owner. The newer UI is built
and validated offline; live publication and browser acceptance remain unverified.
The coding sandbox cannot access the system service manager. The social/workspace release requires both November migrations even on the October-migrated host.

## Current social/workspace rollout

This release now changes the database. On the existing October-migrated host, use
`bash scripts/migrate-social-workspaces.sh --check`, then
`bash scripts/migrate-social-workspaces.sh` from a normal host terminal. The helper
stops apps, backs up the DB, applies both November migrations, builds and starts
locally. Validate locally before `saha online` and `saha versions`. Older UI-only
artifacts are superseded. See [Hosting](HOSTING.md).

## UI-only rollout reference

In a normal host terminal, as the repository owner:

```sh
cd ~/Downloads/saha
saha stop && saha build && saha start --local && saha online && saha versions
```

The build requires stopped web services, backs up both outputs and restores them
on compilation failure. Startup validates the schema, readiness and matching
release identities. Public publication validates identities through the tunnel.
For a fresh installation or older schema, follow [Hosting](HOSTING.md) and
[Schema/cutover](OPEN-COLLABORATION-DEPLOYMENT.md) first.

## Troubleshooting and operations

| Symptom/task | Action |
| --- | --- |
| Services and availability | `saha status` |
| Host/proxy routing | `saha routes`; `saha doctor` |
| Backend or public failure | `saha diagnose`; inspect `journalctl -u saha-backend` |
| Which build is served? | `saha versions --local`, then `saha versions` |
| Remove public exposure | `saha offline` (apps/data services remain) |
| Stop apps and tunnel | `saha stop` (shared nginx/data services remain) |
| Missing schema | Follow the ordered migration/backup procedure; retain the startup schema gate |
| Service bus `Operation not permitted` | Run in a normal host terminal; authorization cannot override sandbox restrictions |

Backend production settings use explicit hosts, HTTPS origins, secure cookies and
loopback trusted proxies. Staging is hardened like production; mocks are limited
to development. Private HTTP LAN access does not provide production secure-cookie
sessions; use a trusted private HTTPS origin for persistent admin sessions.

Never rotate vault/chat binding keys casually: preserve existing ciphertext keys,
Matrix signing keys and room bindings. Back up application PostgreSQL, object
storage and relevant configuration; separately back up any future chat database.
Automated backups/disaster recovery have not been established by these checks.

The host installer does not enable services at boot or change Cloudflare account
rules. Historical boot/firewall settings are not a fresh audit. See
[security boundaries](../security/CURRENT-SECURITY.md) and the dated evidence.
