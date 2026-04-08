#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from urllib.parse import unquote_plus

import pymysql
from pymysql.cursors import DictCursor


# ----------------------------
# SQLi/XSS 시그니처
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


@dataclass
class RequestAnalysis:
    log_id: int
    log_time: str
    src_ip: str
    method: str
    uri: str
    query_string: str
    status_code: int
    score: int
    verdict: str
    reasons: str
    raw_request: str


@dataclass
class UserRiskSummary:
    src_ip: str
    total_requests: int
    benign_count: int
    suspicious_count: int
    sqli_count: int
    xss_count: int
    total_score: int
    average_score: float
    max_score: int
    final_verdict: str
    sample_reasons: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze suspicious users from apache_security_logs in MariaDB")
    parser.add_argument("--db-host", default="192.168.35.223")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-user", default="log_writer")
    parser.add_argument("--db-password", required=True)
    parser.add_argument("--db-name", default="web_logs")
    parser.add_argument("--hours", type=int, default=24, help="최근 N시간 로그 조회")
    parser.add_argument("--limit", type=int, default=5000, help="최대 조회 건수")
    parser.add_argument("--min-score-suspicious", type=int, default=4)
    parser.add_argument("--min-score-sqli", type=int, default=7)
    parser.add_argument("--min-score-xss", type=int, default=7)
    parser.add_argument("--top", type=int, default=20, help="상위 몇 명 출력할지")
    return parser.parse_args()


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return unquote_plus(str(text)).strip()


def safe_int(value: Optional[object], default: int = 0) -> int:
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


def contains_login_uri(uri: str) -> bool:
    uri_lower = (uri or "").lower()
    return any(hint in uri_lower for hint in LOGIN_URI_HINTS)


def contains_query_heavy_uri(uri: str) -> bool:
    uri_lower = (uri or "").lower()
    return any(hint in uri_lower for hint in QUERY_HEAVY_URI_HINTS)


def evaluate_request(
    row: Dict,
    suspicious_threshold: int,
    sqli_threshold: int,
    xss_threshold: int,
) -> RequestAnalysis:
    raw_req = normalize_text(row.get("raw_request"))
    uri = normalize_text(row.get("uri"))
    qs = normalize_text(row.get("query_string"))
    status_code = safe_int(row.get("status_code"))
    dur_us = safe_int(row.get("duration_us"))
    ttfb_us = safe_int(row.get("ttfb_us"))
    req_ct = normalize_text(row.get("req_content_type"))

    combined_target = " ".join([raw_req, uri, qs]).strip()

    score = 0
    reasons: List[str] = []
    sqli_hits = 0
    xss_hits = 0

    # SQLi
    for name, pattern, points in SQLI_PATTERNS:
        if pattern.search(combined_target):
            score += points
            sqli_hits += 1
            reasons.append(f"sqli:{name}(+{points})")

    # XSS
    for name, pattern, points in XSS_PATTERNS:
        if pattern.search(combined_target):
            score += points
            xss_hits += 1
            reasons.append(f"xss:{name}(+{points})")

    # 길이 / 특수문자
    qs_len = len(qs)
    if qs_len >= 40:
        score += 1
        reasons.append("long_query(+1)")
    if qs_len >= 80:
        score += 1
        reasons.append("very_long_query(+1)")

    ratio = special_char_ratio(qs)
    if ratio >= 0.15:
        score += 1
        reasons.append("special_char_ratio_high(+1)")
    if ratio >= 0.30:
        score += 1
        reasons.append("special_char_ratio_very_high(+1)")

    # 상태 코드
    if status_code in {400, 403, 500}:
        score += 2
        reasons.append(f"error_status:{status_code}(+2)")

    # 시간 기반
    if dur_us >= 2_000_000:
        score += 3
        reasons.append("high_duration(+3)")
    if dur_us >= 5_000_000:
        score += 2
        reasons.append("very_high_duration(+2)")
    if ttfb_us >= 2_000_000:
        score += 2
        reasons.append("high_ttfb(+2)")

    # URI 맥락
    if contains_login_uri(uri):
        score += 1
        reasons.append("login_endpoint(+1)")

    if contains_query_heavy_uri(uri) and qs:
        if re.search(r"(?i)\b(select|union|sleep|benchmark|waitfor|or|and|script|javascript|alert)\b", qs):
            score += 2
            reasons.append("query_endpoint_with_attack_tokens(+2)")

    # Content-Type
    if req_ct.lower() in {"application/json", "application/x-www-form-urlencoded"} and contains_login_uri(uri):
        score += 1
        reasons.append("auth_payload_content_type(+1)")

    # 최종 요청 판정
    if xss_hits > 0 and score >= xss_threshold:
        verdict = "xss"
    elif sqli_hits > 0 and score >= sqli_threshold:
        verdict = "sqli"
    elif score >= suspicious_threshold:
        verdict = "suspicious"
    else:
        verdict = "benign"

    return RequestAnalysis(
        log_id=safe_int(row.get("id")),
        log_time=str(row.get("log_time")),
        src_ip=normalize_text(row.get("src_ip")) or "-",
        method=normalize_text(row.get("method")) or "-",
        uri=uri or "-",
        query_string=qs or "",
        status_code=status_code,
        score=score,
        verdict=verdict,
        reasons=";".join(reasons),
        raw_request=raw_req or "",
    )


