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
import html
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, unquote_plus

# ----------------------------
# 패턴 정의
# ----------------------------
SQLI_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("union_select", re.compile(r"(?i)\bunion\b\s+\bselect\b"), 5),
    ("or_true", re.compile(r"(?i)(?:'|%27|\")?\s*\bor\b\s+[\w\"']+\s*=\s*[\w\"']+"), 4),
    ("and_true", re.compile(r"(?i)(?:'|%27|\")?\s*\band\b\s+[\w\"']+\s*=\s*[\w\"']+"), 3),
    ("sql_comment", re.compile(r"(?i)(--|#|/\*)"), 2),
    ("sleep_func", re.compile(r"(?i)\bsleep\s*\("), 5),
    ("benchmark_func", re.compile(r"(?i)\bbenchmark\s*\("), 5),
    ("waitfor_delay", re.compile(r"(?i)\bwaitfor\b\s+\bdelay\b"), 5),
    ("information_schema", re.compile(r"(?i)\binformation_schema\b"), 5),
    ("select_from", re.compile(r"(?i)\bselect\b.+\bfrom\b"), 4),
    ("drop_table", re.compile(r"(?i)\bdrop\b\s+\btable\b"), 5),
    ("insert_into", re.compile(r"(?i)\binsert\b\s+\binto\b"), 4),
    ("update_set", re.compile(r"(?i)\bupdate\b.+\bset\b"), 4),
    ("delete_from", re.compile(r"(?i)\bdelete\b\s+\bfrom\b"), 4),
    ("quote_termination", re.compile(r"(?i)(?:'|%27)\s*(?:or|and|union|;|--)"), 4),
]

XSS_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("script_tag", re.compile(r"(?i)<\s*script\b"), 5),
    ("img_onerror", re.compile(r"(?i)<\s*img\b[^>]*onerror\s*="), 5),
    ("svg_onload", re.compile(r"(?i)<\s*svg\b[^>]*onload\s*="), 5),
    ("javascript_uri", re.compile(r"(?i)javascript\s*:"), 4),
    ("event_handler", re.compile(r"(?i)\bon\w+\s*="), 3),
    ("alert_call", re.compile(r"(?i)\balert\s*\("), 3),
    ("document_cookie", re.compile(r"(?i)document\.cookie"), 4),
]

TRAVERSAL_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("dotdot_slash", re.compile(r"(?i)(?:\.\./|\.\.\\\\|%2e%2e%2f|%2e%2e/|\.\.%2f|%252e%252e%252f)"), 4),
    ("etc_passwd", re.compile(r"(?i)/etc/passwd|win\.ini"), 5),
]

FILE_DISCLOSURE_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("php_filter_wrapper", re.compile(r"(?i)php\s*://\s*filter|php%3a%2f%2ffilter|php%253a%252f%252ffilter"), 5),
    ("base64_source_filter", re.compile(r"(?i)convert\.base64-encode"), 2),
    ("resource_parameter", re.compile(r"(?i)(?:^|[?&/])resource\s*=|resource%3d|resource%253d"), 2),
    ("admin_config_php", re.compile(r"(?i)(?:resource\s*=|resource%3d|resource%253d)admin/config\.php\b"), 2),
    ("config_php", re.compile(r"(?i)(?:resource\s*=|resource%3d|resource%253d)config\.php\b"), 2),
    ("index_php", re.compile(r"(?i)(?:resource\s*=|resource%3d|resource%253d)index\.php\b"), 1),
]

