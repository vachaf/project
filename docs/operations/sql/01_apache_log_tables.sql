-- 01_apache_log_tables.sql
--
-- 목적:
--   apache_log_shipper.py, export_db_logs_cli.py, 그리고 후속 prepare/LLM 파이프라인에서
--   사용하는 소스 Apache 로그 테이블을 생성합니다.
--
-- 범위:
--   - apache_access_logs
--   - apache_security_logs
--   - apache_error_logs
--
-- 범위 제외 대상:
--   - DB 기반 MVP 운영/제어 테이블
--     해당 테이블은 docs/operations/sql/01_analysis_job_tables.sql을 참고하십시오.
--
-- 시간 정책:
--   log_time 및 created_at 컬럼은 MariaDB DATETIME(3)을 사용합니다.
--   apache_log_shipper.py는 정규화된 UTC naive DATETIME(3) 값을 저장합니다.

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
-- 이 테이블은 Apache key=value 관측 필드를 저장합니다. prepare 단계에서만 생성되는
-- 후속 필드(raw_request_target, path_normalized_from_raw_request,
-- likely_html_fallback_response 등)는 의도적으로 저장하지 않습니다.

CREATE TABLE IF NOT EXISTS apache_security_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    -- 스키마 / 시간 / 상관관계 식별자
    log_schema VARCHAR(64) DEFAULT NULL,
    log_time DATETIME(3) NOT NULL,
    request_id VARCHAR(128) DEFAULT NULL,
    error_link_id VARCHAR(128) DEFAULT NULL,

    -- 가상 호스트 / 서버 식별 정보
    vhost VARCHAR(255) DEFAULT NULL,
    server_name VARCHAR(255) DEFAULT NULL,
    server_port INT UNSIGNED DEFAULT NULL,
    local_ip VARCHAR(45) DEFAULT NULL,

    -- 클라이언트 / 피어 식별 관측값
    client_ip_source VARCHAR(64) DEFAULT NULL,
    src_ip VARCHAR(45) DEFAULT NULL,
    peer_ip VARCHAR(45) DEFAULT NULL,
    remoteip_proxy_chain TEXT,

    -- 요청 라인 / 요청 대상
    method VARCHAR(16) DEFAULT NULL,
    raw_request TEXT,
    request_target TEXT,
    uri TEXT,
    query_string TEXT,
    protocol VARCHAR(16) DEFAULT NULL,

    -- 응답 / 입출력 메타데이터
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

    -- 관측된 요청 / 응답 헤더 메타데이터
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

    -- 개인정보 보호를 위해 존재 여부 플래그만 저장
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