#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage2 산출물을 Web UI read-only viewer 용 payload 로 정규화한다.

원칙
- deterministic adapter only
- LLM 호출 없음
- 새 공격 판별/성공 추론/심각도 재계산 없음
- context-only summary / supporting_events 를 finding 으로 승격하지 않음
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


CONTEXT_COLLECTIONS: List[Tuple[str, str]] = [
    ("probing_sequence_summaries", "probing_sequence"),
    ("sensitive_path_probe_summaries", "sensitive_path_probe"),
    ("mixed_baseline_scanner_summaries", "mixed_baseline_scanner"),
    ("ip_behavior_aggregates", "ip_behavior"),
    ("auth_behavior_summaries", "auth_behavior"),
    ("method_behavior_summaries", "method_behavior"),
    ("protocol_anomaly_summaries", "protocol_anomalies"),
    ("static_baseline_summaries", "static_baseline"),
    ("crawler_baseline_summaries", "crawler_baseline"),
]

APACHE_GUARDRAILS = [
    "Apache logs alone do not prove exploit success, login success, account takeover, credential stuffing success, lockout, upload/delete success, XST/CORS success, file exposure, DB access, browser execution, static file existence, crawler identity, or server compromise.",
    "status_code, content_type, response_body_bytes, route name, and lab-* UA are evidence fields, not success proof.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage2 결과를 Web UI viewer payload 로 변환")
    parser.add_argument("--stage2-report", default=None, help="선택: <base>_stage2_report.json")
    parser.add_argument("--stage2-report-input", required=True, help="필수: <base>_stage2_report_input.json")
    parser.add_argument("--stage1-results", default=None, help="선택: <base>_stage1_results.json")
    parser.add_argument("--llm-input", default=None, help="선택: <base>_llm_input.json")
    parser.add_argument("--raw-export", default=None, help="선택: export_db_logs_cli.py raw export JSON")
    parser.add_argument("--noise-summary", default=None, help="선택: <base>_noise_summary.json")
    parser.add_argument("--out", required=True, help="출력 viewer payload JSON 경로")
    parser.add_argument("--include-raw-log", action="store_true", help="raw_export 의 raw_log 포함")
    parser.add_argument("--pretty", action="store_true", help="JSON pretty 출력")
    return parser.parse_args()


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="milliseconds")


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, payload: Any, pretty: bool) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)


def normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def ensure_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def normalize_string_list(value: Any) -> List[str]:
    items = ensure_list(value)
    normalized: List[str] = []
    for item in items:
        text = normalize_str(item)
        if text:
            normalized.append(text)
    return normalized


def normalize_reason_hints(value: Any) -> List[str]:
    if isinstance(value, list):
        return [normalize_str(item) for item in value if normalize_str(item)]
    if isinstance(value, str):
        text = normalize_str(value)
        return [text] if text else []
    return []