CMDI_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("pipe_exec", re.compile(r"(?i)\|\s*(?:whoami|id|cat|uname|ls|pwd)\b"), 4),
    ("semicolon_exec", re.compile(r"(?i);\s*(?:cat|id|whoami|uname|curl|wget|bash|sh)\b"), 4),
    ("subshell", re.compile(r"(?i)(?:\$\((?:id|whoami|uname|cat)|`(?:id|whoami|uname|cat))"), 4),
]

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
EDUCATIONAL_SQL_SEARCH_TERMS = (
    "how to",
    "tutorial",
    "example",
    "guide",
    "docs",
    "documentation",
    "learn",
    "syntax",
    "sql tutorial",
    "select tutorial",
    "union tutorial",
    "사용법",
    "예제",
    "튜토리얼",
    "강의",
    "문서",
    "학습",
    "설명",
)
SUPPORTING_SQL_KEYWORDS = (
    "select",
    "union",
    "from",
    "where",
    "or",
    "and",
    "users",
    "sqlite_master",
    "information_schema",
)
ENCODED_PAYLOAD_MARKERS = ("%27", "%2527", "%2f", "%252f", "%20", "%2520", "%2e", "%252e")
SQLI_BOOLEAN_CONDITION_PATTERN = re.compile(r"(?i)\b(?:or|and)\b\s+(?:\d+|[\w\"']+)\s*=\s*(?:\d+|[\w\"']+)")
SQLI_XCLOSE_PATTERN = re.compile(r"(?i)x\s*'\s*\)\s*\)")
SQLI_UNION_COLUMN_ENUM_PATTERN = re.compile(r"(?i)\bunion\b\s+\bselect\b\s+[^\n]{0,160},\s*[^\n]{0,160}")
SQLI_SCHEMA_ACCESS_PATTERN = re.compile(r"(?i)\b(?:information_schema|sqlite_master|mysql\.user)\b")
SQLI_FROM_USERS_PATTERN = re.compile(r"(?i)\bfrom\b\s+users\b")
SQLI_COMMENT_PATTERN = re.compile(r"(?i)(--|#|/\*)")
REPEATED_QUOTE_PATTERN = re.compile(r"(?i)(?:'|%27|%2527|\"|%22){2,}")
HTML_ENTITY_RE = re.compile(r"&#x?[0-9a-fA-F]+;", re.IGNORECASE)
SCRIPT_TAG_PATTERN = re.compile(r"(?i)<\s*script\b")
SCRIPT_TAG_CAPTURE_RE = re.compile(r"<\s*([a-z]+)\b", re.IGNORECASE)
EVENT_HANDLER_ASSIGNMENT_RE = re.compile(r"(?i)\b(on[a-z0-9_]+)\s*=")
JAVASCRIPT_PROTOCOL_RE = re.compile(r"(?i)javascript\s*:")
BROWSER_DATA_ACCESS_RE = re.compile(r"(?i)(document\.cookie|localStorage|sessionStorage)")
EXTERNAL_NAVIGATION_RE = re.compile(
    r"(?i)(document\.location|window\.location|location\.href|location\s*=|fetch\s*\(|new\s+Image\s*\(\s*\)\s*\.src|navigator\.sendBeacon\s*\()"
)
EXTERNAL_URL_RE = re.compile(r"(?i)\b(?:https?:)?//[^\s\"'<>]+")
XSS_QUOTE_BREAKOUT_PATTERN = re.compile(r"(?i)(?:['\"]\s*>|['\"]\s*<|['\"]\s*on[a-z0-9_]+\s*=)")
XSS_TAG_INJECTION_PATTERN = re.compile(r"(?i)<\s*(?:script|img|svg|iframe|body|a)\b")
PHP_FILTER_CANONICAL_PATTERN = re.compile(r"(?i)php\s*://\s*filter")
EDUCATIONAL_XSS_SEARCH_TERMS = (
    "how to",
    "tutorial",
    "prevent",
    "example",
    "guide",
    "docs",
    "documentation",
    "사용법",
    "예제",
    "튜토리얼",
    "강의",
    "문서",
)
EDUCATIONAL_XSS_KEYWORDS = (
    "xss",
    "script",
    "javascript",
    "onerror",
    "onload",
    "onclick",
    "document.cookie",
    "cookie",
    "localstorage",
    "sessionstorage",
)


@dataclass
class Candidate:
    source_table: str
    log_id: Optional[int]
    log_time: Optional[str]
    src_ip: str
    method: str
    uri: str
    query_string: str
    status_code: int
    score: int
    verdict_hint: str
    reason_hints: List[str]
    request_id: str
    error_link_id: str
    raw_request: str
    user_agent: str
    referer: str
    duration_us: int
    ttfb_us: int
    raw_log: str
    response_body_bytes: int
    resp_content_type: str
    raw_request_target: str
    path_normalized_from_raw_request: bool
    likely_html_fallback_response: bool
    hpp_detected: bool
    hpp_param_names: List[str]
    embedded_attack_hint: str
    incident_group_key: str = ""
    merged_row_count: int = 1
    merged_source_tables: List[str] = field(default_factory=list)
    merged_log_ids: List[int] = field(default_factory=list)


@dataclass
class NoiseAggregate:
    category: str
    src_ip: str
    uri: str
    method: str
    status_code: int
    count: int
    start: Optional[str]
    end: Optional[str]
    user_agent: str
    note: str


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
    current = raw_text(value)
    if not current:
        return []

    if len(current) > DECODE_VARIANT_MAX_CHARS:
        current = current[:DECODE_VARIANT_MAX_CHARS]

    variants: List[Dict[str, Any]] = [{"depth": 0, "text": current}]
    for depth in range(1, max(0, max_depth) + 1):
        try:
            decoded = unquote_plus(current)
        except Exception:
            break
        if len(decoded) > DECODE_VARIANT_MAX_CHARS:
            decoded = decoded[:DECODE_VARIANT_MAX_CHARS]
        if decoded == current:
            break
        variants.append({"depth": depth, "text": decoded})
        current = decoded
    return variants


