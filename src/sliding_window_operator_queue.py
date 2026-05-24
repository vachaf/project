#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sliding Window Operator Queue builder.

v1 scope
- Read rollup_input.json and rollup_summary.json artifacts.
- Build queue_items.json and queue_summary.json under data/operator_queue/<date>/.
- Route rollups into quiet / needs_review / data_quality_check states.
- Mark LLM eligibility without requiring LLM execution.
- Use atomic writes and conservative output reuse policy.

This module intentionally does not run Stage1/Stage2, does not run any LLM
reporter, does not create Web UI state, and must not generate security verdicts,
confidence levels, threat levels, or success/intrusion conclusions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo

QUEUE_ITEMS_SCHEMA = "sliding_window_operator_queue_items_v1"
QUEUE_ITEM_SCHEMA = "sliding_window_operator_queue_item_v1"
QUEUE_SUMMARY_SCHEMA = "sliding_window_operator_queue_summary_v1"
ROLLUP_INPUT_SCHEMA = "sliding_window_rollup_input_v1"
ROLLUP_SUMMARY_SCHEMA = "sliding_window_rollup_summary_v1"
DEFAULT_TIMEZONE = "Asia/Seoul"
DEFAULT_ROLLUP_ROOT = "data/rollups"
DEFAULT_OUT_ROOT = "data/operator_queue"
QUEUE_OUTPUT_NAMES = (
    "queue_items.json",
    "queue_summary.json",
)
TOP_OBSERVED_LIMIT = 5
PAYLOAD_LIKE_REASON_HINTS: set[str] = {
    "sqli",
    "sqli_hint",
    "xss",
    "xss_hint",
    "path_traversal_candidate",
    "cmdi_hint",
    "hpp_hint",
    "php_wrapper_hint",
    "file_disclosure_hint",
    "log4shell_jndi_hint",
    "ssrf_like_target",
    "ssti_hint",
    "xxe_hint",
    "webshell_like",
}
GUARDRAILS = {
    "summary_only": True,
    "apache_logs_only": True,
    "no_success_inference": True,
    "no_body_inference": True,
    "no_context_promotion": True,
    "no_new_security_verdict": True,
}


class PartialExistingQueueArtifactsError(RuntimeError):
    """Raised when only some queue artifacts exist and overwrite is disabled."""

    def __init__(self, out_dir: Path, existing: list[str], missing: list[str]) -> None:
        self.out_dir = out_dir
        self.existing = existing
        self.missing = missing
        super().__init__(
            "partial existing operator queue artifacts: "
            f"out_dir={out_dir} existing={existing} missing={missing}"
        )


