-- 11_analysis_app_grants.sql
--
-- 목적:
--   Web UI 백엔드 / Analysis Agent가 작업 라이프사이클 메타데이터를 관리할 때 사용하는
--   DB 기반 MVP 애플리케이션 계정을 생성하고 권한을 부여합니다.
--
-- 선행 조건:
--   - docs/operations/sql/01_analysis_job_tables.sql에서 다음 테이블을 생성해야 합니다:
--     users, analysis_jobs, analysis_reports, job_events.
--
-- 범위:
--   - analysis_app은 작업 라이프사이클 메타데이터를 읽고 쓸 수 있습니다.
--   - analysis_app은 소스 Apache 로그 테이블에 쓰기 권한을 가지면 안 됩니다.
--   - log_reader는 소스 로그 읽기 전용 계정으로 유지하며 작업 쓰기 용도로 사용하지 않습니다.
--
-- 실제 환경에 적용하기 전에 예시 호스트 IP와 비밀번호를 반드시 변경하세요.

USE web_logs;

CREATE USER IF NOT EXISTS 'analysis_app'@'192.168.56.110' IDENTIFIED BY 'YourPass'; -- Web UI 백엔드 / Analysis Agent 예시 계정

-- users는 최소 조회용 테이블로 시작할 수 있습니다. 실제 사용자 생성/수정은
-- 후속 관리자 또는 마이그레이션 워크플로에서 별도로 처리할 수 있습니다.
GRANT SELECT ON web_logs.users TO 'analysis_app'@'192.168.56.110';

-- 작업 라이프사이클 테이블: Web UI는 PENDING 작업을 등록하고,
-- Analysis Agent는 작업을 할당받아 라이프사이클 상태를 갱신합니다.
GRANT SELECT, INSERT, UPDATE ON web_logs.analysis_jobs TO 'analysis_app'@'192.168.56.110';

-- 보고서/산출물 메타데이터 테이블: Analysis Agent는 완료 또는 일부 완료된
-- 보고서 경로를 등록/갱신하고, Web UI는 이를 조회합니다.
GRANT SELECT, INSERT, UPDATE ON web_logs.analysis_reports TO 'analysis_app'@'192.168.56.110';

-- 이벤트 타임라인: 일반 운영에서는 append-only로 사용합니다.
-- MVP에서는 UPDATE 권한을 의도적으로 부여하지 않습니다.
GRANT SELECT, INSERT ON web_logs.job_events TO 'analysis_app'@'192.168.56.110';

FLUSH PRIVILEGES;