def build_html_entity_decoded_variant(value: str) -> str:
    current = raw_text(value)
    if not current:
        return ""
    if len(current) > DECODE_VARIANT_MAX_CHARS:
        current = current[:DECODE_VARIANT_MAX_CHARS]
    try:
        decoded = html.unescape(current)
    except Exception:
        return current
    if len(decoded) > DECODE_VARIANT_MAX_CHARS:
        decoded = decoded[:DECODE_VARIANT_MAX_CHARS]
    return decoded


def build_html_entity_variants(value: str, source: str) -> List[Dict[str, Any]]:
    raw_value = raw_text(value)
    if not raw_value or not HTML_ENTITY_RE.search(raw_value):
        return []
    decoded = build_html_entity_decoded_variant(raw_value)
    if not decoded or decoded == raw_value:
        return []
    return [{
        "depth": 0,
        "text": decoded,
        "variant_type": "html_entity",
        "source": source,
        "source_text": raw_value,
    }]


def append_html_entity_variants(variants: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    html_variants: List[Dict[str, Any]] = []
    seen_texts = {raw_text(item.get("text")) for item in variants if raw_text(item.get("text"))}
    for item in list(variants):
        for extra_variant in build_html_entity_variants(raw_text(item.get("text")), source=source):
            text = raw_text(extra_variant.get("text"))
            if not text or text in seen_texts:
                continue
            extra_variant["source_variant_depth"] = safe_int(item.get("depth"), 0)
            html_variants.append(extra_variant)
            seen_texts.add(text)
    variants.extend(html_variants)
    return variants


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
    hints: List[str] = []
    score_boost = 0
    variants = query_variants + raw_request_target_variants
    samples = unique_non_empty_texts(
        [combined_target] + [raw_text(item.get("text")) for item in variants]
    )
    if not samples:
        return 0, []

    pattern_hits = {
        name: any(pattern.search(sample) for sample in samples)
        for name, pattern, _ in FILE_DISCLOSURE_PATTERNS
    }
    points_by_name = {name: points for name, _, points in FILE_DISCLOSURE_PATTERNS}

    canonical_in_base = bool(PHP_FILTER_CANONICAL_PATTERN.search(combined_target))
    canonical_depth1 = False
    canonical_depth2 = False
    for variant in variants:
        text = raw_text(variant.get("text"))
        depth = safe_int(variant.get("depth"), 0)
        if not text or not PHP_FILTER_CANONICAL_PATTERN.search(text):
            continue
        if depth >= 1:
            canonical_depth1 = True
        if depth >= 2:
            canonical_depth2 = True

    resource_context = any(
        pattern_hits.get(name, False)
        for name in ("php_filter_wrapper", "base64_source_filter", "resource_parameter")
    )

    if pattern_hits.get("php_filter_wrapper"):
        score_boost += points_by_name["php_filter_wrapper"]
        append_unique_hint(hints, "file_disclosure:php_filter_wrapper")
    if pattern_hits.get("base64_source_filter"):
        score_boost += points_by_name["base64_source_filter"]
        append_unique_hint(hints, "file_disclosure:base64_source_intent")
    if pattern_hits.get("resource_parameter"):
        score_boost += points_by_name["resource_parameter"]
        append_unique_hint(hints, "file_disclosure:resource_parameter")

    if resource_context:
        if pattern_hits.get("admin_config_php"):
            score_boost += points_by_name["admin_config_php"]
            append_unique_hint(hints, "file_disclosure:sensitive_resource:admin_config_php")
        elif pattern_hits.get("config_php"):
            score_boost += points_by_name["config_php"]
            append_unique_hint(hints, "file_disclosure:sensitive_resource:config_php")

        if pattern_hits.get("index_php"):
            score_boost += points_by_name["index_php"]
            append_unique_hint(hints, "file_disclosure:sensitive_resource:index_php")

    if not canonical_in_base and canonical_depth1:
        append_unique_hint(hints, "encoding:url_decoded_php_wrapper")
    if canonical_depth2:
        append_unique_hint(hints, "encoding:double_decoded_php_wrapper")
        if not canonical_in_base and not canonical_depth1:
            score_boost += 1

    return score_boost, hints


def detect_educational_sql_search_context(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    return any(term in lowered for term in EDUCATIONAL_SQL_SEARCH_TERMS)


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


def get_sqli_structure_flags(text: str) -> Dict[str, bool]:
    raw = raw_text(text)
    normalized = normalize_text(text)
    samples = unique_non_empty_texts([raw, normalized])
    comment_samples = [strip_html_entities_for_sql_comment_scan(sample) for sample in samples]
    return {
        "quote_termination": any(SQLI_PATTERNS[-1][1].search(sample) for sample in samples),
        "sql_comment": any(SQLI_COMMENT_PATTERN.search(sample) for sample in comment_samples),
        "xclose": any(SQLI_XCLOSE_PATTERN.search(sample) for sample in samples),
        "boolean_condition": any(SQLI_BOOLEAN_CONDITION_PATTERN.search(sample) for sample in samples),
        "union_column_list": any(SQLI_UNION_COLUMN_ENUM_PATTERN.search(sample) for sample in samples),
        "schema_access": any(SQLI_SCHEMA_ACCESS_PATTERN.search(sample) for sample in samples),
        "from_users": any(SQLI_FROM_USERS_PATTERN.search(sample) for sample in samples),
    }


def has_encoded_payload_marker(text: str) -> bool:
    lowered = raw_text(text).lower()
    return any(marker in lowered for marker in ENCODED_PAYLOAD_MARKERS)


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
        "log_time": choose_best_time(row),
        "src_ip": get_src_ip(row),
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


def is_high_signal_sqli_candidate(candidate: Candidate, min_score: int) -> bool:
    if candidate.verdict_hint != "sqli":
        return False
    return candidate.score >= max(min_score, 7)


def build_supporting_events(filtered_rows: List[Dict[str, Any]], candidates: List[Candidate], min_score: int) -> List[Dict[str, Any]]:
    high_signal_candidates = [candidate for candidate in candidates if is_high_signal_sqli_candidate(candidate, min_score=min_score)]
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
        additional_hints: List[str] = []

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
            additional_hints.append("supporting:same_uri_nearby_high_signal_sqli")

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
                "supporting_reason": "nearby_high_signal_sqli_context",
                "supporting_role": "temporal_context",
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
                "temporal_context_role": "temporal_context",
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
    if len(items) < PROBING_SEQUENCE_MIN_REQUESTS:
        return None

    distinct_paths: List[str] = []
    seen_paths = set()
    for item in items:
        path = normalize_text(item.get("path")).lower()
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        distinct_paths.append(path)

    if len(distinct_paths) < PROBING_SEQUENCE_MIN_DISTINCT_PATHS:
        return None

    status_counts = Counter(str(safe_int(item.get("status_code"), 0)) for item in items)
    content_type_counts = Counter(normalize_content_type_bucket(item.get("resp_content_type")) or "-" for item in items)

    html_200_rows = [
        item
        for item in items
        if safe_int(item.get("status_code"), 0) == 200
        and normalize_content_type_bucket(item.get("resp_content_type")) == "text/html"
        and safe_int(item.get("response_body_bytes"), 0) > 0
    ]
    response_size_repetition: Dict[str, Any] = {}
    if html_200_rows:
        size_counter = Counter(safe_int(item.get("response_body_bytes"), 0) for item in html_200_rows)
        dominant_size, dominant_count = size_counter.most_common(1)[0]
        if dominant_size > 0 and dominant_count >= 2 and dominant_count * 2 >= len(html_200_rows):
            response_size_repetition = {
                "dominant_response_body_bytes": dominant_size,
                "dominant_count": dominant_count,
            }

    reason_hints: List[str] = []
    for item in items:
        extend_unique_hints(reason_hints, get_probe_sequence_reason_hints(item.get("path")))
    if response_size_repetition:
        append_unique_hint(reason_hints, "dir_probe:repeated_fallback_like_html")

    sorted_items = sorted(items, key=lambda item: normalize_text(item.get("log_time")))
    return {
        "category": "low_signal_dir_probe_burst",
        "policy": "context_only",
        "src_ip": normalize_text(sorted_items[0].get("src_ip")) or "-",
        "start": normalize_text(sorted_items[0].get("log_time")),
        "end": normalize_text(sorted_items[-1].get("log_time")),
        "window_sec": window_sec,
        "request_count": len(items),
        "distinct_path_count": len(distinct_paths),
        "sample_paths": distinct_paths[:PROBING_SEQUENCE_SAMPLE_PATH_LIMIT],
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (-safe_int(kv[1]), kv[0]))),
        "content_type_counts": dict(sorted(content_type_counts.items(), key=lambda kv: (-safe_int(kv[1]), kv[0]))),
        "response_size_repetition": response_size_repetition,
        "reason_hints": reason_hints,
        "interpretation_hint": (
            "Multiple low-signal directory probing paths from the same source in a short window. "
            "Context only; do not treat as confirmed compromise."
        ),
    }


