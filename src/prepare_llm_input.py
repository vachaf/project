#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_db_logs_cli.py 로 생성한 KST 기준 JSON export 를 입력받아
LLM 분석용 정제 산출물을 생성하는 전처리 스크립트.

주요 역할
- 정상 잡음(socket.io polling, 정적 리소스 등) 식별
- 반복 정상 요청 집계(noise_summary)
- 규칙 기반 의심 후보 추출(analysis_candidates)
- 선택한 소스 테이블 범위(기본값: security)만 대상으로 분석
- 동일 테이블 안의 incident 중복 row 를 incident 기준으로 dedup
- LLM 입력용 통합 JSON 생성

권장 위치
- 별도 분석 VM 의 파이프라인 디렉터리
- 예: /opt/web_log_analysis/src/prepare_llm_input.py

입력
- export_db_logs_cli.py 의 JSON payload

출력
- <base>_llm_input.json
- <base>_analysis_candidates.json
- <base>_noise_summary.json
- <base>_filtered_out_rows.json (선택)
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
import hashlib
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, unquote_plus

try:
    from src.prepare.decoders import (
        append_html_entity_variants as _append_html_entity_variants,
        build_decoded_variants as _build_decoded_variants,
        build_html_entity_decoded_variant as _build_html_entity_decoded_variant,
        build_html_entity_variants as _build_html_entity_variants,
    )
    from src.prepare.l3_hints import (
        classify_ssrf_target as _classify_ssrf_target,
        classify_webshell_path as _classify_webshell_path,
        detect_educational_ssti_search_context as _detect_educational_ssti_search_context,
        detect_log4shell_hints as _detect_log4shell_hints,
        detect_ssrf_hints as _detect_ssrf_hints,
        detect_ssti_hints as _detect_ssti_hints,
        detect_webshell_hints as _detect_webshell_hints,
        extract_query_pairs_from_variants as _extract_query_pairs_from_variants,
    )
    from src.prepare.sqli_hints import (
        EDUCATIONAL_SQL_SEARCH_TERMS,
        REPEATED_QUOTE_PATTERN,
        SQLI_BOOLEAN_CONDITION_PATTERN,
        SQLI_BOOLEAN_TRUE_CONDITION_PATTERN,
        SQLI_COMMENT_PATTERN,
        SQLI_FROM_USERS_PATTERN,
        SQLI_PAREN_TERMINATION_PATTERN,
        SQLI_PATTERNS,
        SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN,
        SQLI_SCHEMA_ACCESS_PATTERN,
        SQLI_UNION_COLUMN_ENUM_PATTERN,
        SQLI_XCLOSE_PATTERN,
        SUPPORTING_SQL_KEYWORDS,
        detect_educational_sql_search_context as _detect_educational_sql_search_context,
    )
    from src.prepare.xss_hints import (
        BROWSER_DATA_ACCESS_RE,
        EDUCATIONAL_XSS_KEYWORDS,
        EDUCATIONAL_XSS_SEARCH_TERMS,
        EVENT_HANDLER_ASSIGNMENT_RE,
        EXTERNAL_NAVIGATION_RE,
        EXTERNAL_URL_RE,
        JAVASCRIPT_PROTOCOL_RE,
        SCRIPT_TAG_CAPTURE_RE,
        SCRIPT_TAG_PATTERN,
        XSS_PATTERNS,
        XSS_QUOTE_BREAKOUT_PATTERN,
        XSS_TAG_INJECTION_PATTERN,
    )
    from src.prepare.traversal_cmdi_hints import (
        CMDI_PATTERNS,
        TRAVERSAL_PATTERNS,
    )
    from src.prepare.file_disclosure_hints import (
        FILE_DISCLOSURE_PATTERNS,
        PHP_FILTER_CANONICAL_PATTERN,
        detect_file_disclosure_hints as _detect_file_disclosure_hints,
    )
    from src.prepare.method_summaries import (
        METHOD_BASELINE_FAMILIES,
        METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        METHOD_BEHAVIOR_WINDOW_SEC,
        METHOD_DESTRUCTIVE_FAMILIES,
        METHOD_RISKY_FAMILIES,
        build_method_behavior_reason_hints_for_row as _build_method_behavior_reason_hints_for_row,
        build_method_behavior_summaries as _build_method_behavior_summaries,
        build_method_behavior_summary_contexts as _build_method_behavior_summary_contexts,
    )
    from src.prepare.auth_behavior import (
        build_auth_behavior_summaries as _build_auth_behavior_summaries,
        build_auth_behavior_summary_contexts as _build_auth_behavior_summary_contexts,
        finalize_auth_behavior_bucket as _finalize_auth_behavior_bucket,
    )
    from src.prepare.protocol_anomalies import (
        PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
        PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT,
        PROTOCOL_ANOMALY_WINDOW_SEC,
        build_protocol_anomaly_reason_hints_for_row as _build_protocol_anomaly_reason_hints_for_row,
        build_protocol_anomaly_summaries as _build_protocol_anomaly_summaries,
        build_protocol_anomaly_summary_contexts as _build_protocol_anomaly_summary_contexts,
        finalize_protocol_anomaly_bucket as _finalize_protocol_anomaly_bucket,
    )
    from src.prepare.static_baseline import (
        STATIC_BASELINE_MIN_STATIC_PATHS,
        STATIC_BASELINE_SAMPLE_REQUEST_LIMIT,
        STATIC_BASELINE_WINDOW_SEC,
        build_static_baseline_reason_hints_for_row as _build_static_baseline_reason_hints_for_row,
        build_static_baseline_summaries as _build_static_baseline_summaries,
        build_static_baseline_summary_contexts as _build_static_baseline_summary_contexts,
        finalize_static_baseline_bucket as _finalize_static_baseline_bucket,
    )
    from src.prepare.crawler_baseline import (
        build_crawler_baseline_reason_hints_for_row as _build_crawler_baseline_reason_hints_for_row,
        build_crawler_baseline_summaries as _build_crawler_baseline_summaries,
        build_crawler_baseline_summary_contexts as _build_crawler_baseline_summary_contexts,
        classify_crawler_baseline_path_category as _classify_crawler_baseline_path_category,
        classify_crawler_like_user_agent_family as _classify_crawler_like_user_agent_family,
        finalize_crawler_baseline_bucket as _finalize_crawler_baseline_bucket,
    )
    from src.prepare.sensitive_path_probe import (
        build_sensitive_path_probe_summaries as _build_sensitive_path_probe_summaries,
        build_sensitive_path_probe_summary_contexts as _build_sensitive_path_probe_summary_contexts,
        classify_sensitive_path_probe_category as _classify_sensitive_path_probe_category,
        finalize_sensitive_path_probe_bucket as _finalize_sensitive_path_probe_bucket,
    )
    from src.prepare.ip_behavior import (
        IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        IP_BEHAVIOR_SENSITIVE_PATH_LIMIT,
        IP_BEHAVIOR_WINDOW_SEC,
        build_ip_behavior_aggregates as _build_ip_behavior_aggregates,
        finalize_ip_behavior_bucket as _finalize_ip_behavior_bucket,
        is_sensitive_ip_behavior_path as _is_sensitive_ip_behavior_path,
    )
    from src.prepare.probing_sequence import (
        build_probing_sequence_summaries as _build_probing_sequence_summaries,
        finalize_probing_sequence_bucket as _finalize_probing_sequence_bucket,
    )
    from src.prepare.mixed_baseline_scanner import (
        build_mixed_baseline_scanner_row_context as _build_mixed_baseline_scanner_row_context,
        build_mixed_baseline_scanner_summaries as _build_mixed_baseline_scanner_summaries,
        finalize_mixed_baseline_scanner_bucket as _finalize_mixed_baseline_scanner_bucket,
    )
    from src.prepare.models import Candidate, NoiseAggregate
except ImportError:
    from prepare.decoders import (
        append_html_entity_variants as _append_html_entity_variants,
        build_decoded_variants as _build_decoded_variants,
        build_html_entity_decoded_variant as _build_html_entity_decoded_variant,
        build_html_entity_variants as _build_html_entity_variants,
    )
    from prepare.l3_hints import (
        classify_ssrf_target as _classify_ssrf_target,
        classify_webshell_path as _classify_webshell_path,
        detect_educational_ssti_search_context as _detect_educational_ssti_search_context,
        detect_log4shell_hints as _detect_log4shell_hints,
        detect_ssrf_hints as _detect_ssrf_hints,
        detect_ssti_hints as _detect_ssti_hints,
        detect_webshell_hints as _detect_webshell_hints,
        extract_query_pairs_from_variants as _extract_query_pairs_from_variants,
    )
    from prepare.sqli_hints import (
        EDUCATIONAL_SQL_SEARCH_TERMS,
        REPEATED_QUOTE_PATTERN,
        SQLI_BOOLEAN_CONDITION_PATTERN,
        SQLI_BOOLEAN_TRUE_CONDITION_PATTERN,
        SQLI_COMMENT_PATTERN,
        SQLI_FROM_USERS_PATTERN,
        SQLI_PAREN_TERMINATION_PATTERN,
        SQLI_PATTERNS,
        SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN,
        SQLI_SCHEMA_ACCESS_PATTERN,
        SQLI_UNION_COLUMN_ENUM_PATTERN,
        SQLI_XCLOSE_PATTERN,
        SUPPORTING_SQL_KEYWORDS,
        detect_educational_sql_search_context as _detect_educational_sql_search_context,
    )
    from prepare.xss_hints import (
        BROWSER_DATA_ACCESS_RE,
        EDUCATIONAL_XSS_KEYWORDS,
        EDUCATIONAL_XSS_SEARCH_TERMS,
        EVENT_HANDLER_ASSIGNMENT_RE,
        EXTERNAL_NAVIGATION_RE,
        EXTERNAL_URL_RE,
        JAVASCRIPT_PROTOCOL_RE,
        SCRIPT_TAG_CAPTURE_RE,
        SCRIPT_TAG_PATTERN,
        XSS_PATTERNS,
        XSS_QUOTE_BREAKOUT_PATTERN,
        XSS_TAG_INJECTION_PATTERN,
    )
    from prepare.traversal_cmdi_hints import (
        CMDI_PATTERNS,
        TRAVERSAL_PATTERNS,
    )
    from prepare.file_disclosure_hints import (
        FILE_DISCLOSURE_PATTERNS,
        PHP_FILTER_CANONICAL_PATTERN,
        detect_file_disclosure_hints as _detect_file_disclosure_hints,
    )
    from prepare.method_summaries import (
        METHOD_BASELINE_FAMILIES,
        METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        METHOD_BEHAVIOR_WINDOW_SEC,
        METHOD_DESTRUCTIVE_FAMILIES,
        METHOD_RISKY_FAMILIES,
        build_method_behavior_reason_hints_for_row as _build_method_behavior_reason_hints_for_row,
        build_method_behavior_summaries as _build_method_behavior_summaries,
        build_method_behavior_summary_contexts as _build_method_behavior_summary_contexts,
    )
    from prepare.auth_behavior import (
        build_auth_behavior_summaries as _build_auth_behavior_summaries,
        build_auth_behavior_summary_contexts as _build_auth_behavior_summary_contexts,
        finalize_auth_behavior_bucket as _finalize_auth_behavior_bucket,
    )
    from prepare.protocol_anomalies import (
        PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
        PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT,
        PROTOCOL_ANOMALY_WINDOW_SEC,
        build_protocol_anomaly_reason_hints_for_row as _build_protocol_anomaly_reason_hints_for_row,
        build_protocol_anomaly_summaries as _build_protocol_anomaly_summaries,
        build_protocol_anomaly_summary_contexts as _build_protocol_anomaly_summary_contexts,
        finalize_protocol_anomaly_bucket as _finalize_protocol_anomaly_bucket,
    )
    from prepare.static_baseline import (
        STATIC_BASELINE_MIN_STATIC_PATHS,
        STATIC_BASELINE_SAMPLE_REQUEST_LIMIT,
        STATIC_BASELINE_WINDOW_SEC,
        build_static_baseline_reason_hints_for_row as _build_static_baseline_reason_hints_for_row,
        build_static_baseline_summaries as _build_static_baseline_summaries,
        build_static_baseline_summary_contexts as _build_static_baseline_summary_contexts,
        finalize_static_baseline_bucket as _finalize_static_baseline_bucket,
    )
    from prepare.crawler_baseline import (
        build_crawler_baseline_reason_hints_for_row as _build_crawler_baseline_reason_hints_for_row,
        build_crawler_baseline_summaries as _build_crawler_baseline_summaries,
        build_crawler_baseline_summary_contexts as _build_crawler_baseline_summary_contexts,
        classify_crawler_baseline_path_category as _classify_crawler_baseline_path_category,
        classify_crawler_like_user_agent_family as _classify_crawler_like_user_agent_family,
        finalize_crawler_baseline_bucket as _finalize_crawler_baseline_bucket,
    )
    from prepare.sensitive_path_probe import (
        build_sensitive_path_probe_summaries as _build_sensitive_path_probe_summaries,
        build_sensitive_path_probe_summary_contexts as _build_sensitive_path_probe_summary_contexts,
        classify_sensitive_path_probe_category as _classify_sensitive_path_probe_category,
        finalize_sensitive_path_probe_bucket as _finalize_sensitive_path_probe_bucket,
    )
    from prepare.ip_behavior import (
        IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        IP_BEHAVIOR_SENSITIVE_PATH_LIMIT,
        IP_BEHAVIOR_WINDOW_SEC,
        build_ip_behavior_aggregates as _build_ip_behavior_aggregates,
        finalize_ip_behavior_bucket as _finalize_ip_behavior_bucket,
        is_sensitive_ip_behavior_path as _is_sensitive_ip_behavior_path,
    )
    from prepare.probing_sequence import (
        build_probing_sequence_summaries as _build_probing_sequence_summaries,
        finalize_probing_sequence_bucket as _finalize_probing_sequence_bucket,
    )
    from prepare.mixed_baseline_scanner import (
        build_mixed_baseline_scanner_row_context as _build_mixed_baseline_scanner_row_context,
        build_mixed_baseline_scanner_summaries as _build_mixed_baseline_scanner_summaries,
        finalize_mixed_baseline_scanner_bucket as _finalize_mixed_baseline_scanner_bucket,
    )
    from prepare.models import Candidate, NoiseAggregate

# ----------------------------
# 패턴 정의
# ----------------------------
AUTOMATION_UA_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("sqlmap", re.compile(r"(?i)sqlmap"), 4),
    ("nikto", re.compile(r"(?i)nikto"), 4),
    ("nmap", re.compile(r"(?i)nmap"), 3),
    ("python_requests", re.compile(r"(?i)python-requests"), 2),
    ("curl", re.compile(r"(?i)^curl/"), 1),
    ("wget", re.compile(r"(?i)^wget/"), 1),
]

AUTH_SUCCESS_ATTACK_HINT_PATTERN = re.compile(
    r"(?i)\b("
    r"bypass|exploit|attack|abuse|intrud|tamper|payload|fuzz|poc|scanner|sqlmap|nikto|nmap"
    r")\b"
)

LOGIN_URI_HINTS = (
    "/login",
    "/user/login",
    "/rest/user/login",
    "/authenticate",
    "/auth",
    "/signin",
    "/session",
)

AUTH_ENDPOINT_FAMILY_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("auth_login", re.compile(r"(?i)(?:^|[^a-z0-9])login(?:[^a-z0-9]|$)")),
    ("auth_signin", re.compile(r"(?i)(?:^|[^a-z0-9])signin(?:[^a-z0-9]|$)")),
    ("auth_session", re.compile(r"(?i)(?:^|[^a-z0-9])session(?:[^a-z0-9]|$)")),
    ("auth_token", re.compile(r"(?i)(?:^|[^a-z0-9])token(?:[^a-z0-9]|$)")),
    (
        "auth_endpoint",
        re.compile(r"(?i)(?:^|[^a-z0-9])(?:auth|authenticate|authentication)(?:[^a-z0-9]|$)"),
    ),
]

QUERY_HEAVY_URI_HINTS = (
    "/search",
    "/products/search",
    "/rest/products/search",
    "/filter",
    "/query",
)

DIR_PROBE_PATH_HINTS = (
    "/.git",
    "/.svn",
    "/.hg",
    "/.env",
    "/backup",
    "/backups",
    "/wp-admin",
    "/phpmyadmin",
    "/pma",
    "/manager",
    "/manager/html",
    "/server-status",
    "/cgi-bin",
    "/actuator",
    "/swagger",
    "/api-docs",
    "/console",
    "/debug",
    "/setup",
    "/vendor",
    "/uploads",
    "/upload",
    "/config",
    "/configs",
    "/autodiscover",
    "/owa",
)

DIR_PROBE_FILE_HINTS = (
    "web.config",
    "config.php",
    "phpinfo.php",
    ".git/config",
    ".env",
    ".ds_store",
    "id_rsa",
    "passwd",
    "shadow",
    "win.ini",
    "docker-compose.yml",
    "composer.json",
)

PROBING_SEQUENCE_PATH_PREFIX_HINTS = (
    "/.git",
    "/.svn",
    "/.hg",
    "/.env",
    "/config",
    "/config.php",
    "/backup",
    "/backups",
    "/db",
    "/database",
    "/admin",
    "/administrator",
    "/manager",
    "/manager/html",
    "/server-status",
    "/server-info",
    "/phpmyadmin",
    "/wp-admin",
    "/wp-login.php",
    "/login",
    "/console",
)

PROBING_SEQUENCE_PATH_SEGMENT_HINTS = (
    ".git",
    ".svn",
    ".hg",
    ".env",
    "admin",
    "administrator",
    "manager",
    "backup",
    "backups",
    "config",
    "database",
    "phpmyadmin",
    "console",
)

PROBING_SEQUENCE_SUFFIX_HINTS = (
    ".bak",
    ".old",
    ".backup",
    ".zip",
    ".tar",
    ".gz",
    ".sql",
    ".conf",
    ".ini",
    ".env",
)

STATIC_EXTENSIONS = (
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".map", ".webp",
)

STATIC_PREFIXES = (
    "/assets/", "/frontend/", "/dist/", "/public/", "/img/", "/images/", "/fonts/", "/static/",
)

BROWSER_UA_HINTS = (
    "mozilla/", "chrome/", "safari/", "firefox/", "edg/", "applewebkit/",
)

