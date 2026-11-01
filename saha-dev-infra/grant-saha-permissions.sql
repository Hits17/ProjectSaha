-- Run once as postgres superuser:
-- sudo -u postgres psql -d saha -f grant-saha-permissions.sql

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO saha;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO saha;
GRANT ALL PRIVILEGES ON SCHEMA public TO saha;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO saha;

-- Ensure future tables created by postgres also get granted to saha
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON TABLES TO saha;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON SEQUENCES TO saha;
