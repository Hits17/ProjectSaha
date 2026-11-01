# Saha CLI with the existing nginx and Cloudflare setup

This integration is mapped to the configuration found on this machine. It keeps
the existing native PostgreSQL, Docker infrastructure and Cloudflare tunnel.
No tunnel credentials were copied into the repository and no new public domain
or chat endpoint was added. Chat is still local testing only.

| Entry | nginx destination | Application/service |
|---|---|---|
| `https://sahasolutions.com` and `www` | Cloudflare Tunnel → local port 80 | `saha-frontend`, loopback port 3000 |
| `/api/*`, `/health*` on that origin | local port 80 | `saha-backend`, loopback port 8000 |
| `/api/v1/notifications/stream` | unbuffered SSE on port 80 | same backend, streaming enabled |
| Private LAN/VPN admin | port 8080; excluded from tunnel | `saha-admin`, loopback port 3002; API to 8000 |
| Databases/storage/search/mail | existing local infrastructure | native `postgresql` + `saha-infra` Docker Compose |

Production browser API URLs are relative to the current origin. Both production
apps therefore use their nginx `/api/` route, even if a developer's `.env.local`
still contains `http://localhost:8000`. Local `next dev` may use that setting.
New institution, project, collection and chat-coordination endpoints are under
`/api/v1/` and require no additional nginx locations.

## Current session-fix patch on the already-migrated host

The signed-in Home CTA and session lifecycle patch adds no schema migration or
package dependency. It includes backend refresh/logout locking, so restart all
three applications after building. From a normal host terminal:

```sh
cd ~/Downloads/saha
saha stop && saha build && saha start --local && saha versions --local
# Check home/login/reload, two tabs, expiry, uploads and admin before publishing:
saha online && saha versions
```

See [Session consistency](SESSION-CONSISTENCY.md) and [current candidate/served
identities](CURRENT-STATUS.md). The migration procedures below remain for hosts
that have not yet installed the social/workspace schema; do not rerun them for
this session-only patch. Never build over a running `.next` directory.

## Current installation status

The owner completed installation with `scripts/install-host.py --apply` and reported
backup `/var/backups/saha-host-backup-kxzm1bx5`. A subsequent `saha online` confirmed
matching local and public builds with HTTP 200. This is recorded operator evidence,
not a fresh probe. The new social/workspace release is a later change and needs
the two November migrations and new builds. The coding sandbox cannot access
systemd or host sockets; it has not published this release. See [Current status](CURRENT-STATUS.md).

## Install the mapping, without activation

From `/home/hitarth/Downloads/saha`, in a host terminal with sudo access:

```sh
sudo python3 scripts/install-host.py --check
sudo python3 scripts/install-host.py --apply
```

The installer stages reviewable files, verifies systemd, tests nginx and validates
the **existing** `/etc/cloudflared/config.yml`. It backs up the old CLI, units and
nginx files under `/var/backups/saha-host-backup-*`, installs the mapping and runs
`systemctl daemon-reload`. Failure restores the previous files. It does **not**
reload nginx, start services, enable boot startup, change tunnel routes, mutate
database schema or rewrite application secrets. The CLI is anchored to this
repository path, so repeat installation if the repository moves.

## Deploy this development release deliberately

The currently served builds were not overwritten. For this already October-migrated host, run from a normal terminal:

```sh
bash scripts/migrate-social-workspaces.sh --check
bash scripts/migrate-social-workspaces.sh
saha versions --local
# Complete the local smoke checks, then:
saha online
saha versions
```

The helper verifies the configured native localhost:5432/saha target, stops apps,
creates a private readable backup, applies only both November migrations, builds
while stopped, checks schema, and starts locally. It leaves the public tunnel
stopped. If any step fails, it stops rather than publishing a partial release.
For an older August-only schema, use `migrate-open-collaboration.sh`, which includes
the five October migrations as well. Do not run the fresh baseline against live data.

The individual stages are:

1. Back up the application database and follow `OPEN-COLLABORATION-DEPLOYMENT.md`
   for the applicable migration sequence. The two November migrations are now required; they also make older projects private. Apply only the migrations missing from the
   actual deployment; never run the fresh baseline against an existing database.
2. Run `saha stop`, then `saha build`. The build command refuses to run unless
   both web services are confirmed stopped. It preserves the old `.next` outputs
   in `~/.local/state/saha/build-backups/`, and restores both old builds if either
   new build fails. It does not install dependencies, run migrations or restart
   services. The complete application dependency graph must already be installed.
3. Run `saha start --local`. This starts the grouped `saha.service`, native
   PostgreSQL, existing Docker infrastructure and nginx. It tests/reloads nginx
   and waits for API readiness plus both UI origins. Docker images are neither
   pulled nor recreated automatically. The backend refuses startup if required
   model tables/columns are missing; this gate is read-only.
4. Check institution/project/collection permissions and the transaction routes
   using local/private access. Production secure cookies still require HTTPS;
   do not weaken `COOKIE_SECURE` to make plain LAN HTTP behave like HTTPS.
5. Run `saha online` after local checks. It refuses to start the tunnel when
   local nginx readiness is failing and reports public readiness separately.

The release disables historical plaintext/server-decrypted chat routes with 410.
Since the owner selected local chat testing only, public chat remains unavailable
until a separately configured Matrix/Element deployment passes real-client tests.
Starting Saha never starts or publishes the isolated local chat test stack.

## CLI commands

