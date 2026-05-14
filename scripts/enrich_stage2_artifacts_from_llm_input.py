#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enrich Stage2 dry-run artifacts from prepare llm_input candidates.

Purpose
- Fix observability/raw-log dry-run artifacts where stage2_report_input.top_incidents
  or viewer_payload.findings lost request metadata that was still present in
  llm_input.analysis_candidates.

Typical use
  python3 scripts/enrich_stage2_artifacts_from_llm_input.py \
    --llm-input data/processed/security_llm_input.json \
    --stage2-report-input reports/security_stage2_report_input.json \
    --viewer-payload reports/security_viewer_payload.json \
    --pretty

Scope
- This is a deterministic enrichment helper. It does not infer success, severity,
  compromise, file exposure, login result, upload result, or DB effect.
- It only fills missing or placeholder fields from already-prepared candidate
  evidence matched by request_id / incident_group_key / source_table:log_id.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PLACEHOLDER_STRINGS = {"", "-", "None", "null"}
PLACEHOLDER_NUMBERS = {None, 0}

TEXT_FIELDS = [
    "method",
    "raw_request",
    "query_string",
    "raw_request_target",
    "resp_content_type",
    "user_agent",
    "referer",
    "duration_us",
    "ttfb_us",
    "handler",
    "log_schema",
]

NUMERIC_FIELDS = [
    "response_body_bytes",
    "status_code",
    "score",
]

LIST_FIELDS = [
    "reason_hints",
    "evidence_fields",
    "hpp_param_names",
    "recommended_actions",
]

BOOL_FIELDS = [
    "path_normalized_from_raw_request",
    "likely_html_fallback_response",
    "hpp_detected",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich Stage2 artifacts from llm_input.analysis_candidates.")
    parser.add_argument("--llm-input", required=True, help="prepare output <base>_llm_input.json")
    parser.add_argument("--stage2-report-input", required=True, help="Stage2 input JSON to enrich in place unless --out-stage2-report-input is set")
    parser.add_argument("--viewer-payload", default=None, help="Optional viewer_payload JSON to enrich in place unless --out-viewer-payload is set")
    parser.add_argument("--out-stage2-report-input", default=None, help="Optional output path for enriched Stage2 input")
    parser.add_argument("--out-viewer-payload", default=None, help="Optional output path for enriched viewer payload")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON outputs")
    parser.add_argument("--dry-run", action="store_true", help="Report planned changes without writing files")
    return parser.parse_args()


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return payload


def dump_json(path: str, payload: Any, pretty: bool) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)
        if pretty:
            f.write("\n")


def norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_missing_text(value: Any) -> bool:
    return norm(value) in PLACEHOLDER_STRINGS