def build_probing_sequence_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = PROBING_SEQUENCE_WINDOW_SEC,
) -> List[Dict[str, Any]]:
    probe_rows_by_ip: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        method = get_method(row)
        if method not in {"GET", "HEAD", "OPTIONS"}:
            continue
        path = get_probe_sequence_path(
            uri=get_uri(row),
            raw_request_target=extract_raw_request_target(raw_text(row.get("raw_request"))),
        )
        if not is_likely_probe_sequence_path(path, query_string=normalize_text(row.get("query_string"))):
            continue

        dt = parse_flexible_iso_dt(choose_best_time(row) or "")
        if dt is None:
            continue

        probe_rows_by_ip[get_src_ip(row)].append(
            {
                "src_ip": get_src_ip(row),
                "log_time": choose_best_time(row),
                "dt": dt,
                "path": path,
                "status_code": get_status_code(row),
                "resp_content_type": get_resp_content_type(row),
                "response_body_bytes": get_response_body_bytes(row),
            }
        )

    summaries: List[Dict[str, Any]] = []
    for src_ip, items in probe_rows_by_ip.items():
        sorted_items = sorted(items, key=lambda item: item["dt"])
        bucket: List[Dict[str, Any]] = []
        bucket_start: Optional[datetime] = None
        for item in sorted_items:
            if not bucket:
                bucket = [item]
                bucket_start = item["dt"]
                continue

            if bucket_start is not None and (item["dt"] - bucket_start).total_seconds() <= window_sec:
                bucket.append(item)
                continue

            summary = finalize_probing_sequence_bucket(bucket, window_sec=window_sec)
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = finalize_probing_sequence_bucket(bucket, window_sec=window_sec)
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            safe_int(item.get("request_count"), 0),
            safe_int(item.get("distinct_path_count"), 0),
            normalize_text(item.get("start")),
        ),
        reverse=True,
    )
    return summaries


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


