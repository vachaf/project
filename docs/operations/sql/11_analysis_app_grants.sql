-- 11_analysis_app_grants.sql
--
-- Purpose:
--   Create and grant the DB-backed MVP application account used by the
--   Web UI backend / Analysis Agent for job lifecycle metadata.
--
-- Preconditions:
--   - docs/operations/sql/01_analysis_job_tables.sql has created:
--     users, analysis_jobs, analysis_reports, job_events.
--
-- Scope:
--   - analysis_app can read/write job lifecycle metadata.
--   - analysis_app must not write source Apache log tables.
--   - log_reader remains source-log read-only and is not used for job writes.
--
-- Replace the example host IP and password before applying in a real environment.

USE web_logs;

CREATE USER IF NOT EXISTS 'analysis_app'@'192.168.56.110' IDENTIFIED BY 'YourPass'; -- Web UI backend / Analysis Agent example

-- users may start as a minimal lookup table. Creation/update of real users can
-- be handled by a separate admin/migration workflow later.
GRANT SELECT ON web_logs.users TO 'analysis_app'@'192.168.56.110';

-- Job lifecycle table: Web UI inserts PENDING jobs; Analysis Agent claims and
-- updates lifecycle state.
GRANT SELECT, INSERT, UPDATE ON web_logs.analysis_jobs TO 'analysis_app'@'192.168.56.110';

-- Report/artifact metadata table: Analysis Agent inserts/updates completed or
-- partially completed report paths; Web UI reads them.
GRANT SELECT, INSERT, UPDATE ON web_logs.analysis_reports TO 'analysis_app'@'192.168.56.110';

-- Event timeline: append-only in normal operation. UPDATE is intentionally not
-- granted for the MVP.
GRANT SELECT, INSERT ON web_logs.job_events TO 'analysis_app'@'192.168.56.110';

FLUSH PRIVILEGES;
