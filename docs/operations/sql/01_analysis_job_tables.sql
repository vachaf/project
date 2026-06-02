-- 01_analysis_job_tables.sql
--
-- 목적:
--   web_log_analysis MVP를 위한 데이터베이스 기반 분석 작업 라이프사이클 테이블을 추가합니다.
--
-- 범위:
--   - users (사용자)
--   - analysis_jobs (분석 작업)
--   - analysis_reports (분석 보고서)
--   - job_events (작업 이벤트)
--
-- 첫 번째 SQL 파일의 범위 제외 대상:
--   - apache_access_logs / apache_security_logs / apache_error_logs
--     이 소스 로그 테이블들은 docs/operations/02_MariaDB_환경_구축_및_설치.md에 정의되어 있습니다.
--   - log_collection_checkpoints
--     src/apache_log_shipper.py는 현재 파일 상태 오프셋 추적 방식을 사용합니다. 
--     DB 체크포인트 테이블 사용 여부는 후속 결정 과제로 남겨둡니다.
--
-- 시간 정책:
--   이 스키마의 MariaDB DATETIME(3) 컬럼은 변환되지 않은 UTC 타임스탬프(naive)를 저장합니다.
--   MVP 버전의 웹 UI 입력 및 표시용 시간은 'Asia/Seoul'로 유지됩니다.
--
-- 보안 정책:
--   이 테이블들에는 API 키, .env 내용, 공급자 비밀 정보(secrets), 공급자 원본 에러 본문,
--   원본 요청 본문(raw request bodies) 또는 응답 본문을 저장하지 마십시오.

USE web_logs;

-- -----------------------------------------------------------------------------
-- users (사용자 테이블)
-- -----------------------------------------------------------------------------
-- 최소 기능의 웹 UI 사용자 테이블입니다.
-- v1 버전은 단일 운영자/관리자 유저로 시작하거나, 작업 요청자(requested_by)에 NULL을 허용할 수 있습니다.

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(128) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'operator',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),

    PRIMARY KEY (id),
    UNIQUE KEY uk_users_username (username),
    KEY idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -----------------------------------------------------------------------------
-- analysis_jobs (분석 작업 큐 테이블)
-- -----------------------------------------------------------------------------
-- 사용자가 요청한 분석 작업의 실행 큐입니다.
-- 이는 operator_queue와 다릅니다:
--   - analysis_jobs: DB 기반의 실행 라이프사이클 큐
--   - operator_queue: 롤업 검토 산출물 큐 (queue_items.json / queue_summary.json)
--
-- 애플리케이션 레벨에서 다음 검증을 강제해야 합니다:
--   - time_from < time_to
--   - MVP 버전에서는 requested_timezone = 'Asia/Seoul' 고정
--   - MVP 버전에서는 analysis_mode = 'full_report' 고정
--   - status 값은 PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED 중 하나여야 함
--   - 최대 시간 범위 정책 적용 (일반 웹 UI 작업의 경우 초기 24시간 제한)
--   - 동일 유저/시간/모드/타임존에 대한 중복 PENDING/RUNNING 작업 처리 로직 필요
--
-- 원자적 할당 패턴 (Atomic claim pattern):
--   UPDATE analysis_jobs
--   SET status='RUNNING', started_at=CURRENT_TIMESTAMP(3), worker_id=?,
--       heartbeat_at=CURRENT_TIMESTAMP(3), attempt_count=attempt_count+1
--   WHERE id=? AND status='PENDING';
--
-- 워커(Worker)는 영향받은 행의 수(affected_rows)가 정확히 1일 때만 작업을 실행해야 합니다.

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    requested_by BIGINT UNSIGNED DEFAULT NULL,

    -- DB 데이터 내보내기 쿼리에 사용되는 변환되지 않은 UTC DATETIME(3) 범위
    time_from DATETIME(3) NOT NULL,
    time_to DATETIME(3) NOT NULL,

    -- MVP 웹 UI는 Asia/Seoul 입력 및 표시만 허용합니다.
    requested_timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Seoul',

    -- MVP 상태값: PENDING / RUNNING / SUCCEEDED / FAILED
    -- (CANCELLED 상태는 차후 버전을 위해 예약됨)
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',

    -- MVP 모드: full_report
    -- (full_report는 export + prepare + Stage1 + Stage2 + viewer_payload 전체 과정을 의미함)
    analysis_mode VARCHAR(64) NOT NULL DEFAULT 'full_report',

    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    started_at DATETIME(3) DEFAULT NULL,
    finished_at DATETIME(3) DEFAULT NULL,

    worker_id VARCHAR(128) DEFAULT NULL,
    heartbeat_at DATETIME(3) DEFAULT NULL,
    attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
    max_attempts INT UNSIGNED NOT NULL DEFAULT 1,

    -- 마스킹 처리된(개인정보 등이 정제된) 운영자 안전 에러 요약본만 저장합니다.
    -- 공급자의 원본 응답 본문이나 기밀 정보는 저장하지 마십시오.
    error_message TEXT,

    -- 서버에서 생성한 작업 스코프 경로만 저장합니다. 사용자가 입력한 임의의 경로는 허용하지 마십시오.
    artifact_root TEXT,

    PRIMARY KEY (id),
    KEY idx_analysis_jobs_status_created_at (status, created_at),
    KEY idx_analysis_jobs_time_range (time_from, time_to),
    KEY idx_analysis_jobs_requested_by (requested_by),
    KEY idx_analysis_jobs_mode_status (analysis_mode, status),
    KEY idx_analysis_jobs_worker_status (worker_id, status),
    CONSTRAINT fk_analysis_jobs_requested_by
        FOREIGN KEY (requested_by) REFERENCES users(id)
        ON UPDATE RESTRICT
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -----------------------------------------------------------------------------
-- analysis_reports (분석 보고서 메타데이터 테이블)
-- -----------------------------------------------------------------------------
-- 완료되었거나 일부 완료된 분석 작업의 메타데이터 및 산출물 경로를 저장합니다.
-- 용량이 큰 JSON 산출물은 디스크에 유지하고, DB에는 경로와 요약된 컴팩트 데이터만 저장합니다.

