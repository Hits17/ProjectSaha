# Isolated local validation

Updated 2026-11-01: the fresh test schema now also applies `2026-11-01-social-media.sql` and `2026-11-01-project-workspaces.sql`. Existing test volumes do not rerun Docker initialization scripts: apply the new migrations to the dedicated `saha_test` DB before the prerequisite check, or deliberately recreate only disposable test volumes. Never reset application volumes. The expanded integration suite checks standalone project privacy and reference permissions. See [development](../../docs/DEVELOPMENT.md).

The owner selected **local testing only**. This stack has a different project
name and data volumes from the application. It never rewrites application `.env`
files, migrates the running database or rebuilds the served `.next` tree.
All published ports bind to `127.0.0.1`.

Preparation was executed and configuration/certificates validated. **Containers
could not be started in the agent sandbox:** Docker access is denied and both
TCP and Unix sockets return `Operation not permitted`. Image pulls/ARM64 image
manifests and the live tests below remain unverified. Run them in a normal local
terminal with Docker access, without disabling certificate checks.

## Prepare and run backend integration tests

From this directory:

```sh
python3 prepare.py
python3 run_tests.py
```

Preparation has already created ignored `generated/` files on this machine;
the generator refuses to overwrite them. The runner starts only dedicated
PostgreSQL on port 15432 and Redis on 16379, requires the `saha_test` schema and
Redis before running **all** backend tests, then stops those two test services.
It preserves their volumes. It does not turn an inaccessible service into a
passing run. Install the backend `.venv` with `uv sync --all-extras --frozen`
first on a new machine. `--already-running` uses the prepared services without
starting/stopping them.

## Local Matrix/Element acceptance environment

This uses **test identities only** on `saha-chat.localhost` and HTTPS endpoints
`https://localhost:18448` (Matrix) and `https://localhost:18449` (Element). These
are unrelated to any future permanent production server name.

```sh
docker compose --env-file generated/stack.env -f compose.yml config --quiet
docker compose --env-file generated/stack.env -f compose.yml pull chat-db synapse element tls
docker compose --env-file generated/stack.env -f compose.yml up -d --wait chat-db
docker compose --env-file generated/stack.env -f compose.yml run --rm --no-deps synapse --generate-keys --config-path /data/homeserver.yaml
docker compose --env-file generated/stack.env -f compose.yml up -d synapse element tls
```

The dedicated Synapse process runs as the preparing user's UID/GID so its
owner-only bind-mounted configuration and signing keys stay private. The Element
config is non-secret and readable by its container user. TLS private keys and
database passwords remain mode 0600 in ignored files. Certificates expire after
30 days; preserve server secrets when renewing them.

Inspect the pull output to confirm **linux/arm64** support on this Jetson before
starting. Versions chosen from official upstream releases: Synapse v1.164.1,
Element v1.12.33, Caddy v2.11.7 and PostgreSQL 16.15. These references have not
been pulled or audited here. Redis's `7-alpine` tag is a floating **test-only**
reference. This stack is not a production deployment.

Import `generated/tls/ca.crt` into a dedicated browser test profile's trusted
authorities. Do not use a certificate bypass. The generated `backend-chat.env`
sets `SSL_CERT_FILE` to that CA for an isolated Saha backend process. It keeps
TLS verification enabled. Do not copy it into the running application's `.env`.

Provision `saha-service`, `alice` and `bob` using the official interactive tool
(repeat this command for each username; decline admin privilege):

```sh
docker compose --env-file generated/stack.env -f compose.yml exec synapse register_new_matrix_user -c /data/homeserver.yaml http://localhost:8008
```

Never log the service account into Element or upload its device keys. Obtain a
dedicated service login token using Matrix's supported password-login endpoint
with a private interactive client; put it in the owner-only
`generated/backend-chat.env`. Do not print or commit it. Personal users sign in
to Element separately; Saha's linking flow also requires fresh password/MFA
step-up. Use the dedicated test database for the isolated Saha backend.

Verify the endpoints with the CA:

```sh
curl --fail --cacert generated/tls/ca.crt https://localhost:18448/_matrix/client/versions
curl --fail --cacert generated/tls/ca.crt https://localhost:18449/config.json
```

Then execute **every** check in `../../docs/ENCRYPTED-CHAT.md`, including two
verified client devices, ciphertext and attachment inspection, plaintext-event
denial, kicks/future-key exclusion, recovery and outage behavior. The membership
bot's absence of device keys is checked by Saha on room preparation. A successful
startup or mocked suite alone does not complete these checks.

Official references used for the preparation:

- https://element-hq.github.io/synapse/latest/setup/installation.html
- https://github.com/element-hq/synapse/releases/tag/v1.164.1
- https://github.com/element-hq/element-web/releases/tag/v1.12.33
- https://github.com/element-hq/element-web/blob/develop/docs/install.md
- https://github.com/caddyserver/caddy/releases/tag/v2.11.7
- https://caddyserver.com/docs/caddyfile/directives/tls
- https://hub.docker.com/_/postgres
