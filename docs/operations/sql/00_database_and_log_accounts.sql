-- 00_database_and_log_accounts.sql
--
-- 목적:
--   Apache 로그 수집 및 내보내기 경로에서 사용하는 
--   MariaDB 데이터베이스와 소스 로그 DB 계정을 생성합니다.
--
-- 범위:
--   - web_logs 데이터베이스
--   - log_writer: 소스 로그 수집/입력용 계정
--   - log_reader: 소스 로그 내보내기/읽기 전용 계정
--
-- 주의사항:
--   테이블 단위의 권한 부여는 보안을 위해 의도적으로 분리되어 있습니다.
--   이 스크립트에서는 데이터베이스와 기본 계정만 생성하며, 
--   log_writer 계정이 운영/제어용 테이블에 광범위한 쓰기 권한을 
--   가지지 않도록 세부 테이블 권한은 별도 스크립트에서 관리합니다.
--
-- 실제 환경에 적용하기 전에 예시로 작성된 호스트 IP와 비밀번호를 반드시 변경하세요.

-- 1. 웹 로그 저장을 위한 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS web_logs
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

-- 2. 소스 로그 수집 및 입력용 계정 생성 (로그를 보내는 서버들)
-- (예시 아파치 서비스 서버)
CREATE USER IF NOT EXISTS 'log_writer'@'192.168.56.105' IDENTIFIED BY 'YourPass'; 

-- 3. LLM 및 분석 서버용 소스 로그 내보내기/읽기 전용 계정 생성
-- (분석/조회 전용 서버)
CREATE USER IF NOT EXISTS 'log_reader'@'192.168.56.110' IDENTIFIED BY 'YourPass'; 

-- 4. 변경된 권한 즉시 적용
FLUSH PRIVILEGES;