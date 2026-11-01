"""Run full tests using only the prepared isolated test services and credentials."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
BACKEND = BASE.parent.parent / "apps/backend"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--already-running", action="store_true", help="Use existing dedicated test services without starting or stopping them")
    args = parser.parse_args()
    generated = BASE / "generated"
    if not (generated / "backend-test.env").is_file():
        raise SystemExit("Run prepare.py first. No application .env file will be changed.")
    environment = os.environ.copy()
    for line in (generated / "backend-test.env").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            environment[key] = value
    # Match conftest's test-origin settings even if the caller has deployment
    # settings exported in their shell. These credentials apply only to children.
    environment.update(ALLOWED_HOSTS='["*"]', CORS_ORIGINS='["http://localhost:3000"]',
                       COOKIE_SECURE="false", KYC_MOCK_MODE="true", VAULT_V1_ROTATION_PENDING="false")
    python = BACKEND / ".venv/bin/python"
    compose = ["docker", "compose", "--env-file", str(generated / "stack.env"), "-f", str(BASE / "compose.yml")]
    if not args.already_running:
        try:
            subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.SubprocessError):
            raise SystemExit("Docker is inaccessible in this session. Run this check from a terminal with Docker/socket access; no services were started.")
    started = False
    try:
        if not args.already_running:
            started = True
            subprocess.run(compose + ["up", "-d", "--wait", "--wait-timeout", "90", "test-db", "test-redis"], check=True, timeout=180)
        subprocess.run([str(python), "scripts/check_test_database.py"], cwd=BACKEND, env=environment, check=True, timeout=30)
        subprocess.run([str(python), "-m", "pytest", "-q", "--strict-markers", "-p", "no:cacheprovider"], cwd=BACKEND, env=environment, check=True, timeout=300)
    finally:
        if started:
            # Only this dedicated project's two test services; retain test volumes.
            subprocess.run(compose + ["stop", "-t", "10", "test-db", "test-redis"], timeout=45, check=False)


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Isolated test run failed ({type(exc).__name__}); it was not treated as a passing or skipped run.", file=sys.stderr)
        raise SystemExit(1)
