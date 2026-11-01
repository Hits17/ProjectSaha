-- Migration: add 'trademark' to the Open Innovation Library resource types so
-- the library can also carry genericized/abandoned trademarks now free to use
-- (aspirin, escalator, thermos, …) alongside patents and research papers (2026-07-04)
--
-- IMPORTANT: `ALTER TYPE … ADD VALUE` cannot run inside a transaction block, so
-- apply it as a single statement as the postgres superuser (not the `saha` app
-- role, which does not own the type). Run BEFORE restarting saha-backend:
--   sudo -u postgres psql -d saha -c "ALTER TYPE open_resource_type ADD VALUE IF NOT EXISTS 'trademark';"
--
-- Fresh installs get this automatically via init-scripts/01-schema.sql.

ALTER TYPE open_resource_type ADD VALUE IF NOT EXISTS 'trademark';
