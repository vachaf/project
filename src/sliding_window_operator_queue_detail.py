#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic Operator Queue item detail preview.

This script reads data/operator_queue/<date>/queue_items.json, selects one
queue item by rollup_id, and renders a human-readable detail preview to stdout.

It intentionally does not create artifacts, does not run Stage1/Stage2, does not
call any LLM, and must not generate security verdicts, success conclusions,
threat scores, confidence levels, or incident classifications.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

DEFAULT_QUEUE_ROOT = "data/operator_queue"
QUEUE_ITEMS_FILENAME = "queue_items.json"
DETAIL_VIEW_SCHEMA = "sliding_window_operator_queue_item_detail_view_v1"
APACHE_LOGS_ONLY_NOTES = [
    "This detail view is derived from Apache log artifacts only.",
    "It does not include raw POST body, response body, DB result, browser execution, or server-side application state.",
    "HTTP 200, text/html, response_body_bytes, or repeated requests are not success evidence by themselves.",
    "Review status, LLM eligibility, and recommended action are routing signals, not security verdicts.",
]
NON_CONCLUSIONS = [
    "This detail view does not conclude attack success, intrusion, data exposure, account takeover, upload persistence, browser execution, DB impact, or server compromise.",
]


class QueueDetailError(RuntimeError):
    """Base class for queue detail preview errors."""


class QueueItemsNotFoundError(QueueDetailError):
    """Raised when queue_items.json is missing."""


class QueueItemNotFoundError(QueueDetailError):
    """Raised when a requested rollup_id is not present in queue_items.json."""


class InvalidQueueItemsError(QueueDetailError):
    """Raised when queue_items.json has an unsupported shape."""


