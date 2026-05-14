#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert Apache observability raw security logs into export_db_logs_cli-compatible JSON.

Purpose
- Allow lab/observability raw log runs to flow into the existing pipeline without
  changing prepare_llm_input.py.
- Convert raw app_security.filtered.log lines produced by apache_security_io_v1
  into a JSON shape compatible with run_analysis_pipeline.py --export-input.

Input
- lab/observability/runs/<run_id>/raw/app_security.filtered.log
- or an explicit --security-log path

Output
- lab/observability/runs/<run_id>/exported/security.json by default
- or an explicit --out path

Non-goals
- Do not infer attack category, severity, success, exposure, or compromise.
- Do not parse request/response bodies.
- Do not create findings or incidents.
- Do not merge error logs into security rows; error logs remain separate context.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

DEFAULT_QUERY_TIMEZONE = "Asia/Seoul"
DEFAULT_DB_TIMEZONE = "UTC"
DEFAULT_DATABASE = "web_logs"
DEFAULT_TABLE_OPTION = "security"
DEFAULT_LOG_SCHEMA = "apache_security_io_v1"

QUERY_TZ = ZoneInfo(DEFAULT_QUERY_TIMEZONE)
DB_TZ = timezone.utc

KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
REQUEST_LINE_RE = re.compile(r"^(?P<method>\S+)\s+(?P<target>\S+)(?:\s+(?P<protocol>\S+))?")

INTEGER_FIELDS = {
    "status_code",
    "original_status_code",
    "response_body_bytes",
    "in_bytes",
    "out_bytes",
    "total_bytes",
    "duration_us",
    "ttfb_us",
    "keepalive_count",
    "req_content_length",
    "server_port",
}

TEXT_NORMALIZE_DASH_FIELDS = {
    "request_id",
    "error_link_id",
    "vhost",
    "server_name",
    "local_ip",
    "src_ip",
    "peer_ip",
    "method",
    "raw_request",
    "uri",
    "query_string",
    "protocol",
    "connection_status",
    "handler",
    "req_content_type",
    "resp_content_type",
    "location",
    "referer",
    "origin",
    "user_agent",
    "host",
    "x_forwarded_for",
    "x_real_ip",
    "forwarded",
}

ROW_FIELD_ORDER = [
    "id",
    "log_time",
    "request_id",
    "error_link_id",
    "vhost",
    "server_name",
    "server_port",
    "local_ip",
    "src_ip",
    "peer_ip",
    "method",
    "raw_request",
    "uri",
    "query_string",
    "protocol",
    "status_code",
    "original_status_code",
    "response_body_bytes",
    "in_bytes",
    "out_bytes",
    "total_bytes",
    "duration_us",
    "ttfb_us",
    "keepalive_count",
    "connection_status",
    "handler",
    "req_content_type",
    "req_content_length",
    "resp_content_type",
    "location",
    "referer",
    "origin",
    "user_agent",
    "host",
    "x_forwarded_for",
    "x_real_ip",
    "forwarded",
    "log_schema",
    "attack_label",
    "risk_score",
    "matched_rule",
    "is_suspicious",
    "raw_log",
    "created_at",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert lab observability Apache security logs to export JSON compatible with prepare_llm_input.py."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run-dir", help="Observability run directory, e.g. lab/observability/runs/obs_php_sample_002")
    source.add_argument("--security-log", help="Explicit app_security.filtered.log path")

    parser.add_argument("--run-id", default=None, help="Run ID override. Defaults to run-dir basename or input filename stem.")
    parser.add_argument("--out", default=None, help="Output JSON path. Defaults to <run-dir>/exported/security.json when --run-dir is used.")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Database name to place in export meta. Default: web_logs")
    parser.add_argument("--query-timezone", default=DEFAULT_QUERY_TIMEZONE, help="Output/query timezone. Default: Asia/Seoul")
    parser.add_argument("--db-timezone", default=DEFAULT_DB_TIMEZONE, help="DB timezone label for export meta. Default: UTC")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of security rows to convert")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--include-empty-lines", action="store_true", help="Include malformed/empty lines as skipped stats only; rows are never generated for empty lines")
    return parser.parse_args()


