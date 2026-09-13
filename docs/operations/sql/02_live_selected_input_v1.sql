-- Live Selected Input Contract v1 migration for an existing web_logs database.
-- Apply after 01_analysis_job_tables.sql.

USE web_logs;

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS input_kind VARCHAR(64) NOT NULL DEFAULT 'time_range'
        AFTER analysis_mode,
    ADD COLUMN IF NOT EXISTS input_source_table VARCHAR(128) DEFAULT NULL
        AFTER input_kind,
    ADD COLUMN IF NOT EXISTS input_fingerprint
        CHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL
        AFTER input_source_table;

CREATE TABLE IF NOT EXISTS analysis_job_selected_logs (
    job_id BIGINT UNSIGNED NOT NULL,
    selection_index SMALLINT UNSIGNED NOT NULL,
    selected_log_id BIGINT UNSIGNED NOT NULL,

    PRIMARY KEY (job_id, selection_index),
    UNIQUE KEY uk_analysis_job_selected_log (job_id, selected_log_id),
    KEY idx_analysis_job_selected_log_id (selected_log_id),
    CONSTRAINT fk_analysis_job_selected_logs_job_id
        FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

ALTER TABLE analysis_jobs
    ADD INDEX IF NOT EXISTS idx_analysis_jobs_input_duplicate (
        input_kind, input_source_table, input_fingerprint, status
    );
