-- Runs once on first start (empty data volume), as the POSTGRES_USER superuser.
-- The application creates its own tables on start-up; this only prepares the databases.

-- Store and compare timestamps in UTC.
ALTER DATABASE helpdesk SET timezone TO 'UTC';

-- Separate database for running the backend test suite against PostgreSQL
-- (TEST_DATABASE_URL=postgresql://helpdesk:<password>@localhost:5433/helpdesk_test).
CREATE DATABASE helpdesk_test;
ALTER DATABASE helpdesk_test SET timezone TO 'UTC';
