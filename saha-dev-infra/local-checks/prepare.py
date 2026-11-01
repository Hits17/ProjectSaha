"""Prepare isolated localhost configuration; never starts or changes services."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess

BASE = Path(__file__).resolve().parent


def write_private(path, data):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(data)


def prepare(output):
    if output.exists():
        raise SystemExit("Output already exists; existing server secrets will not be overwritten.")
    output.mkdir(mode=0o700, parents=True)
    (output / "synapse").mkdir(mode=0o700)
    (output / "tls").mkdir(mode=0o700)
    password = secrets.token_urlsafe(36)
    test_password = secrets.token_urlsafe(36)
    spec = importlib.util.spec_from_file_location("chat_config", BASE.parent / "chat/generate_config.py")
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    env = {
        "MATRIX_SERVER_NAME": "saha-chat.localhost",
        "MATRIX_HOMESERVER_URL": "https://localhost:18448",
        "ELEMENT_WEB_URL": "https://localhost:18449",
        "CHAT_POSTGRES_PASSWORD": password,
    }
    for name, config in config_module.configuration(env).items():
        destination = output / name if name == "element.json" else output / "synapse" / name
        write_private(destination, json.dumps(config, indent=2) + "\n")
    # Element's static client configuration contains no secret and is read by
    # its non-root container UID. Other generated files remain owner-only.
    (output / "element.json").chmod(0o644)
    write_private(output / "stack.env", f"TEST_POSTGRES_PASSWORD={test_password}\nCHAT_POSTGRES_PASSWORD={password}\nLOCAL_UID={os.getuid()}\nLOCAL_GID={os.getgid()}\n")
    write_private(output / "backend-test.env", "\n".join([
        "APP_ENV=development",
        f"DATABASE_URL=postgresql+asyncpg://postgres:{test_password}@127.0.0.1:15432/saha_test",
        "REDIS_URL=redis://127.0.0.1:16379/0",
        f"SECRET_KEY={secrets.token_urlsafe(48)}",
        f"VAULT_ENCRYPTION_KEY={secrets.token_urlsafe(32)}",
        f"MINIO_ACCESS_KEY={secrets.token_urlsafe(16)}",
        f"MINIO_SECRET_KEY={secrets.token_urlsafe(32)}",
        "LIBRARY_DIGEST_ENABLED=false", "REQUIRE_STEP_UP_AUTH=false", "",
    ]))
    write_private(output / "backend-chat.env", "\n".join([
        f"{key}={env[key]}" for key in ("MATRIX_SERVER_NAME", "MATRIX_HOMESERVER_URL", "ELEMENT_WEB_URL")
    ]) + f"\nMATRIX_SERVICE_USER_ID=@saha-service:saha-chat.localhost\nMATRIX_SERVICE_ACCESS_TOKEN=\nSSL_CERT_FILE={output / 'tls/ca.crt'}\n")
    tls = output / "tls"
    commands = [
        ["openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-days", "30",
         "-keyout", str(tls / "ca.key"), "-out", str(tls / "ca.crt"), "-subj", "/CN=Saha local test CA",
         "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign"],
        ["openssl", "req", "-new", "-newkey", "rsa:3072", "-nodes", "-keyout", str(tls / "localhost.key"),
         "-out", str(tls / "localhost.csr"), "-subj", "/CN=localhost"],
        ["openssl", "x509", "-req", "-in", str(tls / "localhost.csr"), "-CA", str(tls / "ca.crt"),
         "-CAkey", str(tls / "ca.key"), "-CAcreateserial", "-out", str(tls / "localhost.crt"),
         "-days", "30", "-extfile", str(tls / "extensions.cnf")],
    ]
    write_private(tls / "extensions.cnf", "subjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n")
    previous_umask = os.umask(0o077)
    try:
        for command in commands:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    finally:
        os.umask(previous_umask)
    print(f"Prepared localhost-only test files in {output}. No services started; no system trust changed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE / "generated")
    args = parser.parse_args()
    prepare(args.output.resolve())