```sh
saha routes          # display the exact host/port mapping
saha doctor          # compare installed wiring and inspect production build URLs
saha status          # service states, local nginx and public readiness
saha diagnose        # compare backend, nginx/public Host and Cloudflare responses
saha versions --local # compare running local web/API/admin builds with source
saha versions        # also verify public web/API through the tunnel
saha start --local   # keep tunnel stopped; start/check local Saha
saha start           # start/check local Saha, then open tunnel
saha offline         # stop tunnel, retain local application access
saha online          # publish only after local readiness passes
saha restart --local # restart apps and keep public tunnel stopped
saha stop            # stop tunnel/apps; retain shared nginx and data services
saha build           # build only while both web services are confirmed stopped
```

`sudo systemctl start saha` is the grouped application service. It starts local
dependencies and apps, but **not** Cloudflare Tunnel. Use the CLI for readiness
gating and public exposure. `sudo systemctl enable saha` is optional boot startup
after release validation. Existing cloudflared boot enablement is not changed by
this installer; use `saha offline` for an immediate public disconnect.

Keep production backend settings aligned with the existing `.env`: `APP_ENV`
production, `DEBUG=false`, `FRONTEND_URL=https://sahasolutions.com`, allowed hosts
including both public domains and local health-check hosts, public HTTPS CORS
origins, secure cookies, and loopback-only trusted proxy CIDRs. The inspected
file already sets these. Cookie domain `.sahasolutions.com` applies only to those
domains; plain LAN admin access does not provide equivalent persistent cookie
sessions. Use a private trusted HTTPS origin if persistent admin cookie sessions
are needed. The installer preserves these settings.

In Cloudflare, preserve the existing public-domain ingress to local nginx and the
404 catch-all. Do not add admin port 8080 or local test endpoints to the tunnel.
If custom cache rules exist, bypass cache for `/api/*`, `/health*` and authenticated
dashboard traffic. These account-level rules were not inspected or changed here.

Proxy templates accept edge IP/protocol headers only from local tunnel peers,
replace incoming forwarded chains and keep SSE unbuffered. Access logs omit URL
query strings and Referer to reduce token leakage. Shared nginx is retained when
Saha is stopped, allowing other hosted tools to keep their own services.

Operational references:

- https://nginx.org/en/docs/http/ngx_http_proxy_module.html
- https://www.freedesktop.org/software/systemd/man/251/systemd.unit.html
- https://developers.cloudflare.com/tunnel/troubleshooting/https-origins/

## Public readiness returns 403

If all local services are active and local readiness is healthy, run
`saha diagnose`. It compares direct backend readiness, nginx with the public
Host header, and the public HTTPS endpoint. It reports response metadata and
Cloudflare Ray ID without dumping response bodies, cookies or credentials.
A 403 alone does not establish whether Cloudflare or the origin denied it.
`CF-Mitigated: challenge` specifically identifies a Cloudflare challenge; use its
Ray ID in Cloudflare Security Events to identify the matching rule. A cross-host
redirect may indicate an Access/login gateway. Do not disable all security rules
based on a status code alone.

The CLI uses an explicit Saha user agent and verifies the real readiness JSON,
including healthy PostgreSQL and Redis. HTTP 200 from a login/challenge page is
not accepted as healthy. Existing global CLI wrappers reference `bin/saha`
directly, so this diagnostic change needs no frontend rebuild or service restart.

Reference: https://developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/

## Verify that the tunnel serves this release

Cloudflare forwards to nginx; it does not choose a source revision itself. The
installed units use `apps/frontend/.next` and `apps/admin/.next`. During the
2026-11-01 audit those directories still contained August 6 builds, missing all
new collaboration routes, despite matching nginx/systemd configuration. The
previous doctor check was insufficient and has been corrected.

`saha build` now records a content fingerprint and build ID in each
`.next/saha-build.json`. The compiled Next.js response header `X-Saha-Build`
contains that same ID. The backend computes its source identity once at import
and emits its own header, allowing an old running worker to be detected after
source edits. Secrets, environment files, dependencies, test files and generated
build outputs are excluded from fingerprints.

Doctor checks required routes and build receipts against current source. Version
checks compare expected identities with the actual responses from local nginx,
private admin, and both public web/API paths. Missing/different identifiers or
HTTP 403 remain **unverified**. The CLI refuses to confirm a current release just
because services report active or a login page returns HTTP 200.

To replace the old builds, from a normal host terminal after the database
migrations are applied:

```sh
saha stop
saha build
saha start --local
saha versions --local
saha online
saha versions
```

Stop on any failed command; do not proceed to publication after a failed local
version check. `saha online` now checks local versions before opening the tunnel
and requires matching public versions after public readiness. If public HTTP 403
persists, diagnose the edge/origin denial separately; rebuilding cannot establish
which Cloudflare security rule, if any, caused it.

## Backend 502 after the new web build

The 2026-11-01 service journal confirmed startup was refusing all nine new
collaboration tables and six added columns because the October migrations had
not been applied. A 502 here is nginx reporting that the backend never started;
the startup schema gate must remain enabled.

From the normal terminal, as the repository owner:

```sh
cd /home/hitarth/Downloads/saha
bash scripts/migrate-open-collaboration.sh
```

This verifies the configured database is native PostgreSQL on localhost:5432/saha,
stops apps/tunnel, creates a private custom-format database backup, checks archive
readability, applies the five October and two November migrations in order, validates the
application schema, builds while stopped, then starts and verifies the local release. It stops on error
and never runs the fresh database baseline. The shell opens migration input so
the postgres account need not traverse a private home directory. No nginx reinstallation is required; the helper now rebuilds the expanded release. Existing database migrations through August
are prerequisites; the journal showed only October objects missing.

The helper leaves the tunnel stopped. Once local checks pass, use `saha online`.
Its public version checks may still reveal the separate public HTTP 403 issue.
A non-mutating prerequisite check is available with `--check`.
