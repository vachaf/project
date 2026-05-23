#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a summary artifact for a single sliding-window prepare result.

This module intentionally summarizes existing export/prepare artifacts only. It
must not create new security verdicts, infer attack success, infer response/body
contents, or promote context-only data into findings.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = "sliding_window_summary_v1"
CONTEXT_COUNT_KEYS = (
    "supporting_events",
    "false_positive_review_candidates",
    "probing_sequence_summaries",
    "static_baseline_summaries",
    "crawler_baseline_summaries",
    "sensitive_path_probe_summaries",
    "mixed_baseline_scanner_summaries",
    "ip_behavior_aggregates",
    "auth_behavior_summaries",
    "method_behavior_summaries",
    "protocol_anomaly_summaries",
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def get_nested(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def counter_to_dict(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): count for key, count in sorted(counter.items(), key=lambda item: str(item[0]))}


def reason_hint_prefix(hint: Any) -> str:
    if not isinstance(hint, str):
        return ""
    text = hint.strip()
    if not text:
        return ""
    return text.split(":", 1)[0].split("(", 1)[0].strip()


def reason_hint_prefixes(reason_hints: Iterable[Any]) -> list[str]:
    prefixes: list[str] = []
    seen: set[str] = set()
    for hint in reason_hints:
        prefix = reason_hint_prefix(hint)
        if prefix and prefix not in seen:
            prefixes.append(prefix)
            seen.add(prefix)
    return prefixes


def count_distribution(candidates: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[Any] = Counter()
    for item in candidates:
        value = item.get(field)
        if value is not None and value != "":
            counter[value] += 1
    return counter_to_dict(counter)


def reason_prefix_distribution(candidates: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in candidates:
        for prefix in reason_hint_prefixes(as_list(item.get("reason_hints"))):
            counter[prefix] += 1
    return counter_to_dict(counter)


def build_candidate_index(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    index: list[dict[str, Any]] = []
    for item in candidates:
        index.append(
            {
                "request_id": item.get("request_id"),
                "src_ip": item.get("src_ip"),
                "method": item.get("method"),
                "uri": item.get("uri"),
                "status_code": item.get("status_code"),
                "score": item.get("score"),
                "verdict_hint": item.get("verdict_hint"),
                "reason_hint_prefixes": reason_hint_prefixes(as_list(item.get("reason_hints"))),
            }
        )
    return index


def context_summary_count(prepare_counts: Mapping[str, Any]) -> int:
    total = 0
    for key in CONTEXT_COUNT_KEYS:
        value = prepare_counts.get(key, 0)
        if isinstance(value, int):
            total += value
    return total


def build_artifact_status(window_dir: Path) -> dict[str, dict[str, Any]]:
    artifacts = {
        "export": "export.json",
        "llm_input": "llm_input.json",
        "analysis_candidates": "analysis_candidates.json",
        "noise_summary": "noise_summary.json",
        "window_summary": "window_summary.json",
    }
    return {
        name: {
            "path": filename,
            "exists": (window_dir / filename).exists(),
        }
        for name, filename in artifacts.items()
    }


def build_window_summary(
    *,
    window_plan: Mapping[str, Any],
    window_dir: Path,
    export_payload: Mapping[str, Any],
    llm_input_payload: Mapping[str, Any],
    analysis_candidates_payload: Any,
    noise_summary_payload: Any,
) -> dict[str, Any]:
    export_meta = as_mapping(export_payload.get("meta"))
    export_counts = as_mapping(export_payload.get("counts"))
    llm_meta = as_mapping(llm_input_payload.get("meta"))
    prepare_counts = as_mapping(llm_meta.get("counts"))
    candidates = [item for item in as_list(analysis_candidates_payload) if isinstance(item, dict)]
    noise_groups = as_list(noise_summary_payload)

    candidate_request_ids = [
        item.get("request_id")
        for item in candidates
        if item.get("request_id") not in (None, "")
    ]

    selected_source_tables = as_list(llm_meta.get("selected_source_tables"))
    analysis_primary_table = llm_meta.get("analysis_primary_table")
    filtered_out_breakdown = as_mapping(llm_meta.get("filtered_out_breakdown"))

    return {
        "schema": SCHEMA,
        "window": {
            "window_id": window_plan.get("window_id"),
            "start": window_plan.get("start") or get_nested(llm_meta, "analysis_window", "start") or export_meta.get("start"),
            "end_exclusive": window_plan.get("end") or get_nested(llm_meta, "analysis_window", "end_exclusive") or export_meta.get("end_exclusive"),
            "timezone": llm_meta.get("query_timezone") or export_meta.get("query_timezone"),
            "duration_minutes": window_plan.get("duration_minutes"),
            "is_partial": bool(window_plan.get("is_partial", False)),
        },
        "artifact_status": build_artifact_status(window_dir),
        "source": {
            "database": export_meta.get("database") or llm_meta.get("source_database"),
            "table_option": export_meta.get("table_option") or llm_meta.get("source_table_option"),
            "selected_source_tables": selected_source_tables,
            "analysis_primary_table": analysis_primary_table,
        },
        "counts": {
            "export": {
                "access": export_counts.get("access", 0),
                "security": export_counts.get("security", 0),
                "error": export_counts.get("error", 0),
                "total": export_meta.get("total_count", sum(v for v in export_counts.values() if isinstance(v, int))),
            },
            "prepare": {
                "total_exported_rows": prepare_counts.get("total_exported_rows", 0),
                "selected_source_rows": prepare_counts.get("selected_source_rows", 0),
                "filtered_out_rows": prepare_counts.get("filtered_out_rows", 0),
                "candidate_rows_before_dedup": prepare_counts.get("candidate_rows_before_dedup", 0),
                "candidate_rows": prepare_counts.get("candidate_rows", len(candidates)),
                "candidate_duplicate_rows_removed": prepare_counts.get("candidate_duplicate_rows_removed", 0),
                "distinct_incident_candidates": prepare_counts.get("distinct_incident_candidates", len(candidates)),
                "noise_group_count": prepare_counts.get("noise_group_count", len(noise_groups)),
                "supporting_events": prepare_counts.get("supporting_events", 0),
                "context_summary_count": context_summary_count(prepare_counts),
            },
        },
        "distributions": {
            "candidate_status_code": count_distribution(candidates, "status_code"),
            "candidate_method": count_distribution(candidates, "method"),
            "candidate_verdict_hint": count_distribution(candidates, "verdict_hint"),
            "candidate_src_ip": count_distribution(candidates, "src_ip"),
            "candidate_uri": count_distribution(candidates, "uri"),
            "candidate_reason_hint_prefix": reason_prefix_distribution(candidates),
            "filtered_out_breakdown": filtered_out_breakdown,
        },
        "candidate_index": build_candidate_index(candidates),
        "rollup_hints": {
            "has_candidates": bool(candidates),
            "has_noise_groups": bool(noise_groups),
            "has_supporting_events": bool(prepare_counts.get("supporting_events", 0)),
            "has_context_summaries": context_summary_count(prepare_counts) > 0,
            "candidate_request_ids": candidate_request_ids,
        },
        "guardrails": {
            "summary_only": True,
            "no_new_security_verdict": True,
            "no_success_inference": True,
            "no_body_inference": True,
            "no_context_promotion": True,
        },
    }


def build_window_summary_from_dir(window_plan: Mapping[str, Any], window_dir: Path) -> dict[str, Any]:
    return build_window_summary(
        window_plan=window_plan,
        window_dir=window_dir,
        export_payload=load_json(window_dir / "export.json"),
        llm_input_payload=load_json(window_dir / "llm_input.json"),
        analysis_candidates_payload=load_json(window_dir / "analysis_candidates.json"),
        noise_summary_payload=load_json(window_dir / "noise_summary.json"),
    )


def write_window_summary(window_plan: Mapping[str, Any], window_dir: Path) -> Path:
    summary = build_window_summary_from_dir(window_plan, window_dir)
    output_path = window_dir / "window_summary.json"
    write_json(output_path, summary)
    return output_path