def is_missing_number(value: Any) -> bool:
    return value in PLACEHOLDER_NUMBERS


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def merge_unique(existing: Iterable[Any], incoming: Iterable[Any]) -> List[Any]:
    result: List[Any] = []
    seen = set()
    for value in list(existing) + list(incoming):
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def build_candidate_lookup(llm_input: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    candidates = llm_input.get("analysis_candidates") or []
    if not isinstance(candidates, list):
        candidates = []

    by_request_id: Dict[str, Dict[str, Any]] = {}
    by_incident_group_key: Dict[str, Dict[str, Any]] = {}
    by_source_log: Dict[str, Dict[str, Any]] = {}

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        request_id = norm(candidate.get("request_id"))
        incident_group_key = norm(candidate.get("incident_group_key"))
        source_table = norm(candidate.get("source_table"))
        log_id = norm(candidate.get("log_id"))

        if request_id:
            by_request_id.setdefault(request_id, candidate)
        if incident_group_key:
            by_incident_group_key.setdefault(incident_group_key, candidate)
        if source_table and log_id and log_id != "-":
            by_source_log.setdefault(f"{source_table}:{log_id}", candidate)

    return {
        "by_request_id": by_request_id,
        "by_incident_group_key": by_incident_group_key,
        "by_source_log": by_source_log,
    }


def find_candidate(item: Dict[str, Any], lookup: Dict[str, Dict[str, Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    incident_group_key = norm(item.get("incident_group_key"))
    if incident_group_key and incident_group_key in lookup["by_incident_group_key"]:
        return lookup["by_incident_group_key"][incident_group_key]

    request_id = norm(item.get("request_id"))
    if request_id and request_id in lookup["by_request_id"]:
        return lookup["by_request_id"][request_id]

    source_table = norm(item.get("source_table"))
    log_id = norm(item.get("log_id"))
    if source_table and log_id and log_id != "-":
        return lookup["by_source_log"].get(f"{source_table}:{log_id}")
    return None


def infer_category(item: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    verdict_hint = norm(item.get("verdict_hint")) or norm(candidate.get("verdict_hint"))
    verdict = norm(item.get("verdict"))
    hints = [norm(x).lower() for x in as_list(item.get("reason_hints")) + as_list(candidate.get("reason_hints"))]
    joined = " ".join(hints + [verdict_hint.lower(), verdict.lower()])

    if "traversal" in joined or "path_traversal" in joined:
        return "path_traversal_candidate"
    if "sqli" in joined or "sql" in joined or "likely_sqli" in joined:
        return "sqli_candidate"
    if "xss" in joined or "script" in joined or "likely_xss" in joined:
        return "xss_candidate"
    if verdict_hint:
        return f"{verdict_hint}_candidate"
    return norm(item.get("category")) or "candidate"


def enrich_item(item: Dict[str, Any], candidate: Optional[Dict[str, Any]]) -> int:
    if not candidate:
        return 0
    changed = 0

    for field in TEXT_FIELDS:
        incoming = candidate.get(field)
        if incoming is not None and is_missing_text(item.get(field)) and not is_missing_text(incoming):
            item[field] = incoming
            changed += 1

    for field in NUMERIC_FIELDS:
        incoming = candidate.get(field)
        if incoming is not None and is_missing_number(item.get(field)) and not is_missing_number(incoming):
            item[field] = incoming
            changed += 1

    for field in BOOL_FIELDS:
        if field not in item and field in candidate:
            item[field] = bool(candidate.get(field))
            changed += 1

    for field in LIST_FIELDS:
        existing = as_list(item.get(field))
        incoming = as_list(candidate.get(field))
        merged = merge_unique(existing, incoming)
        if merged != existing:
            item[field] = merged
            changed += 1

    # Keep verdict_hint if the item omitted it.
    if is_missing_text(item.get("verdict_hint")) and not is_missing_text(candidate.get("verdict_hint")):
        item["verdict_hint"] = candidate.get("verdict_hint")
        changed += 1

    # Fix obvious category mismatches from reason_hints/verdict_hint.
    inferred_category = infer_category(item, candidate)
    if inferred_category and norm(item.get("category")) != inferred_category:
        if is_missing_text(item.get("category")) or norm(item.get("category")) in {"xss_candidate", "sqli_candidate", "path_traversal_candidate", "candidate"}:
            item["category"] = inferred_category
            changed += 1

    return changed


def enrich_stage2_report_input(payload: Dict[str, Any], lookup: Dict[str, Dict[str, Dict[str, Any]]]) -> int:
    changed = 0
    top_incidents = payload.get("top_incidents")
    if not isinstance(top_incidents, list):
        return changed
    for item in top_incidents:
        if not isinstance(item, dict):
            continue
        changed += enrich_item(item, find_candidate(item, lookup))
    return changed


def enrich_viewer_payload(payload: Dict[str, Any], lookup: Dict[str, Dict[str, Dict[str, Any]]]) -> int:
    changed = 0
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return changed
    for item in findings:
        if not isinstance(item, dict):
            continue
        changed += enrich_item(item, find_candidate(item, lookup))
    return changed


def main() -> int:
    args = parse_args()
    llm_input = load_json(args.llm_input)
    lookup = build_candidate_lookup(llm_input)

    stage2 = load_json(args.stage2_report_input)
    stage2_changes = enrich_stage2_report_input(stage2, lookup)
    stage2_out = args.out_stage2_report_input or args.stage2_report_input

    viewer_changes = 0
    viewer = None
    viewer_out = None
    if args.viewer_payload:
        viewer = load_json(args.viewer_payload)
        viewer_changes = enrich_viewer_payload(viewer, lookup)
        viewer_out = args.out_viewer_payload or args.viewer_payload

    print(f"[INFO] stage2_report_input changes={stage2_changes}")
    print(f"[INFO] viewer_payload changes={viewer_changes}")

    if args.dry_run:
        print("[OK] dry-run only; no files written")
        return 0

    dump_json(stage2_out, stage2, pretty=args.pretty)
    print(f"[OK] wrote: {stage2_out}")
    if viewer is not None and viewer_out is not None:
        dump_json(viewer_out, viewer, pretty=args.pretty)
        print(f"[OK] wrote: {viewer_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
