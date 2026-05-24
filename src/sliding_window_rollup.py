#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sliding Window rollup artifact builder.

v1.0 scope
- Read window_summary.json artifacts.
- Record missing/invalid window status.
- Merge candidate_index entries.
- Deduplicate only by request_id.
- Preserve candidates without request_id.
- Mark fallback duplicates without removing them.
- Merge simple distributions.
- Write rollup_input.json, dedup_candidates.json, and rollup_summary.json.

This module intentionally does not run Stage1/Stage2, does not create runs/, and
must not generate new security verdicts, scores, confidence levels, threat
levels, uri-family hints, or low-and-slow hints.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional
from zoneinfo import ZoneInfo

SCHEMA = "sliding_window_rollup_input_v1"
DEDUP_SCHEMA = "sliding_window_dedup_candidates_v1"
SUMMARY_SCHEMA = "sliding_window_rollup_summary_v1"
WINDOW_SUMMARY_SCHEMA = "sliding_window_summary_v1"
DEFAULT_TIMEZONE = "Asia/Seoul"
DEFAULT_WINDOW_OUTPUT_ROOT = "data/windowed"
DEFAULT_ROLLUP_OUTPUT_ROOT = "data/rollups"
DEFAULT_WINDOW_MINUTES = 60
DEFAULT_STRIDE_MINUTES = 60
DISTRIBUTION_KEYS = (
    "candidate_status_code",
    "candidate_method",
    "candidate_verdict_hint",
    "candidate_src_ip",
    "candidate_uri",
    "candidate_reason_hint_prefix",
    "filtered_out_breakdown",
)