def normalize_path(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return str(Path(value).expanduser().resolve())


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value
            continue
        if isinstance(value, (list, dict)):
            if value:
                return value
            continue
        return value
    return None


def build_source_table_log_id(item: Dict[str, Any]) -> str:
    source_table = normalize_str(first_non_empty(item.get("source_table"), item.get("_source_table")))
    log_id = first_non_empty(item.get("log_id"), item.get("id"))
    if source_table and log_id not in (None, ""):
        return f"{source_table}:{log_id}"
    return ""


def build_fingerprint(item: Dict[str, Any]) -> str:
    parts = [
        normalize_str(item.get("src_ip")),
        normalize_str(item.get("method")),
        normalize_str(item.get("uri")),
        normalize_str(item.get("status_code")),
        normalize_str(item.get("log_time")),
    ]
    if all(parts):
        return "|".join(parts)
    return ""


def build_merge_key(item: Dict[str, Any]) -> str:
    request_id = normalize_str(item.get("request_id"))
    if request_id:
        return f"rid:{request_id}"

    incident_key = normalize_str(first_non_empty(item.get("incident_group_key"), item.get("dedup_key")))
    if incident_key:
        return f"ikey:{incident_key}"

    source_log = build_source_table_log_id(item)
    if source_log:
        return f"log:{source_log}"

    fingerprint = build_fingerprint(item)
    if fingerprint:
        return f"fp:{fingerprint}"

    return stable_json_dumps(item)


def build_context_key(context_type: str, item: Dict[str, Any]) -> str:
    base = build_merge_key(item)
    if base != stable_json_dumps(item):
        return f"{context_type}:{base}"
    sample_request_id = normalize_str(item.get("sample_request_id"))
    if sample_request_id:
        return f"{context_type}:sample_request_id:{sample_request_id}"
    sample_uri = normalize_str(item.get("sample_uri"))
    src_ip = normalize_str(item.get("src_ip"))
    window_start = normalize_str(item.get("window_start"))
    window_end = normalize_str(item.get("window_end"))
    fallback = "|".join([src_ip, sample_uri, window_start, window_end])
    if fallback.strip("|"):
        return f"{context_type}:summary:{fallback}"
    return f"{context_type}:json:{stable_json_dumps(item)}"


def build_event_key(item: Dict[str, Any]) -> str:
    return f"supporting:{build_merge_key(item)}"


def raw_export_rows(payload: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    root = ensure_dict(payload)
    data = root.get("data")
    if isinstance(data, dict):
        for source_table, table_rows in data.items():
            for row in ensure_list(table_rows):
                if isinstance(row, dict):
                    item = dict(row)
                    item.setdefault("_source_table", source_table)
                    rows.append(item)
        return rows
    if isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict):
                rows.append(dict(row))
    return rows


def build_lookup(items: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for item in items:
        key = build_merge_key(item)
        if key not in lookup:
            lookup[key] = item
    return lookup


def lookup_match(item: Dict[str, Any], lookup: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = [
        normalize_str(item.get("request_id")) and f"rid:{normalize_str(item.get('request_id'))}",
        normalize_str(first_non_empty(item.get("incident_group_key"), item.get("dedup_key")))
        and f"ikey:{normalize_str(first_non_empty(item.get('incident_group_key'), item.get('dedup_key')))}",
        build_source_table_log_id(item) and f"log:{build_source_table_log_id(item)}",
        build_fingerprint(item) and f"fp:{build_fingerprint(item)}",
    ]
    for key in candidates:
        if key and key in lookup:
            return lookup[key]
    return None


def merge_missing(base: Dict[str, Any], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not extra:
        return base
    merged = dict(base)
    for key, value in extra.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
    return merged


def extract_report_fields(stage2_report_payload: Dict[str, Any]) -> Dict[str, Any]:
    report = ensure_dict(stage2_report_payload.get("report"))
    return {
        "report_title": report.get("report_title"),
        "overall_assessment": report.get("overall_assessment"),
        "executive_summary": ensure_list(report.get("executive_summary")),
        "key_findings": ensure_list(report.get("key_findings")),
        "notable_incidents": ensure_list(report.get("notable_incidents")),
        "notable_source_ips": ensure_list(report.get("notable_source_ips")),
        "noise_interpretation": report.get("noise_interpretation"),
        "recommended_actions": ensure_list(report.get("recommended_actions")),
        "confidence_and_limitations": report.get("confidence_and_limitations"),
        "presentation_takeaway": report.get("presentation_takeaway"),
    }


def normalize_finding_category(item: Dict[str, Any]) -> str:
    # UI badge grouping only. This reuses existing verdict/reason_hints/URI/method signals and does not create new detections.
    verdict = normalize_str(item.get("verdict")).lower()
    verdict_hint = normalize_str(item.get("verdict_hint")).lower()
    reason_hints = [hint.lower() for hint in normalize_reason_hints(item.get("reason_hints"))]
    uri = normalize_str(item.get("uri")).lower()
    method = normalize_str(item.get("method")).upper()
    joined = " ".join([verdict, verdict_hint] + reason_hints)

    def has_hint(prefix: str) -> bool:
        return any(hint.startswith(prefix) for hint in reason_hints)

    if "auth" in joined or has_hint("auth:") or "login" in uri:
        return "auth_behavior_candidate"
    if "traversal" in joined or "path_traversal" in joined or has_hint("traversal:") or has_hint("cmdi:"):
        return "path_traversal_candidate"
    if "sqli" in joined or has_hint("sqli:"):
        return "sqli_candidate"
    if "xss" in joined or has_hint("xss:"):
        return "xss_candidate"
    if "file_disclosure" in joined or has_hint("file_disclosure:") or "php://filter" in uri:
        return "file_disclosure_candidate"
    if has_hint("method:") or has_hint("protocol:") or method in {"TRACE", "OPTIONS", "PUT", "DELETE", "PATCH"}:
        return "method_behavior_candidate"
    if has_hint("sensitive_path:") or any(token in uri for token in (".env", "phpinfo", "server-status", "wp-login", "wp-admin")):
        return "sensitive_path_candidate"
    return "generic_candidate"


def select_findings_source(
    stage2_report_input: Dict[str, Any],
    stage1_results_payload: Dict[str, Any],
    llm_input_payload: Dict[str, Any],
) -> Tuple[str, List[Dict[str, Any]]]:
    top_incidents = ensure_list(stage2_report_input.get("top_incidents"))
    if top_incidents:
        return "stage2_report_input.top_incidents", [item for item in top_incidents if isinstance(item, dict)]

    stage1_results = ensure_list(stage1_results_payload.get("results"))
    if stage1_results:
        return "stage1_results.results", [item for item in stage1_results if isinstance(item, dict)]

    analysis_candidates = ensure_list(llm_input_payload.get("analysis_candidates"))
    return "llm_input.analysis_candidates", [item for item in analysis_candidates if isinstance(item, dict)]


def build_finding(
    item: Dict[str, Any],
    source_name: str,
    raw_match: Optional[Dict[str, Any]],
    include_raw_log: bool,
) -> Dict[str, Any]:
    finding = {
        "source": source_name,
        "context_only": False,
        "incident_ref": normalize_str(item.get("incident_ref")),
        "incident_group_key": normalize_str(item.get("incident_group_key")),
        "dedup_key": normalize_str(item.get("dedup_key")),
        "request_id": normalize_str(item.get("request_id")),
        "source_table": normalize_str(first_non_empty(item.get("source_table"), item.get("_source_table"))),
        "log_id": first_non_empty(item.get("log_id"), item.get("id")),
        "src_ip": normalize_str(item.get("src_ip")),
        "method": normalize_str(item.get("method")),
        "uri": normalize_str(item.get("uri")),
        "query_string": normalize_str(item.get("query_string")),
        "status_code": item.get("status_code"),
        "log_time": normalize_str(item.get("log_time")),
        "severity": normalize_str(item.get("severity")),
        "confidence": normalize_str(item.get("confidence")),
        "verdict": normalize_str(item.get("verdict")),
        "verdict_hint": normalize_str(item.get("verdict_hint")),
        "category": normalize_finding_category(item),
        "score": item.get("score"),
        "reasoning_summary": normalize_str(item.get("reasoning_summary")),
        "reason_hints": normalize_reason_hints(item.get("reason_hints")),
        "evidence_fields": normalize_string_list(item.get("evidence_fields")),
        "recommended_actions": normalize_string_list(item.get("recommended_actions")),
        "response_body_bytes": item.get("response_body_bytes"),
        "resp_content_type": normalize_str(item.get("resp_content_type")),
        "handler": normalize_str(item.get("handler")),
        "log_schema": normalize_str(item.get("log_schema")),
        "raw_request_target": normalize_str(item.get("raw_request_target")),
        "raw_request": normalize_str(item.get("raw_request")),
        "path_normalized_from_raw_request": bool(item.get("path_normalized_from_raw_request")),
        "likely_html_fallback_response": bool(item.get("likely_html_fallback_response")),
        "hpp_detected": bool(item.get("hpp_detected")),
        "hpp_param_names": ensure_list(item.get("hpp_param_names")),
        "embedded_attack_hint": normalize_str(item.get("embedded_attack_hint")),
        "user_agent": normalize_str(item.get("user_agent")),
        "merged_row_count": item.get("merged_row_count"),
        "merged_source_tables": ensure_list(item.get("merged_source_tables")),
        "merged_log_ids": ensure_list(item.get("merged_log_ids")),
    }
    if raw_match:
        finding["raw_export_match"] = {
            "source_table": normalize_str(first_non_empty(raw_match.get("_source_table"), raw_match.get("source_table"))),
            "log_id": first_non_empty(raw_match.get("id"), raw_match.get("log_id")),
            "request_id": normalize_str(raw_match.get("request_id")),
        }
        if include_raw_log:
            raw_log = normalize_str(raw_match.get("raw_log"))
            if raw_log:
                finding["raw_log"] = raw_log
    return finding


def build_context_item(context_type: str, item: Dict[str, Any]) -> Dict[str, Any]:
    context_item = dict(item)
    context_item["context_type"] = context_type
    context_item["context_only"] = True
    context_item["should_promote_to_candidate"] = item.get("should_promote_to_candidate")
    context_item["guardrail_note"] = (
        "Preserve should_promote_to_candidate as source metadata only; the viewer must not auto-promote this context into a candidate or finding."
    )
    return context_item


def build_supporting_event(
    item: Dict[str, Any],
    raw_match: Optional[Dict[str, Any]],
    include_raw_log: bool,
) -> Dict[str, Any]:
    event = dict(item)
    event["context_only"] = True
    event["reason_hints"] = normalize_reason_hints(item.get("reason_hints"))
    event["guardrail_note"] = "Supporting events are context-only and must not be promoted into incidents by the viewer."
    if raw_match:
        if not normalize_str(event.get("log_time")):
            event["log_time"] = normalize_str(raw_match.get("log_time"))
        if not normalize_str(event.get("method")):
            event["method"] = normalize_str(raw_match.get("method"))
        if not normalize_str(event.get("uri")):
            event["uri"] = normalize_str(raw_match.get("uri"))
        if event.get("status_code") in (None, ""):
            event["status_code"] = raw_match.get("status_code")
        if not normalize_str(event.get("user_agent")):
            event["user_agent"] = normalize_str(raw_match.get("user_agent"))
        if include_raw_log:
            raw_log = normalize_str(raw_match.get("raw_log"))
            if raw_log:
                event["raw_log"] = raw_log
    return event


def build_noise(
    stage2_report_input: Dict[str, Any],
    llm_input_payload: Dict[str, Any],
    noise_summary_payload: Any,
) -> Dict[str, Any]:
    distributions = ensure_dict(stage2_report_input.get("distributions"))
    noise: Dict[str, Any] = {
        "filtered_out_breakdown": ensure_dict(distributions.get("filtered_out_breakdown")),
        "top_filtered_categories": ensure_list(stage2_report_input.get("top_filtered_categories")),
        "top_out_of_candidate_recon": ensure_list(stage2_report_input.get("top_out_of_candidate_recon")),
    }
    if isinstance(noise_summary_payload, (dict, list)):
        noise["noise_summary_file"] = noise_summary_payload
    llm_noise_summary = llm_input_payload.get("noise_summary")
    if isinstance(llm_noise_summary, (dict, list)):
        noise["llm_input_noise_summary"] = llm_noise_summary
    return noise


def main() -> int:
    args = parse_args()

    stage2_report_input_path = Path(args.stage2_report_input).expanduser().resolve()
    if not stage2_report_input_path.exists():
        raise FileNotFoundError(f"stage2_report_input 파일을 찾을 수 없습니다: {stage2_report_input_path}")

    stage2_report_payload = ensure_dict(load_json(args.stage2_report)) if args.stage2_report else {}
    stage2_report_input = ensure_dict(load_json(str(stage2_report_input_path)))
    stage1_results_payload = ensure_dict(load_json(args.stage1_results)) if args.stage1_results and Path(args.stage1_results).exists() else {}
    llm_input_payload = ensure_dict(load_json(args.llm_input)) if args.llm_input and Path(args.llm_input).exists() else {}
    noise_summary_payload: Any = None
    if args.noise_summary and Path(args.noise_summary).exists():
        noise_summary_payload = load_json(args.noise_summary)
    raw_export_payload: Any = None
    if args.raw_export and Path(args.raw_export).exists():
        raw_export_payload = load_json(args.raw_export)

    raw_rows = raw_export_rows(raw_export_payload)
    raw_lookup = build_lookup(raw_rows)

    stage1_results = [item for item in ensure_list(stage1_results_payload.get("results")) if isinstance(item, dict)]
    stage1_lookup = build_lookup(stage1_results)
    analysis_candidates = [item for item in ensure_list(llm_input_payload.get("analysis_candidates")) if isinstance(item, dict)]
    candidate_lookup = build_lookup(analysis_candidates)

    finding_source_name, finding_source_items = select_findings_source(stage2_report_input, stage1_results_payload, llm_input_payload)

    findings: List[Dict[str, Any]] = []
    for source_item in finding_source_items:
        stage1_match = lookup_match(source_item, stage1_lookup)
        candidate_match = lookup_match(source_item, candidate_lookup)
        merged = merge_missing(merge_missing(dict(source_item), stage1_match), candidate_match)
        raw_match = lookup_match(merged, raw_lookup)
        findings.append(build_finding(merged, finding_source_name, raw_match=raw_match, include_raw_log=bool(args.include_raw_log)))

    contexts: List[Dict[str, Any]] = []
    seen_context_keys = set()
    for source_payload in (stage2_report_input, llm_input_payload):
        for collection_name, context_type in CONTEXT_COLLECTIONS:
            for item in ensure_list(source_payload.get(collection_name)):
                if not isinstance(item, dict):
                    continue
                key = build_context_key(context_type, item)
                if key in seen_context_keys:
                    continue
                seen_context_keys.add(key)
                contexts.append(build_context_item(context_type, item))

    supporting_events: List[Dict[str, Any]] = []
    seen_event_keys = set()
    for source_payload in (stage2_report_input, llm_input_payload):
        for item in ensure_list(source_payload.get("supporting_events")):
            if not isinstance(item, dict):
                continue
            key = build_event_key(item)
            if key in seen_event_keys:
                continue
            seen_event_keys.add(key)
            raw_match = lookup_match(item, raw_lookup)
            supporting_events.append(build_supporting_event(item, raw_match=raw_match, include_raw_log=bool(args.include_raw_log)))

    report_fields = extract_report_fields(stage2_report_payload)
    pipeline_counts = ensure_dict(stage2_report_input.get("pipeline_counts"))
    warnings: List[str] = []
    candidate_rows = safe_int(pipeline_counts.get("candidate_rows"), 0)
    if candidate_rows and candidate_rows != len(findings):
        warnings.append(
            "pipeline_counts.candidate_rows and findings length differ; this can happen when top_incidents is capped or resume inputs are partial."
        )
    if not ensure_dict(stage2_report_payload.get("report")):
        warnings.append("stage2_report.report is empty or null; report sections were populated conservatively from available inputs.")

    payload = {
        "schema_version": "viewer_payload.v1",
        "meta": {
            "generated_at": iso_now(),
            "source_of_truth": {
                "findings": finding_source_name,
                "contexts": "stage2_report_input + llm_input context-only collections",
                "supporting_events": "stage2_report_input.supporting_events + llm_input.supporting_events",
            },
            "include_raw_log": bool(args.include_raw_log),
        },
        "summary": {
            "report_title": report_fields.get("report_title"),
            "overall_assessment": report_fields.get("overall_assessment"),
            "executive_summary": report_fields.get("executive_summary"),
            "pipeline_counts": pipeline_counts,
            "finding_count": len(findings),
            "context_count": len(contexts),
            "supporting_event_count": len(supporting_events),
        },
        "report": report_fields,
        "findings": findings,
        "contexts": contexts,
        "supporting_events": supporting_events,
        "noise": build_noise(stage2_report_input, llm_input_payload, noise_summary_payload),
        "policies": {
            "policy_notes": ensure_dict(stage2_report_input.get("policy_notes")),
            "apache_logs_only": True,
            "guardrails": APACHE_GUARDRAILS,
        },
        "source_files": {
            "stage2_report": normalize_path(args.stage2_report),
            "stage2_report_input": normalize_path(args.stage2_report_input),
            "stage1_results": normalize_path(args.stage1_results),
            "llm_input": normalize_path(args.llm_input),
            "raw_export": normalize_path(args.raw_export),
            "noise_summary": normalize_path(args.noise_summary),
            "out": normalize_path(args.out),
        },
        "integrity": {
            "finding_count": len(findings),
            "context_count": len(contexts),
            "supporting_event_count": len(supporting_events),
            "warnings": warnings,
        },
    }

    dump_json(args.out, payload, pretty=args.pretty)
    print(f"[OK] viewer_payload: {Path(args.out).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