CREATE TABLE IF NOT EXISTS analysis_reports (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_id BIGINT UNSIGNED NOT NULL,

    summary TEXT,
    artifact_root TEXT NOT NULL,

    export_path TEXT,
    llm_input_path TEXT,
    analysis_candidates_path TEXT,
    noise_summary_path TEXT,

    window_summary_path TEXT,
    rollup_input_path TEXT,
    rollup_summary_path TEXT,
    operator_queue_items_path TEXT,
    operator_queue_summary_path TEXT,

    stage1_result_path TEXT,
    stage2_report_path TEXT,
    stage2_report_md_path TEXT,
    viewer_payload_path TEXT,
    lint_result_path TEXT,

    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    PRIMARY KEY (id),
    UNIQUE KEY uk_analysis_reports_job_id (job_id),
    KEY idx_analysis_reports_created_at (created_at),
    CONSTRAINT fk_analysis_reports_job_id
        FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -----------------------------------------------------------------------------
-- job_events (작업 이벤트 타임라인 테이블)
-- -----------------------------------------------------------------------------
-- 분석 작업 실행의 단계별 타임라인 기록 테이블입니다.
-- detail_json 컬럼에는 민감 정보가 정제된 구조화된 메타데이터만 저장해야 합니다.

CREATE TABLE IF NOT EXISTS job_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_id BIGINT UNSIGNED NOT NULL,
    event_time DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    event_type VARCHAR(64) NOT NULL,
    message TEXT,
    detail_json LONGTEXT,

    PRIMARY KEY (id),
    KEY idx_job_events_job_time (job_id, event_time),
    KEY idx_job_events_event_type (event_type),
    CONSTRAINT fk_job_events_job_id
        FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 권장하는 MVP용 event_type 값 목록 (CHECK 제약 조건 대신 애플리케이션 유효성 검사로 강제함):
--   JOB_CREATED (작업 생성됨)
--   JOB_CLAIMED (작업 할당됨)
--   JOB_STARTED (작업 실행 시작됨)
--   EXPORT_STARTED (내보내기 시작됨)
--   EXPORT_COMPLETED (내보내기 완료됨)
--   EXPORT_FAILED (내보내기 실패함)
--   EXPORT_NO_DATA (내보내기 결과 분석 대상 로그가 없음)
--   PIPELINE_STARTED (분석 파이프라인 시작됨)
--   PIPELINE_COMPLETED (분석 파이프라인 완료됨)
--   PIPELINE_FAILED (분석 파이프라인 실패함)
--   REPORT_SAVE_STARTED (분석 보고서 메타데이터 저장 시작됨)
--   REPORT_SAVE_COMPLETED (분석 보고서 메타데이터 저장 완료됨)
--   REPORT_SAVE_FAILED (분석 보고서 메타데이터 저장 실패함)
--   JOB_NO_DATA (no-data 작업 호환 이벤트)
--   JOB_SUCCEEDED (작업 성공함)
--   JOB_FAILED (작업 실패함)
--
-- Phase 2 이후에만 검토할 fine-grained event_type 후보:
--   PREPARE_STARTED / PREPARE_COMPLETED / PREPARE_FAILED
--   STAGE1_STARTED / STAGE1_COMPLETED / STAGE1_FAILED
--   STAGE2_STARTED / STAGE2_COMPLETED / STAGE2_FAILED
--   VIEWER_PAYLOAD_STARTED / VIEWER_PAYLOAD_COMPLETED / VIEWER_PAYLOAD_FAILED
