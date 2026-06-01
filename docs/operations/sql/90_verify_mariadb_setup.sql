-- 90_verify_mariadb_setup.sql
--
-- 목적:
--   소스 로그 SQL 및 DB 기반 MVP SQL을 적용한 뒤 MariaDB 설정 상태를 확인합니다.
--
-- 예상 적용 파일:
--   00_database_and_log_accounts.sql
--   01_apache_log_tables.sql
--   01_analysis_job_tables.sql
--   10_log_source_table_grants.sql
--   11_analysis_app_grants.sql
--
-- 환경이 다르면 SHOW GRANTS 문에 들어간 예시 호스트를 실제 값으로 바꿔서 확인하십시오.

USE web_logs;

-- -----------------------------------------------------------------------------
-- 테이블 존재 여부
-- -----------------------------------------------------------------------------

SHOW TABLES;

-- -----------------------------------------------------------------------------
-- 소스 로그 테이블 구조
-- -----------------------------------------------------------------------------

DESCRIBE apache_access_logs;
DESCRIBE apache_security_logs;
DESCRIBE apache_error_logs;

SHOW INDEX FROM apache_access_logs;
SHOW INDEX FROM apache_security_logs;
SHOW INDEX FROM apache_error_logs;

-- v1/v2/remoteip_v2 호환 소스 필드
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

-- 기대 결과: 행이 없어야 합니다. security 로그의 Host 헤더는 req_host에 저장합니다.
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'web_logs'
  AND TABLE_NAME = 'apache_security_logs'
  AND COLUMN_NAME = 'host';

-- 기대 결과: 행이 없어야 합니다. 아래 항목들은 DB 컬럼이 아니라 prepare_llm_input.py 출력 필드입니다.
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
-- DB 기반 MVP 운영/제어 테이블 구조
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
-- 계정 / 권한
-- -----------------------------------------------------------------------------

SELECT User, Host
FROM mysql.user
WHERE User IN ('log_writer', 'log_reader', 'analysis_app')
ORDER BY User, Host;

SHOW GRANTS FOR 'log_writer'@'192.168.56.105';
SHOW GRANTS FOR 'log_writer'@'192.168.56.111';
SHOW GRANTS FOR 'log_reader'@'192.168.56.110';
SHOW GRANTS FOR 'analysis_app'@'192.168.56.110';