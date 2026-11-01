#!/bin/bash
# Apply this release to the configured native saha DB, with a private backup.
# Run as the repository owner from a normal host terminal, not under sudo.
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"
case "${1:-}" in
  ""|--check) ;;
  *) echo "Usage: bash scripts/migrate-social-workspaces.sh [--check]" >&2; exit 2 ;;
esac
if [ "$(id -u)" = 0 ]; then
  echo "Run as the repository owner without sudo; privileged steps request sudo themselves." >&2
  exit 1
fi
for program in sudo pg_dump pg_restore psql; do
  command -v "$program" >/dev/null
done

# Refuse to migrate a guessed database when the application points elsewhere.
(
  cd apps/backend
  .venv/bin/python - <<'PY'
from sqlalchemy.engine import make_url
from app.core.config import settings
url = make_url(settings.DATABASE_URL)
if url.get_backend_name() != "postgresql" or url.database != "saha" or url.host not in {"localhost", "127.0.0.1", "::1"} or (url.port or 5432) != 5432:
    raise SystemExit("This helper supports only the configured native localhost:5432/saha database. No database changed.")
print("Configured database matches the native saha migration target.")
PY
)

migrations=(
  2026-11-01-social-media.sql
  2026-11-01-project-workspaces.sql
)
for migration in "${migrations[@]}"; do
  test -r "saha-dev-infra/migrations/$migration"
done
if [ "${1:-}" = --check ]; then
  echo "Tools and migration files are present. No service or database operations performed."
  exit 0
fi

sudo -v
./bin/saha stop
umask 077
backup_dir="$HOME/.local/state/saha/database-backups"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
backup_file=$(mktemp "$backup_dir/saha-before-social-workspaces-XXXXXXXX")
echo "Creating database backup: $backup_file"
sudo -u postgres pg_dump -h /var/run/postgresql -p 5432 -Fc -d saha > "$backup_file"
pg_restore --list "$backup_file" >/dev/null
echo "Backup archive is readable. Applying collaboration migrations (including invite-only project conversion)."
for migration in "${migrations[@]}"; do
  echo "Applying $migration"
  # Open input as the repository owner; postgres need not traverse the home directory.
  sudo -u postgres psql -X -h /var/run/postgresql -p 5432 -d saha -v ON_ERROR_STOP=1 \
    < "saha-dev-infra/migrations/$migration"
done
(
  cd apps/backend
  .venv/bin/python scripts/check_host_schema.py
)
./bin/saha build
./bin/saha start --local
./bin/saha versions --local
echo "Migrations and local release checks completed. Backup retained: $backup_file"
echo "The tunnel remains stopped. Run saha online to verify and restore public access."