def as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_under_work_dir(work_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (work_dir / path).resolve()


def queue_items_path(*, work_dir: Path, date: str, queue_root: str) -> Path:
    return resolve_under_work_dir(work_dir, queue_root) / date / QUEUE_ITEMS_FILENAME


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_queue_items_payload(*, work_dir: Path, date: str, queue_root: str = DEFAULT_QUEUE_ROOT) -> dict[str, Any]:
    path = queue_items_path(work_dir=work_dir, date=date, queue_root=queue_root)
    if not path.exists():
        raise QueueItemsNotFoundError(f"queue_items.json not found: {path}")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise InvalidQueueItemsError(f"queue_items.json must be a JSON object: {path}")
    items = payload.get("items")
    if not isinstance(items, list):
        raise InvalidQueueItemsError(f"queue_items.json missing list field 'items': {path}")
    return payload


def find_queue_item(payload: Mapping[str, Any], rollup_id: str) -> dict[str, Any]:
    for item in as_list(payload.get("items")):
        if isinstance(item, dict) and item.get("rollup_id") == rollup_id:
            return item
    available = [str(item.get("rollup_id")) for item in as_list(payload.get("items")) if isinstance(item, dict) and item.get("rollup_id")]
    suffix = f" available={available}" if available else " available=[]"
    raise QueueItemNotFoundError(f"rollup_id not found in queue_items.json: {rollup_id}{suffix}")


def bool_label(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def value_or_dash(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def format_top_entries(entries: Any) -> str:
    values: list[str] = []
    for entry in as_list(entries):
        if not isinstance(entry, dict):
            continue
        value = value_or_dash(entry.get("value"))
        count = entry.get("count")
        if isinstance(count, int):
            values.append(f"{value} ({count})")
        else:
            values.append(value)
    return ", ".join(values) if values else "-"


def build_detail_view(*, queue_payload: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    time_range = as_mapping(item.get("time_range"))
    counts = as_mapping(item.get("counts"))
    signals = as_mapping(item.get("signals"))
    top_observed = as_mapping(item.get("top_observed"))
    rollup_id = value_or_dash(item.get("rollup_id"))
    source_selection = as_mapping(queue_payload.get("source_selection"))

    return {
        "schema": DETAIL_VIEW_SCHEMA,
        "queue_date": queue_payload.get("queue_date") or item.get("queue_date"),
        "rollup_id": rollup_id,
        "summary": {
            "time_range": {
                "start": time_range.get("start"),
                "end_exclusive": time_range.get("end_exclusive"),
                "timezone": time_range.get("timezone"),
                "duration_minutes": time_range.get("duration_minutes"),
            },
            "review_status": item.get("review_status"),
            "data_quality_status": item.get("data_quality_status"),
            "recommended_action": item.get("recommended_action"),
            "llm_eligible": item.get("llm_eligible"),
            "llm_required": item.get("llm_required"),
        },
        "quality_assessment": {
            "status": item.get("data_quality_status"),
            "missing_or_failed_windows": counts.get("windows_missing_or_failed", 0),
            "possible_duplicates_marked": counts.get("possible_duplicate_count", 0),
            "dedup_removed_by_request_id": counts.get("dedup_removed_by_request_id", 0),
        },
        "routing": {
            "review_status": item.get("review_status"),
            "operator_state": item.get("operator_state"),
            "recommended_action": item.get("recommended_action"),
            "llm_eligible": item.get("llm_eligible"),
            "llm_required": item.get("llm_required"),
        },
        "counts": {
            "window_count": counts.get("window_count", 0),
            "windows_successfully_loaded": counts.get("windows_successfully_loaded", 0),
            "windows_missing_or_failed": counts.get("windows_missing_or_failed", 0),
            "candidate_rows_total": counts.get("candidate_rows_total", 0),
            "candidate_index_count": counts.get("candidate_index_count", 0),
            "dedup_removed_by_request_id": counts.get("dedup_removed_by_request_id", 0),
            "possible_duplicate_count": counts.get("possible_duplicate_count", 0),
            "noise_group_count_total": counts.get("noise_group_count_total", 0),
        },
        "observed_signals": {
            "has_candidates": signals.get("has_candidates"),
            "has_payload_like_reason_hint": signals.get("has_payload_like_reason_hint"),
            "has_repeated_src_ip": signals.get("has_repeated_src_ip"),
            "has_repeated_uri": signals.get("has_repeated_uri"),
            "has_repeated_reason_hint_prefix": signals.get("has_repeated_reason_hint_prefix"),
            "has_missing_windows": signals.get("has_missing_windows"),
            "has_possible_duplicates": signals.get("has_possible_duplicates"),
            "is_quiet": signals.get("is_quiet"),
        },
        "top_observed": {
            "src_ip": as_list(top_observed.get("src_ip")),
            "uri": as_list(top_observed.get("uri")),
            "reason_hint_prefix": as_list(top_observed.get("reason_hint_prefix")),
            "status_code": as_list(top_observed.get("status_code")),
        },
        "drilldown": {
            "rollup_input_path": item.get("rollup_path"),
            "rollup_summary_path": item.get("rollup_summary_path"),
            "candidate_source": "rollup_input.candidate_index",
        },
        "source_selection": source_selection,
        "apache_logs_only_notes": APACHE_LOGS_ONLY_NOTES,
        "non_conclusions": NON_CONCLUSIONS,
        "guardrails": as_mapping(item.get("guardrails")),
    }


def render_text(detail: Mapping[str, Any]) -> str:
    summary = as_mapping(detail.get("summary"))
    time_range = as_mapping(summary.get("time_range"))
    quality = as_mapping(detail.get("quality_assessment"))
    routing = as_mapping(detail.get("routing"))
    counts = as_mapping(detail.get("counts"))
    signals = as_mapping(detail.get("observed_signals"))
    top_observed = as_mapping(detail.get("top_observed"))
    drilldown = as_mapping(detail.get("drilldown"))
    source_selection = as_mapping(detail.get("source_selection"))

    lines = [
        "Operator Queue Item Detail",
        "==========================",
        f"Rollup ID: {value_or_dash(detail.get('rollup_id'))}",
        f"Queue date: {value_or_dash(detail.get('queue_date'))}",
        "",
        "1. Data quality",
        f"- status: {value_or_dash(quality.get('status'))}",
        f"- missing_or_failed_windows: {value_or_dash(quality.get('missing_or_failed_windows'))}",
        f"- possible_duplicates_marked: {value_or_dash(quality.get('possible_duplicates_marked'))}",
        f"- dedup_removed_by_request_id: {value_or_dash(quality.get('dedup_removed_by_request_id'))}",
        "",
        "2. Review routing",
        f"- review_status: {value_or_dash(routing.get('review_status'))}",
        f"- operator_state: {value_or_dash(routing.get('operator_state'))}",
        f"- recommended_action: {value_or_dash(routing.get('recommended_action'))}",
        f"- llm_eligible: {bool_label(routing.get('llm_eligible'))}",
        f"- llm_required: {bool_label(routing.get('llm_required'))}",
        "",
        "3. Scope",
        f"- start: {value_or_dash(time_range.get('start'))}",
        f"- end_exclusive: {value_or_dash(time_range.get('end_exclusive'))}",
        f"- timezone: {value_or_dash(time_range.get('timezone'))}",
        f"- duration_minutes: {value_or_dash(time_range.get('duration_minutes'))}",
        "",
        "4. Counts",
    ]
    for key in (
        "window_count",
        "windows_successfully_loaded",
        "windows_missing_or_failed",
        "candidate_rows_total",
        "candidate_index_count",
        "dedup_removed_by_request_id",
        "possible_duplicate_count",
        "noise_group_count_total",
    ):
        lines.append(f"- {key}: {value_or_dash(counts.get(key))}")

    lines.extend([
        "",
        "5. Observed signals",
    ])
    for key in (
        "has_candidates",
        "has_payload_like_reason_hint",
        "has_repeated_src_ip",
        "has_repeated_uri",
        "has_repeated_reason_hint_prefix",
        "has_missing_windows",
        "has_possible_duplicates",
        "is_quiet",
    ):
        lines.append(f"- {key}: {bool_label(signals.get(key))}")

    lines.extend([
        "",
        "6. Top observed distributions",
        f"- src_ip: {format_top_entries(top_observed.get('src_ip'))}",
        f"- uri: {format_top_entries(top_observed.get('uri'))}",
        f"- reason_hint_prefix: {format_top_entries(top_observed.get('reason_hint_prefix'))}",
        f"- status_code: {format_top_entries(top_observed.get('status_code'))}",
        "",
        "7. Drilldown",
        f"- rollup_input_path: {value_or_dash(drilldown.get('rollup_input_path'))}",
        f"- rollup_summary_path: {value_or_dash(drilldown.get('rollup_summary_path'))}",
        f"- candidate_source: {value_or_dash(drilldown.get('candidate_source'))}",
        "",
        "8. Source selection",
        f"- rollup_root: {value_or_dash(source_selection.get('rollup_root'))}",
        f"- rollup_pattern: {value_or_dash(source_selection.get('rollup_pattern'))}",
        f"- matched_rollup_count: {value_or_dash(source_selection.get('matched_rollup_count'))}",
        "",
        "9. Apache logs-only notes",
    ])
    lines.extend(f"- {note}" for note in as_list(detail.get("apache_logs_only_notes")))
    lines.extend([
        "",
        "10. Non-conclusions",
    ])
    lines.extend(f"- {note}" for note in as_list(detail.get("non_conclusions")))
    return "\n".join(lines) + "\n"


def render_markdown(detail: Mapping[str, Any]) -> str:
    text = render_text(detail)
    lines = text.rstrip("\n").splitlines()
    converted: list[str] = []
    for index, line in enumerate(lines):
        if index == 0:
            converted.append(f"# {line}")
        elif index == 1 and set(line) == {"="}:
            continue
        elif line[:3].replace(".", "").isdigit() and ". " in line:
            converted.append(f"## {line}")
        else:
            converted.append(line)
    return "\n".join(converted) + "\n"


def build_detail_for_rollup(*, work_dir: Path, date: str, queue_root: str, rollup_id: str) -> dict[str, Any]:
    payload = load_queue_items_payload(work_dir=work_dir, date=date, queue_root=queue_root)
    item = find_queue_item(payload, rollup_id)
    return build_detail_view(queue_payload=payload, item=item)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview one Operator Queue item in a human-readable detail format")
    parser.add_argument("--work-dir", default=".", help="repository/work root")
    parser.add_argument("--date", required=True, help="queue date in YYYY-MM-DD")
    parser.add_argument("--queue-root", default=DEFAULT_QUEUE_ROOT, help="operator queue root directory")
    parser.add_argument("--rollup-id", required=True, help="rollup_id to preview")
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text", help="stdout format")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    work_dir = Path(args.work_dir).expanduser().resolve()
    try:
        detail = build_detail_for_rollup(
            work_dir=work_dir,
            date=args.date,
            queue_root=args.queue_root,
            rollup_id=args.rollup_id,
        )
    except QueueDetailError as exc:
        print(f"[QUEUE_DETAIL] ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[QUEUE_DETAIL] ERROR: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(detail, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(render_markdown(detail), end="")
    else:
        print(render_text(detail), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
