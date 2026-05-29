-- 10_log_source_table_grants.sql
--
-- Purpose:
--   Apply least-privilege grants for source Apache log ingestion/export.
--
-- Preconditions:
--   - docs/operations/sql/00_database_and_log_accounts.sql has created accounts.
--   - docs/operations/sql/01_apache_log_tables.sql has created source log tables.
--
-- Scope:
--   - log_writer: write source Apache log tables only.
--   - log_reader: read source Apache log tables only.
--
-- Notes:
--   Do not use log_reader for DB-backed analysis job writes.
--   DB-backed MVP operation/control table grants should use a separate account,
--   for example analysis_app, and should be applied separately.
--
-- Replace example host IPs before applying in a real environment.

USE web_logs;

-- JUICE SHOP example writer.
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_access_logs TO 'log_writer'@'192.168.56.105';
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_security_logs TO 'log_writer'@'192.168.56.105';
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_error_logs TO 'log_writer'@'192.168.56.105';

-- OPENCART example writer.
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_access_logs TO 'log_writer'@'192.168.56.111';
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_security_logs TO 'log_writer'@'192.168.56.111';
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_error_logs TO 'log_writer'@'192.168.56.111';

-- LLM / Analysis server read-only source log export account.
GRANT SELECT ON web_logs.apache_access_logs TO 'log_reader'@'192.168.56.110';
GRANT SELECT ON web_logs.apache_security_logs TO 'log_reader'@'192.168.56.110';
GRANT SELECT ON web_logs.apache_error_logs TO 'log_reader'@'192.168.56.110';

FLUSH PRIVILEGES;
