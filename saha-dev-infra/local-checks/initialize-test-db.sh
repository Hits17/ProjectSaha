#!/bin/sh
set -eu
# Invoked only by the fresh, dedicated test database container.
test "$POSTGRES_DB" = saha_test
psql -U postgres -d saha_test -v ON_ERROR_STOP=1 -c 'CREATE ROLE saha;'
psql -U postgres -d saha_test -v ON_ERROR_STOP=1 -f /saha/schema/01-schema.sql
for migration in \
  2026-08-05-security-hardening.sql \
  2026-08-06-social-feed.sql \
  2026-08-06-content-moderation.sql \
  2026-10-31-open-collaboration.sql \
  2026-10-31-encrypted-chat.sql \
  2026-10-31-resource-provenance.sql \
  2026-10-31-open-projects.sql \
  2026-10-31-research-collections.sql \
  2026-11-01-social-media.sql \
  2026-11-01-project-workspaces.sql; do
  psql -U postgres -d saha_test -v ON_ERROR_STOP=1 -f "/saha/migrations/$migration"
done