def parse_datetime_text(text: str, tz: ZoneInfo) -> datetime:
    value = text.strip()
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
        )
        dt: Optional[datetime] = None
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            raise ValueError(f"invalid datetime: {text!r}")
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def fmt_dt(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


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


def make_window_id(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return f"sw_{start.strftime('%H%M')}_{end.strftime('%H%M')}"
    return f"sw_{start.strftime('%Y%m%d_%H%M')}_{end.strftime('%Y%m%d_%H%M')}"


def make_rollup_id(start: datetime, end: datetime) -> str:
    return f"rollup_{start.strftime('%Y%m%d_%H%M')}_{end.strftime('%H%M')}"


def generate_windows(
    *,
    analysis_start: datetime,
    analysis_end: datetime,
    window_minutes: int,
    stride_minutes: int,
    include_partial_final: bool = False,
) -> list[tuple[datetime, datetime]]:
    if window_minutes <= 0:
        raise ValueError("window-minutes must be positive")
    if stride_minutes <= 0:
        raise ValueError("stride-minutes must be positive")

    window_delta = timedelta(minutes=window_minutes)
    stride_delta = timedelta(minutes=stride_minutes)
    windows: list[tuple[datetime, datetime]] = []
    current = analysis_start
    while current < analysis_end:
        candidate_end = current + window_delta
        if candidate_end <= analysis_end:
            windows.append((current, candidate_end))
        elif include_partial_final:
            windows.append((current, analysis_end))
        next_start = current + stride_delta
        if next_start <= current:
            raise ValueError("stride did not advance window start")
        current = next_start
    return windows


def discover_window_summary_paths(
    *,
    work_dir: Path,
    analysis_start: str,
    analysis_end: str,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    stride_minutes: int = DEFAULT_STRIDE_MINUTES,
    timezone: str = DEFAULT_TIMEZONE,
    window_output_root: str = DEFAULT_WINDOW_OUTPUT_ROOT,
    include_partial_final: bool = False,
) -> list[Path]:
    tz = ZoneInfo(timezone)
    start = parse_datetime_text(analysis_start, tz)
    end = parse_datetime_text(analysis_end, tz)
    root = resolve_under_work_dir(work_dir, window_output_root)
    paths: list[Path] = []
    for window_start, window_end in generate_windows(
        analysis_start=start,
        analysis_end=end,
        window_minutes=window_minutes,
        stride_minutes=stride_minutes,
        include_partial_final=include_partial_final,
    ):
        window_id = make_window_id(window_start, window_end)
        date_dir = window_start.strftime("%Y-%m-%d")
        paths.append(root / date_dir / window_id / "window_summary.json")
    return paths


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Mapping[str, Any], *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if pretty else None
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_window_summaries(
    window_summary_paths: list[Path],
    *,
    work_dir: Path,
    strict: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []

    for path in window_summary_paths:
        display_path = path_for_display(path, work_dir)
        if not path.exists():
            status = {
                "window_id": None,
                "path": display_path,
                "status": "missing",
                "reason": "window_summary_not_found",
            }
            statuses.append(status)
            if strict:
                raise FileNotFoundError(f"window summary not found: {path}")
            continue

        try:
            payload = load_json(path)
        except Exception as exc:
            status = {
                "window_id": None,
                "path": display_path,
                "status": "failed",
                "reason": f"invalid_json: {exc}",
            }
            statuses.append(status)
            if strict:
                raise
            continue

        if not isinstance(payload, dict) or payload.get("schema") != WINDOW_SUMMARY_SCHEMA:
            window_id = as_mapping(payload.get("window") if isinstance(payload, dict) else {}).get("window_id")
            status = {
                "window_id": window_id,
                "path": display_path,
                "status": "failed",
                "reason": "unsupported_schema",
                "schema": payload.get("schema") if isinstance(payload, dict) else None,
            }
            statuses.append(status)
            if strict:
                raise ValueError(f"unsupported window summary schema: {path}")
            continue

        window = as_mapping(payload.get("window"))
        artifact_status = as_mapping(payload.get("artifact_status"))
        statuses.append(
            {
                "window_id": window.get("window_id"),
                "path": display_path,
                "start": window.get("start"),
                "end_exclusive": window.get("end_exclusive"),
                "artifact_status": {
                    key: bool(as_mapping(value).get("exists"))
                    for key, value in artifact_status.items()
                },
                "status": "loaded",
            }
        )
        summaries.append(payload)

    return summaries, statuses


def sorted_unique(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if value not in (None, "")})


def fallback_key(candidate: Mapping[str, Any]) -> str:
    reason_prefixes = candidate.get("reason_hint_prefixes")
    if isinstance(reason_prefixes, list):
        reason_part = ",".join(sorted(str(item) for item in reason_prefixes if item not in (None, "")))
    else:
        reason_part = ""
    return "|".join(
        [
            str(candidate.get("src_ip") or ""),
            str(candidate.get("method") or ""),
            str(candidate.get("uri") or ""),
            str(candidate.get("status_code") or ""),
            reason_part,
        ]
    )


def merge_candidate_index(window_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for summary in window_summaries:
        window_id = as_mapping(summary.get("window")).get("window_id")
        path = as_mapping(summary.get("source_window_status", {})).get("path")
        for candidate in as_list(summary.get("candidate_index")):
            if not isinstance(candidate, dict):
                continue
            item = {
                "request_id": candidate.get("request_id"),
                "src_ip": candidate.get("src_ip"),
                "method": candidate.get("method"),
                "uri": candidate.get("uri"),
                "status_code": candidate.get("status_code"),
                "score": candidate.get("score"),
                "verdict_hint": candidate.get("verdict_hint"),
                "reason_hint_prefixes": as_list(candidate.get("reason_hint_prefixes")),
                "source_window_ids": [window_id] if window_id else [],
            }
            if path:
                item["source_window_paths"] = [path]
            merged.append(item)
    return merged


def find_possible_duplicates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        key = fallback_key(candidate)
        if key.strip("|"):
            groups[key].append(candidate)

    possible: list[dict[str, Any]] = []
    for key, items in sorted(groups.items(), key=lambda item: item[0]):
        if len(items) < 2:
            continue
        possible.append(
            {
                "fallback_key": key,
                "request_ids": sorted_unique(item.get("request_id") for item in items),
                "source_window_ids": sorted_unique(
                    window_id
                    for item in items
                    for window_id in as_list(item.get("source_window_ids"))
                ),
                "count": len(items),
                "action": "marked_only_not_removed",
            }
        )
    return possible


def dedup_candidates_by_request_id(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_request_id: dict[str, dict[str, Any]] = {}
    missing_request_id: list[dict[str, Any]] = []
    duplicate_request_ids: list[dict[str, Any]] = []

    for candidate in candidates:
        req_id = str(candidate.get("request_id") or "").strip()
        if not req_id:
            preserved = dict(candidate)
            preserved["dedup_status"] = "preserved_missing_request_id"
            preserved["aggregation_type"] = "preserved_missing_request_id"
            missing_request_id.append(preserved)
            continue

        if req_id not in by_request_id:
            kept = dict(candidate)
            kept["source_window_ids"] = sorted_unique(kept.get("source_window_ids", []))
            kept["aggregation_type"] = "single_window_existing_candidate"
            by_request_id[req_id] = kept
            continue

        kept = by_request_id[req_id]
        source_window_ids = set(as_list(kept.get("source_window_ids")))
        source_window_ids.update(as_list(candidate.get("source_window_ids")))
        kept["source_window_ids"] = sorted_unique(source_window_ids)
        kept["aggregation_type"] = "cross_window_same_request_id"
        duplicate_request_ids.append(
            {
                "request_id": req_id,
                "source_window_ids": kept["source_window_ids"],
                "kept_source_window_id": kept["source_window_ids"][0] if kept["source_window_ids"] else None,
                "removed_count": 1,
                "action": "merged_by_request_id",
            }
        )

    deduped = list(by_request_id.values()) + missing_request_id
    possible_duplicates = find_possible_duplicates(deduped)
    removed_by_request_id = len(candidates) - len(deduped)

    report = {
        "primary_key": "request_id",
        "fallback_key": [
            "src_ip",
            "method",
            "uri",
            "status_code",
            "reason_hint_prefixes",
        ],
        "input_count": len(candidates),
        "output_count": len(deduped),
        "removed_by_request_id": removed_by_request_id,
        "missing_request_id_preserved": len(missing_request_id),
        "duplicate_request_ids": duplicate_request_ids,
        "possible_duplicates": possible_duplicates,
    }
    return deduped, report


def aggregate_distributions(window_summaries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counters: dict[str, Counter[str]] = {key: Counter() for key in DISTRIBUTION_KEYS}
    for summary in window_summaries:
        distributions = as_mapping(summary.get("distributions"))
        for key in DISTRIBUTION_KEYS:
            values = as_mapping(distributions.get(key))
            for item_key, item_value in values.items():
                if isinstance(item_value, int):
                    counters[key][str(item_key)] += item_value
    return {
        key: {str(item_key): count for item_key, count in sorted(counter.items(), key=lambda item: str(item[0]))}
        for key, counter in counters.items()
    }


def sum_nested_count(window_summaries: list[dict[str, Any]], section: str, key: str) -> int:
    total = 0
    for summary in window_summaries:
        value = as_mapping(as_mapping(summary.get("counts")).get(section)).get(key, 0)
        if isinstance(value, int):
            total += value
    return total


def build_rollup_id(start_text: str, end_text: str, timezone: str) -> str:
    tz = ZoneInfo(timezone)
    start = parse_datetime_text(start_text, tz)
    end = parse_datetime_text(end_text, tz)
    return make_rollup_id(start, end)


def default_rollup_out_dir(
    *,
    work_dir: Path,
    rollup_output_root: str,
    analysis_start: str,
    analysis_end: str,
    timezone: str,
) -> Path:
    tz = ZoneInfo(timezone)
    start = parse_datetime_text(analysis_start, tz)
    end = parse_datetime_text(analysis_end, tz)
    root = resolve_under_work_dir(work_dir, rollup_output_root)
    date_dir = start.strftime("%Y-%m-%d")
    rollup_id = make_rollup_id(start, end)
    return root / date_dir / rollup_id


def build_rollup_input(
    *,
    rollup_id: str,
    analysis_start: str,
    analysis_end: str,
    timezone: str,
    duration_minutes: int,
    window_summaries: list[dict[str, Any]],
    window_load_status: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    merged_candidates = merge_candidate_index(window_summaries)
    deduped_candidates, dedup_report = dedup_candidates_by_request_id(merged_candidates)
    distributions = aggregate_distributions(window_summaries)
    loaded_count = sum(1 for item in window_load_status if item.get("status") == "loaded")
    failed_count = len(window_load_status) - loaded_count
    request_ids = [str(candidate.get("request_id")) for candidate in merged_candidates if candidate.get("request_id")]
    distinct_request_ids = sorted(set(request_ids))

    counts = {
        "window_count": len(window_load_status),
        "windows_successfully_loaded": loaded_count,
        "windows_missing_or_failed": failed_count,
        "export_total": sum_nested_count(window_summaries, "export", "total"),
        "prepare_total_exported_rows": sum_nested_count(window_summaries, "prepare", "total_exported_rows"),
        "candidate_rows_total": len(merged_candidates),
        "candidate_request_ids_total": len(request_ids),
        "candidate_request_ids_distinct": len(distinct_request_ids),
        "dedup_removed_by_request_id": dedup_report["removed_by_request_id"],
        "possible_duplicate_count": len(dedup_report["possible_duplicates"]),
        "noise_group_count_total": sum_nested_count(window_summaries, "prepare", "noise_group_count"),
        "candidate_index_count": len(deduped_candidates),
    }

    guardrails = {
        "summary_only": True,
        "apache_logs_only": True,
        "no_new_security_verdict": True,
        "no_success_inference": True,
        "no_body_inference": True,
        "no_context_promotion": True,
        "no_policy_recalculation": True,
        "preserve_prepare_scores": True,
    }

    rollup_input = {
        "schema": SCHEMA,
        "rollup": {
            "rollup_id": rollup_id,
            "start": analysis_start,
            "end_exclusive": analysis_end,
            "timezone": timezone,
            "duration_minutes": duration_minutes,
        },
        "source_windows": window_load_status,
        "counts": counts,
        "dedup": dedup_report,
        "distributions": distributions,
        "candidate_index": deduped_candidates,
        "rollup_context": {
            "notes": [
                "rollup_context is informational only",
                "v1.0 does not generate uri_family_hints or low_and_slow_hints",
                "rollup does not promote context to candidate",
            ]
        },
        "guardrails": guardrails,
    }

    dedup_candidates = {
        "schema": DEDUP_SCHEMA,
        "rollup_id": rollup_id,
        "dedup": dedup_report,
        "candidate_index": deduped_candidates,
        "guardrails": guardrails,
    }

    rollup_summary = {
        "schema": SUMMARY_SCHEMA,
        "rollup": rollup_input["rollup"],
        "counts": counts,
        "source_windows": window_load_status,
        "guardrails": guardrails,
        "incomplete_analysis": failed_count > 0,
    }
    return rollup_input, dedup_candidates, rollup_summary


def write_rollup_artifacts(
    *,
    out_dir: Path,
    rollup_input: dict[str, Any],
    dedup_candidates: dict[str, Any],
    rollup_summary: dict[str, Any],
    pretty: bool = False,
) -> None:
    write_json(out_dir / "rollup_input.json", rollup_input, pretty=pretty)
    write_json(out_dir / "dedup_candidates.json", dedup_candidates, pretty=pretty)
    write_json(out_dir / "rollup_summary.json", rollup_summary, pretty=pretty)


def build_and_write_rollup(
    *,
    work_dir: Path,
    analysis_start: str,
    analysis_end: str,
    window_minutes: int,
    stride_minutes: int,
    timezone: str,
    window_output_root: str,
    rollup_output_root: str,
    out_dir: Optional[Path],
    strict: bool,
    pretty: bool,
    include_partial_final: bool = False,
) -> dict[str, Any]:
    tz = ZoneInfo(timezone)
    start_dt = parse_datetime_text(analysis_start, tz)
    end_dt = parse_datetime_text(analysis_end, tz)
    if start_dt >= end_dt:
        raise ValueError("analysis-start must be earlier than analysis-end")
    duration_minutes = int((end_dt - start_dt).total_seconds() // 60)
    normalized_start = fmt_dt(start_dt)
    normalized_end = fmt_dt(end_dt)
    rollup_id = make_rollup_id(start_dt, end_dt)

    paths = discover_window_summary_paths(
        work_dir=work_dir,
        analysis_start=normalized_start,
        analysis_end=normalized_end,
        window_minutes=window_minutes,
        stride_minutes=stride_minutes,
        timezone=timezone,
        window_output_root=window_output_root,
        include_partial_final=include_partial_final,
    )
    summaries, statuses = load_window_summaries(paths, work_dir=work_dir, strict=strict)
    rollup_input, dedup_candidates, rollup_summary = build_rollup_input(
        rollup_id=rollup_id,
        analysis_start=normalized_start,
        analysis_end=normalized_end,
        timezone=timezone,
        duration_minutes=duration_minutes,
        window_summaries=summaries,
        window_load_status=statuses,
    )
    output_dir = out_dir or default_rollup_out_dir(
        work_dir=work_dir,
        rollup_output_root=rollup_output_root,
        analysis_start=normalized_start,
        analysis_end=normalized_end,
        timezone=timezone,
    )
    if not output_dir.is_absolute():
        output_dir = work_dir / output_dir
    write_rollup_artifacts(
        out_dir=output_dir,
        rollup_input=rollup_input,
        dedup_candidates=dedup_candidates,
        rollup_summary=rollup_summary,
        pretty=pretty,
    )
    return {
        "rollup_id": rollup_id,
        "out_dir": path_for_display(output_dir, work_dir),
        "rollup_input_path": path_for_display(output_dir / "rollup_input.json", work_dir),
        "dedup_candidates_path": path_for_display(output_dir / "dedup_candidates.json", work_dir),
        "rollup_summary_path": path_for_display(output_dir / "rollup_summary.json", work_dir),
        "counts": rollup_input["counts"],
    }


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Sliding Window rollup input artifacts")
    parser.add_argument("--work-dir", default=".", help="repository/work root")
    parser.add_argument("--analysis-start", required=True, help="rollup start time")
    parser.add_argument("--analysis-end", required=True, help="rollup end time")
    parser.add_argument("--window-minutes", type=int, default=DEFAULT_WINDOW_MINUTES)
    parser.add_argument("--stride-minutes", type=int, default=DEFAULT_STRIDE_MINUTES)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--window-output-root", default=DEFAULT_WINDOW_OUTPUT_ROOT)
    parser.add_argument("--rollup-output-root", default=DEFAULT_ROLLUP_OUTPUT_ROOT)
    parser.add_argument("--out-dir", default=None, help="explicit output directory")
    parser.add_argument("--include-partial-final", action="store_true")
    parser.add_argument("--strict", action="store_true", help="fail on missing/invalid window_summary")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON artifacts")
    parser.add_argument("--json", action="store_true", help="print JSON summary")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    work_dir = Path(args.work_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else None
    try:
        result = build_and_write_rollup(
            work_dir=work_dir,
            analysis_start=args.analysis_start,
            analysis_end=args.analysis_end,
            window_minutes=args.window_minutes,
            stride_minutes=args.stride_minutes,
            timezone=args.timezone,
            window_output_root=args.window_output_root,
            rollup_output_root=args.rollup_output_root,
            out_dir=out_dir,
            strict=args.strict,
            pretty=args.pretty,
            include_partial_final=args.include_partial_final,
        )
    except Exception as exc:
        print(f"[ROLLUP] ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    else:
        print(f"[ROLLUP] rollup_id={result['rollup_id']}")
        print(f"[ROLLUP] out_dir={result['out_dir']}")
        print(f"[ROLLUP] rollup_input={result['rollup_input_path']}")
        print(f"[ROLLUP] dedup_candidates={result['dedup_candidates_path']}")
        print(f"[ROLLUP] rollup_summary={result['rollup_summary_path']}")
        counts = result["counts"]
        print(
            "[ROLLUP] summary: "
            f"windows_loaded={counts['windows_successfully_loaded']} "
            f"windows_missing_or_failed={counts['windows_missing_or_failed']} "
            f"candidate_rows_total={counts['candidate_rows_total']} "
            f"candidate_index_count={counts['candidate_index_count']} "
            f"dedup_removed_by_request_id={counts['dedup_removed_by_request_id']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
