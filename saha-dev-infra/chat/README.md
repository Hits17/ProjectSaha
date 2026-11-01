# Optional dedicated encrypted-chat deployment

Reviewed 2026-11-01. Standalone project chat reuses its invite-only community room. This is an optional template, not the configured public deployment. The selected setup remains [local testing only](../local-checks/README.md); follow all [two-device acceptance checks](../../docs/ENCRYPTED-CHAT.md). Public posts/media, project tasks and reference links are not E2EE.

This is a preparation template, not a running service. See `../../docs/ENCRYPTED-CHAT.md` for the threat boundary and mandatory acceptance tests.

1. Review maintained official Synapse, Element and PostgreSQL images for your architecture. Put pinned versions/digests in a local `.env` copied from `.env.example`. The example deliberately cannot launch unchanged.
2. Set real HTTPS URLs and a permanent server name; changing a Matrix server name later is not a normal configuration change. Set a random database password. Export these settings in your shell and run `python3 generate_config.py` from this directory. The generator refuses to overwrite existing configuration/secrets.
3. Align ownership of `generated/homeserver.yaml` and `generated/log.config` with the selected Synapse image's runtime UID. Keep those secret files mode 0600. Make the non-secret `element.json` readable by the Element image's UID. Do not solve permissions by making the homeserver secret file world-readable.
4. Review `docker compose config`, then start this dedicated stack when ready. The database has no host port; Synapse/Element bind only to loopback at 8008/8088. Put both behind an HTTPS reverse proxy with matching domain/Host handling. Do not publish the old plaintext application chat.
5. Provision accounts with Synapse's supported registration/SSO tooling. A `register_new_matrix_user` operation using the local config can create the dedicated service user without enabling public registration. Obtain a dedicated service access token through the homeserver's supported login flow. Do not log into Element or create encryption keys for that service account. Use separate personal accounts for every participant.
6. Configure Saha's five `MATRIX_*`/`ELEMENT_WEB_URL` backend settings. Apply Saha's schema migrations, deploy matching frontend/backend, then execute all two-device tests before enabling ordinary use.

The template does not configure DNS, TLS certificates, SSO, TURN/video, backups or image upgrades automatically. Validate ARM64 image availability before pulling on the Jetson. Do not reuse the Saha application database for the chat server.

Authoritative install guidance:

- https://element-hq.github.io/synapse/latest/setup/installation.html
- https://web-docs.element.dev/install.html