def build_filtered_row_payload(row: Dict[str, Any]) -> Dict[str, Any]:
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

    reason_hints = get_probe_sequence_reason_hints(probe_path)

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
    structure_flags = get_sqli_structure_flags(combined_target)
    xss_structure_flags = get_xss_structure_flags(
        combined_target=combined_target,
        query_variants=query_variants,
        raw_request_target_variants=raw_request_target_variants,
    )
    strong_sqli_structure = any(
        structure_flags.get(name, False)
        for name in ("quote_termination", "sql_comment", "xclose", "boolean_condition", "union_column_list", "schema_access")
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
        if not structure_flags.get("boolean_condition"):
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

    raw_candidate_count = len(candidates)
    deduped_candidates, candidate_group_summaries = deduplicate_candidates(candidates)
    supporting_events = build_supporting_events(filtered_out_rows, deduped_candidates, min_score=min_score)
    probing_sequence_summaries = build_probing_sequence_summaries(all_rows)
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
            },
            "thresholds": {
                "candidate_min_score": min_score,
                "noise_min_repeat_aggregate": min_repeat_aggregate,
                "supporting_event_time_window_sec": SUPPORTING_EVENT_TIME_WINDOW_SEC,
                "probing_sequence_window_sec": PROBING_SEQUENCE_WINDOW_SEC,
            },
            "counts": {
                "total_exported_rows": safe_int(original_meta.get("total_count"), len(all_rows)),
                "selected_source_rows": len(all_rows),
                "filtered_out_rows": len(filtered_out_rows),
                "filtered_out_non_aggregated_rows": len(non_aggregated_filtered),
                "noise_group_count": len(noise_payload),
                "candidate_rows_before_dedup": raw_candidate_count,
                "candidate_rows": len(candidate_payload),
                "candidate_duplicate_rows_removed": raw_candidate_count - len(candidate_payload),
                "distinct_incident_candidates": len(candidate_payload),
                "supporting_events": len(supporting_events),
                "false_positive_review_candidates": len(false_positive_review_candidates),
                "probing_sequence_summaries": len(probing_sequence_summaries),
            },
            "filtered_out_breakdown": dict(noise_counter),
        },
        "noise_summary": noise_payload,
        "candidate_group_summary": candidate_group_summaries,
        "analysis_candidates": candidate_payload,
        "supporting_events": supporting_events,
        "false_positive_review_candidates": false_positive_review_candidates,
        "probing_sequence_summaries": probing_sequence_summaries,
    }

    filtered_payload = [build_filtered_row_payload(r) for r in non_aggregated_filtered]

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
