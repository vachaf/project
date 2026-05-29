-- 90_verify_mariadb_setup.sql
--
-- Purpose:
--   Verify the MariaDB setup after applying source-log and DB-backed MVP SQL.
--
-- Expected setup files:
--   00_database_and_log_accounts.sql
--   01_apache_log_tables.sql
--   01_analysis_job_tables.sql
--   10_log_source_table_grants.sql
--   11_analysis_app_grants.sql
--
-- Replace example hosts in SHOW GRANTS statements if your environment differs.

USE web_logs;

-- -----------------------------------------------------------------------------
-- Table existence
-- -----------------------------------------------------------------------------

SHOW TABLES;

-- -----------------------------------------------------------------------------
-- Source log table structure
-- -----------------------------------------------------------------------------

DESCRIBE apache_access_logs;
DESCRIBE apache_security_logs;
DESCRIBE apache_error_logs;

SHOW INDEX FROM apache_access_logs;
SHOW INDEX FROM apache_security_logs;
SHOW INDEX FROM apache_error_logs;

-- v1/v2/remoteip_v2-compatible source fields.
SELECT
  COLUMN_NAME,
  DATA_TYPE,
  IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'web_logs'
  AND TABLE_NAME = 'apache_security_logs'
  AND COLUMN_NAME IN (
    'log_schema',
    'request_target',
    'client_ip_source',
    'req_host',
    'x_forwarded_for',
    'x_real_ip',
    'forwarded',
    'has_cookie',
    'has_authorization',
    'remoteip_proxy_chain'
  )
ORDER BY ORDINAL_POSITION;

-- Expected: no rows. Security log Host header is stored as req_host.
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'web_logs'
  AND TABLE_NAME = 'apache_security_logs'
  AND COLUMN_NAME = 'host';

-- Expected: no rows. These are prepare_llm_input.py output fields, not DB columns.
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'web_logs'
  AND TABLE_NAME = 'apache_security_logs'
  AND COLUMN_NAME IN (
    'raw_request_target',
    'path_normalized_from_raw_request',
    'likely_html_fallback_response'
  );

-- -----------------------------------------------------------------------------
-- DB-backed MVP operation/control table structure
-- -----------------------------------------------------------------------------

DESCRIBE users;
DESCRIBE analysis_jobs;
DESCRIBE analysis_reports;
DESCRIBE job_events;

SHOW INDEX FROM users;
SHOW INDEX FROM analysis_jobs;
SHOW INDEX FROM analysis_reports;
SHOW INDEX FROM job_events;

-- -----------------------------------------------------------------------------
-- Accounts / grants
-- -----------------------------------------------------------------------------

SELECT User, Host
FROM mysql.user
WHERE User IN ('log_writer', 'log_reader', 'analysis_app')
ORDER BY User, Host;

SHOW GRANTS FOR 'log_writer'@'192.168.56.105';
SHOW GRANTS FOR 'log_writer'@'192.168.56.111';
SHOW GRANTS FOR 'log_reader'@'192.168.56.110';
SHOW GRANTS FOR 'analysis_app'@'192.168.56.110';