def strip_quotes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def normalize_dash(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return None if text == "-" else text


def safe_int(value: Optional[Any]) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "-", "None", "null"}:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def safe_float(value: Optional[Any]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "-", "None", "null"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_kv_line(line: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for match in KV_RE.finditer(line):
        key = match.group(1)
        value = strip_quotes(match.group(2))
        result[key] = value if value is not None else ""
    return result


def parse_log_time(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    text = raw.strip()
    candidates = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=DB_TZ)
        return dt
    except ValueError:
        return None


def to_output_time(dt: Optional[datetime], query_tz: ZoneInfo) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DB_TZ)
    return dt.astimezone(query_tz).isoformat(timespec="milliseconds")


def now_output_time(query_tz: ZoneInfo) -> str:
    return datetime.now(tz=query_tz).isoformat(timespec="milliseconds")


def derive_request_target(raw_request: Optional[str], uri: Optional[str], query_string: Optional[str]) -> str:
    raw = normalize_dash(raw_request) or ""
    m = REQUEST_LINE_RE.match(raw)
    if m:
        return m.group("target") or ""
    path = normalize_dash(uri) or ""
    qs = query_string or ""
    if qs and not qs.startswith("?"):
        qs = "?" + qs
    return path + qs


def normalize_row(raw: Dict[str, str], raw_line: str, row_id: int, query_tz: ZoneInfo) -> Dict[str, Any]:
    parsed_time = parse_log_time(raw.get("log_time"))
    log_time = to_output_time(parsed_time, query_tz)

    row: Dict[str, Any] = {}
    row["id"] = row_id

    for field in TEXT_NORMALIZE_DASH_FIELDS:
        row[field] = normalize_dash(raw.get(field))

    for field in INTEGER_FIELDS:
        row[field] = safe_int(raw.get(field))

    row["log_time"] = log_time
    row["log_schema"] = normalize_dash(raw.get("log_schema")) or DEFAULT_LOG_SCHEMA
    row["raw_log"] = raw_line
    row["created_at"] = log_time

    # Compatibility/default fields used by existing shipper/DB schema.
    row["attack_label"] = normalize_dash(raw.get("attack_label")) or "unknown"
    row["risk_score"] = safe_float(raw.get("risk_score")) if raw.get("risk_score") is not None else 0.0
    row["matched_rule"] = normalize_dash(raw.get("matched_rule"))
    row["is_suspicious"] = bool(safe_int(raw.get("is_suspicious")) or 0)

    # Keep request target as a convenience field for downstream inspection.
    # Existing prepare code may ignore it, but it is useful for raw-export compatibility.
    row["raw_request_target"] = derive_request_target(row.get("raw_request"), row.get("uri"), row.get("query_string"))

    # DB schema historically had these optional fields; keep them as nullable.
    for optional in (
        "resp_html_norm_fingerprint",
        "resp_html_fingerprint_version",
        "resp_html_baseline_name",
        "resp_html_baseline_match",
        "resp_html_baseline_confidence",
        "resp_html_features_json",
    ):
        row[optional] = normalize_dash(raw.get(optional))

    # Output deterministic ordering while retaining any future keys at the end.
    ordered: Dict[str, Any] = {}
    for key in ROW_FIELD_ORDER:
        if key in row:
            ordered[key] = row[key]
    for key in sorted(row):
        if key not in ordered:
            ordered[key] = row[key]
    return ordered


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, str]:
    if args.run_dir:
        run_dir = Path(args.run_dir).expanduser().resolve()
        input_path = run_dir / "raw" / "app_security.filtered.log"
        out_path = Path(args.out).expanduser().resolve() if args.out else run_dir / "exported" / "security.json"
        run_id = args.run_id or run_dir.name
        return input_path, out_path, run_id

    input_path = Path(args.security_log).expanduser().resolve()
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
    else:
        out_path = input_path.with_name(input_path.stem + ".export.json")
    run_id = args.run_id or input_path.stem
    return input_path, out_path, run_id


def min_max_times(rows: Iterable[Dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
    values = [row.get("log_time") for row in rows if row.get("log_time")]
    if not values:
        return None, None
    return min(values), max(values)


def build_payload(
    *,
    rows: List[Dict[str, Any]],
    skipped_lines: int,
    malformed_lines: int,
    source_log: Path,
    run_id: str,
    database: str,
    query_tz_name: str,
    db_tz_name: str,
    query_tz: ZoneInfo,
) -> Dict[str, Any]:
    start, end = min_max_times(rows)
    counts = {"access": 0, "security": len(rows), "error": 0}
    return {
        "meta": {
            "database": database,
            "exported_at": now_output_time(query_tz),
            "query_timezone": query_tz_name,
            "db_timezone": db_tz_name,
            "range_mode": "observability_raw_log",
            "start": start,
            "end_exclusive": end,
            "start_db_query": None,
            "end_exclusive_db_query": None,
            "table_option": DEFAULT_TABLE_OPTION,
            "limit_per_table": None,
            "total_count": len(rows),
            "source": "observability_raw_log",
            "source_log": str(source_log),
            "run_id": run_id,
            "log_schema": DEFAULT_LOG_SCHEMA,
            "skipped_lines": skipped_lines,
            "malformed_lines": malformed_lines,
            "analysis_recommendation": {
                "primary_table_for_llm": "security",
                "use_error_for_correlation": True,
                "use_access_for_ops_baseline": False,
            },
            "guardrails": {
                "raw_body_collected": False,
                "response_body_collected": False,
                "do_not_infer_success_from_status_code": True,
                "do_not_infer_file_exposure_from_size_or_content_type": True,
            },
        },
        "counts": counts,
        "data": {
            "access": [],
            "security": rows,
            "error": [],
        },
    }


def convert(args: argparse.Namespace) -> Path:
    query_tz = ZoneInfo(args.query_timezone)
    input_path, out_path, run_id = resolve_paths(args)

    if not input_path.exists():
        raise FileNotFoundError(f"security log not found: {input_path}")

    rows: List[Dict[str, Any]] = []
    skipped_lines = 0
    malformed_lines = 0

    with input_path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            raw_line = line.rstrip("\n")
            if not raw_line:
                skipped_lines += 1
                continue
            raw = parse_kv_line(raw_line)
            if not raw:
                malformed_lines += 1
                continue
            if args.limit is not None and len(rows) >= args.limit:
                break
            rows.append(normalize_row(raw, raw_line, row_id=len(rows) + 1, query_tz=query_tz))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(
        rows=rows,
        skipped_lines=skipped_lines,
        malformed_lines=malformed_lines,
        source_log=input_path,
        run_id=run_id,
        database=args.database,
        query_tz_name=args.query_timezone,
        db_tz_name=args.db_timezone,
        query_tz=query_tz,
    )

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if args.pretty else None)
        if args.pretty:
            f.write("\n")

    print(f"[OK] converted rows: {len(rows)}")
    print(f"[OK] skipped_lines={skipped_lines} malformed_lines={malformed_lines}")
    print(f"[OK] output: {out_path}")
    return out_path


def main() -> int:
    args = parse_args()
    try:
        convert(args)
        return 0
    except KeyboardInterrupt:
        print("\n[INFO] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