def as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_under_work_dir(work_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (work_dir / path).resolve()


def path_for_display(path: Path, work_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(work_dir.resolve()))
    except ValueError:
        return str(path)


def now_iso(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def atomic_write_json(path: Path, payload: Mapping[str, Any], *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if pretty else None
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=indent) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def queue_output_paths(out_dir: Path) -> dict[str, Path]:
    return {name: out_dir / name for name in QUEUE_OUTPUT_NAMES}


def classify_queue_outputs(out_dir: Path) -> tuple[str, list[str], list[str]]:
    paths = queue_output_paths(out_dir)
    existing = [name for name, path in paths.items() if path.exists()]
    missing = [name for name, path in paths.items() if not path.exists()]
    if len(existing) == len(paths):
        return "all", existing, missing
    if existing:
        return "partial", existing, missing
    return "none", existing, missing


def load_existing_queue_counts(out_dir: Path) -> dict[str, Any]:
    summary_path = out_dir / "queue_summary.json"
    if not summary_path.exists():
        return {}
    try:
        payload = load_json(summary_path)
    except Exception:
        return {}
    return as_mapping(payload).get("counts", {}) if isinstance(payload, dict) else {}


def discover_rollup_dirs(*, work_dir: Path, date: str, rollup_root: str) -> list[Path]:
    root = resolve_under_work_dir(work_dir, rollup_root) / date
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and path.name.startswith("rollup_"))


def top_observed_from_distribution(distribution: Mapping[str, Any], *, limit: int = TOP_OBSERVED_LIMIT) -> list[dict[str, Any]]:
    items: list[tuple[str, int]] = []
    for key, value in distribution.items():
        if isinstance(value, int):
            items.append((str(key), value))
    items.sort(key=lambda item: (-item[1], item[0]))
    return [{"value": key, "count": count} for key, count in items[:limit]]


def has_repeated(distribution: Mapping[str, Any], *, threshold: int = 2) -> bool:
    return any(isinstance(value, int) and value >= threshold for value in distribution.values())


def derive_top_observed(rollup_input: Mapping[str, Any], *, limit: int = TOP_OBSERVED_LIMIT) -> dict[str, list[dict[str, Any]]]:
    distributions = as_mapping(rollup_input.get("distributions"))
    return {
        "src_ip": top_observed_from_distribution(as_mapping(distributions.get("candidate_src_ip")), limit=limit),
        "uri": top_observed_from_distribution(as_mapping(distributions.get("candidate_uri")), limit=limit),
        "reason_hint_prefix": top_observed_from_distribution(
            as_mapping(distributions.get("candidate_reason_hint_prefix")),
            limit=limit,
        ),
        "status_code": top_observed_from_distribution(
            as_mapping(distributions.get("candidate_status_code")),
            limit=limit,
        ),
    }


def has_payload_like_reason_hint(rollup_input: Mapping[str, Any]) -> bool:
    distribution = as_mapping(as_mapping(rollup_input.get("distributions")).get("candidate_reason_hint_prefix"))
    return any(key in PAYLOAD_LIKE_REASON_HINTS and isinstance(value, int) and value > 0 for key, value in distribution.items())


def derive_data_quality_status(
    *,
    rollup_input: Optional[Mapping[str, Any]],
    rollup_summary: Optional[Mapping[str, Any]],
    input_missing: bool,
    summary_missing: bool,
) -> str:
    if input_missing or summary_missing:
        return "missing_rollup_artifact"

    if not rollup_input or rollup_input.get("schema") != ROLLUP_INPUT_SCHEMA:
        return "degraded_invalid_window"
    if not rollup_summary or rollup_summary.get("schema") != ROLLUP_SUMMARY_SCHEMA:
        return "degraded_invalid_window"

    source_windows = as_list(rollup_summary.get("source_windows"))
    if any(isinstance(item, dict) and item.get("status") == "failed" for item in source_windows):
        return "degraded_invalid_window"

    counts = as_mapping(rollup_summary.get("counts"))
    if rollup_summary.get("incomplete_analysis") is True:
        return "incomplete_missing_window"
    if isinstance(counts.get("windows_missing_or_failed"), int) and counts["windows_missing_or_failed"] > 0:
        return "incomplete_missing_window"

    return "complete"


def derive_signals(*, rollup_input: Mapping[str, Any], counts: Mapping[str, Any], data_quality_status: str) -> dict[str, bool]:
    distributions = as_mapping(rollup_input.get("distributions"))
    candidate_src_ip = as_mapping(distributions.get("candidate_src_ip"))
    candidate_uri = as_mapping(distributions.get("candidate_uri"))
    candidate_reason_hint_prefix = as_mapping(distributions.get("candidate_reason_hint_prefix"))

    candidate_index_count = counts.get("candidate_index_count", 0)
    windows_missing_or_failed = counts.get("windows_missing_or_failed", 0)
    possible_duplicate_count = counts.get("possible_duplicate_count", 0)

    return {
        "has_candidates": isinstance(candidate_index_count, int) and candidate_index_count > 0,
        "has_missing_windows": isinstance(windows_missing_or_failed, int) and windows_missing_or_failed > 0,
        "has_possible_duplicates": isinstance(possible_duplicate_count, int) and possible_duplicate_count > 0,
        "has_repeated_src_ip": has_repeated(candidate_src_ip),
        "has_repeated_uri": has_repeated(candidate_uri),
        "has_repeated_reason_hint_prefix": has_repeated(candidate_reason_hint_prefix),
        "has_payload_like_reason_hint": has_payload_like_reason_hint(rollup_input),
        "is_quiet": data_quality_status == "complete" and isinstance(candidate_index_count, int) and candidate_index_count == 0,
    }


def derive_review_status(*, data_quality_status: str, counts: Mapping[str, Any]) -> str:
    if data_quality_status != "complete":
        return "data_quality_check"
    candidate_index_count = counts.get("candidate_index_count", 0)
    if isinstance(candidate_index_count, int) and candidate_index_count == 0:
        return "quiet"
    return "needs_review"


def derive_llm_eligible(*, data_quality_status: str, counts: Mapping[str, Any], signals: Mapping[str, bool]) -> bool:
    candidate_index_count = counts.get("candidate_index_count", 0)
    if data_quality_status != "complete":
        return False
    if not isinstance(candidate_index_count, int) or candidate_index_count <= 0:
        return False
    return bool(
        signals.get("has_payload_like_reason_hint")
        or signals.get("has_repeated_src_ip")
        or signals.get("has_repeated_uri")
        or signals.get("has_repeated_reason_hint_prefix")
    )


def derive_recommended_action(*, data_quality_status: str, review_status: str, llm_eligible: bool) -> str:
    if data_quality_status != "complete":
        return "data_quality_check"
    if review_status == "quiet":
        return "skip_no_candidates"
    if review_status == "needs_review" and llm_eligible:
        return "review_before_optional_briefing"
    return "review_rollup_summary"


def zero_counts() -> dict[str, int]:
    return {
        "window_count": 0,
        "windows_successfully_loaded": 0,
        "windows_missing_or_failed": 0,
        "candidate_rows_total": 0,
        "candidate_index_count": 0,
        "dedup_removed_by_request_id": 0,
        "possible_duplicate_count": 0,
        "noise_group_count_total": 0,
    }


def normalize_counts(counts: Mapping[str, Any]) -> dict[str, int]:
    base = zero_counts()
    for key in base:
        value = counts.get(key, 0)
        base[key] = value if isinstance(value, int) else 0
    return base


def build_missing_item(*, date: str, work_dir: Path, rollup_dir: Path, generated_at: str) -> dict[str, Any]:
    rollup_id = rollup_dir.name
    rollup_input_path = rollup_dir / "rollup_input.json"
    rollup_summary_path = rollup_dir / "rollup_summary.json"
    counts = zero_counts()
    data_quality_status = "missing_rollup_artifact"
    review_status = "data_quality_check"
    signals = derive_signals(rollup_input={}, counts=counts, data_quality_status=data_quality_status)
    return {
        "schema": QUEUE_ITEM_SCHEMA,
        "queue_date": date,
        "generated_at": generated_at,
        "rollup_id": rollup_id,
        "rollup_path": path_for_display(rollup_input_path, work_dir),
        "rollup_summary_path": path_for_display(rollup_summary_path, work_dir),
        "time_range": {},
        "data_quality_status": data_quality_status,
        "review_status": review_status,
        "operator_state": "unreviewed",
        "llm_eligible": False,
        "llm_required": False,
        "recommended_action": "data_quality_check",
        "counts": counts,
        "signals": signals,
        "top_observed": {"src_ip": [], "uri": [], "reason_hint_prefix": [], "status_code": []},
        "guardrails": GUARDRAILS,
    }


def build_queue_item(*, date: str, work_dir: Path, rollup_dir: Path, generated_at: str) -> dict[str, Any]:
    rollup_input_path = rollup_dir / "rollup_input.json"
    rollup_summary_path = rollup_dir / "rollup_summary.json"
    input_missing = not rollup_input_path.exists()
    summary_missing = not rollup_summary_path.exists()

    if input_missing or summary_missing:
        return build_missing_item(date=date, work_dir=work_dir, rollup_dir=rollup_dir, generated_at=generated_at)

    rollup_input: Optional[dict[str, Any]]
    rollup_summary: Optional[dict[str, Any]]
    try:
        loaded_input = load_json(rollup_input_path)
        rollup_input = loaded_input if isinstance(loaded_input, dict) else None
    except Exception:
        rollup_input = None
    try:
        loaded_summary = load_json(rollup_summary_path)
        rollup_summary = loaded_summary if isinstance(loaded_summary, dict) else None
    except Exception:
        rollup_summary = None

    data_quality_status = derive_data_quality_status(
        rollup_input=rollup_input,
        rollup_summary=rollup_summary,
        input_missing=False,
        summary_missing=False,
    )
    counts = normalize_counts(as_mapping(as_mapping(rollup_summary).get("counts")))
    signals = derive_signals(rollup_input=as_mapping(rollup_input), counts=counts, data_quality_status=data_quality_status)
    review_status = derive_review_status(data_quality_status=data_quality_status, counts=counts)
    llm_eligible = derive_llm_eligible(data_quality_status=data_quality_status, counts=counts, signals=signals)
    recommended_action = derive_recommended_action(
        data_quality_status=data_quality_status,
        review_status=review_status,
        llm_eligible=llm_eligible,
    )
    rollup = as_mapping(as_mapping(rollup_summary).get("rollup"))

    return {
        "schema": QUEUE_ITEM_SCHEMA,
        "queue_date": date,
        "generated_at": generated_at,
        "rollup_id": rollup.get("rollup_id") or rollup_dir.name,
        "rollup_path": path_for_display(rollup_input_path, work_dir),
        "rollup_summary_path": path_for_display(rollup_summary_path, work_dir),
        "time_range": {
            "start": rollup.get("start"),
            "end_exclusive": rollup.get("end_exclusive"),
            "timezone": rollup.get("timezone"),
            "duration_minutes": rollup.get("duration_minutes"),
        }
        if rollup
        else {},
        "data_quality_status": data_quality_status,
        "review_status": review_status,
        "operator_state": "unreviewed",
        "llm_eligible": llm_eligible,
        "llm_required": False,
        "recommended_action": recommended_action,
        "counts": counts,
        "signals": signals,
        "top_observed": derive_top_observed(as_mapping(rollup_input)),
        "guardrails": GUARDRAILS,
    }


def count_items(items: list[dict[str, Any]]) -> dict[str, int]:
    review_status = Counter(str(item.get("review_status")) for item in items)
    data_quality_status = Counter(str(item.get("data_quality_status")) for item in items)
    operator_state = Counter(str(item.get("operator_state")) for item in items)
    return {
        "rollup_items_total": len(items),
        "quiet": review_status.get("quiet", 0),
        "needs_review": review_status.get("needs_review", 0),
        "data_quality_check": review_status.get("data_quality_check", 0),
        "complete": data_quality_status.get("complete", 0),
        "incomplete_missing_window": data_quality_status.get("incomplete_missing_window", 0),
        "degraded_invalid_window": data_quality_status.get("degraded_invalid_window", 0),
        "missing_rollup_artifact": data_quality_status.get("missing_rollup_artifact", 0),
        "llm_eligible": sum(1 for item in items if item.get("llm_eligible") is True),
        "llm_required": sum(1 for item in items if item.get("llm_required") is True),
        "unreviewed": operator_state.get("unreviewed", 0),
        "reviewed": operator_state.get("reviewed", 0),
        "deferred": operator_state.get("deferred", 0),
    }


def build_queue_payloads(
    *,
    work_dir: Path,
    date: str,
    rollup_root: str,
    out_root: str,
    timezone: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = now_iso(timezone)
    rollup_dirs = discover_rollup_dirs(work_dir=work_dir, date=date, rollup_root=rollup_root)
    items = [build_queue_item(date=date, work_dir=work_dir, rollup_dir=rollup_dir, generated_at=generated_at) for rollup_dir in rollup_dirs]
    source_rollup_root = resolve_under_work_dir(work_dir, rollup_root) / date
    out_dir = resolve_under_work_dir(work_dir, out_root) / date
    items_path = out_dir / "queue_items.json"

    items_payload = {
        "schema": QUEUE_ITEMS_SCHEMA,
        "queue_date": date,
        "generated_at": generated_at,
        "source_rollup_root": path_for_display(source_rollup_root, work_dir),
        "items": items,
        "guardrails": GUARDRAILS,
    }
    summary_payload = {
        "schema": QUEUE_SUMMARY_SCHEMA,
        "queue_date": date,
        "generated_at": generated_at,
        "source_rollup_root": path_for_display(source_rollup_root, work_dir),
        "counts": count_items(items),
        "items_path": path_for_display(items_path, work_dir),
        "guardrails": GUARDRAILS,
    }
    return items_payload, summary_payload


def write_queue_artifacts(
    *,
    out_dir: Path,
    items_payload: Mapping[str, Any],
    summary_payload: Mapping[str, Any],
    pretty: bool = False,
) -> None:
    atomic_write_json(out_dir / "queue_items.json", items_payload, pretty=pretty)
    atomic_write_json(out_dir / "queue_summary.json", summary_payload, pretty=pretty)


def build_and_write_queue(
    *,
    work_dir: Path,
    date: str,
    rollup_root: str,
    out_root: str,
    timezone: str,
    pretty: bool,
    overwrite: bool = False,
) -> dict[str, Any]:
    out_dir = resolve_under_work_dir(work_dir, out_root) / date
    output_state, existing, missing = classify_queue_outputs(out_dir)
    result_base = {
        "queue_date": date,
        "out_dir": path_for_display(out_dir, work_dir),
        "queue_items_path": path_for_display(out_dir / "queue_items.json", work_dir),
        "queue_summary_path": path_for_display(out_dir / "queue_summary.json", work_dir),
    }

    if output_state == "all" and not overwrite:
        return {
            **result_base,
            "status": "skipped_existing",
            "existing_outputs": existing,
            "missing_outputs": missing,
            "counts": load_existing_queue_counts(out_dir),
        }

    if output_state == "partial" and not overwrite:
        raise PartialExistingQueueArtifactsError(out_dir, existing, missing)

    items_payload, summary_payload = build_queue_payloads(
        work_dir=work_dir,
        date=date,
        rollup_root=rollup_root,
        out_root=out_root,
        timezone=timezone,
    )
    write_queue_artifacts(out_dir=out_dir, items_payload=items_payload, summary_payload=summary_payload, pretty=pretty)
    return {
        **result_base,
        "status": "written",
        "existing_outputs": existing,
        "missing_outputs": missing,
        "counts": summary_payload["counts"],
    }


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Sliding Window operator queue artifacts")
    parser.add_argument("--work-dir", default=".", help="repository/work root")
    parser.add_argument("--date", required=True, help="queue date in YYYY-MM-DD")
    parser.add_argument("--rollup-root", default=DEFAULT_ROLLUP_ROOT)
    parser.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing queue artifacts")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON artifacts")
    parser.add_argument("--json", action="store_true", help="print JSON summary")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    work_dir = Path(args.work_dir).expanduser().resolve()
    try:
        result = build_and_write_queue(
            work_dir=work_dir,
            date=args.date,
            rollup_root=args.rollup_root,
            out_root=args.out_root,
            timezone=args.timezone,
            pretty=args.pretty,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(f"[QUEUE] ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    else:
        if result["status"] == "skipped_existing":
            print(f"[QUEUE] skip existing: {result['out_dir']}")
        print(f"[QUEUE] status={result['status']}")
        print(f"[QUEUE] date={result['queue_date']}")
        print(f"[QUEUE] out_dir={result['out_dir']}")
        print(f"[QUEUE] queue_items={result['queue_items_path']}")
        print(f"[QUEUE] queue_summary={result['queue_summary_path']}")
        counts = result.get("counts", {})
        print(
            "[QUEUE] summary: "
            f"status={result['status']} "
            f"rollup_items_total={counts.get('rollup_items_total', 0)} "
            f"quiet={counts.get('quiet', 0)} "
            f"needs_review={counts.get('needs_review', 0)} "
            f"data_quality_check={counts.get('data_quality_check', 0)} "
            f"llm_eligible={counts.get('llm_eligible', 0)} "
            f"llm_required={counts.get('llm_required', 0)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
