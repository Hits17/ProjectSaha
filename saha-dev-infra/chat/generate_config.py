"""Prepare Synapse/Element config only; never starts services or overwrites keys.

Load reviewed settings into the environment first, then run this from chat/.
JSON output is valid YAML for Synapse; no external Python dependency is needed.
"""
import json
import os
import pathlib
import secrets
from urllib.parse import urlsplit


def configuration(env):
    name = env.get("MATRIX_SERVER_NAME", "")
    if not name or "/" in name or "example" in name or any(c.isspace() for c in name):
        raise ValueError("Choose your actual permanent MATRIX_SERVER_NAME")
    homeserver = env.get("MATRIX_HOMESERVER_URL", "")
    element = env.get("ELEMENT_WEB_URL", "")
    for value in (homeserver, element):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Set real HTTPS homeserver and Element URLs without credentials")
    password = env.get("CHAT_POSTGRES_PASSWORD", "")
    if len(password) < 24 or "REPLACE" in password:
        raise ValueError("Set a random CHAT_POSTGRES_PASSWORD of at least 24 characters")
    synapse = {
        "server_name": name, "public_baseurl": homeserver.rstrip("/") + "/",
        "pid_file": "/data/homeserver.pid", "report_stats": False,
        "listeners": [{"port": 8008, "tls": False, "type": "http", "x_forwarded": True,
                       "resources": [{"names": ["client"], "compress": False}]}],
        "database": {"name": "psycopg2", "args": {"user": "synapse", "password": password,
            "database": "synapse", "host": "chat-db", "port": 5432, "cp_min": 2, "cp_max": 5}},
        "enable_registration": False, "allow_public_rooms_without_auth": False,
        "allow_public_rooms_over_federation": False,
        "registration_shared_secret": secrets.token_urlsafe(48),
        "macaroon_secret_key": secrets.token_urlsafe(48),
        "form_secret": secrets.token_urlsafe(48),
        "signing_key_path": "/data/server.signing.key", "media_store_path": "/data/media_store",
        "log_config": "/data/log.config", "trusted_key_servers": [], "suppress_key_server_warning": True,
    }
    client = {"default_server_config": {"m.homeserver": {"base_url": homeserver, "server_name": name},
        "io.element.e2ee": {"default": True}}, "brand": "Saha Chat", "disable_guests": True,
        "disable_custom_urls": True, "default_theme": "light"}
    logging = {"version": 1, "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
        "root": {"handlers": ["console"], "level": "WARNING"}, "disable_existing_loggers": False}
    return {"homeserver.yaml": synapse, "element.json": client, "log.config": logging}


def main():
    output = pathlib.Path("generated")
    if output.exists():
        raise SystemExit("generated/ already exists. Preserve existing server secrets; review changes manually.")
    configs = configuration(os.environ)
    output.mkdir(mode=0o700)
    for name, data in configs.items():
        # Synapse runs as its container user; the host directory/config owner
        # must be aligned with that UID before mounting. Do not make secrets public.
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2)
    print("Prepared configuration in generated/. No services were started.")


if __name__ == "__main__":
    main()
