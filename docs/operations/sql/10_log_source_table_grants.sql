-- 10_log_source_table_grants.sql
--
-- 목적:
--   소스 Apache 로그 수집/내보내기 계정에 최소 권한 원칙에 따른 권한을 부여합니다.
--
-- 선행 조건:
--   - docs/operations/sql/00_database_and_log_accounts.sql에서 계정을 생성해야 합니다.
--   - docs/operations/sql/01_apache_log_tables.sql에서 소스 로그 테이블을 생성해야 합니다.
--
-- 범위:
--   - log_writer: 소스 Apache 로그 테이블에만 쓰기 가능
--   - log_reader: 소스 Apache 로그 테이블에만 읽기 가능
--
-- 주의사항:
--   log_reader를 DB 기반 분석 작업 쓰기 용도로 사용하지 마십시오.
--   DB 기반 MVP 운영/제어 테이블 권한은 analysis_app 같은 별도 계정으로 분리하고,
--   별도 스크립트에서 부여해야 합니다.
--
-- 실제 환경에 적용하기 전에 예시 호스트 IP를 반드시 변경하세요.

USE web_logs;

-- JUICE SHOP 예시 로그 입력 서버
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_access_logs TO 'log_writer'@'192.168.56.105';
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_security_logs TO 'log_writer'@'192.168.56.105';
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_error_logs TO 'log_writer'@'192.168.56.105';

-- OPENCART 예시 로그 입력 서버
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_access_logs TO 'log_writer'@'192.168.56.111';
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_security_logs TO 'log_writer'@'192.168.56.111';
GRANT SELECT, INSERT, UPDATE ON web_logs.apache_error_logs TO 'log_writer'@'192.168.56.111';

-- LLM / 분석 서버용 소스 로그 읽기 전용 내보내기 계정
GRANT SELECT ON web_logs.apache_access_logs TO 'log_reader'@'192.168.56.110';
GRANT SELECT ON web_logs.apache_security_logs TO 'log_reader'@'192.168.56.110';
GRANT SELECT ON web_logs.apache_error_logs TO 'log_reader'@'192.168.56.110';

FLUSH PRIVILEGES;