def fetch_security_logs(conn, hours: int, limit: int) -> List[Dict]:
    sql = """
    SELECT
        id,
        log_time,
        src_ip,
        method,
        raw_request,
        uri,
        query_string,
        status_code,
        duration_us,
        ttfb_us,
        req_content_type
    FROM apache_security_logs
    WHERE log_time >= NOW() - INTERVAL %s HOUR
    ORDER BY log_time DESC
    LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (hours, limit))
        return cur.fetchall()


def summarize_by_user(results: List[RequestAnalysis]) -> List[UserRiskSummary]:
    grouped: Dict[str, List[RequestAnalysis]] = defaultdict(list)
    for r in results:
        grouped[r.src_ip].append(r)

    summaries: List[UserRiskSummary] = []

    for src_ip, items in grouped.items():
        total_requests = len(items)
        benign_count = sum(1 for x in items if x.verdict == "benign")
        suspicious_count = sum(1 for x in items if x.verdict == "suspicious")
        sqli_count = sum(1 for x in items if x.verdict == "sqli")
        xss_count = sum(1 for x in items if x.verdict == "xss")
        total_score = sum(x.score for x in items)
        average_score = round(total_score / total_requests, 2) if total_requests else 0.0
        max_score = max((x.score for x in items), default=0)

        # 사용자 최종 판정 규칙
        if sqli_count >= 3 or xss_count >= 3 or total_score >= 20:
            final_verdict = "high_risk"
        elif sqli_count >= 1 or xss_count >= 1 or suspicious_count >= 3 or total_score >= 10:
            final_verdict = "medium_risk"
        elif suspicious_count >= 1:
            final_verdict = "low_risk"
        else:
            final_verdict = "benign"

        sample_reasons = " | ".join(
            [x.reasons for x in items if x.reasons][:3]
        )

        summaries.append(
            UserRiskSummary(
                src_ip=src_ip,
                total_requests=total_requests,
                benign_count=benign_count,
                suspicious_count=suspicious_count,
                sqli_count=sqli_count,
                xss_count=xss_count,
                total_score=total_score,
                average_score=average_score,
                max_score=max_score,
                final_verdict=final_verdict,
                sample_reasons=sample_reasons,
            )
        )

    summaries.sort(
        key=lambda x: (x.total_score, x.sqli_count, x.xss_count, x.max_score),
        reverse=True
    )
    return summaries


def print_request_examples(results: List[RequestAnalysis], top: int = 10) -> None:
    print("\n[요청 단위 상위 의심 사례]")
    ranked = sorted(results, key=lambda x: x.score, reverse=True)[:top]
    for r in ranked:
        print(
            f"id={r.log_id} time={r.log_time} ip={r.src_ip} verdict={r.verdict} "
            f"score={r.score} method={r.method} uri={r.uri} qs={r.query_string}"
        )
        if r.reasons:
            print(f"  reasons={r.reasons}")
        if r.raw_request:
            print(f"  raw_request={r.raw_request}")


def print_user_summaries(summaries: List[UserRiskSummary], top: int = 20) -> None:
    print("[사용자/IP 단위 위험도]")
    for s in summaries[:top]:
        print(
            f"ip={s.src_ip} verdict={s.final_verdict} total={s.total_requests} "
            f"sqli={s.sqli_count} xss={s.xss_count} suspicious={s.suspicious_count} "
            f"score_sum={s.total_score} avg={s.average_score} max={s.max_score}"
        )
        if s.sample_reasons:
            print(f"  sample_reasons={s.sample_reasons}")


def main() -> None:
    args = parse_args()

    conn = pymysql.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )

    try:
        rows = fetch_security_logs(conn, args.hours, args.limit)
        if not rows:
            print("조회된 로그가 없습니다.")
            return

        analyzed = [
            evaluate_request(
                row,
                suspicious_threshold=args.min_score_suspicious,
                sqli_threshold=args.min_score_sqli,
                xss_threshold=args.min_score_xss,
            )
            for row in rows
        ]

        summaries = summarize_by_user(analyzed)

        print_user_summaries(summaries, top=args.top)
        print_request_examples(analyzed, top=min(args.top, 10))

    finally:
        conn.close()


if __name__ == "__main__":
    main()