SOURCE_PRIORITY = {"security": 3, "access": 2, "error": 1}
SOURCE_ORDER = ["security", "access", "error"]
DECODE_VARIANT_MAX_CHARS = 4096
SUPPORTING_EVENT_TIME_WINDOW_SEC = 120
TEMPORAL_CONTEXT_BUCKET_SEC = 120
PROBING_SEQUENCE_WINDOW_SEC = 120
PROBING_SEQUENCE_MIN_REQUESTS = 3
PROBING_SEQUENCE_MIN_DISTINCT_PATHS = 3
PROBING_SEQUENCE_SAMPLE_PATH_LIMIT = 10
CRAWLER_BASELINE_WINDOW_SEC = 300
CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT = 10
SENSITIVE_PATH_PROBE_WINDOW_SEC = 300
SENSITIVE_PATH_PROBE_SAMPLE_REQUEST_LIMIT = 10
SENSITIVE_PATH_PROBE_REPRESENTATIVE_CANDIDATE_LIMIT = 1
MIXED_BASELINE_SCANNER_WINDOW_SEC = 300
MIXED_BASELINE_SCANNER_MIN_REQUEST_COUNT = 4
MIXED_BASELINE_SCANNER_SAMPLE_REQUEST_LIMIT = 10
AUTH_BEHAVIOR_WINDOW_SEC = 300
AUTH_BEHAVIOR_RAPID_WINDOW_SEC = 60
AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT = 3
STANDARD_HTTP_METHODS = {
    "GET",
    "HEAD",
    "POST",
    "PUT",
    "DELETE",
    "CONNECT",
    "OPTIONS",
    "TRACE",
    "PATCH",
}
STATIC_BASELINE_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp")
HEALTH_LIKE_PATHS = {
    "/health",
    "/api/health",
    "/status",
    "/ping",
}
CRAWLER_BROWSE_PRODUCT_SEGMENTS = {"product", "products"}
CRAWLER_BROWSE_CATEGORY_SEGMENTS = {"category", "categories"}
CRAWLER_BROWSE_GENERIC_SEGMENTS = {"list", "browse"}
SEARCH_PARAM_NAMES = {"q", "query", "search", "keyword", "term", "s"}
NORMAL_SEARCH_VALUE_RE = re.compile(r"(?i)^[a-z0-9][a-z0-9 _-]{0,63}$")
STRONG_ATTACK_HINT_PREFIXES = (
    "sqli:",
    "xss:",
    "traversal:",
    "file_disclosure:",
    "cmdi:",
    "hpp:",
    "l3:",
    "log4shell:",
    "ssrf:",
    "ssti:",
    "webshell:",
)
STRONG_ATTACK_HINTS = {
    "encoding:double_decoded_sqli",
    "encoding:html_entity_decoded_xss",
}
ATTACK_ENCODED_PAYLOAD_RE = re.compile(
    r"(?i)(%27|%2527|%22|%2522|%3c|%253c|%3e|%253e|%28|%2528|%29|%2529|%2e%2e|%252e%252e|%00|%2500|%3a%2f%2f|%253a%252f%252f|%3b|%253b)"
)
HTML_ENTITY_RE = re.compile(r"&#x?[0-9a-fA-F]+;", re.IGNORECASE)
NORMAL_SEARCH_ATTACK_TEXT_RE = re.compile(
    r"(?i)(<\s*script\b|javascript\s*:|alert\s*\(|document\.cookie|localstorage|sessionstorage|php\s*://\s*filter|(?:\.\./|\.\.\\\\)|%3c|%253c|%3e|%253e|%27|%2527|%22|%2522|%28|%2528|%29|%2529|%2e%2e|%252e%252e|%00|%2500|%3a%2f%2f|%253a%252f%252f|%3b|%253b)"
)
# ----------------------------
# 공용 유틸
# ----------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export JSON을 LLM 분석용으로 정제합니다.")
    parser.add_argument("--input", required=True, help="export_db_logs_cli.py 결과 JSON")
    parser.add_argument("--out-dir", default=".", help="산출물 저장 디렉터리")
    parser.add_argument("--base-name", default=None, help="산출물 파일명 접두어")
    parser.add_argument("--min-score", type=int, default=4, help="후보 포함 최소 점수")
    parser.add_argument("--min-repeat-aggregate", type=int, default=3, help="반복 정상 요청 집계 최소 건수")
    parser.add_argument("--include-source-tables", default="security", help="분석에 포함할 소스 테이블 쉼표 목록 (기본값: security, 예: security,error)")
    parser.add_argument("--write-filtered-out", action="store_true", help="제외된 row 상세 JSON 저장")
    parser.add_argument("--pretty", action="store_true", help="JSON pretty 출력")
    return parser.parse_args()


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, payload: Any, pretty: bool) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)


def normalize_text(value: Optional[Any]) -> str:
    if value is None:
        return ""
    return unquote_plus(str(value)).strip()


def raw_text(value: Optional[Any]) -> str:
    if value is None:
        return ""
    return str(value).strip()


def append_unique_hint(hints: List[str], hint: str) -> None:
    text = raw_text(hint)
    if text and text not in hints:
        hints.append(text)


def extend_unique_hints(hints: List[str], extra_hints: Iterable[str]) -> None:
    for hint in extra_hints:
        append_unique_hint(hints, hint)


def build_decoded_variants(value: str, max_depth: int = 2) -> List[Dict[str, Any]]:
    return _build_decoded_variants(value, max_depth=max_depth)


def build_html_entity_decoded_variant(value: str) -> str:
    return _build_html_entity_decoded_variant(value)


def build_html_entity_variants(value: str, source: str) -> List[Dict[str, Any]]:
    return _build_html_entity_variants(value, source=source)


