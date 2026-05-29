-- 00_database_and_log_accounts.sql
--
-- Purpose:
--   Create the MariaDB database and source-log DB accounts used by the
--   Apache log ingestion/export path.
--
-- Scope:
--   - web_logs database
--   - log_writer source-log ingestion accounts
--   - log_reader source-log export/read-only account
--
-- Notes:
--   Table-scoped grants are intentionally kept in
--   docs/operations/sql/10_log_source_table_grants.sql so log_writer does not
--   receive broad write permission on DB-backed MVP operation/control tables.
--
-- Replace example host IPs and passwords before applying in a real environment.

CREATE DATABASE IF NOT EXISTS web_logs
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

-- Source log ingestion accounts.
CREATE USER IF NOT EXISTS 'log_writer'@'192.168.56.105' IDENTIFIED BY 'YourPass'; -- JUICE SHOP example
CREATE USER IF NOT EXISTS 'log_writer'@'192.168.56.111' IDENTIFIED BY 'YourPass'; -- OPENCART example

-- Source log export/read-only account for the LLM/analysis server.
CREATE USER IF NOT EXISTS 'log_reader'@'192.168.56.110' IDENTIFIED BY 'YourPass'; -- LLM / Analysis server example

FLUSH PRIVILEGES;
