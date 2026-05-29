-- 01_apache_log_tables.sql
--
-- Purpose:
--   Create source Apache log tables used by apache_log_shipper.py,
--   export_db_logs_cli.py, and the downstream prepare/LLM pipeline.
--
-- Scope:
--   - apache_access_logs
--   - apache_security_logs
--   - apache_error_logs
--
-- Out of scope:
--   - DB-backed MVP operation/control tables.
--     See docs/operations/sql/01_analysis_job_tables.sql.
--
-- Time policy:
--   log_time and created_at columns use MariaDB DATETIME(3).
--   apache_log_shipper.py stores normalized UTC naive DATETIME(3) values.

USE web_logs;

-- -----------------------------------------------------------------------------
-- apache_access_logs
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS apache_access_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NOT NULL,
    client_ip VARCHAR(45) DEFAULT NULL,
    method VARCHAR(16) DEFAULT NULL,
    raw_request TEXT,
    uri TEXT,
    query_string TEXT,
    protocol VARCHAR(16) DEFAULT NULL,
    status_code SMALLINT UNSIGNED DEFAULT NULL,
    response_body_bytes BIGINT UNSIGNED DEFAULT NULL,
    referer TEXT,
    user_agent TEXT,
    host VARCHAR(255) DEFAULT NULL,
    vhost VARCHAR(255) DEFAULT NULL,
    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_access_log_time (log_time),
    KEY idx_access_client_ip (client_ip),
    KEY idx_access_status_code (status_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -----------------------------------------------------------------------------
-- apache_security_logs
-- -----------------------------------------------------------------------------
-- This table stores Apache key=value observation fields. It intentionally does
-- not store prepare-only downstream fields such as raw_request_target,
-- path_normalized_from_raw_request, or likely_html_fallback_response.

CREATE TABLE IF NOT EXISTS apache_security_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    -- schema / time / correlation
    log_schema VARCHAR(64) DEFAULT NULL,
    log_time DATETIME(3) NOT NULL,
    request_id VARCHAR(128) DEFAULT NULL,
    error_link_id VARCHAR(128) DEFAULT NULL,

    -- vhost / server identity
    vhost VARCHAR(255) DEFAULT NULL,
    server_name VARCHAR(255) DEFAULT NULL,
    server_port INT UNSIGNED DEFAULT NULL,
    local_ip VARCHAR(45) DEFAULT NULL,

    -- client / peer identity observations
    client_ip_source VARCHAR(64) DEFAULT NULL,
    src_ip VARCHAR(45) DEFAULT NULL,
    peer_ip VARCHAR(45) DEFAULT NULL,
    remoteip_proxy_chain TEXT,

    -- request line / target
    method VARCHAR(16) DEFAULT NULL,
    raw_request TEXT,
    request_target TEXT,
    uri TEXT,
    query_string TEXT,
    protocol VARCHAR(16) DEFAULT NULL,

    -- response / IO metadata
    status_code SMALLINT UNSIGNED DEFAULT NULL,
    original_status_code SMALLINT UNSIGNED DEFAULT NULL,
    response_body_bytes BIGINT UNSIGNED DEFAULT NULL,
    in_bytes BIGINT UNSIGNED DEFAULT NULL,
    out_bytes BIGINT UNSIGNED DEFAULT NULL,
    total_bytes BIGINT UNSIGNED DEFAULT NULL,
    duration_us BIGINT UNSIGNED DEFAULT NULL,
    ttfb_us BIGINT UNSIGNED DEFAULT NULL,
    keepalive_count INT UNSIGNED DEFAULT NULL,
    connection_status VARCHAR(8) DEFAULT NULL,
    handler VARCHAR(255) DEFAULT NULL,

    -- request / response headers as observed metadata
    req_content_type VARCHAR(255) DEFAULT NULL,
    req_content_length BIGINT UNSIGNED DEFAULT NULL,
    resp_content_type VARCHAR(255) DEFAULT NULL,
    location TEXT,
    referer TEXT,
    origin TEXT,
    user_agent TEXT,
    req_host VARCHAR(255) DEFAULT NULL,
    x_forwarded_for TEXT,
    x_real_ip TEXT,
    forwarded TEXT,

    -- privacy-preserving presence flags only
    has_cookie TINYINT(1) DEFAULT NULL,
    has_authorization TINYINT(1) DEFAULT NULL,

    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    PRIMARY KEY (id),
    KEY idx_security_log_time (log_time),
    KEY idx_security_request_id (request_id),
    KEY idx_security_error_link_id (error_link_id),
    KEY idx_security_src_ip (src_ip),
    KEY idx_security_status_code (status_code),
    KEY idx_security_log_schema (log_schema),
    KEY idx_security_client_ip_source (client_ip_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -----------------------------------------------------------------------------
-- apache_error_logs
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS apache_error_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NOT NULL,
    error_link_id VARCHAR(128) DEFAULT NULL,
    request_id VARCHAR(128) DEFAULT NULL,
    module_name VARCHAR(128) DEFAULT NULL,
    log_level VARCHAR(64) DEFAULT NULL,
    src_ip VARCHAR(45) DEFAULT NULL,
    peer_ip VARCHAR(45) DEFAULT NULL,
    message LONGTEXT,
    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_error_log_time (log_time),
    KEY idx_error_error_link_id (error_link_id),
    KEY idx_error_request_id (request_id),
    KEY idx_error_log_level (log_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