def append_html_entity_variants(variants: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    return _append_html_entity_variants(variants, source=source)


def extract_query_pairs_from_variants(
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    return _extract_query_pairs_from_variants(query_variants, raw_request_target_variants)


def detect_log4shell_hints(
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    return _detect_log4shell_hints(combined_target, query_variants, raw_request_target_variants)


def classify_ssrf_target(value: str) -> List[str]:
    return _classify_ssrf_target(value)


def detect_ssrf_hints(
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    return _detect_ssrf_hints(query_variants, raw_request_target_variants)


def detect_educational_ssti_search_context(text: str) -> bool:
    return _detect_educational_ssti_search_context(text)


def detect_ssti_hints(
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    return _detect_ssti_hints(combined_target, query_variants, raw_request_target_variants)


def classify_webshell_path(path: str) -> List[str]:
    return _classify_webshell_path(path)


def detect_webshell_hints(
    uri: str,
    raw_request_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    request_path = get_effective_request_path(uri, raw_request_target)
    return _detect_webshell_hints(request_path, query_variants, raw_request_target_variants)


def unique_non_empty_texts(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        text = raw_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def build_analysis_texts(
    raw_request: str,
    uri: str,
    query_string: str,
    raw_request_target: str,
    raw_log: str,
) -> Tuple[str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    query_variants = build_decoded_variants(query_string, max_depth=2)
    raw_request_target_variants = build_decoded_variants(raw_request_target, max_depth=2)
    append_html_entity_variants(query_variants, source="query_string")
    append_html_entity_variants(raw_request_target_variants, source="raw_request_target")

    base_text = " ".join(
        unique_non_empty_texts([
            raw_text(raw_request),
            normalize_text(raw_request),
            normalize_text(uri),
            raw_text(query_string),
            normalize_text(query_string),
            raw_request_target,
            normalize_text(raw_log),
        ])
    ).strip()
    variant_text = " ".join(
        unique_non_empty_texts(
            [
                item.get("text", "")
                for item in query_variants
                if raw_text(item.get("variant_type")) == "html_entity" or safe_int(item.get("depth"), 0) >= 1
            ]
            + [
                item.get("text", "")
                for item in raw_request_target_variants
                if raw_text(item.get("variant_type")) == "html_entity" or safe_int(item.get("depth"), 0) >= 1
            ]
        )
    ).strip()
    combined_text = " ".join(unique_non_empty_texts([base_text, variant_text])).strip()
    return base_text, combined_text, query_variants, raw_request_target_variants


def strip_html_entities_for_sql_comment_scan(text: str) -> str:
    return HTML_ENTITY_RE.sub("", raw_text(text))


def matches_sqli_pattern(name: str, pattern: re.Pattern[str], text: str) -> bool:
    sample = strip_html_entities_for_sql_comment_scan(text) if name == "sql_comment" else text
    return bool(sample and pattern.search(sample))


def get_matching_pattern_names(patterns: List[Tuple[str, re.Pattern[str], int]], text: str) -> List[str]:
    if not text:
        return []
    names: List[str] = []
    for name, pattern, _ in patterns:
        if name == "sql_comment":
            if matches_sqli_pattern(name, pattern, text):
                names.append(name)
            continue
        if pattern.search(text):
            names.append(name)
    return names


def has_any_attack_pattern(text: str) -> bool:
    if not text:
        return False
    if get_matching_pattern_names(SQLI_PATTERNS, text):
        return True
    pattern_groups = (XSS_PATTERNS, TRAVERSAL_PATTERNS, CMDI_PATTERNS)
    return any(pattern.search(text) for group in pattern_groups for _, pattern, _ in group)


def detect_decoded_attack_hints(
    base_text: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    hints: List[str] = []
    score_boost = 0

    variant_depth0_attack = False
    depth1_has_attack = False
    depth2_has_attack = False
    depth1_has_sqli = False
    depth2_has_sqli = False
    html_entity_payload = False
    html_entity_decoded = False
    html_entity_decoded_xss = False

    for variant in query_variants + raw_request_target_variants:
        depth = safe_int(variant.get("depth"), 0)
        text = raw_text(variant.get("text"))
        variant_type = raw_text(variant.get("variant_type")) or "url_decode"
        if not text:
            continue
        if variant_type == "html_entity":
            html_entity_payload = True
            html_entity_decoded = True
            if get_matching_pattern_names(XSS_PATTERNS, text):
                html_entity_decoded_xss = True
            continue
        variant_has_attack = has_any_attack_pattern(text)
        variant_has_sqli = bool(get_matching_pattern_names(SQLI_PATTERNS, text))
        if depth == 0 and variant_has_attack:
            variant_depth0_attack = True
        if depth >= 1 and variant_has_attack:
            depth1_has_attack = True
        if depth >= 2 and variant_has_attack:
            depth2_has_attack = True
        if depth >= 1 and variant_has_sqli:
            depth1_has_sqli = True
        if depth >= 2 and variant_has_sqli:
            depth2_has_sqli = True

    if depth1_has_attack and not variant_depth0_attack:
        hints.append("encoding:url_encoded_payload")
    if depth2_has_attack:
        hints.append("encoding:double_decoded_payload")
        hints.append("encoding:decoded_depth_2")
    if depth2_has_sqli:
        hints.append("encoding:double_decoded_sqli")
    if depth2_has_sqli and not depth1_has_sqli:
        score_boost += 2
    if html_entity_payload:
        hints.append("encoding:html_entity_payload")
    if html_entity_decoded:
        hints.append("encoding:html_entity_decoded")
    if html_entity_decoded_xss:
        hints.append("encoding:html_entity_decoded_xss")

    return score_boost, hints


def detect_file_disclosure_hints(
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    return _detect_file_disclosure_hints(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )


def detect_educational_sql_search_context(text: str) -> bool:
    return _detect_educational_sql_search_context(text)


def detect_educational_xss_search_context(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    natural_language_term = any(
        re.search(r"(?i)(?<![\w./-])" + re.escape(term).replace(r"\ ", r"\s+") + r"(?![\w./-])", lowered)
        if re.search(r"[a-z]", term)
        else term in lowered
        for term in EDUCATIONAL_XSS_SEARCH_TERMS
    )
    return natural_language_term and any(keyword in lowered for keyword in EDUCATIONAL_XSS_KEYWORDS)


def get_sqli_structure_flags(
    text: str,
    query_variants: Optional[List[Dict[str, Any]]] = None,
    raw_request_target_variants: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, bool]:
    raw = raw_text(text)
    normalized = normalize_text(text)
    samples = unique_non_empty_texts(
        [raw, normalized]
        + [raw_text(item.get("text")) for item in (query_variants or [])]
        + [raw_text(item.get("text")) for item in (raw_request_target_variants or [])]
    )
    comment_samples = [strip_html_entities_for_sql_comment_scan(sample) for sample in samples]
    quote_termination = any(SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN.search(sample) for sample in samples)
    boolean_condition = any(SQLI_BOOLEAN_CONDITION_PATTERN.search(sample) for sample in samples)
    boolean_true_condition = any(SQLI_BOOLEAN_TRUE_CONDITION_PATTERN.search(sample) for sample in samples)
    sql_comment = any(SQLI_COMMENT_PATTERN.search(sample) for sample in comment_samples)
    xclose = any(SQLI_XCLOSE_PATTERN.search(sample) for sample in samples)
    parenthesis_termination = any(SQLI_PAREN_TERMINATION_PATTERN.search(sample) for sample in samples)
    return {
        "quote_termination": quote_termination,
        "parenthesis_termination": parenthesis_termination,
        "sql_comment": sql_comment,
        "comment_sequence": sql_comment and (quote_termination or boolean_condition or parenthesis_termination or xclose),
        "xclose": xclose,
        "xclose_pattern": xclose and (boolean_condition or sql_comment),
        "boolean_condition": boolean_condition,
        "boolean_true_condition": boolean_true_condition,
        "union_column_list": any(SQLI_UNION_COLUMN_ENUM_PATTERN.search(sample) for sample in samples),
        "schema_access": any(SQLI_SCHEMA_ACCESS_PATTERN.search(sample) for sample in samples),
        "from_users": any(SQLI_FROM_USERS_PATTERN.search(sample) for sample in samples),
    }


def has_encoded_payload_marker(text: str) -> bool:
    return bool(ATTACK_ENCODED_PAYLOAD_RE.search(raw_text(text)))


def has_mixed_case_script_tag(text: str) -> bool:
    for match in SCRIPT_TAG_CAPTURE_RE.finditer(raw_text(text)):
        tag = raw_text(match.group(1))
        if tag.lower() == "script" and not (tag.islower() or tag.isupper()):
            return True
    return False


def get_xss_context_hints(
    *,
    raw_query_string: str,
    query_string: str,
    raw_request_target: str,
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> List[str]:
    hints: List[str] = []
    raw_samples = unique_non_empty_texts([raw_query_string, raw_request_target])
    analysis_samples = unique_non_empty_texts(
        [query_string, combined_target]
        + [raw_text(item.get("text")) for item in query_variants + raw_request_target_variants]
    )

    browser_data_access = False
    external_navigation = False
    external_url_seen = False
    html_entity_decoded_script = False
    html_entity_present = any(HTML_ENTITY_RE.search(sample) for sample in raw_samples)

    for sample in analysis_samples:
        if SCRIPT_TAG_PATTERN.search(sample):
            append_unique_hint(hints, "xss:script_tag")
        if has_mixed_case_script_tag(sample):
            append_unique_hint(hints, "xss:mixed_case_script_tag")

        event_names = sorted({raw_text(name).lower() for name in EVENT_HANDLER_ASSIGNMENT_RE.findall(sample) if raw_text(name)})
        if event_names:
            append_unique_hint(hints, "xss:event_handler")
            for event_name in event_names:
                append_unique_hint(hints, f"xss:event_handler:{event_name}")

        if JAVASCRIPT_PROTOCOL_RE.search(sample):
            append_unique_hint(hints, "xss:javascript_protocol")

        browser_access_matches = [raw_text(name).lower() for name in BROWSER_DATA_ACCESS_RE.findall(sample) if raw_text(name)]
        if browser_access_matches:
            browser_data_access = True
            append_unique_hint(hints, "xss:browser_data_access")
            if any(name == "document.cookie" for name in browser_access_matches):
                append_unique_hint(hints, "xss:document_cookie")

        if EXTERNAL_NAVIGATION_RE.search(sample):
            external_navigation = True
            append_unique_hint(hints, "xss:external_navigation")
        if EXTERNAL_URL_RE.search(sample):
            external_url_seen = True

    for variant in query_variants + raw_request_target_variants:
        if raw_text(variant.get("variant_type")) != "html_entity":
            continue
        if SCRIPT_TAG_PATTERN.search(raw_text(variant.get("text"))):
            html_entity_decoded_script = True
            break

    if html_entity_decoded_script:
        if html_entity_present:
            append_unique_hint(hints, "xss:html_entity_encoded")
        append_unique_hint(hints, "xss:html_entity_decoded_script")
    if browser_data_access and (external_navigation or external_url_seen):
        append_unique_hint(hints, "xss:external_exfil_intent")

    return hints


def has_xss_attack_structure(texts: Iterable[str]) -> bool:
    for sample in unique_non_empty_texts(texts):
        if (
            XSS_QUOTE_BREAKOUT_PATTERN.search(sample)
            or XSS_TAG_INJECTION_PATTERN.search(sample)
            or EVENT_HANDLER_ASSIGNMENT_RE.search(sample)
            or JAVASCRIPT_PROTOCOL_RE.search(sample)
            or re.search(r"(?i)\balert\s*\(", sample)
            or BROWSER_DATA_ACCESS_RE.search(sample)
        ):
            return True
        if HTML_ENTITY_RE.search(sample):
            decoded = build_html_entity_decoded_variant(sample)
            if decoded != sample and (
                SCRIPT_TAG_PATTERN.search(decoded)
                or EVENT_HANDLER_ASSIGNMENT_RE.search(decoded)
                or JAVASCRIPT_PROTOCOL_RE.search(decoded)
            ):
                return True
    return False


def get_xss_structure_flags(
    *,
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Dict[str, bool]:
    samples = unique_non_empty_texts(
        [combined_target] + [raw_text(item.get("text")) for item in query_variants + raw_request_target_variants]
    )
    html_entity_decoded_samples = [
        raw_text(item.get("text"))
        for item in query_variants + raw_request_target_variants
        if raw_text(item.get("variant_type")) == "html_entity"
    ]
    return {
        "script_tag": any(SCRIPT_TAG_PATTERN.search(sample) for sample in samples),
        "mixed_case_script_tag": any(has_mixed_case_script_tag(sample) for sample in samples),
        "event_handler_assignment": any(EVENT_HANDLER_ASSIGNMENT_RE.search(sample) for sample in samples),
        "javascript_protocol": any(JAVASCRIPT_PROTOCOL_RE.search(sample) for sample in samples),
        "browser_data_access": any(BROWSER_DATA_ACCESS_RE.search(sample) for sample in samples),
        "external_navigation": any(EXTERNAL_NAVIGATION_RE.search(sample) for sample in samples),
        "quote_breakout": any(XSS_QUOTE_BREAKOUT_PATTERN.search(sample) for sample in samples),
        "html_entity_decoded_script": any(SCRIPT_TAG_PATTERN.search(sample) for sample in html_entity_decoded_samples),
    }


def build_false_positive_review_candidate(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_req_original = raw_text(row.get("raw_request"))
    raw_request_target = extract_raw_request_target(raw_req_original)
    raw_qs = raw_text(row.get("query_string"))
    qs = normalize_text(row.get("query_string"))
    _, combined_target, query_variants, raw_request_target_variants = build_analysis_texts(
        raw_request=raw_req_original,
        uri=get_uri(row),
        query_string=raw_qs,
        raw_request_target=raw_request_target,
        raw_log="",
    )
    text_for_context = " ".join(unique_non_empty_texts([qs, raw_request_target, combined_target]))
    attack_samples = unique_non_empty_texts(
        [raw_qs, qs, raw_request_target, combined_target]
        + [raw_text(item.get("text")) for item in query_variants + raw_request_target_variants]
    )
    if not detect_educational_xss_search_context(text_for_context):
        return None
    if has_xss_attack_structure(attack_samples):
        return None
    return {
        "review_reason": "educational_xss_keyword_search",
        "source_table": normalize_text(row.get("_source_table")),
        "log_id": safe_int(row.get("id"), 0) or None,
        "log_time": choose_best_time(row),
        "src_ip": get_src_ip(row),
        "request_id": normalize_text(row.get("request_id")),
        "method": get_method(row),
        "uri": get_uri(row),
        "query_string": qs,
        "user_agent": get_user_agent(row),
        "status_code": get_status_code(row),
        "response_body_bytes": get_response_body_bytes(row),
    }


def endpoint_family_key(uri: str) -> str:
    path = path_from_target(uri).lower() if "?" in raw_text(uri) else normalize_text(uri).lower()
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return "/"

    normalized_segments: List[str] = []
    for segment in segments[:3]:
        if re.fullmatch(r"[0-9a-f]{6,}", segment) or re.fullmatch(r"\d+", segment):
            normalized_segments.append("{id}")
        else:
            normalized_segments.append(segment)
    return "/" + "/".join(normalized_segments)


def build_temporal_context_key(src_ip: str, uri: str, log_time: Optional[str]) -> str:
    dt = parse_flexible_iso_dt(log_time or "")
    if dt is not None:
        bucket_start = datetime.fromtimestamp(
            int(dt.timestamp() // TEMPORAL_CONTEXT_BUCKET_SEC) * TEMPORAL_CONTEXT_BUCKET_SEC,
            tz=dt.tzinfo,
        )
        bucket = bucket_start.isoformat(timespec="seconds")
    else:
        bucket = format_time_bucket(log_time)
    return f"{normalize_text(src_ip)}|{endpoint_family_key(uri)}|{bucket}"


def has_supporting_sql_keyword(text: str) -> bool:
    lowered = normalize_text(text).lower()
    return any(keyword in lowered for keyword in SUPPORTING_SQL_KEYWORDS)


def has_high_special_ratio_or_repeated_quotes(text: str) -> bool:
    raw = raw_text(text)
    return bool(REPEATED_QUOTE_PATTERN.search(raw)) or special_char_ratio(normalize_text(text)) >= 0.15


def response_size_differs_significantly(a: int, b: int) -> bool:
    if a <= 0 or b <= 0:
        return abs(a - b) >= 256
    delta = abs(a - b)
    return delta >= max(256, int(max(a, b) * 0.3))


def is_high_signal_attack_candidate(candidate: Candidate, min_score: int) -> bool:
    if candidate.verdict_hint in {
        "possible_false_positive_sql_keyword_search",
        "possible_false_positive_xss_keyword_search",
    }:
        return False
    return candidate.score >= max(min_score, 7)


def build_supporting_events(filtered_rows: List[Dict[str, Any]], candidates: List[Candidate], min_score: int) -> List[Dict[str, Any]]:
    high_signal_candidates = [candidate for candidate in candidates if is_high_signal_attack_candidate(candidate, min_score=min_score)]
    if not high_signal_candidates:
        return []

    candidate_contexts: List[Dict[str, Any]] = []
    for candidate in high_signal_candidates:
        candidate_contexts.append(
            {
                "candidate": candidate,
                "dt": parse_flexible_iso_dt(candidate.log_time or ""),
                "uri": normalize_text(candidate.uri),
                "family": endpoint_family_key(candidate.uri),
            }
        )

    supporting_events: List[Dict[str, Any]] = []
    seen_keys = set()
    for row in filtered_rows:
        src_ip = get_src_ip(row)
        qs = normalize_text(row.get("query_string"))
        if not qs:
            continue

        uri = get_uri(row)
        row_dt = parse_flexible_iso_dt(choose_best_time(row) or "")
        row_family = endpoint_family_key(uri)
        nearby: List[Candidate] = []
        for context in candidate_contexts:
            candidate = context["candidate"]
            if normalize_text(candidate.src_ip) != src_ip:
                continue
            same_endpoint = normalize_text(candidate.uri) == normalize_text(uri) or context["family"] == row_family
            if not same_endpoint:
                continue

            candidate_dt = context["dt"]
            if row_dt is not None and candidate_dt is not None:
                if abs((candidate_dt - row_dt).total_seconds()) > SUPPORTING_EVENT_TIME_WINDOW_SEC:
                    continue
            nearby.append(candidate)

        if not nearby:
            continue

        raw_req_original = raw_text(row.get("raw_request"))
        raw_request_target = extract_raw_request_target(raw_req_original)
        raw_qs = raw_text(row.get("query_string"))
        status_code = get_status_code(row)
        response_body_bytes = get_response_body_bytes(row)
        analysis_texts = unique_non_empty_texts([raw_qs, qs, raw_request_target])
        reference_baseline = is_likely_normal_search_baseline(
            row,
            analysis_texts=analysis_texts,
            reason_hints=(),
        )
        additional_hints: List[str] = []

        if reference_baseline:
            additional_hints.append("supporting:normal_search_baseline")
            additional_hints.append("supporting:same_endpoint_reference_baseline")
        else:
            if has_supporting_sql_keyword(qs):
                additional_hints.append("supporting:sql_keyword_fragment")
            if has_high_special_ratio_or_repeated_quotes(raw_qs):
                additional_hints.append("supporting:special_chars_or_quote_repetition")
            if has_encoded_payload_marker(raw_qs) or has_encoded_payload_marker(raw_request_target):
                additional_hints.append("supporting:encoded_payload_trace")
            if any(candidate.status_code != status_code for candidate in nearby):
                additional_hints.append("supporting:status_delta_from_nearby_candidate")
            if any(response_size_differs_significantly(response_body_bytes, candidate.response_body_bytes) for candidate in nearby):
                additional_hints.append("supporting:response_size_delta_from_nearby_candidate")
            if any(normalize_text(candidate.uri) == normalize_text(uri) for candidate in nearby):
                additional_hints.append("supporting:same_uri_nearby_high_signal_candidate")

        if not additional_hints:
            continue

        request_id = normalize_text(row.get("request_id"))
        source_table = normalize_text(row.get("_source_table"))
        log_time = choose_best_time(row)
        dedup_key = request_id or f"{source_table}:{safe_int(row.get('id'), 0)}:{log_time}:{raw_request_target}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        supporting_events.append(
            {
                "supporting_reason": "nearby_normal_search_baseline" if reference_baseline else "nearby_high_signal_attack_context",
                "supporting_role": "reference_baseline" if reference_baseline else "temporal_context",
                "source_table": source_table,
                "log_time": log_time,
                "src_ip": src_ip,
                "method": get_method(row),
                "uri": uri,
                "query_string": qs,
                "status_code": status_code,
                "response_body_bytes": response_body_bytes,
                "duration_us": safe_int(row.get("duration_us")),
                "ttfb_us": safe_int(row.get("ttfb_us")),
                "resp_content_type": get_resp_content_type(row),
                "user_agent": get_user_agent(row),
                "raw_request": normalize_text(row.get("raw_request")),
                "raw_request_target": raw_request_target,
                "request_id": request_id,
                "reason_hints": additional_hints,
                "temporal_context_key": build_temporal_context_key(src_ip, uri, log_time),
                "temporal_context_role": "reference_baseline" if reference_baseline else "temporal_context",
                "nearby_candidate_count": len(nearby),
            }
        )

    supporting_events.sort(
        key=lambda item: (
            safe_int(item.get("nearby_candidate_count"), 0),
            normalize_text(item.get("log_time")),
        ),
        reverse=True,
    )
    return supporting_events


def finalize_probing_sequence_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
) -> Optional[Dict[str, Any]]:
    return _finalize_probing_sequence_bucket(
        items,
        window_sec=window_sec,
        min_requests=PROBING_SEQUENCE_MIN_REQUESTS,
        min_distinct_paths=PROBING_SEQUENCE_MIN_DISTINCT_PATHS,
        sample_path_limit=PROBING_SEQUENCE_SAMPLE_PATH_LIMIT,
        normalize_text=normalize_text,
        safe_int=safe_int,
        normalize_content_type_bucket=normalize_content_type_bucket,
        extend_unique_hints=extend_unique_hints,
        get_probe_sequence_reason_hints=get_probe_sequence_reason_hints,
        append_unique_hint=append_unique_hint,
    )


def build_probing_sequence_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = PROBING_SEQUENCE_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_probing_sequence_summaries(
        rows,
        window_sec=window_sec,
        finalize_bucket=finalize_probing_sequence_bucket,
        get_method=get_method,
        get_probe_sequence_path=get_probe_sequence_path,
        get_uri=get_uri,
        extract_raw_request_target=extract_raw_request_target,
        raw_text=raw_text,
        is_likely_probe_sequence_path=is_likely_probe_sequence_path,
        normalize_text=normalize_text,
        parse_flexible_iso_dt=parse_flexible_iso_dt,
        choose_best_time=choose_best_time,
        get_src_ip=get_src_ip,
        get_status_code=get_status_code,
        get_resp_content_type=get_resp_content_type,
        get_response_body_bytes=get_response_body_bytes,
        safe_int=safe_int,
    )


def finalize_static_baseline_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
) -> Optional[Dict[str, Any]]:
    return _finalize_static_baseline_bucket(
        items,
        window_sec=window_sec,
        min_static_paths=STATIC_BASELINE_MIN_STATIC_PATHS,
        sample_request_limit=STATIC_BASELINE_SAMPLE_REQUEST_LIMIT,
    )


def build_static_baseline_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = STATIC_BASELINE_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_static_baseline_summaries(
        rows,
        window_sec=window_sec,
        min_static_paths=STATIC_BASELINE_MIN_STATIC_PATHS,
        sample_request_limit=STATIC_BASELINE_SAMPLE_REQUEST_LIMIT,
        get_src_ip_fn=get_src_ip,
        choose_best_time_fn=choose_best_time,
        raw_text_fn=raw_text,
        extract_raw_request_target_fn=extract_raw_request_target,
        get_uri_fn=get_uri,
        get_effective_request_path_fn=get_effective_request_path,
        get_method_fn=get_method,
        classify_static_baseline_asset_category_fn=classify_static_baseline_asset_category,
        get_status_code_fn=get_status_code,
        get_sample_request_id_fn=get_sample_request_id,
    )


def build_static_baseline_summary_contexts(
    static_baseline_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _build_static_baseline_summary_contexts(static_baseline_summaries)


def row_is_covered_by_static_baseline_context(
    row: Dict[str, Any],
    static_baseline_contexts: List[Dict[str, Any]],
) -> bool:
    if not static_baseline_contexts:
        return False

    static_hints = build_static_baseline_reason_hints_for_row(row)
    if not static_hints:
        return False

    src_ip = get_src_ip(row)
    row_dt = parse_flexible_iso_dt(choose_best_time(row) or "")
    if not src_ip or row_dt is None:
        return False

    for context in static_baseline_contexts:
        if context["src_ip"] != src_ip:
            continue
        if context["start_dt"] <= row_dt <= context["end_dt"]:
            return True
    return False


def build_row_context_reason_hints(row: Dict[str, Any]) -> List[str]:
    uri = get_uri(row)
    raw_req_original = raw_text(row.get("raw_request"))
    raw_request_target = extract_raw_request_target(raw_req_original)
    raw_qs = raw_text(row.get("query_string"))
    qs = normalize_text(row.get("query_string"))
    raw_log = raw_text(row.get("raw_log"))
    probe_path = get_effective_request_path(uri, raw_request_target).lower()
    hpp_detected, hpp_param_names = analyze_query_parameters(qs)

    base_text, combined_target, query_variants, raw_request_target_variants = build_analysis_texts(
        raw_request=raw_req_original,
        uri=uri,
        query_string=raw_qs,
        raw_request_target=raw_request_target,
        raw_log=raw_log,
    )

    reason_hints: List[str] = []
    for name, pattern, _ in SQLI_PATTERNS:
        if matches_sqli_pattern(name, pattern, combined_target):
            append_unique_hint(reason_hints, f"sqli:{name}")
    for name, pattern, _ in XSS_PATTERNS:
        if pattern.search(combined_target):
            append_unique_hint(reason_hints, f"xss:{name}")
    for name, pattern, _ in TRAVERSAL_PATTERNS:
        if pattern.search(combined_target):
            append_unique_hint(reason_hints, f"traversal:{name}")
    for name, pattern, _ in CMDI_PATTERNS:
        if pattern.search(combined_target):
            append_unique_hint(reason_hints, f"cmdi:{name}")

    _, decoded_hints = detect_decoded_attack_hints(
        base_text=base_text,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    extend_unique_hints(reason_hints, decoded_hints)

    _, file_disclosure_hints = detect_file_disclosure_hints(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    extend_unique_hints(reason_hints, file_disclosure_hints)
    _, log4shell_hints = detect_log4shell_hints(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    extend_unique_hints(reason_hints, log4shell_hints)
    _, ssrf_hints = detect_ssrf_hints(
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    extend_unique_hints(reason_hints, ssrf_hints)
    _, ssti_hints = detect_ssti_hints(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    extend_unique_hints(reason_hints, ssti_hints)
    _, webshell_hints = detect_webshell_hints(
        uri=uri,
        raw_request_target=raw_request_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    extend_unique_hints(reason_hints, webshell_hints)
    extend_unique_hints(
        reason_hints,
        get_xss_context_hints(
            raw_query_string=raw_qs,
            query_string=qs,
            raw_request_target=raw_request_target,
            combined_target=combined_target,
            query_variants=query_variants,
            raw_request_target_variants=raw_request_target_variants,
        ),
    )

    if is_likely_probe_sequence_path(probe_path, query_string=qs):
        extend_unique_hints(reason_hints, get_probe_sequence_reason_hints(probe_path))

    if hpp_detected:
        append_unique_hint(reason_hints, "hpp:duplicate_param_names")
        if hpp_param_names:
            append_unique_hint(reason_hints, "hpp:param_names=" + ",".join(hpp_param_names))

    return reason_hints


def get_attack_categories_from_reason_hints(reason_hints: Iterable[str]) -> List[str]:
    categories: List[str] = []
    for hint in reason_hints:
        normalized = raw_text(hint)
        if not normalized:
            continue
        if normalized.startswith("sqli:") or normalized == "encoding:double_decoded_sqli":
            append_unique_hint(categories, "sqli")
        elif normalized.startswith("xss:") or normalized == "encoding:html_entity_decoded_xss":
            append_unique_hint(categories, "xss")
        elif normalized.startswith("traversal:") or normalized.startswith("path_traversal:"):
            append_unique_hint(categories, "path_traversal")
        elif normalized.startswith("file_disclosure:"):
            append_unique_hint(categories, "file_disclosure")
        elif normalized.startswith("dir_probe:"):
            append_unique_hint(categories, "dir_probe")
        elif normalized.startswith("hpp:"):
            append_unique_hint(categories, "hpp")
        elif normalized.startswith("cmdi:"):
            append_unique_hint(categories, "command_injection")
        elif normalized.startswith("log4shell:") or normalized == "l3:log4shell":
            append_unique_hint(categories, "log4shell")
        elif normalized.startswith("ssrf:") or normalized == "l3:ssrf":
            append_unique_hint(categories, "ssrf")
        elif normalized.startswith("ssti:") or normalized == "l3:ssti":
            append_unique_hint(categories, "ssti")
        elif normalized.startswith("webshell:") or normalized == "l3:webshell_probe":
            append_unique_hint(categories, "webshell")
    return categories


def get_sample_request_id(row: Dict[str, Any]) -> str:
    for value in (
        normalize_identifier(row.get("request_id")),
        normalize_identifier(row.get("log_id")),
        normalize_identifier(row.get("id")),
        normalize_identifier(row.get("error_link_id")),
    ):
        if value:
            return value
    return ""


def is_sensitive_ip_behavior_path(path: str) -> bool:
    return _is_sensitive_ip_behavior_path(
        path,
        get_probe_sequence_reason_hints_fn=get_probe_sequence_reason_hints,
    )


def finalize_ip_behavior_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
) -> Optional[Dict[str, Any]]:
    return _finalize_ip_behavior_bucket(
        items,
        window_sec=window_sec,
        sample_request_limit=IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        sensitive_path_limit=IP_BEHAVIOR_SENSITIVE_PATH_LIMIT,
        normalize_text_fn=normalize_text,
        safe_int_fn=safe_int,
        append_unique_hint_fn=append_unique_hint,
        get_attack_categories_from_reason_hints_fn=get_attack_categories_from_reason_hints,
    )


def build_ip_behavior_aggregates(
    rows: List[Dict[str, Any]],
    window_sec: int = IP_BEHAVIOR_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_ip_behavior_aggregates(
        rows,
        window_sec=window_sec,
        sample_request_limit=IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        sensitive_path_limit=IP_BEHAVIOR_SENSITIVE_PATH_LIMIT,
        get_src_ip_fn=get_src_ip,
        choose_best_time_fn=choose_best_time,
        parse_flexible_iso_dt_fn=parse_flexible_iso_dt,
        get_uri_fn=get_uri,
        raw_text_fn=raw_text,
        extract_raw_request_target_fn=extract_raw_request_target,
        get_effective_request_path_fn=get_effective_request_path,
        get_method_fn=get_method,
        get_status_code_fn=get_status_code,
        get_user_agent_fn=get_user_agent,
        get_sample_request_id_fn=get_sample_request_id,
        build_row_context_reason_hints_fn=build_row_context_reason_hints,
        is_sensitive_ip_behavior_path_fn=_is_sensitive_ip_behavior_path,
        finalize_ip_behavior_bucket_fn=_finalize_ip_behavior_bucket,
        normalize_text_fn=normalize_text,
        get_probe_sequence_reason_hints_fn=get_probe_sequence_reason_hints,
        get_attack_categories_from_reason_hints_fn=get_attack_categories_from_reason_hints,
        append_unique_hint_fn=append_unique_hint,
        safe_int_fn=safe_int,
    )


def max_bucket_size_within_window(
    items: List[Dict[str, Any]],
    window_sec: int,
    *,
    status_predicate: Optional[Any] = None,
) -> int:
    if not items:
        return 0

    filtered = items
    if status_predicate is not None:
        filtered = [item for item in items if status_predicate(safe_int(item.get("status_code"), 0))]
        if not filtered:
            return 0

    max_count = 0
    left = 0
    for right, item in enumerate(filtered):
        current_dt = item["dt"]
        while left <= right and (current_dt - filtered[left]["dt"]).total_seconds() > window_sec:
            left += 1
        max_count = max(max_count, right - left + 1)
    return max_count


def finalize_auth_behavior_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
    rapid_window_sec: int,
) -> Optional[Dict[str, Any]]:
    return _finalize_auth_behavior_bucket(
        items,
        window_sec=window_sec,
        rapid_window_sec=rapid_window_sec,
        sample_request_limit=AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
    )


def build_auth_behavior_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = AUTH_BEHAVIOR_WINDOW_SEC,
    rapid_window_sec: int = AUTH_BEHAVIOR_RAPID_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_auth_behavior_summaries(
        rows,
        window_sec=window_sec,
        rapid_window_sec=rapid_window_sec,
        sample_request_limit=AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        auth_endpoint_family_patterns=AUTH_ENDPOINT_FAMILY_PATTERNS,
    )


def classify_method_behavior_family(method: str) -> str:
    normalized = normalize_text(method).upper()
    if not normalized or normalized == "-":
        return "unknown"
    if normalized in METHOD_RISKY_FAMILIES:
        return "risky"
    if normalized in METHOD_BASELINE_FAMILIES:
        return "baseline"
    if normalized not in STANDARD_HTTP_METHODS:
        return "unknown"
    return "other"


def has_method_protocol_anomaly(row: Dict[str, Any], method: str) -> bool:
    normalized_method = normalize_text(method).upper()
    if not normalized_method or normalized_method == "-":
        return True
    if not re.fullmatch(r"[A-Z!#$%&'*+.^_`|~-]{1,32}", normalized_method):
        return True

    protocol = normalize_text(row.get("protocol"))
    if protocol and not re.fullmatch(r"HTTP/\d(?:\.\d)?", protocol, re.IGNORECASE):
        return True
    return False


def get_row_protocol_value(row: Dict[str, Any]) -> str:
    protocol = normalize_text(row.get("protocol"))
    if protocol:
        return protocol.upper()

    raw_request = raw_text(row.get("raw_request"))
    parts = raw_request.split()
    if len(parts) >= 3 and parts[-1].upper().startswith("HTTP/"):
        return parts[-1].upper()
    return ""


def get_row_host_value(row: Dict[str, Any]) -> str:
    return normalize_text(row.get("host")) or normalize_text(row.get("request_host"))


def is_valid_host_header_value(host: str) -> bool:
    normalized = normalize_text(host).strip("[]")
    if not normalized:
        return False
    if normalized.lower() == "localhost":
        return True
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", normalized):
        octets = normalized.split(".")
        return all(0 <= safe_int(octet, -1) <= 255 for octet in octets)
    if ":" in normalized and normalized.count(":") >= 2:
        return bool(re.fullmatch(r"[0-9a-fA-F:]+", normalized))
    if ".." in normalized:
        return False
    return bool(
        re.fullmatch(
            r"(?i)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*",
            normalized,
        )
    )


def get_protocol_anomaly_types_for_row(row: Dict[str, Any]) -> List[str]:
    method = normalize_text(get_method(row)).upper()
    protocol = get_row_protocol_value(row)
    host = get_row_host_value(row)
    status_code = get_status_code(row)
    raw_request_target = extract_raw_request_target(raw_text(row.get("raw_request")))
    request_path = get_effective_request_path(get_uri(row), raw_request_target)

    anomaly_types: List[str] = []

    if not method or method == "-" or method not in STANDARD_HTTP_METHODS or not re.fullmatch(r"[A-Z!#$%&'*+.^_`|~-]{1,32}", method):
        append_unique_hint(anomaly_types, "unsupported_method")

    if protocol == "HTTP/1.0":
        append_unique_hint(anomaly_types, "http10_request")

    if protocol:
        normalized_protocol = protocol.upper()
        if normalized_protocol.startswith("HTTP/") and normalized_protocol not in {
            "HTTP/1.0",
            "HTTP/1.1",
            "HTTP/2",
            "HTTP/2.0",
            "HTTP/3",
            "HTTP/3.0",
        }:
            append_unique_hint(anomaly_types, "bad_protocol_version")
        elif not re.fullmatch(r"HTTP/\d(?:\.\d)?", normalized_protocol):
            append_unique_hint(anomaly_types, "bad_protocol_version")

    if protocol == "HTTP/1.1" and not host and status_code in {400, 408, 414, 421, 431}:
        append_unique_hint(anomaly_types, "missing_host")

    if host and not is_valid_host_header_value(host):
        append_unique_hint(anomaly_types, "odd_host")

    if len(request_path) >= PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN:
        append_unique_hint(anomaly_types, "long_path")

    return anomaly_types


def build_protocol_anomaly_reason_hints_for_row(
    row: Dict[str, Any],
    *,
    include_inference_limit: bool = False,
) -> List[str]:
    return _build_protocol_anomaly_reason_hints_for_row(
        row,
        include_inference_limit=include_inference_limit,
        long_path_min_len=PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
        standard_http_methods=STANDARD_HTTP_METHODS,
    )


def build_method_behavior_reason_hints_for_row(
    row: Dict[str, Any],
    *,
    include_inference_limit: bool = False,
) -> List[str]:
    return _build_method_behavior_reason_hints_for_row(
        row,
        include_inference_limit=include_inference_limit,
        method_destructive_families=METHOD_DESTRUCTIVE_FAMILIES,
        method_risky_families=METHOD_RISKY_FAMILIES,
        method_baseline_families=METHOD_BASELINE_FAMILIES,
        standard_http_methods=STANDARD_HTTP_METHODS,
    )


def build_method_behavior_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = METHOD_BEHAVIOR_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_method_behavior_summaries(
        rows,
        window_sec=window_sec,
        sample_request_limit=METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        method_risky_families=METHOD_RISKY_FAMILIES,
        method_baseline_families=METHOD_BASELINE_FAMILIES,
        method_destructive_families=METHOD_DESTRUCTIVE_FAMILIES,
        standard_http_methods=STANDARD_HTTP_METHODS,
    )


def finalize_protocol_anomaly_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
) -> Optional[Dict[str, Any]]:
    return _finalize_protocol_anomaly_bucket(
        items,
        window_sec=window_sec,
        sample_request_limit=PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT,
        long_path_min_len=PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
        standard_http_methods=STANDARD_HTTP_METHODS,
    )


def build_protocol_anomaly_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = PROTOCOL_ANOMALY_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_protocol_anomaly_summaries(
        rows,
        window_sec=window_sec,
        sample_request_limit=PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT,
        long_path_min_len=PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
        standard_http_methods=STANDARD_HTTP_METHODS,
    )


def build_method_behavior_summary_contexts(
    method_behavior_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _build_method_behavior_summary_contexts(method_behavior_summaries)


def build_protocol_anomaly_summary_contexts(
    protocol_anomaly_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _build_protocol_anomaly_summary_contexts(protocol_anomaly_summaries)


def row_is_covered_by_protocol_anomaly_context(
    row: Dict[str, Any],
    protocol_anomaly_contexts: List[Dict[str, Any]],
) -> bool:
    if not protocol_anomaly_contexts:
        return False

    protocol_hints = build_protocol_anomaly_reason_hints_for_row(row, include_inference_limit=False)
    if not protocol_hints:
        return False

    src_ip = get_src_ip(row)
    row_dt = parse_flexible_iso_dt(choose_best_time(row) or "")
    if not src_ip or row_dt is None:
        return False

    for context in protocol_anomaly_contexts:
        if context["src_ip"] != src_ip:
            continue
        if context["start_dt"] <= row_dt <= context["end_dt"]:
            return True
    return False


def row_is_covered_by_method_behavior_context(
    row: Dict[str, Any],
    method_behavior_contexts: List[Dict[str, Any]],
) -> bool:
    if not method_behavior_contexts:
        return False

    method_hints = build_method_behavior_reason_hints_for_row(row, include_inference_limit=False)
    if not method_hints:
        return False

    src_ip = get_src_ip(row)
    row_dt = parse_flexible_iso_dt(choose_best_time(row) or "")
    if not src_ip or row_dt is None:
        return False

    for context in method_behavior_contexts:
        if context["src_ip"] != src_ip:
            continue
        if context["start_dt"] <= row_dt <= context["end_dt"]:
            return True
    return False


def build_auth_behavior_summary_contexts(
    auth_behavior_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _build_auth_behavior_summary_contexts(auth_behavior_summaries)


def build_auth_behavior_support_reason_hints(summary: Dict[str, Any]) -> List[str]:
    hints: List[str] = []
    if bool(summary.get("has_repeated_401")):
        append_unique_hint(hints, "auth_abuse:repeated_401")
    if bool(summary.get("has_rapid_burst")):
        append_unique_hint(hints, "auth_abuse:rapid_fail_burst")
    if bool(summary.get("has_mixed_401_200")):
        append_unique_hint(hints, "auth_abuse:mixed_401_200_sequence")
    append_unique_hint(hints, "auth_abuse:repeated_auth_endpoint")
    append_unique_hint(hints, "auth_abuse:covered_by_auth_behavior_summary")
    append_unique_hint(hints, "auth_abuse:post_body_not_visible")
    append_unique_hint(hints, "auth_abuse:no_auth_success_inference")
    return hints


def choose_auth_behavior_representative_candidates(
    items: List[Candidate],
    summary: Dict[str, Any],
    representative_limit: int,
) -> List[Candidate]:
    if len(items) <= representative_limit:
        return list(items)

    sorted_items = sorted(items, key=lambda item: normalize_text(item.log_time))
    selected_indexes: List[int] = []

    def add_index(idx: int) -> None:
        if idx not in selected_indexes:
            selected_indexes.append(idx)

    add_index(0)
    peak_idx = max(
        range(len(sorted_items)),
        key=lambda idx: (
            sorted_items[idx].score,
            sorted_items[idx].duration_us,
            sorted_items[idx].ttfb_us,
            normalize_text(sorted_items[idx].log_time),
        ),
    )
    add_index(peak_idx)
    if bool(summary.get("has_rapid_burst")) or bool(summary.get("has_mixed_401_200")):
        add_index(len(sorted_items) - 1)

    if len(selected_indexes) < min(representative_limit, len(sorted_items)):
        ranked_remaining = sorted(
            range(len(sorted_items)),
            key=lambda idx: (
                sorted_items[idx].score,
                sorted_items[idx].duration_us,
                sorted_items[idx].ttfb_us,
                normalize_text(sorted_items[idx].log_time),
            ),
            reverse=True,
        )
        for idx in ranked_remaining:
            add_index(idx)
            if len(selected_indexes) >= representative_limit:
                break

    selected_candidates = [sorted_items[idx] for idx in selected_indexes[:representative_limit]]
    selected_candidates.sort(key=lambda item: normalize_text(item.log_time))
    return selected_candidates


def build_auth_behavior_supporting_event(
    candidate: Candidate,
    summary: Dict[str, Any],
    covered_candidate_count: int,
) -> Dict[str, Any]:
    return {
        "supporting_reason": "covered_by_auth_behavior_summary",
        "supporting_role": "auth_behavior_support",
        "context_role": "auth_behavior_context",
        "should_promote_to_candidate": False,
        "source_table": candidate.source_table,
        "log_id": candidate.log_id,
        "log_time": candidate.log_time,
        "src_ip": candidate.src_ip,
        "method": candidate.method,
        "uri": candidate.uri,
        "query_string": candidate.query_string,
        "status_code": candidate.status_code,
        "response_body_bytes": candidate.response_body_bytes,
        "duration_us": candidate.duration_us,
        "ttfb_us": candidate.ttfb_us,
        "resp_content_type": candidate.resp_content_type,
        "user_agent": candidate.user_agent,
        "raw_request": candidate.raw_request,
        "raw_request_target": candidate.raw_request_target,
        "request_id": candidate.request_id,
        "incident_group_key": candidate.incident_group_key or build_incident_group_key(candidate),
        "reason_hints": build_auth_behavior_support_reason_hints(summary),
        "temporal_context_key": build_temporal_context_key(candidate.src_ip, candidate.uri, candidate.log_time),
        "temporal_context_role": "auth_behavior_context",
        "nearby_candidate_count": covered_candidate_count,
        "endpoint_family": normalize_text(summary.get("endpoint_family")) or "auth_endpoint",
        "auth_summary_window_start": normalize_text(summary.get("window_start")),
        "auth_summary_window_end": normalize_text(summary.get("window_end")),
        "interpretation_limit": "post_body_not_visible_no_auth_success_inference",
    }


def reduce_repeated_auth_candidates(
    candidates: List[Candidate],
    auth_behavior_summaries: List[Dict[str, Any]],
    representative_limit: int = AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT,
) -> Tuple[List[Candidate], List[Dict[str, Any]]]:
    contexts = build_auth_behavior_summary_contexts(auth_behavior_summaries)
    if not contexts:
        return candidates, []

    grouped_candidates: Dict[str, List[Candidate]] = defaultdict(list)
    matched_summary_by_group: Dict[str, Dict[str, Any]] = {}
    passthrough_candidates: List[Candidate] = []

    for candidate in candidates:
        if candidate.status_code != 401:
            passthrough_candidates.append(candidate)
            continue

        candidate_dt = parse_flexible_iso_dt(candidate.log_time or "")
        if candidate_dt is None:
            passthrough_candidates.append(candidate)
            continue

        endpoint_family = get_auth_endpoint_family(candidate.method, candidate.uri, raw_request_target=candidate.raw_request_target)
        if not endpoint_family:
            passthrough_candidates.append(candidate)
            continue

        matched_context: Optional[Dict[str, Any]] = None
        for context in contexts:
            if context["src_ip"] != normalize_text(candidate.src_ip):
                continue
            if context["endpoint_family"] != endpoint_family:
                continue
            if context["start_dt"] <= candidate_dt <= context["end_dt"]:
                matched_context = context
                break

        if matched_context is None:
            passthrough_candidates.append(candidate)
            continue

        summary_key = matched_context["summary_key"]
        grouped_candidates[summary_key].append(candidate)
        matched_summary_by_group[summary_key] = matched_context["summary"]

    reduced_candidates: List[Candidate] = list(passthrough_candidates)
    supporting_events: List[Dict[str, Any]] = []
    for summary_key, items in grouped_candidates.items():
        summary = matched_summary_by_group[summary_key]
        if len(items) <= representative_limit:
            reduced_candidates.extend(items)
            continue

        representative_candidates = choose_auth_behavior_representative_candidates(
            items,
            summary=summary,
            representative_limit=representative_limit,
        )
        representative_keys = {id(item) for item in representative_candidates}
        reduced_candidates.extend(representative_candidates)
        for candidate in items:
            if id(candidate) in representative_keys:
                continue
            supporting_events.append(
                build_auth_behavior_supporting_event(
                    candidate,
                    summary=summary,
                    covered_candidate_count=len(items),
                )
            )

    reduced_candidates.sort(key=lambda item: (item.score, normalize_text(item.log_time)), reverse=True)
    supporting_events.sort(
        key=lambda item: (
            safe_int(item.get("nearby_candidate_count"), 0),
            normalize_text(item.get("log_time")),
        ),
        reverse=True,
    )
    return reduced_candidates, supporting_events


def candidate_is_sensitive_path_probe_only(candidate: Candidate) -> bool:
    if normalize_text(candidate.verdict_hint) != "suspicious":
        return False

    path = get_effective_request_path(candidate.uri, candidate.raw_request_target).lower()
    if not classify_sensitive_path_probe_category(path, candidate.method):
        return False

    if get_attack_categories_from_reason_hints(candidate.reason_hints):
        return False

    return True


def build_sensitive_path_probe_support_reason_hints(candidate: Candidate) -> List[str]:
    hints = build_sensitive_path_reason_hints_for_row(asdict(candidate))
    append_unique_hint(hints, "sensitive_path:covered_by_sensitive_path_probe_summary")
    return [raw_text(hint) for hint in hints if raw_text(hint)]


def build_sensitive_path_probe_supporting_event(
    candidate: Candidate,
    summary: Dict[str, Any],
    covered_candidate_count: int,
) -> Dict[str, Any]:
    return {
        "supporting_reason": "covered_by_sensitive_path_probe_summary",
        "supporting_role": "sensitive_path_probe_support",
        "context_role": "sensitive_path_probe_context",
        "should_promote_to_candidate": False,
        "source_table": candidate.source_table,
        "log_id": candidate.log_id,
        "log_time": candidate.log_time,
        "src_ip": candidate.src_ip,
        "method": candidate.method,
        "uri": candidate.uri,
        "query_string": candidate.query_string,
        "status_code": candidate.status_code,
        "response_body_bytes": candidate.response_body_bytes,
        "duration_us": candidate.duration_us,
        "ttfb_us": candidate.ttfb_us,
        "resp_content_type": candidate.resp_content_type,
        "user_agent": candidate.user_agent,
        "raw_request": candidate.raw_request,
        "raw_request_target": candidate.raw_request_target,
        "request_id": candidate.request_id,
        "incident_group_key": candidate.incident_group_key or build_incident_group_key(candidate),
        "reason_hints": build_sensitive_path_probe_support_reason_hints(candidate),
        "temporal_context_key": build_temporal_context_key(candidate.src_ip, candidate.uri, candidate.log_time),
        "temporal_context_role": "sensitive_path_probe_context",
        "nearby_candidate_count": covered_candidate_count,
        "sensitive_path_summary_window_start": normalize_text(summary.get("window_start")),
        "sensitive_path_summary_window_end": normalize_text(summary.get("window_end")),
        "interpretation_limit": "sensitive_path_probe_no_file_or_app_exposure_inference",
    }


def reduce_repeated_sensitive_path_candidates(
    candidates: List[Candidate],
    sensitive_path_probe_summaries: List[Dict[str, Any]],
    representative_limit: int = SENSITIVE_PATH_PROBE_REPRESENTATIVE_CANDIDATE_LIMIT,
) -> Tuple[List[Candidate], List[Dict[str, Any]]]:
    contexts = build_sensitive_path_probe_summary_contexts(sensitive_path_probe_summaries)
    if not contexts:
        return candidates, []

    grouped_candidates: Dict[str, List[Candidate]] = defaultdict(list)
    matched_summary_by_group: Dict[str, Dict[str, Any]] = {}
    passthrough_candidates: List[Candidate] = []

    for candidate in candidates:
        if not candidate_is_sensitive_path_probe_only(candidate):
            passthrough_candidates.append(candidate)
            continue

        candidate_dt = parse_flexible_iso_dt(candidate.log_time or "")
        if candidate_dt is None:
            passthrough_candidates.append(candidate)
            continue

        matched_context: Optional[Dict[str, Any]] = None
        for context in contexts:
            if context["src_ip"] != normalize_text(candidate.src_ip):
                continue
            if context["start_dt"] <= candidate_dt <= context["end_dt"]:
                matched_context = context
                break

        if matched_context is None:
            passthrough_candidates.append(candidate)
            continue

        summary_key = "|".join(
            [
                normalize_text(matched_context["summary"].get("src_ip")),
                normalize_text(matched_context["summary"].get("window_start")),
                normalize_text(matched_context["summary"].get("window_end")),
            ]
        )
        grouped_candidates[summary_key].append(candidate)
        matched_summary_by_group[summary_key] = matched_context["summary"]

    reduced_candidates: List[Candidate] = list(passthrough_candidates)
    supporting_events: List[Dict[str, Any]] = []
    for summary_key, items in grouped_candidates.items():
        summary = matched_summary_by_group[summary_key]
        if len(items) <= representative_limit:
            reduced_candidates.extend(items)
            continue

        sorted_items = sorted(
            items,
            key=lambda item: (
                item.score,
                item.duration_us,
                item.ttfb_us,
                normalize_text(item.log_time),
            ),
            reverse=True,
        )
        representative_candidates = sorted_items[:representative_limit]
        representative_keys = {id(item) for item in representative_candidates}
        reduced_candidates.extend(representative_candidates)
        for candidate in items:
            if id(candidate) in representative_keys:
                continue
            supporting_events.append(
                build_sensitive_path_probe_supporting_event(
                    candidate,
                    summary=summary,
                    covered_candidate_count=len(items),
                )
            )

    reduced_candidates.sort(key=lambda item: (item.score, normalize_text(item.log_time)), reverse=True)
    supporting_events.sort(
        key=lambda item: (
            safe_int(item.get("nearby_candidate_count"), 0),
            normalize_text(item.get("log_time")),
        ),
        reverse=True,
    )
    return reduced_candidates, supporting_events


def safe_int(value: Optional[Any], default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def special_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    special_count = sum(1 for ch in text if ch in "'\"`;=#()/*-%,<>")
    return special_count / max(len(text), 1)


def looks_like_browser_ua(ua: str) -> bool:
    ua_lower = (ua or "").lower()
    return any(hint in ua_lower for hint in BROWSER_UA_HINTS)


def contains_login_uri(uri: str) -> bool:
    uri_lower = (uri or "").lower()
    return any(hint in uri_lower for hint in LOGIN_URI_HINTS)


def get_auth_endpoint_family(method: str, uri: str, raw_request_target: str = "") -> str:
    if normalize_text(method).upper() != "POST":
        return ""

    path = get_effective_request_path(uri, raw_request_target).lower()
    if not path:
        return ""

    for family, pattern in AUTH_ENDPOINT_FAMILY_PATTERNS:
        if pattern.search(path):
            return family
    return ""


def is_auth_endpoint_request(method: str, uri: str, raw_request_target: str = "") -> bool:
    return bool(get_auth_endpoint_family(method, uri, raw_request_target=raw_request_target))


def contains_query_heavy_uri(uri: str) -> bool:
    uri_lower = (uri or "").lower()
    return any(hint in uri_lower for hint in QUERY_HEAVY_URI_HINTS)


def is_json_content_type(content_type: str) -> bool:
    value = (content_type or "").lower()
    return value.startswith("application/json") or value.endswith("+json")


def has_auth_success_attack_hint(*values: str) -> bool:
    combined = " ".join(normalize_text(value) for value in values if value)
    return bool(combined and AUTH_SUCCESS_ATTACK_HINT_PATTERN.search(combined))


def is_static_resource(uri: str) -> bool:
    uri_lower = (uri or "").lower()
    return uri_lower.endswith(STATIC_EXTENSIONS) or any(uri_lower.startswith(p) for p in STATIC_PREFIXES)


def is_health_like_path(path: str) -> bool:
    return normalize_text(path).lower() in HEALTH_LIKE_PATHS


def classify_static_baseline_asset_category(path: str, method: str) -> str:
    normalized_method = normalize_text(method).upper()
    normalized_path = normalize_text(path).lower()
    if normalized_method not in {"GET", "HEAD"} or not normalized_path:
        return ""

    if normalized_path == "/favicon.ico":
        return "favicon"
    if normalized_path == "/robots.txt":
        return "robots_txt"
    if normalized_path == "/sitemap.xml":
        return "sitemap_xml"
    if is_health_like_path(normalized_path):
        return "health_check"
    if normalized_method == "GET" and normalized_path == "/":
        return "normal_get"
    if normalized_path.endswith(".js"):
        return "javascript_asset"
    if normalized_path.endswith(".css"):
        return "css_asset"
    if normalized_path.endswith(STATIC_BASELINE_IMAGE_EXTENSIONS):
        return "image_asset"
    if is_static_resource(normalized_path):
        return "static_asset"
    return ""


def build_static_baseline_reason_hints_for_row(row: Dict[str, Any]) -> List[str]:
    return _build_static_baseline_reason_hints_for_row(
        row,
        raw_text_fn=raw_text,
        extract_raw_request_target_fn=extract_raw_request_target,
        get_uri_fn=get_uri,
        get_effective_request_path_fn=get_effective_request_path,
        get_method_fn=get_method,
        classify_static_baseline_asset_category_fn=classify_static_baseline_asset_category,
    )


def classify_crawler_like_user_agent_family(user_agent: str) -> str:
    return _classify_crawler_like_user_agent_family(user_agent)


def classify_crawler_baseline_path_category(path: str, method: str) -> str:
    return _classify_crawler_baseline_path_category(
        path,
        method,
        product_segments=CRAWLER_BROWSE_PRODUCT_SEGMENTS,
        category_segments=CRAWLER_BROWSE_CATEGORY_SEGMENTS,
        generic_segments=CRAWLER_BROWSE_GENERIC_SEGMENTS,
    )


def build_crawler_baseline_reason_hints_for_row(
    row: Dict[str, Any],
    *,
    repeated_sequence: bool = False,
) -> List[str]:
    return _build_crawler_baseline_reason_hints_for_row(
        row,
        repeated_sequence=repeated_sequence,
        raw_text_fn=raw_text,
        extract_raw_request_target_fn=extract_raw_request_target,
        get_uri_fn=get_uri,
        get_effective_request_path_fn=get_effective_request_path,
        get_method_fn=get_method,
        get_user_agent_fn=get_user_agent,
        product_segments=CRAWLER_BROWSE_PRODUCT_SEGMENTS,
        category_segments=CRAWLER_BROWSE_CATEGORY_SEGMENTS,
        generic_segments=CRAWLER_BROWSE_GENERIC_SEGMENTS,
    )


def finalize_crawler_baseline_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
) -> Optional[Dict[str, Any]]:
    return _finalize_crawler_baseline_bucket(
        items,
        window_sec=window_sec,
        sample_request_limit=CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT,
    )


def build_crawler_baseline_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = CRAWLER_BASELINE_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_crawler_baseline_summaries(
        rows,
        window_sec=window_sec,
        sample_request_limit=CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT,
        get_src_ip_fn=get_src_ip,
        choose_best_time_fn=choose_best_time,
        raw_text_fn=raw_text,
        extract_raw_request_target_fn=extract_raw_request_target,
        get_uri_fn=get_uri,
        get_effective_request_path_fn=get_effective_request_path,
        get_method_fn=get_method,
        get_user_agent_fn=get_user_agent,
        get_status_code_fn=get_status_code,
        get_sample_request_id_fn=get_sample_request_id,
        product_segments=CRAWLER_BROWSE_PRODUCT_SEGMENTS,
        category_segments=CRAWLER_BROWSE_CATEGORY_SEGMENTS,
        generic_segments=CRAWLER_BROWSE_GENERIC_SEGMENTS,
    )


def build_crawler_baseline_summary_contexts(
    crawler_baseline_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _build_crawler_baseline_summary_contexts(crawler_baseline_summaries)


def get_crawler_baseline_context_for_row(
    row: Dict[str, Any],
    crawler_baseline_contexts: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not crawler_baseline_contexts:
        return None

    crawler_hints = build_crawler_baseline_reason_hints_for_row(row)
    if not crawler_hints:
        return None

    src_ip = get_src_ip(row)
    row_dt = parse_flexible_iso_dt(choose_best_time(row) or "")
    if not src_ip or row_dt is None:
        return None

    for context in crawler_baseline_contexts:
        if context["src_ip"] != src_ip:
            continue
        if context["start_dt"] <= row_dt <= context["end_dt"]:
            return context
    return None


def classify_sensitive_path_probe_category(path: str, method: str) -> str:
    return _classify_sensitive_path_probe_category(path, method)


def build_sensitive_path_reason_hints_for_row(
    row: Dict[str, Any],
    *,
    repeated_sequence: bool = False,
) -> List[str]:
    raw_request_target = extract_raw_request_target(raw_text(row.get("raw_request")))
    path = get_effective_request_path(get_uri(row), raw_request_target).lower()
    category = classify_sensitive_path_probe_category(path, get_method(row))
    if not category:
        return []

    hints: List[str] = []
    if category == "wp_login":
        append_unique_hint(hints, "sensitive_path:wp_login")
        append_unique_hint(hints, "sensitive_path:admin_path")
        append_unique_hint(hints, "sensitive_path:no_app_presence_inference")
    elif category == "wp_admin":
        append_unique_hint(hints, "sensitive_path:wp_admin")
        append_unique_hint(hints, "sensitive_path:admin_path")
        append_unique_hint(hints, "sensitive_path:no_admin_access_inference")
    elif category == "env_file":
        append_unique_hint(hints, "sensitive_path:env_file")
        append_unique_hint(hints, "sensitive_path:config_like_path")
        append_unique_hint(hints, "sensitive_path:no_file_exposure_inference")
    elif category == "phpinfo":
        append_unique_hint(hints, "sensitive_path:phpinfo")
        append_unique_hint(hints, "sensitive_path:diagnostic_path")
        append_unique_hint(hints, "sensitive_path:no_phpinfo_exposure_inference")
    elif category == "server_status":
        append_unique_hint(hints, "sensitive_path:server_status")
        append_unique_hint(hints, "sensitive_path:no_server_status_exposure_inference")
    elif category == "backup_artifact":
        append_unique_hint(hints, "sensitive_path:backup_artifact")
        append_unique_hint(hints, "sensitive_path:no_backup_exposure_inference")
    elif category == "config_php":
        append_unique_hint(hints, "sensitive_path:config_php")
        append_unique_hint(hints, "sensitive_path:config_like_path")
        append_unique_hint(hints, "sensitive_path:no_file_exposure_inference")
    elif category == "admin_config_php":
        append_unique_hint(hints, "sensitive_path:admin_config_php")
        append_unique_hint(hints, "sensitive_path:admin_path")
        append_unique_hint(hints, "sensitive_path:config_like_path")
        append_unique_hint(hints, "sensitive_path:no_file_exposure_inference")
    elif category == "backup_directory":
        append_unique_hint(hints, "sensitive_path:backup_directory")
        append_unique_hint(hints, "sensitive_path:no_backup_exposure_inference")
    elif category == "admin_directory":
        append_unique_hint(hints, "sensitive_path:admin_path")
        append_unique_hint(hints, "sensitive_path:no_admin_access_inference")

    if repeated_sequence:
        append_unique_hint(hints, "sensitive_path:repeated_sensitive_path_sequence")
        append_unique_hint(hints, "sensitive_path:no_success_inference")

    return hints


def finalize_sensitive_path_probe_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
) -> Optional[Dict[str, Any]]:
    return _finalize_sensitive_path_probe_bucket(
        items,
        window_sec=window_sec,
        sample_request_limit=SENSITIVE_PATH_PROBE_SAMPLE_REQUEST_LIMIT,
    )


def build_sensitive_path_probe_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = SENSITIVE_PATH_PROBE_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_sensitive_path_probe_summaries(
        rows,
        window_sec=window_sec,
        sample_request_limit=SENSITIVE_PATH_PROBE_SAMPLE_REQUEST_LIMIT,
        get_src_ip_fn=get_src_ip,
        choose_best_time_fn=choose_best_time,
        parse_flexible_iso_dt_fn=parse_flexible_iso_dt,
        raw_text_fn=raw_text,
        extract_raw_request_target_fn=extract_raw_request_target,
        get_uri_fn=get_uri,
        get_effective_request_path_fn=get_effective_request_path,
        get_method_fn=get_method,
        classify_sensitive_path_probe_category_fn=classify_sensitive_path_probe_category,
        get_status_code_fn=get_status_code,
        build_sensitive_path_reason_hints_for_row_fn=build_sensitive_path_reason_hints_for_row,
        get_sample_request_id_fn=get_sample_request_id,
    )


def build_sensitive_path_probe_summary_contexts(
    sensitive_path_probe_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _build_sensitive_path_probe_summary_contexts(
        sensitive_path_probe_summaries,
        parse_flexible_iso_dt_fn=parse_flexible_iso_dt,
    )


def get_sensitive_path_probe_context_for_row(
    row: Dict[str, Any],
    sensitive_path_probe_contexts: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not sensitive_path_probe_contexts:
        return None

    sensitive_hints = build_sensitive_path_reason_hints_for_row(row)
    if not sensitive_hints:
        return None

    src_ip = get_src_ip(row)
    row_dt = parse_flexible_iso_dt(choose_best_time(row) or "")
    if not src_ip or row_dt is None:
        return None

    for context in sensitive_path_probe_contexts:
        if context["src_ip"] != src_ip:
            continue
        if context["start_dt"] <= row_dt <= context["end_dt"]:
            return context
    return None


def map_mixed_static_path_category(asset_category: str) -> str:
    category = normalize_text(asset_category)
    if category in {"javascript_asset", "css_asset", "image_asset", "static_asset"}:
        return "static_asset"
    return category


def map_mixed_crawler_path_category(path_category: str) -> str:
    category = normalize_text(path_category)
    mapping = {
        "robots_txt": "crawler_robots_txt",
        "sitemap_xml": "crawler_sitemap",
        "product_browse": "crawler_product_browse",
        "category_browse": "crawler_category_browse",
        "browse_like": "crawler_browse_like",
        "normal_get": "crawler_normal_get",
    }
    return mapping.get(category, "")


def map_mixed_sensitive_path_category(path_category: str) -> str:
    category = normalize_text(path_category)
    mapping = {
        "wp_login": "sensitive_wp_login",
        "wp_admin": "sensitive_wp_admin",
        "env_file": "sensitive_env_file",
        "phpinfo": "sensitive_phpinfo",
        "server_status": "sensitive_server_status",
        "backup_artifact": "sensitive_backup_artifact",
        "config_php": "sensitive_config_php",
        "admin_config_php": "sensitive_admin_config_php",
        "backup_directory": "sensitive_backup_directory",
        "admin_directory": "sensitive_admin_directory",
    }
    return mapping.get(category, "")


def build_mixed_baseline_scanner_row_context(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return _build_mixed_baseline_scanner_row_context(
        row,
        extract_raw_request_target=extract_raw_request_target,
        raw_text=raw_text,
        get_effective_request_path=get_effective_request_path,
        get_uri=get_uri,
        get_method=get_method,
        get_user_agent=get_user_agent,
        classify_static_baseline_asset_category=classify_static_baseline_asset_category,
        classify_crawler_baseline_path_category=classify_crawler_baseline_path_category,
        classify_crawler_like_user_agent_family=classify_crawler_like_user_agent_family,
        classify_sensitive_path_probe_category=classify_sensitive_path_probe_category,
        map_mixed_static_path_category=map_mixed_static_path_category,
        map_mixed_crawler_path_category=map_mixed_crawler_path_category,
        map_mixed_sensitive_path_category=map_mixed_sensitive_path_category,
        append_unique_hint=append_unique_hint,
        get_src_ip=get_src_ip,
        choose_best_time=choose_best_time,
        parse_flexible_iso_dt=parse_flexible_iso_dt,
        get_status_code=get_status_code,
        get_sample_request_id=get_sample_request_id,
    )


def finalize_mixed_baseline_scanner_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
) -> Optional[Dict[str, Any]]:
    return _finalize_mixed_baseline_scanner_bucket(
        items,
        window_sec=window_sec,
        min_request_count=MIXED_BASELINE_SCANNER_MIN_REQUEST_COUNT,
        sample_request_limit=MIXED_BASELINE_SCANNER_SAMPLE_REQUEST_LIMIT,
        safe_int=safe_int,
        extend_unique_hints=extend_unique_hints,
        normalize_text=normalize_text,
        append_unique_hint=append_unique_hint,
    )


def build_mixed_baseline_scanner_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = MIXED_BASELINE_SCANNER_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    return _build_mixed_baseline_scanner_summaries(
        rows,
        window_sec=window_sec,
        get_src_ip=get_src_ip,
        build_mixed_baseline_scanner_row_context=build_mixed_baseline_scanner_row_context,
        finalize_mixed_baseline_scanner_bucket=finalize_mixed_baseline_scanner_bucket,
        safe_int=safe_int,
        normalize_text=normalize_text,
    )


def parse_iso_dt(text: str) -> Optional[datetime]:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def choose_best_time(row: Dict[str, Any]) -> Optional[str]:
    return normalize_text(row.get("log_time")) or normalize_text(row.get("created_at")) or None


def normalize_identifier(value: Optional[Any]) -> str:
    normalized = normalize_text(value)
    if normalized in {"", "-", "none", "null", "n/a", "na"}:
        return ""
    return normalized


def parse_flexible_iso_dt(text: str) -> Optional[datetime]:
    raw = normalize_text(text)
    if not raw:
        return None
    candidates = [raw]
    if raw.endswith(" 09:00") or raw.endswith(" 00:00"):
        candidates.append(raw[:-6] + "+" + raw[-5:])
    if " " in raw and raw.count(":") >= 3 and "+" not in raw and raw[-6:-5] == " ":
        candidates.append(raw[:-6] + "+" + raw[-5:])
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def format_time_bucket(text: Optional[str]) -> str:
    dt = parse_flexible_iso_dt(text or "")
    if dt is not None:
        return dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    raw = normalize_text(text)
    return raw[:19] if raw else "unknown-time"


def stable_hash(parts: List[str]) -> str:
    joined = "||".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def merge_reason_hints(items: List[Candidate]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for item in items:
        for hint in item.reason_hints:
            if hint not in seen:
                seen.add(hint)
                merged.append(hint)
    return merged


def sort_source_tables(items: List[Candidate]) -> List[str]:
    unique = {item.source_table for item in items if item.source_table}
    return [name for name in SOURCE_ORDER if name in unique] + sorted(unique - set(SOURCE_ORDER))


def build_incident_group_key(candidate: Candidate) -> str:
    request_id = normalize_identifier(candidate.request_id)
    if request_id:
        return f"rid:{request_id}"

    error_link_id = normalize_identifier(candidate.error_link_id)
    if error_link_id:
        return f"eid:{error_link_id}"

    fingerprint_parts = [
        normalize_text(candidate.src_ip),
        normalize_text(candidate.method),
        normalize_text(candidate.uri),
        normalize_text(candidate.query_string),
        normalize_text(candidate.raw_request),
        str(candidate.status_code),
        normalize_text(candidate.verdict_hint),
        format_time_bucket(candidate.log_time),
    ]
    return "fp:" + stable_hash(fingerprint_parts)


def choose_representative_candidate(items: List[Candidate]) -> Candidate:
    return sorted(
        items,
        key=lambda item: (
            SOURCE_PRIORITY.get(item.source_table, 0),
            1 if normalize_identifier(item.request_id) else 0,
            1 if normalize_identifier(item.error_link_id) else 0,
            item.score,
            item.duration_us,
            item.ttfb_us,
            normalize_text(item.log_time),
        ),
        reverse=True,
    )[0]


def deduplicate_candidates(candidates: List[Candidate]) -> Tuple[List[Candidate], List[Dict[str, Any]]]:
    grouped: Dict[str, List[Candidate]] = defaultdict(list)
    for candidate in candidates:
        incident_key = build_incident_group_key(candidate)
        candidate.incident_group_key = incident_key
        grouped[incident_key].append(candidate)

    deduped: List[Candidate] = []
    summaries: List[Dict[str, Any]] = []

    for incident_key, items in grouped.items():
        representative = choose_representative_candidate(items)
        representative.incident_group_key = incident_key
        representative.merged_row_count = len(items)
        representative.merged_source_tables = sort_source_tables(items)
        representative.merged_log_ids = sorted({item.log_id for item in items if item.log_id is not None})
        representative.reason_hints = merge_reason_hints(items)

        if not normalize_identifier(representative.request_id):
            for item in items:
                value = normalize_identifier(item.request_id)
                if value:
                    representative.request_id = value
                    break

        if not normalize_identifier(representative.error_link_id):
            for item in items:
                value = normalize_identifier(item.error_link_id)
                if value:
                    representative.error_link_id = value
                    break

        representative.score = max(item.score for item in items)
        deduped.append(representative)
        summaries.append({
            "incident_group_key": incident_key,
            "merged_row_count": len(items),
            "source_tables": representative.merged_source_tables,
            "src_ip": representative.src_ip,
            "method": representative.method,
            "uri": representative.uri,
            "status_code": representative.status_code,
            "verdict_hint": representative.verdict_hint,
            "request_id": normalize_identifier(representative.request_id) or "-",
            "error_link_id": normalize_identifier(representative.error_link_id) or "-",
            "log_time": representative.log_time,
        })

    deduped.sort(key=lambda item: (item.score, normalize_text(item.log_time)), reverse=True)
    summaries.sort(key=lambda item: (item["merged_row_count"], normalize_text(item["log_time"])), reverse=True)
    return deduped, summaries


def parse_source_tables_arg(raw: str) -> List[str]:
    values = [normalize_text(x).lower() for x in (raw or "").split(",")]
    selected: List[str] = []
    for value in values:
        if not value:
            continue
        if value not in SOURCE_ORDER:
            raise ValueError(f"지원하지 않는 source table 입니다: {value}")
        if value not in selected:
            selected.append(value)
    if not selected:
        raise ValueError("최소 1개 이상의 source table 을 지정해야 합니다.")
    return selected


def get_user_agent(row: Dict[str, Any]) -> str:
    return (
        normalize_text(row.get("user_agent"))
        or normalize_text(row.get("ua"))
        or normalize_text(row.get("request_user_agent"))
    )


def get_referer(row: Dict[str, Any]) -> str:
    return normalize_text(row.get("referer")) or normalize_text(row.get("request_referer"))


def get_uri(row: Dict[str, Any]) -> str:
    return normalize_text(row.get("uri")) or normalize_text(row.get("request_uri"))


def get_src_ip(row: Dict[str, Any]) -> str:
    return normalize_text(row.get("src_ip")) or normalize_text(row.get("client_ip")) or "-"


def get_status_code(row: Dict[str, Any]) -> int:
    return safe_int(row.get("status_code") or row.get("status") or row.get("response_status"), 0)


def get_response_body_bytes(row: Dict[str, Any]) -> int:
    return safe_int(row.get("response_body_bytes") or row.get("body_bytes") or row.get("bytes"), 0)


def get_resp_content_type(row: Dict[str, Any]) -> str:
    return normalize_text(row.get("resp_content_type") or row.get("response_content_type") or row.get("content_type"))


def extract_raw_request_target(raw_request: str) -> str:
    raw = "" if raw_request is None else str(raw_request).strip()
    if not raw:
        return ""

    first_space = raw.find(" ")
    if first_space == -1:
        return ""

    http_marker = raw.rfind(" HTTP/")
    if http_marker == -1:
        target = raw[first_space + 1 :]
    else:
        target = raw[first_space + 1 : http_marker]

    return target.strip()


def path_from_target(target: str) -> str:
    value = normalize_text(target)
    if not value:
        return ""
    return value.split("?", 1)[0]


def get_effective_request_path(uri: str, raw_request_target: str) -> str:
    normalized_raw_path = path_from_target(raw_request_target)
    return normalized_raw_path or normalize_text(uri)


def normalize_content_type_bucket(content_type: str) -> str:
    value = normalize_text(content_type).lower()
    if not value:
        return ""
    return value.split(";", 1)[0].strip()


def get_probe_sequence_path(uri: str, raw_request_target: str) -> str:
    return get_effective_request_path(uri, raw_request_target).lower()


def get_probe_sequence_reason_hints(path: str) -> List[str]:
    normalized_path = normalize_text(path).lower()
    if not normalized_path:
        return []

    hints: List[str] = []
    append_unique_hint(hints, "dir_probe:burst")

    segments = [segment for segment in normalized_path.split("/") if segment]
    hidden_segment = any(segment.startswith(".") and segment != ".well-known" for segment in segments)
    sensitive_prefix = any(
        normalized_path == prefix or normalized_path.startswith(prefix + "/")
        for prefix in PROBING_SEQUENCE_PATH_PREFIX_HINTS
    )
    sensitive_suffix = any(normalized_path.endswith(suffix) for suffix in PROBING_SEQUENCE_SUFFIX_HINTS)
    sensitive_segment = any(segment in PROBING_SEQUENCE_PATH_SEGMENT_HINTS for segment in segments)
    if hidden_segment or sensitive_prefix or sensitive_suffix or sensitive_segment:
        append_unique_hint(hints, "dir_probe:sensitive_path")
    if normalized_path in {"/config.php", "/admin/config.php"}:
        append_unique_hint(hints, "dir_probe:sensitive_config_path")
    if normalized_path == "/config.php":
        append_unique_hint(hints, "file_probe:config_php")
    if normalized_path == "/admin/config.php":
        append_unique_hint(hints, "file_probe:admin_config_php")

    admin_prefix = (
        "/admin",
        "/administrator",
        "/manager",
        "/manager/html",
        "/server-status",
        "/server-info",
        "/phpmyadmin",
        "/wp-admin",
        "/wp-login.php",
        "/login",
        "/console",
    )
    if any(normalized_path == prefix or normalized_path.startswith(prefix + "/") for prefix in admin_prefix):
        append_unique_hint(hints, "dir_probe:admin_path")

    return hints


def is_likely_probe_sequence_path(path: str, query_string: str = "") -> bool:
    normalized_path = normalize_text(path).lower()
    if not normalized_path or normalized_path == "/":
        return False

    segments = [segment for segment in normalized_path.split("/") if segment]
    hidden_segment = any(segment.startswith(".") and segment != ".well-known" for segment in segments)
    prefix_hint = any(
        normalized_path == prefix or normalized_path.startswith(prefix + "/")
        for prefix in PROBING_SEQUENCE_PATH_PREFIX_HINTS
    )
    suffix_hint = any(normalized_path.endswith(suffix) for suffix in PROBING_SEQUENCE_SUFFIX_HINTS)
    segment_hint = any(segment in PROBING_SEQUENCE_PATH_SEGMENT_HINTS for segment in segments)
    if hidden_segment or prefix_hint or suffix_hint or segment_hint:
        return True

    query_lower = normalize_text(query_string).lower()
    if query_lower and any(token in query_lower for token in DIR_PROBE_FILE_HINTS):
        return True
    return False


def analyze_query_parameters(query_string: str) -> Tuple[bool, List[str]]:
    raw = "" if query_string is None else str(query_string).strip()
    if raw.startswith("?"):
        raw = raw[1:]
    if not raw:
        return False, []

    counts: Dict[str, int] = defaultdict(int)
    try:
        pairs = parse_qsl(raw, keep_blank_values=True)
    except Exception:
        pairs = []

    for key, _ in pairs:
        key_norm = normalize_text(key)
        if key_norm:
            counts[key_norm] += 1

    duplicate_names = sorted([name for name, count in counts.items() if count >= 2])
    return bool(duplicate_names), duplicate_names


def extract_query_pairs(query_string: str, raw_request_target: str = "") -> List[Tuple[str, str]]:
    raw_candidates = [raw_text(query_string)]
    raw_target = raw_text(raw_request_target)
    if "?" in raw_target:
        raw_candidates.append(raw_target.split("?", 1)[1])

    pairs: List[Tuple[str, str]] = []
    seen = set()
    for raw in raw_candidates:
        text = raw[1:] if raw.startswith("?") else raw
        if not text:
            continue
        try:
            parsed_pairs = parse_qsl(text, keep_blank_values=True)
        except Exception:
            continue
        for key, value in parsed_pairs:
            key_norm = normalize_text(key).lower()
            value_norm = normalize_text(value)
            if not key_norm:
                continue
            dedup_key = (key_norm, value_norm)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            pairs.append((key_norm, value_norm))
    return pairs


def get_search_param_values(query_string: str, raw_request_target: str = "") -> List[str]:
    return [
        value
        for key, value in extract_query_pairs(query_string, raw_request_target=raw_request_target)
        if key in SEARCH_PARAM_NAMES and value
    ]


def is_plain_search_value(value: str) -> bool:
    text = raw_text(value)
    if not text:
        return False
    if len(text) > 64:
        return False
    if not NORMAL_SEARCH_VALUE_RE.fullmatch(text):
        return False
    return bool(re.search(r"[A-Za-z0-9]", text))


def has_strong_attack_hints(reason_hints: Iterable[str], analysis_texts: Iterable[str]) -> bool:
    normalized_hints = [raw_text(hint) for hint in reason_hints if raw_text(hint)]
    if any(hint.startswith(STRONG_ATTACK_HINT_PREFIXES) for hint in normalized_hints):
        return True
    if any(hint in STRONG_ATTACK_HINTS for hint in normalized_hints):
        return True

    samples = unique_non_empty_texts(analysis_texts)
    if not samples:
        return False
    if has_xss_attack_structure(samples):
        return True

    for sample in samples:
        if get_matching_pattern_names(SQLI_PATTERNS, sample):
            return True
        if get_matching_pattern_names(TRAVERSAL_PATTERNS, sample):
            return True
        if get_matching_pattern_names(CMDI_PATTERNS, sample):
            return True
        if NORMAL_SEARCH_ATTACK_TEXT_RE.search(sample):
            return True
    return False


def is_likely_normal_search_baseline(
    row: Dict[str, Any],
    analysis_texts: Iterable[str],
    reason_hints: Iterable[str],
) -> bool:
    method = get_method(row)
    if method not in {"GET", "HEAD"}:
        return False
    if normalize_text(row.get("error_link_id")):
        return False

    status_code = get_status_code(row)
    if status_code not in {200, 204, 304, 404}:
        return False

    raw_request_target = raw_text(row.get("raw_request_target"))
    if not raw_request_target:
        raw_request_target = extract_raw_request_target(raw_text(row.get("raw_request")))

    search_values = get_search_param_values(
        raw_text(row.get("query_string")),
        raw_request_target=raw_request_target,
    )
    if not search_values:
        return False
    if not all(is_plain_search_value(value) for value in search_values):
        return False
    if has_strong_attack_hints(reason_hints, analysis_texts):
        return False
    return True


def sanitize_filtered_reason_hints(
    row: Dict[str, Any],
    reason_hints: Iterable[str],
    analysis_texts: Iterable[str],
    crawler_baseline_contexts: Optional[List[Dict[str, Any]]] = None,
    method_behavior_contexts: Optional[List[Dict[str, Any]]] = None,
    protocol_anomaly_contexts: Optional[List[Dict[str, Any]]] = None,
    static_baseline_contexts: Optional[List[Dict[str, Any]]] = None,
    sensitive_path_probe_contexts: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    sanitized = [raw_text(hint) for hint in reason_hints if raw_text(hint)]

    noise_category = normalize_text(row.get("_noise_category"))
    if (
        noise_category == "benign_normal_search"
        and is_likely_normal_search_baseline(
            row,
            analysis_texts=analysis_texts,
            reason_hints=sanitized,
        )
    ):
        return [hint for hint in sanitized if not hint.startswith("dir_probe:")]

    raw_request_target = extract_raw_request_target(raw_text(row.get("raw_request")))
    if is_auth_endpoint_request(
        get_method(row),
        get_uri(row),
        raw_request_target=raw_request_target,
    ):
        return [hint for hint in sanitized if not hint.startswith("dir_probe:")]

    crawler_context = get_crawler_baseline_context_for_row(row, crawler_baseline_contexts or [])
    if crawler_context is not None:
        crawler_hints = build_crawler_baseline_reason_hints_for_row(
            row,
            repeated_sequence="crawler_like:repeated_crawl_sequence" in (crawler_context.get("summary", {}).get("reason_hints") or []),
        )
        if crawler_hints:
            preserved_hints = [
                hint
                for hint in sanitized
                if not hint.startswith("dir_probe:") and not hint.startswith("baseline:") and not hint.startswith("crawler_like:")
            ]
            return unique_non_empty_texts(crawler_hints + preserved_hints)

    if row_is_covered_by_protocol_anomaly_context(row, protocol_anomaly_contexts or []):
        protocol_hints = build_protocol_anomaly_reason_hints_for_row(row, include_inference_limit=False)
        if protocol_hints:
            preserved_hints = [
                hint
                for hint in sanitized
                if not hint.startswith("dir_probe:") and not hint.startswith("baseline:")
            ]
            return unique_non_empty_texts(protocol_hints + preserved_hints)

    if row_is_covered_by_method_behavior_context(row, method_behavior_contexts or []):
        method_hints = build_method_behavior_reason_hints_for_row(row, include_inference_limit=False)
        if method_hints:
            preserved_hints = [hint for hint in sanitized if not hint.startswith("dir_probe:")]
            return unique_non_empty_texts(method_hints + preserved_hints)

    if row_is_covered_by_static_baseline_context(row, static_baseline_contexts or []):
        static_hints = build_static_baseline_reason_hints_for_row(row)
        if static_hints:
            preserved_hints = [
                hint
                for hint in sanitized
                if not hint.startswith("dir_probe:") and not hint.startswith("baseline:")
            ]
            return unique_non_empty_texts(static_hints + preserved_hints)

    sensitive_context = get_sensitive_path_probe_context_for_row(row, sensitive_path_probe_contexts or [])
    if sensitive_context is not None:
        sensitive_hints = build_sensitive_path_reason_hints_for_row(
            row,
            repeated_sequence="sensitive_path:repeated_sensitive_path_sequence"
            in (sensitive_context.get("summary", {}).get("reason_hints") or []),
        )
        if sensitive_hints:
            preserved_hints = [
                hint
                for hint in sanitized
                if not hint.startswith("dir_probe:") and not hint.startswith("sensitive_path:")
            ]
            return unique_non_empty_texts(sensitive_hints + preserved_hints)

    return sanitized


def get_method(row: Dict[str, Any]) -> str:
    return normalize_text(row.get("method")) or "-"


def is_benign_fallback_html(
    traversal_hits: int,
    sqli_hits: int,
    xss_hits: int,
    cmdi_hits: int,
    likely_html_fallback_response: bool,
    error_link_id: str,
) -> bool:
    if not likely_html_fallback_response:
        return False
    if traversal_hits != 1:
        return False
    if sqli_hits > 0 or xss_hits > 0 or cmdi_hits > 0:
        return False
    if error_link_id:
        return False
    return True


def is_benign_normal_search(
    uri: str,
    query_string: str,
    method: str,
    status_code: int,
    user_agent: str,
    referer: str,
    error_link_id: str,
    sqli_hits: int,
    xss_hits: int,
    traversal_hits: int,
    cmdi_hits: int,
) -> bool:
    if sqli_hits > 0 or xss_hits > 0 or traversal_hits > 0 or cmdi_hits > 0:
        return False
    if error_link_id:
        return False
    if method not in {"GET", "HEAD"}:
        return False
    if status_code not in {200, 204, 304, 404}:
        return False
    if not looks_like_browser_ua(user_agent):
        return False
    if contains_query_heavy_uri(uri) and query_string:
        return True
    if query_string and status_code in {200, 304}:
        return True
    if query_string and referer:
        return True
    return False


def is_likely_dir_probe(
    uri: str,
    raw_request_target: str,
    query_string: str,
    method: str,
    status_code: int,
    referer: str,
    user_agent: str,
    sqli_hits: int,
    xss_hits: int,
    cmdi_hits: int,
    traversal_hits: int,
    path_normalized_from_raw_request: bool,
    likely_html_fallback_response: bool,
) -> bool:
    if method not in {"GET", "HEAD", "OPTIONS"}:
        return False
    if sqli_hits > 0 or xss_hits > 0 or cmdi_hits > 0:
        return False
    if contains_query_heavy_uri(uri):
        return False
    if query_string and len(query_string) >= 20:
        return False

    probe_path = get_effective_request_path(uri, raw_request_target).lower()
    if not probe_path or probe_path == "/":
        return False

    segments = [segment for segment in probe_path.split("/") if segment]
    hidden_segment = any(segment.startswith(".") and segment != ".well-known" for segment in segments)
    path_hint = any(hint in probe_path for hint in DIR_PROBE_PATH_HINTS)
    file_hint = any(hint in probe_path for hint in DIR_PROBE_FILE_HINTS)
    low_signal_traversal = traversal_hits == 1 and (
        status_code in {401, 403, 404, 405}
        or path_normalized_from_raw_request
        or likely_html_fallback_response
    )

    if not (hidden_segment or path_hint or file_hint or low_signal_traversal):
        return False

    if status_code in {301, 302, 401, 403, 404, 405}:
        return True
    if likely_html_fallback_response:
        return True
    if status_code == 200 and not looks_like_browser_ua(user_agent) and not referer:
        return True
    return False


def is_low_signal_fuzzing(
    uri: str,
    query_string: str,
    method: str,
    status_code: int,
    user_agent: str,
    referer: str,
    error_link_id: str,
    sqli_hits: int,
    xss_hits: int,
    traversal_hits: int,
    cmdi_hits: int,
    hpp_detected: bool,
) -> bool:
    if error_link_id:
        return False
    if contains_query_heavy_uri(uri) and looks_like_browser_ua(user_agent) and sqli_hits == 0 and xss_hits == 0 and traversal_hits == 0 and cmdi_hits == 0:
        return False

    signals = 0
    if sqli_hits > 0 or xss_hits > 0 or cmdi_hits > 0:
        signals += 2
    elif traversal_hits > 0:
        signals += 1

    if query_string and len(query_string) >= 20:
        signals += 1
    if query_string and special_char_ratio(query_string) >= 0.15:
        signals += 1
    if hpp_detected:
        signals += 1
    if not looks_like_browser_ua(user_agent):
        signals += 1
    if not referer and status_code >= 400:
        signals += 1
    if method not in {"GET", "POST", "HEAD", "OPTIONS"}:
        signals += 1

    return signals >= 2


def classify_filtered_noise_category(
    row: Dict[str, Any],
    uri: str,
    query_string: str,
    method: str,
    status_code: int,
    user_agent: str,
    referer: str,
    error_link_id: str,
    raw_request_target: str,
    path_normalized_from_raw_request: bool,
    likely_html_fallback_response: bool,
    sqli_hits: int,
    xss_hits: int,
    traversal_hits: int,
    cmdi_hits: int,
    hpp_detected: bool,
    analysis_texts: Iterable[str],
    reason_hints: Iterable[str],
) -> str:
    if is_benign_fallback_html(
        traversal_hits=traversal_hits,
        sqli_hits=sqli_hits,
        xss_hits=xss_hits,
        cmdi_hits=cmdi_hits,
        likely_html_fallback_response=likely_html_fallback_response,
        error_link_id=error_link_id,
    ):
        return "benign_fallback_html"

    if is_likely_normal_search_baseline(
        row,
        analysis_texts=analysis_texts,
        reason_hints=reason_hints,
    ):
        return "benign_normal_search"

    if (
        is_auth_endpoint_request(method, uri, raw_request_target=raw_request_target)
        and sqli_hits == 0
        and xss_hits == 0
        and traversal_hits == 0
        and cmdi_hits == 0
        and not hpp_detected
    ):
        if 200 <= status_code < 300:
            return "auth_baseline_context"
        if 400 <= status_code < 500:
            return "auth_endpoint_context"

    if is_likely_dir_probe(
        uri=uri,
        raw_request_target=raw_request_target,
        query_string=query_string,
        method=method,
        status_code=status_code,
        referer=referer,
        user_agent=user_agent,
        sqli_hits=sqli_hits,
        xss_hits=xss_hits,
        cmdi_hits=cmdi_hits,
        traversal_hits=traversal_hits,
        path_normalized_from_raw_request=path_normalized_from_raw_request,
        likely_html_fallback_response=likely_html_fallback_response,
    ):
        return "low_signal_dir_probe"

    if is_benign_normal_search(
        uri=uri,
        query_string=query_string,
        method=method,
        status_code=status_code,
        user_agent=user_agent,
        referer=referer,
        error_link_id=error_link_id,
        sqli_hits=sqli_hits,
        xss_hits=xss_hits,
        traversal_hits=traversal_hits,
        cmdi_hits=cmdi_hits,
    ):
        return "benign_normal_search"

    if is_low_signal_fuzzing(
        uri=uri,
        query_string=query_string,
        method=method,
        status_code=status_code,
        user_agent=user_agent,
        referer=referer,
        error_link_id=error_link_id,
        sqli_hits=sqli_hits,
        xss_hits=xss_hits,
        traversal_hits=traversal_hits,
        cmdi_hits=cmdi_hits,
        hpp_detected=hpp_detected,
    ):
        return "low_signal_fuzzing"

    if looks_like_browser_ua(user_agent):
        return "benign_normal_search"
    return "low_signal_fuzzing"


def build_filtered_row_payload(
    row: Dict[str, Any],
    crawler_baseline_contexts: Optional[List[Dict[str, Any]]] = None,
    method_behavior_contexts: Optional[List[Dict[str, Any]]] = None,
    protocol_anomaly_contexts: Optional[List[Dict[str, Any]]] = None,
    static_baseline_contexts: Optional[List[Dict[str, Any]]] = None,
    sensitive_path_probe_contexts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    raw_req_original = "" if row.get("raw_request") is None else str(row.get("raw_request")).strip()
    uri = get_uri(row)
    qs = normalize_text(row.get("query_string"))
    raw_request_target = extract_raw_request_target(raw_req_original)
    probe_path = get_effective_request_path(uri, raw_request_target).lower()
    normalized_raw_path = path_from_target(raw_request_target)
    normalized_uri = normalize_text(uri)
    response_body_bytes = get_response_body_bytes(row)
    resp_content_type = get_resp_content_type(row)
    status_code = get_status_code(row)
    hpp_detected, hpp_param_names = analyze_query_parameters(qs)

    _, combined_target, _, _ = build_analysis_texts(
        raw_request=raw_req_original,
        uri=normalized_uri,
        query_string=raw_text(row.get("query_string")),
        raw_request_target=raw_request_target,
        raw_log=raw_text(row.get("raw_log")),
    )

    traversal_hits = 0
    for _, pattern, _ in TRAVERSAL_PATTERNS:
        if pattern.search(combined_target):
            traversal_hits += 1

    path_normalized_from_raw_request = False
    likely_html_fallback_response = False
    if traversal_hits > 0:
        if normalized_raw_path and normalized_uri and normalized_raw_path != normalized_uri:
            path_normalized_from_raw_request = True
        resp_ct_lower = resp_content_type.lower()
        if status_code == 200 and resp_ct_lower.startswith("text/html") and response_body_bytes >= 10000:
            likely_html_fallback_response = True

    analysis_texts = unique_non_empty_texts([raw_text(row.get("query_string")), raw_request_target])
    reason_hints = sanitize_filtered_reason_hints(
        row,
        get_probe_sequence_reason_hints(probe_path),
        analysis_texts=analysis_texts,
        crawler_baseline_contexts=crawler_baseline_contexts,
        method_behavior_contexts=method_behavior_contexts,
        protocol_anomaly_contexts=protocol_anomaly_contexts,
        static_baseline_contexts=static_baseline_contexts,
        sensitive_path_probe_contexts=sensitive_path_probe_contexts,
    )

    return {
        "source_table": normalize_text(row.get("_source_table")),
        "noise_category": normalize_text(row.get("_noise_category")) or "low_signal_fuzzing",
        "log_time": choose_best_time(row),
        "src_ip": get_src_ip(row),
        "method": get_method(row),
        "uri": uri,
        "query_string": qs,
        "status_code": status_code,
        "request_id": normalize_text(row.get("request_id")),
        "error_link_id": normalize_text(row.get("error_link_id")),
        "user_agent": get_user_agent(row),
        "raw_request": normalize_text(row.get("raw_request")),
        "response_body_bytes": response_body_bytes,
        "resp_content_type": resp_content_type,
        "raw_request_target": raw_request_target,
        "path_normalized_from_raw_request": path_normalized_from_raw_request,
        "likely_html_fallback_response": likely_html_fallback_response,
        "hpp_detected": hpp_detected,
        "hpp_param_names": hpp_param_names,
        "reason_hints": reason_hints,
    }


# ----------------------------
# 규칙 기반 후보 평가
# ----------------------------
def evaluate_row(row: Dict[str, Any], source_table: str, min_score: int) -> Tuple[Optional[Candidate], Optional[str]]:
    uri = get_uri(row)
    raw_req_original = "" if row.get("raw_request") is None else str(row.get("raw_request")).strip()
    raw_req = normalize_text(row.get("raw_request"))
    qs = normalize_text(row.get("query_string"))
    raw_qs = raw_text(row.get("query_string"))
    raw_log = normalize_text(row.get("raw_log"))
    src_ip = get_src_ip(row)
    method = get_method(row)
    status_code = get_status_code(row)
    user_agent = get_user_agent(row)
    referer = get_referer(row)
    duration_us = safe_int(row.get("duration_us"))
    ttfb_us = safe_int(row.get("ttfb_us"))
    request_id = normalize_text(row.get("request_id"))
    error_link_id = normalize_text(row.get("error_link_id"))
    req_ct = normalize_text(row.get("req_content_type"))
    response_body_bytes = get_response_body_bytes(row)
    resp_content_type = get_resp_content_type(row)
    raw_request_target = extract_raw_request_target(raw_req_original)
    normalized_raw_path = path_from_target(raw_request_target)
    probe_path = get_effective_request_path(uri, raw_request_target).lower()
    hpp_detected, hpp_param_names = analyze_query_parameters(qs)
    log_time = choose_best_time(row)

    base_combined_target, combined_target, query_variants, raw_request_target_variants = build_analysis_texts(
        raw_request=raw_req_original,
        uri=uri,
        query_string=raw_qs,
        raw_request_target=raw_request_target,
        raw_log=raw_text(row.get("raw_log")),
    )
    analysis_texts = unique_non_empty_texts(
        [raw_qs, qs, raw_request_target, base_combined_target, combined_target]
        + [raw_text(item.get("text")) for item in query_variants + raw_request_target_variants]
    )

    # 1) 정상 잡음 완전 제외 / 집계 대상 판별
    if source_table in {"access", "security"} and is_normal_socketio_polling(uri, raw_req, qs, status_code, error_link_id, user_agent):
        return None, "socketio_polling"

    if source_table == "access" and is_static_resource(uri) and status_code == 200:
        return None, "static_asset"

    # 2) 의심 점수 계산
    score = 0
    reason_hints: List[str] = []
    sqli_hits = 0
    xss_hits = 0
    traversal_hits = 0
    cmdi_hits = 0
    automation_ua_hits = 0
    log4shell_score_boost = 0
    ssrf_score_boost = 0
    ssti_score_boost = 0
    webshell_score_boost = 0

    for name, pattern, points in SQLI_PATTERNS:
        if matches_sqli_pattern(name, pattern, combined_target):
            score += points
            sqli_hits += 1
            reason_hints.append(f"sqli:{name}(+{points})")

    for name, pattern, points in XSS_PATTERNS:
        if pattern.search(combined_target):
            score += points
            xss_hits += 1
            reason_hints.append(f"xss:{name}(+{points})")

    for name, pattern, points in TRAVERSAL_PATTERNS:
        if pattern.search(combined_target):
            score += points
            traversal_hits += 1
            reason_hints.append(f"traversal:{name}(+{points})")

    for name, pattern, points in CMDI_PATTERNS:
        if pattern.search(combined_target):
            score += points
            cmdi_hits += 1
            reason_hints.append(f"cmdi:{name}(+{points})")

    for name, pattern, points in AUTOMATION_UA_PATTERNS:
        if pattern.search(user_agent):
            score += points
            automation_ua_hits += 1
            reason_hints.append(f"ua:{name}(+{points})")

    decoded_score_boost, decoded_hints = detect_decoded_attack_hints(
        base_text=base_combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    if decoded_score_boost > 0:
        score += decoded_score_boost
    reason_hints.extend(decoded_hints)
    file_disclosure_score_boost, file_disclosure_hints = detect_file_disclosure_hints(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    if file_disclosure_score_boost > 0:
        score += file_disclosure_score_boost
    extend_unique_hints(reason_hints, file_disclosure_hints)
    log4shell_score_boost, log4shell_hints = detect_log4shell_hints(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    if log4shell_score_boost > 0:
        score += log4shell_score_boost
    extend_unique_hints(reason_hints, log4shell_hints)
    ssrf_score_boost, ssrf_hints = detect_ssrf_hints(
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    if ssrf_score_boost > 0:
        score += ssrf_score_boost
    extend_unique_hints(reason_hints, ssrf_hints)
    ssti_score_boost, ssti_hints = detect_ssti_hints(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    if ssti_score_boost > 0:
        score += ssti_score_boost
    extend_unique_hints(reason_hints, ssti_hints)
    webshell_score_boost, webshell_hints = detect_webshell_hints(
        uri=uri,
        raw_request_target=raw_request_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    if webshell_score_boost > 0:
        score += webshell_score_boost
    extend_unique_hints(reason_hints, webshell_hints)
    extend_unique_hints(
        reason_hints,
        get_xss_context_hints(
            raw_query_string=raw_qs,
            query_string=qs,
            raw_request_target=raw_request_target,
            combined_target=combined_target,
            query_variants=query_variants,
            raw_request_target_variants=raw_request_target_variants,
        ),
    )
    extend_unique_hints(reason_hints, build_sensitive_path_reason_hints_for_row(row))

    if hpp_detected:
        score += 1
        reason_hints.append("hpp:duplicate_param_names(+1)")
        if hpp_param_names:
            reason_hints.append("hpp:param_names=" + ",".join(hpp_param_names))

    qs_len = len(qs)
    if qs_len >= 40:
        score += 1
        reason_hints.append("long_query(+1)")
    if qs_len >= 80:
        score += 1
        reason_hints.append("very_long_query(+1)")

    ratio = special_char_ratio(qs)
    if ratio >= 0.15:
        score += 1
        reason_hints.append("special_char_ratio_high(+1)")
    if ratio >= 0.30:
        score += 1
        reason_hints.append("special_char_ratio_very_high(+1)")

    if status_code in {400, 401, 403, 404, 500, 502, 503}:
        score += 2
        reason_hints.append(f"error_status:{status_code}(+2)")

    if error_link_id:
        score += 2
        reason_hints.append("error_linked(+2)")

    if duration_us >= 2_000_000:
        score += 3
        reason_hints.append("high_duration(+3)")
    if duration_us >= 5_000_000:
        score += 2
        reason_hints.append("very_high_duration(+2)")
    if ttfb_us >= 2_000_000:
        score += 2
        reason_hints.append("high_ttfb(+2)")

    is_login_endpoint = contains_login_uri(uri)
    if is_login_endpoint:
        score += 1
        reason_hints.append("login_endpoint(+1)")

    if contains_query_heavy_uri(uri) and qs:
        if re.search(r"(?i)\b(select|union|sleep|benchmark|waitfor|or|and|script|javascript|alert)\b", qs):
            score += 2
            reason_hints.append("query_endpoint_with_attack_tokens(+2)")

    auth_payload_content_type = req_ct.lower() in {"application/json", "application/x-www-form-urlencoded"}
    if auth_payload_content_type and is_login_endpoint:
        score += 1
        reason_hints.append("auth_payload_content_type(+1)")

    if not referer and not looks_like_browser_ua(user_agent) and status_code >= 400:
        score += 1
        reason_hints.append("no_referer_non_browser_error(+1)")

    is_login_success_json_response = (
        is_login_endpoint
        and method == "POST"
        and status_code == 200
        and is_json_content_type(req_ct)
        and is_json_content_type(resp_content_type)
        and response_body_bytes >= 300
    )
    auth_success_attack_hint = has_auth_success_attack_hint(user_agent, raw_req, raw_log, qs)
    if is_login_success_json_response and auth_success_attack_hint:
        score += 2
        reason_hints.append("login_success_json_response(+2)")
        score += 1
        reason_hints.append("possible_auth_bypass_success(+1)")

    if (
        is_login_success_json_response
        and not referer
        and not looks_like_browser_ua(user_agent)
        and (auth_success_attack_hint or automation_ua_hits > 0)
    ):
        score += 1
        reason_hints.append("no_referer_non_browser_login(+1)")

    if source_table == "error":
        score += 2
        reason_hints.append("error_table_context(+2)")

    educational_sql_context = detect_educational_sql_search_context(qs)
    educational_xss_context = detect_educational_xss_search_context(" ".join(unique_non_empty_texts([qs, raw_request_target])))
    educational_ssti_context = detect_educational_ssti_search_context(" ".join(unique_non_empty_texts([qs, raw_request_target])))
    structure_flags = get_sqli_structure_flags(
        combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    if sqli_hits > 0:
        if structure_flags.get("quote_termination") and (
            structure_flags.get("boolean_true_condition")
            or structure_flags.get("comment_sequence")
            or structure_flags.get("xclose_pattern")
        ):
            append_unique_hint(reason_hints, "sqli:quote_termination")
        if structure_flags.get("parenthesis_termination") and (
            structure_flags.get("quote_termination")
            or structure_flags.get("boolean_true_condition")
            or structure_flags.get("comment_sequence")
            or structure_flags.get("xclose_pattern")
        ):
            append_unique_hint(reason_hints, "sqli:parenthesis_termination")
        if structure_flags.get("boolean_true_condition"):
            append_unique_hint(reason_hints, "sqli:boolean_true_condition")
        if structure_flags.get("comment_sequence"):
            append_unique_hint(reason_hints, "sqli:comment_sequence")
        if structure_flags.get("xclose_pattern"):
            append_unique_hint(reason_hints, "sqli:xclose_pattern")
    xss_structure_flags = get_xss_structure_flags(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    strong_sqli_structure = any(
        structure_flags.get(name, False)
        for name in (
            "quote_termination",
            "parenthesis_termination",
            "sql_comment",
            "comment_sequence",
            "xclose",
            "xclose_pattern",
            "boolean_condition",
            "boolean_true_condition",
            "union_column_list",
            "schema_access",
        )
    )
    strong_xss_structure = any(
        xss_structure_flags.get(name, False)
        for name in (
            "mixed_case_script_tag",
            "event_handler_assignment",
            "javascript_protocol",
            "browser_data_access",
            "external_navigation",
            "quote_breakout",
            "html_entity_decoded_script",
        )
    )
    weak_from_users_only = structure_flags.get("from_users", False) and not strong_sqli_structure
    if educational_sql_context and sqli_hits > 0:
        reason_hints.append("context:educational_sql_search")
        reason_hints.append("context:natural_language_query")
        if not structure_flags.get("quote_termination"):
            reason_hints.append("no_quote_termination")
        if not structure_flags.get("sql_comment"):
            reason_hints.append("no_sql_comment")
        if not structure_flags.get("boolean_true_condition"):
            reason_hints.append("no_boolean_condition")
        if not strong_sqli_structure:
            reason_hints.append("fp_hint:sql_keyword_without_attack_structure")
            if weak_from_users_only:
                score = max(0, score - 2)
            else:
                score = max(0, score - 4)
    if educational_xss_context and xss_hits > 0:
        reason_hints.append("context:educational_xss_search")
        reason_hints.append("context:natural_language_query")
        if not xss_structure_flags.get("event_handler_assignment"):
            reason_hints.append("no_event_handler_assignment")
        if not xss_structure_flags.get("javascript_protocol"):
            reason_hints.append("no_javascript_protocol")
        if not xss_structure_flags.get("browser_data_access"):
            reason_hints.append("no_browser_data_access")
        if not strong_xss_structure:
            reason_hints.append("fp_hint:xss_keyword_without_attack_structure")
            score = max(0, score - 4)
    if educational_ssti_context and ssti_score_boost > 0:
        reason_hints.append("context:educational_ssti_search")
        reason_hints.append("context:natural_language_query")
        reason_hints.append("fp_hint:ssti_keyword_without_runtime_evidence")
        score = max(0, score - 4)

    path_normalized_from_raw_request = False
    likely_html_fallback_response = False
    embedded_attack_hint = ""

    if hpp_detected:
        if sqli_hits > 0 and xss_hits > 0:
            embedded_attack_hint = "multiple"
            reason_hints.append("hpp:embedded_attack=multiple")
        elif sqli_hits > 0:
            embedded_attack_hint = "sqli"
            reason_hints.append("hpp:embedded_attack=sqli")
        elif xss_hits > 0:
            embedded_attack_hint = "xss"
            reason_hints.append("hpp:embedded_attack=xss")

    if traversal_hits > 0:
        normalized_uri = normalize_text(uri)
        if normalized_raw_path and normalized_uri and normalized_raw_path != normalized_uri:
            path_normalized_from_raw_request = True
            reason_hints.append("traversal:raw_request_uri_diff")

        resp_ct_lower = resp_content_type.lower()
        if status_code == 200 and resp_ct_lower.startswith("text/html") and response_body_bytes >= 10000:
            likely_html_fallback_response = True
            reason_hints.append("traversal:html_fallback_like_response")
        elif status_code == 200 and (resp_ct_lower.startswith("text/plain") or "octet-stream" in resp_ct_lower):
            reason_hints.append("traversal:file_like_response_type")

    filtered_noise_category = classify_filtered_noise_category(
        row=row,
        uri=uri,
        query_string=qs,
        method=method,
        status_code=status_code,
        user_agent=user_agent,
        referer=referer,
        error_link_id=error_link_id,
        raw_request_target=raw_request_target,
        path_normalized_from_raw_request=path_normalized_from_raw_request,
        likely_html_fallback_response=likely_html_fallback_response,
        sqli_hits=sqli_hits,
        xss_hits=xss_hits,
        traversal_hits=traversal_hits,
        cmdi_hits=cmdi_hits,
        hpp_detected=hpp_detected,
        analysis_texts=analysis_texts,
        reason_hints=reason_hints,
    )
    direct_sensitive_config_probe = probe_path in {"/config.php", "/admin/config.php"}
    php_filter_wrapper_detected = "file_disclosure:php_filter_wrapper" in reason_hints

    if is_benign_fallback_html(
        traversal_hits=traversal_hits,
        sqli_hits=sqli_hits,
        xss_hits=xss_hits,
        cmdi_hits=cmdi_hits,
        likely_html_fallback_response=likely_html_fallback_response,
        error_link_id=error_link_id,
    ):
        return None, filtered_noise_category

    # 3) 최종 판정 힌트
    if educational_sql_context and sqli_hits > 0 and not strong_sqli_structure:
        if score >= min_score:
            verdict_hint = "possible_false_positive_sql_keyword_search"
        else:
            return None, filtered_noise_category
    elif educational_xss_context and xss_hits > 0 and not strong_xss_structure:
        if score >= min_score:
            verdict_hint = "possible_false_positive_xss_keyword_search"
        else:
            return None, filtered_noise_category
    elif xss_hits > 0 and score >= max(min_score, 7):
        verdict_hint = "xss"
    elif sqli_hits > 0 and score >= max(min_score, 7):
        verdict_hint = "sqli"
    elif traversal_hits > 0 and score >= max(min_score, 6):
        verdict_hint = "path_traversal"
    elif cmdi_hits > 0 and score >= max(min_score, 6):
        verdict_hint = "command_injection"
    elif php_filter_wrapper_detected and score >= max(min_score, 6):
        verdict_hint = "suspicious_file_disclosure"
    elif is_login_success_json_response and score >= min_score:
        verdict_hint = "suspicious_auth_success"
    elif score >= min_score:
        if direct_sensitive_config_probe and not php_filter_wrapper_detected:
            return None, filtered_noise_category
        verdict_hint = "suspicious"
    else:
        return None, filtered_noise_category

    candidate = Candidate(
        source_table=source_table,
        log_id=safe_int(row.get("id"), 0) or None,
        log_time=log_time,
        src_ip=src_ip,
        method=method,
        uri=uri or "-",
        query_string=qs,
        status_code=status_code,
        score=score,
        verdict_hint=verdict_hint,
        reason_hints=reason_hints,
        request_id=request_id,
        error_link_id=error_link_id,
        raw_request=raw_req,
        user_agent=user_agent,
        referer=referer,
        duration_us=duration_us,
        ttfb_us=ttfb_us,
        raw_log=raw_log,
        response_body_bytes=response_body_bytes,
        resp_content_type=resp_content_type,
        raw_request_target=raw_request_target,
        path_normalized_from_raw_request=path_normalized_from_raw_request,
        likely_html_fallback_response=likely_html_fallback_response,
        hpp_detected=hpp_detected,
        hpp_param_names=hpp_param_names,
        embedded_attack_hint=embedded_attack_hint,
    )
    return candidate, None


# ----------------------------
# 노이즈 판별/집계
# ----------------------------
def is_normal_socketio_polling(
    uri: str,
    raw_request: str,
    query_string: str,
    status_code: int,
    error_link_id: str,
    user_agent: str,
) -> bool:
    uri_lower = (uri or "").lower()
    raw_lower = (raw_request or "").lower()
    qs_lower = (query_string or "").lower()
    joined = " ".join([uri_lower, raw_lower, qs_lower])

    if not uri_lower.startswith("/socket.io/"):
        return False
    if status_code != 200:
        return False
    if error_link_id:
        return False
    if any(pattern.search(joined) for _, pattern, _ in SQLI_PATTERNS + XSS_PATTERNS + TRAVERSAL_PATTERNS + CMDI_PATTERNS):
        return False
    if "transport=polling" not in joined and "eio=" not in joined:
        return False
    if not looks_like_browser_ua(user_agent):
        return False
    return True


def aggregate_noise_rows(rows: List[Dict[str, Any]], min_repeat: int) -> Tuple[List[Dict[str, Any]], List[NoiseAggregate]]:
    grouped: Dict[Tuple[str, str, str, str, int, str], List[Dict[str, Any]]] = defaultdict(list)
    passthrough: List[Dict[str, Any]] = []

    for row in rows:
        category = normalize_text(row.get("_noise_category"))
        if not category:
            passthrough.append(row)
            continue
        key = (
            category,
            get_src_ip(row),
            get_uri(row),
            get_method(row),
            get_status_code(row),
            get_user_agent(row),
        )
        grouped[key].append(row)

    aggregates: List[NoiseAggregate] = []
    for (category, src_ip, uri, method, status_code, ua), items in grouped.items():
        if len(items) < min_repeat:
            passthrough.extend(items)
            continue

        times = [parse_iso_dt(choose_best_time(x) or "") for x in items]
        times = [t for t in times if t is not None]
        times.sort()
        note = {
            "socketio_polling": "정상 웹 UI 세션 유지로 보이는 반복 polling 요청",
            "static_asset": "정적 리소스 요청 반복",
            "benign_normal_search": "브라우저 기반 일반 검색/조회로 보이는 반복 요청",
            "auth_baseline_context": "인증 endpoint의 정상 또는 보수적 baseline 문맥으로 보이는 반복 요청",
            "auth_endpoint_context": "인증 endpoint의 실패/관찰 문맥으로 보이는 반복 요청",
            "benign_fallback_html": "경로 변형이 있었지만 기본 HTML fallback 으로 해석되는 반복 요청",
            "low_signal_fuzzing": "퍼징/입력 변형 흔적은 있으나 근거가 약한 저신호 반복 요청",
            "low_signal_dir_probe": "디렉터리/민감 경로 존재 확인 수준의 저신호 probe 반복",
        }.get(category, "반복 정상 요청 집계")
        aggregates.append(
            NoiseAggregate(
                category=category,
                src_ip=src_ip,
                uri=uri,
                method=method,
                status_code=status_code,
                count=len(items),
                start=times[0].isoformat(timespec="milliseconds") if times else None,
                end=times[-1].isoformat(timespec="milliseconds") if times else None,
                user_agent=ua,
                note=note,
            )
        )

    aggregates.sort(key=lambda x: (x.category, x.count, x.src_ip), reverse=True)
    return passthrough, aggregates


# ----------------------------
# 메인 파이프라인
# ----------------------------
def collect_rows(payload: Dict[str, Any], source_tables: List[str]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    data = payload.get("data", {})
    for table_name in source_tables:
        for row in data.get(table_name, []) or []:
            yield table_name, row


def build_outputs(payload: Dict[str, Any], min_score: int, min_repeat_aggregate: int, source_tables: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    original_meta = payload.get("meta", {})
    all_rows: List[Dict[str, Any]] = []
    filtered_out_rows: List[Dict[str, Any]] = []
    candidates: List[Candidate] = []

    for source_table, row in collect_rows(payload, source_tables=source_tables):
        working_row = dict(row)
        working_row["_source_table"] = source_table
        candidate, noise_category = evaluate_row(working_row, source_table, min_score=min_score)
        if noise_category:
            working_row["_noise_category"] = noise_category
            filtered_out_rows.append(working_row)
        elif candidate:
            candidates.append(candidate)
        else:
            filtered_out_rows.append(working_row)
        all_rows.append(working_row)

    non_aggregated_filtered, noise_aggregates = aggregate_noise_rows(filtered_out_rows, min_repeat=min_repeat_aggregate)

    noise_counter = Counter(normalize_text(r.get("_noise_category")) or "unclassified" for r in filtered_out_rows)

    auth_behavior_summaries = build_auth_behavior_summaries(all_rows)
    sensitive_path_probe_summaries = build_sensitive_path_probe_summaries(all_rows)
    original_candidate_count = len(candidates)
    reduced_candidates, auth_behavior_supporting_events = reduce_repeated_auth_candidates(
        candidates,
        auth_behavior_summaries=auth_behavior_summaries,
    )
    reduced_candidates, sensitive_path_probe_supporting_events = reduce_repeated_sensitive_path_candidates(
        reduced_candidates,
        sensitive_path_probe_summaries=sensitive_path_probe_summaries,
    )
    raw_candidate_count = len(reduced_candidates)
    deduped_candidates, candidate_group_summaries = deduplicate_candidates(reduced_candidates)
    supporting_events = build_supporting_events(filtered_out_rows, deduped_candidates, min_score=min_score)
    supporting_events.extend(auth_behavior_supporting_events)
    supporting_events.extend(sensitive_path_probe_supporting_events)
    supporting_events.sort(
        key=lambda item: (
            safe_int(item.get("nearby_candidate_count"), 0),
            normalize_text(item.get("log_time")),
        ),
        reverse=True,
    )
    probing_sequence_summaries = build_probing_sequence_summaries(all_rows)
    static_baseline_summaries = build_static_baseline_summaries(all_rows)
    crawler_baseline_summaries = build_crawler_baseline_summaries(all_rows)
    ip_behavior_aggregates = build_ip_behavior_aggregates(all_rows)
    method_behavior_summaries = build_method_behavior_summaries(all_rows)
    protocol_anomaly_summaries = build_protocol_anomaly_summaries(all_rows)
    mixed_baseline_scanner_summaries = build_mixed_baseline_scanner_summaries(all_rows)
    crawler_baseline_contexts = build_crawler_baseline_summary_contexts(crawler_baseline_summaries)
    method_behavior_contexts = build_method_behavior_summary_contexts(method_behavior_summaries)
    protocol_anomaly_contexts = build_protocol_anomaly_summary_contexts(protocol_anomaly_summaries)
    static_baseline_contexts = build_static_baseline_summary_contexts(static_baseline_summaries)
    sensitive_path_probe_contexts = build_sensitive_path_probe_summary_contexts(sensitive_path_probe_summaries)
    false_positive_review_candidates = [
        item
        for item in (
            build_false_positive_review_candidate(row)
            for row in non_aggregated_filtered
        )
        if item
    ]

    candidate_payload = [asdict(x) for x in deduped_candidates]
    noise_payload = [asdict(x) for x in noise_aggregates]

    llm_input = {
        "meta": {
            "query_timezone": original_meta.get("query_timezone", "Asia/Seoul"),
            "analysis_window": {
                "start": original_meta.get("start"),
                "end_exclusive": original_meta.get("end_exclusive"),
            },
            "source_database": original_meta.get("database"),
            "source_table_option": original_meta.get("table_option"),
            "selected_source_tables": source_tables,
            "analysis_primary_table": "security",
            "exported_at": original_meta.get("exported_at"),
            "prepared_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "model_usage_policy": {
                "routine": "gpt-5.4-mini",
                "milestone_or_presentation": "gpt-5.4",
            },
            "pipeline_policy": {
                "db_raw_preserved": True,
                "send_raw_full_export_to_llm": False,
                "noise_is_aggregated_before_llm": True,
                "candidate_selection_is_rule_based_first": True,
                "path_traversal_success_requires_body_validation": True,
                "hpp_context_is_preserved": True,
                "filtered_noise_breakdown_is_preserved": True,
                "supporting_events_are_context_only": True,
                "false_positive_review_candidates_are_context_only": True,
                "probing_sequence_summaries_are_context_only": True,
                "static_baseline_summaries_are_context_only": True,
                "crawler_baseline_summaries_are_context_only": True,
                "sensitive_path_probe_summaries_are_context_only": True,
                "mixed_baseline_scanner_summaries_are_context_only": True,
                "ip_behavior_aggregates_are_context_only": True,
                "auth_behavior_summaries_are_context_only": True,
                "method_behavior_summaries_are_context_only": True,
                "protocol_anomaly_summaries_are_context_only": True,
            },
            "thresholds": {
                "candidate_min_score": min_score,
                "noise_min_repeat_aggregate": min_repeat_aggregate,
                "supporting_event_time_window_sec": SUPPORTING_EVENT_TIME_WINDOW_SEC,
                "probing_sequence_window_sec": PROBING_SEQUENCE_WINDOW_SEC,
                "static_baseline_window_sec": STATIC_BASELINE_WINDOW_SEC,
                "crawler_baseline_window_sec": CRAWLER_BASELINE_WINDOW_SEC,
                "sensitive_path_probe_window_sec": SENSITIVE_PATH_PROBE_WINDOW_SEC,
                "mixed_baseline_scanner_window_sec": MIXED_BASELINE_SCANNER_WINDOW_SEC,
                "ip_behavior_window_sec": IP_BEHAVIOR_WINDOW_SEC,
                "auth_behavior_window_sec": AUTH_BEHAVIOR_WINDOW_SEC,
                "auth_behavior_rapid_window_sec": AUTH_BEHAVIOR_RAPID_WINDOW_SEC,
                "method_behavior_window_sec": METHOD_BEHAVIOR_WINDOW_SEC,
                "protocol_anomaly_window_sec": PROTOCOL_ANOMALY_WINDOW_SEC,
                "protocol_anomaly_long_path_min_len": PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
            },
            "counts": {
                "total_exported_rows": safe_int(original_meta.get("total_count"), len(all_rows)),
                "selected_source_rows": len(all_rows),
                "filtered_out_rows": len(filtered_out_rows),
                "filtered_out_non_aggregated_rows": len(non_aggregated_filtered),
                "noise_group_count": len(noise_payload),
                "candidate_rows_before_auth_behavior_reduction": original_candidate_count,
                "auth_behavior_demoted_candidate_rows": len(auth_behavior_supporting_events),
                "candidate_rows_before_dedup": raw_candidate_count,
                "candidate_rows": len(candidate_payload),
                "candidate_duplicate_rows_removed": raw_candidate_count - len(candidate_payload),
                "distinct_incident_candidates": len(candidate_payload),
                "supporting_events": len(supporting_events),
                "false_positive_review_candidates": len(false_positive_review_candidates),
                "probing_sequence_summaries": len(probing_sequence_summaries),
                "static_baseline_summaries": len(static_baseline_summaries),
                "crawler_baseline_summaries": len(crawler_baseline_summaries),
                "sensitive_path_probe_summaries": len(sensitive_path_probe_summaries),
                "mixed_baseline_scanner_summaries": len(mixed_baseline_scanner_summaries),
                "ip_behavior_aggregates": len(ip_behavior_aggregates),
                "auth_behavior_summaries": len(auth_behavior_summaries),
                "method_behavior_summaries": len(method_behavior_summaries),
                "protocol_anomaly_summaries": len(protocol_anomaly_summaries),
            },
            "filtered_out_breakdown": dict(noise_counter),
        },
        "noise_summary": noise_payload,
        "candidate_group_summary": candidate_group_summaries,
        "analysis_candidates": candidate_payload,
        "supporting_events": supporting_events,
        "false_positive_review_candidates": false_positive_review_candidates,
        "probing_sequence_summaries": probing_sequence_summaries,
        "static_baseline_summaries": static_baseline_summaries,
        "crawler_baseline_summaries": crawler_baseline_summaries,
        "sensitive_path_probe_summaries": sensitive_path_probe_summaries,
        "mixed_baseline_scanner_summaries": mixed_baseline_scanner_summaries,
        "ip_behavior_aggregates": ip_behavior_aggregates,
        "auth_behavior_summaries": auth_behavior_summaries,
        "method_behavior_summaries": method_behavior_summaries,
        "protocol_anomaly_summaries": protocol_anomaly_summaries,
    }

    filtered_payload = [
        build_filtered_row_payload(
            r,
            crawler_baseline_contexts=crawler_baseline_contexts,
            method_behavior_contexts=method_behavior_contexts,
            protocol_anomaly_contexts=protocol_anomaly_contexts,
            static_baseline_contexts=static_baseline_contexts,
            sensitive_path_probe_contexts=sensitive_path_probe_contexts,
        )
        for r in non_aggregated_filtered
    ]

    return llm_input, candidate_payload, noise_payload, filtered_payload


def derive_base_name(input_path: str, explicit_base_name: Optional[str]) -> str:
    if explicit_base_name:
        return explicit_base_name
    return os.path.splitext(os.path.basename(input_path))[0]


def main() -> None:
    args = parse_args()
    payload = load_json(args.input)
    source_tables = parse_source_tables_arg(args.include_source_tables)

    llm_input, candidate_payload, noise_payload, filtered_payload = build_outputs(
        payload,
        min_score=args.min_score,
        min_repeat_aggregate=args.min_repeat_aggregate,
        source_tables=source_tables,
    )

    base_name = derive_base_name(args.input, args.base_name)
    out_dir = args.out_dir

    llm_input_path = os.path.join(out_dir, f"{base_name}_llm_input.json")
    candidates_path = os.path.join(out_dir, f"{base_name}_analysis_candidates.json")
    noise_path = os.path.join(out_dir, f"{base_name}_noise_summary.json")
    filtered_path = os.path.join(out_dir, f"{base_name}_filtered_out_rows.json")

    dump_json(llm_input_path, llm_input, pretty=args.pretty)
    dump_json(candidates_path, candidate_payload, pretty=args.pretty)
    dump_json(noise_path, noise_payload, pretty=args.pretty)
    if args.write_filtered_out:
        dump_json(filtered_path, filtered_payload, pretty=args.pretty)

    print(f"[OK] llm_input: {llm_input_path}")
    print(f"[OK] selected_source_tables: {','.join(source_tables)}")
    print(f"[OK] analysis_candidates: {candidates_path}")
    print(f"[OK] noise_summary: {noise_path}")
    if args.write_filtered_out:
        print(f"[OK] filtered_out_rows: {filtered_path}")
    print(
        "[INFO] counts="
        f"total={llm_input['meta']['counts']['total_exported_rows']} "
        f"candidates_before_dedup={llm_input['meta']['counts']['candidate_rows_before_dedup']} "
        f"distinct_candidates={llm_input['meta']['counts']['candidate_rows']} "
        f"dedup_removed={llm_input['meta']['counts']['candidate_duplicate_rows_removed']} "
        f"filtered={llm_input['meta']['counts']['filtered_out_rows']} "
        f"noise_groups={llm_input['meta']['counts']['noise_group_count']}"
    )


if __name__ == "__main__":
    main()
