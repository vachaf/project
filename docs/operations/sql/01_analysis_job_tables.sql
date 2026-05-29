-- 01_analysis_job_tables.sql
--
-- Purpose:
--   Add DB-backed analysis job lifecycle tables for the web_log_analysis MVP.
--
-- Scope:
--   - users
--   - analysis_jobs
--   - analysis_reports
--   - job_events
--
-- Out of scope for this first SQL file:
--   - apache_access_logs / apache_security_logs / apache_error_logs
--     These source log tables are defined in docs/operations/02_MariaDB_환경_구축_및_설치.md.
--   - log_collection_checkpoints
--     src/apache_log_shipper.py currently uses file-state offset tracking. A DB checkpoint
--     table remains a follow-up decision.
--
-- Time policy:
--   MariaDB DATETIME(3) columns in this schema store UTC naive timestamps.
--   Web UI input/display remains Asia/Seoul for the MVP.
--
-- Safety policy:
--   Do not store API keys, .env contents, provider secrets, raw provider error bodies,
--   raw request bodies, or response bodies in these tables.

USE web_logs;

-- -----------------------------------------------------------------------------
-- users
-- -----------------------------------------------------------------------------
-- Minimal Web UI user table.
-- v1 may start with a single operator/admin user or nullable requested_by jobs.

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
-- analysis_jobs
-- -----------------------------------------------------------------------------
-- Execution queue for user-requested analysis jobs.
-- This is not the same as operator_queue:
--   - analysis_jobs: DB-backed execution lifecycle queue
--   - operator_queue: rollup review artifact queue_items.json / queue_summary.json
--
-- Application-level validation must enforce:
--   - time_from < time_to
--   - requested_timezone = 'Asia/Seoul' for MVP
--   - analysis_mode = 'full_report' for MVP
--   - status in PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED
--   - max time range policy, initially 24 hours for normal Web UI jobs
--   - duplicate PENDING/RUNNING job handling for the same user/time/mode/timezone
--
-- Atomic claim pattern:
--   UPDATE analysis_jobs
--   SET status='RUNNING', started_at=CURRENT_TIMESTAMP(3), worker_id=?,
--       heartbeat_at=CURRENT_TIMESTAMP(3), attempt_count=attempt_count+1
--   WHERE id=? AND status='PENDING';
--
-- The worker may execute the job only when affected_rows == 1.

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    requested_by BIGINT UNSIGNED DEFAULT NULL,

    -- UTC naive DATETIME(3) range used for DB export queries.
    time_from DATETIME(3) NOT NULL,
    time_to DATETIME(3) NOT NULL,

    -- MVP Web UI accepts Asia/Seoul input/display only.
    requested_timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Seoul',

    -- MVP states: PENDING / RUNNING / SUCCEEDED / FAILED.
    -- CANCELLED is reserved for a later version.
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',

    -- MVP mode: full_report.
    -- full_report means export + prepare + Stage1 + Stage2 + viewer_payload.
    analysis_mode VARCHAR(64) NOT NULL DEFAULT 'full_report',

    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    started_at DATETIME(3) DEFAULT NULL,
    finished_at DATETIME(3) DEFAULT NULL,

    worker_id VARCHAR(128) DEFAULT NULL,
    heartbeat_at DATETIME(3) DEFAULT NULL,
    attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
    max_attempts INT UNSIGNED NOT NULL DEFAULT 1,

    -- Store redacted, operator-safe error summaries only.
    -- Do not store provider raw response bodies or secrets.
    error_message TEXT,

    -- Server-generated, job-scoped path only. Do not accept arbitrary user path input.
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
-- analysis_reports
-- -----------------------------------------------------------------------------
-- Metadata and artifact paths for completed or partially completed analysis jobs.
-- Large JSON artifacts stay on disk. DB stores paths and a compact summary only.

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
-- job_events
-- -----------------------------------------------------------------------------
-- Step timeline for analysis job execution.
-- detail_json is intended for redacted structured metadata only.

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

-- Suggested MVP event_type values, enforced by application validation rather than CHECK:
--   JOB_CREATED
--   JOB_CLAIMED
--   EXPORT_STARTED
--   EXPORT_FINISHED
--   PREPARE_STARTED
--   PREPARE_FINISHED
--   WINDOW_STARTED
--   WINDOW_FINISHED
--   ROLLUP_STARTED
--   ROLLUP_FINISHED
--   OPERATOR_QUEUE_STARTED
--   OPERATOR_QUEUE_FINISHED
--   STAGE1_STARTED
--   STAGE1_FINISHED
--   STAGE2_STARTED
--   STAGE2_FINISHED
--   VIEWER_PAYLOAD_WRITTEN
--   JOB_SUCCEEDED
--   JOB_FAILED
