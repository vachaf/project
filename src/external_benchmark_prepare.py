#!/usr/bin/env python3
"""Prepare-only runner for the pinned external security benchmark.

The adapter in this module only represents a normalized request as a neutral
Apache ``security`` export row.  Candidate selection remains entirely owned by
the production :func:`src.prepare_llm_input.build_outputs` implementation.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.external_benchmark_crs import (
    BenchmarkContractError,
    build_normalized_benchmark_cases,
    load_benchmark_manifest,
    load_owasp_crs_cases,
)
from src.prepare_llm_input import build_outputs


RESULT_SCHEMA_VERSION = "external_security_benchmark_prepare_result.v1"
BENCHMARK_NAME = "owasp_crs_path_file_access.v1"
SOURCE_TABLE = "security"
PREPARE_MIN_SCORE = 4
PREPARE_MIN_REPEAT_AGGREGATE = 3
SYNTHETIC_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=9)))
SYNTHETIC_INTERVAL = timedelta(hours=1)

DOCUMENTATION_NETWORKS = {
    930100: "192.0.2",
    930110: "198.51.100",
    930120: "203.0.113",
}

# Reporting-only families from design 101.  They never affect Prepare input or
# candidate selection.
PREPARE_REPORT_FAMILIES = {
    "strict_traversal": {
        "owasp_crs.930100.2",
        "owasp_crs.930100.3",
        "owasp_crs.930110.2",
        "owasp_crs.930110.8",
        "owasp_crs.930110.9",
        "owasp_crs.930110.12",
        "owasp_crs.930120.1",
        "owasp_crs.930120.3",
        "owasp_crs.930120.15",
    },
    "direct_file_resource": {
        "owasp_crs.930120.2",
        "owasp_crs.930120.4",
        "owasp_crs.930120.5",
        "owasp_crs.930120.6",
        "owasp_crs.930120.13",
        "owasp_crs.930120.14",
        "owasp_crs.930120.18",
    },
    "command_like": {
        "owasp_crs.930120.7",
        "owasp_crs.930120.8",
        "owasp_crs.930120.9",
    },
    "negative_controls": {
        "owasp_crs.930110.4",
        "owasp_crs.930110.5",
        "owasp_crs.930110.6",
        "owasp_crs.930110.7",
        "owasp_crs.930120.10",
        "owasp_crs.930120.11",
        "owasp_crs.930120.12",
        "owasp_crs.930120.16",
    },
    "encoded_normalization_risk": {"owasp_crs.930100.3"},
}


class BenchmarkPrepareContractError(ValueError):
    """Raised when a normalized case or Prepare result violates this contract."""


class SyntheticRowAdapterError(BenchmarkPrepareContractError):
    """Raised when a normalized request cannot be represented as a row."""


PrepareBuilder = Callable[
    ...,
    tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, Any],
        list[dict[str, Any]],
    ],
]


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SyntheticRowAdapterError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SyntheticRowAdapterError(f"{label} must be a non-empty string")
    return value


def benchmark_request_id(case_id: str) -> str:
    """Return an order-independent ID safe for the production request_id field."""

    normalized = re.sub(
        r"[^A-Za-z0-9]+", "-", _require_string(case_id, "case_id")
    ).strip("-").lower()
    if not normalized:
        raise SyntheticRowAdapterError("case_id does not contain a request ID token")
    return f"bench-{normalized}"


def benchmark_source_ip(case: Mapping[str, Any]) -> str:
    """Map each pinned rule/test identity injectively into RFC documentation IPs."""

    source = _require_mapping(case.get("source"), "source")
    rule_id = source.get("rule_id")
    test_id = source.get("test_id")
    if isinstance(rule_id, bool) or not isinstance(rule_id, int):
        raise SyntheticRowAdapterError("source.rule_id must be an integer")
    if isinstance(test_id, bool) or not isinstance(test_id, int) or not 1 <= test_id <= 254:
        raise SyntheticRowAdapterError("source.test_id must be an integer from 1 through 254")
    network = DOCUMENTATION_NETWORKS.get(rule_id)
    if network is None:
        raise SyntheticRowAdapterError(f"unsupported benchmark source.rule_id: {rule_id!r}")
    return f"{network}.{test_id}"


def _header_value(headers: Mapping[str, Any], name: str) -> str:
    matches = [
        value
        for key, value in headers.items()
        if isinstance(key, str) and key.casefold() == name.casefold()
    ]
    if len(matches) > 1:
        raise SyntheticRowAdapterError(f"duplicate case-insensitive request header: {name}")
    if not matches:
        return ""
    if not isinstance(matches[0], str):
        raise SyntheticRowAdapterError(f"request.headers.{name} must be a string")
    return matches[0]


def build_synthetic_security_row(
    case: Mapping[str, Any],
    *,
    sequence_index: int = 0,
) -> dict[str, Any]:
    """Convert one normalized case to a neutral Apache security export row.

    The request target is split only at the first literal ``?``.  No URL,
    percent, NUL-like, backslash, or semicolon decoding is performed, and the
    source request body is never represented in the row.
    """

    if not isinstance(case, Mapping):
        raise SyntheticRowAdapterError("case must be an object")
    if (
        isinstance(sequence_index, bool)
        or not isinstance(sequence_index, int)
        or sequence_index < 0
    ):
        raise SyntheticRowAdapterError("sequence_index must be a non-negative integer")

    case_id = _require_string(case.get("case_id"), "case_id")
    request = _require_mapping(case.get("request"), "request")
    method = _require_string(request.get("method"), "request.method")
    request_target = _require_string(request.get("request_target"), "request.request_target")
    http_version = _require_string(request.get("http_version"), "request.http_version")
    headers = _require_mapping(request.get("headers"), "request.headers")

    if "?" in request_target:
        uri, raw_query = request_target.split("?", 1)
        query_string = f"?{raw_query}"
    else:
        uri = request_target
        query_string = ""
    if not uri:
        raise SyntheticRowAdapterError("request.request_target must have a non-empty path portion")

    timestamp = SYNTHETIC_BASE_TIME + sequence_index * SYNTHETIC_INTERVAL
    return {
        "id": sequence_index + 1,
        "request_id": benchmark_request_id(case_id),
        "log_time": timestamp.isoformat(timespec="seconds"),
        "src_ip": benchmark_source_ip(case),
        "method": method,
        "uri": uri,
        "query_string": query_string,
        "protocol": http_version,
        "raw_request": f"{method} {request_target} {http_version}",
        "raw_log": "",
        "status_code": 200,
        "original_status_code": 200,
        "response_body_bytes": 0,
        "duration_us": 0,
        "ttfb_us": 0,
        "referer": _header_value(headers, "Referer"),
        "user_agent": _header_value(headers, "User-Agent"),
        "req_host": _header_value(headers, "Host"),
        "req_content_type": _header_value(headers, "Content-Type"),
        "resp_content_type": "",
    }


def build_prepare_export_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Build the ordinary production export payload for one isolated row."""

    row_copy = copy.deepcopy(dict(row))
    log_time = row_copy.get("log_time")
    return {
        "meta": {
            "table_option": SOURCE_TABLE,
            "start": log_time,
            "end_exclusive": log_time,
            "query_timezone": "Asia/Seoul",
            "database": "external_security_benchmark",
            "total_count": 1,
            "exported_at": "2026-01-01T00:00:00+09:00",
        },
        "counts": {"access": 0, "security": 1, "error": 0},
        "data": {SOURCE_TABLE: [row_copy]},
    }


def _base_case_result(case: Mapping[str, Any]) -> dict[str, Any]:
    source = _require_mapping(case.get("source"), "source")
    observability = _require_mapping(case.get("observability"), "observability")
    expected = _require_mapping(case.get("expected"), "expected")
    request = _require_mapping(case.get("request"), "request")
    return {
        "case_id": _require_string(case.get("case_id"), "case_id"),
        "source": {
            "rule_id": copy.deepcopy(source.get("rule_id")),
            "test_id": copy.deepcopy(source.get("test_id")),
            "expectation": copy.deepcopy(source.get("expectation")),
        },
        "observability": {
            "eligible": copy.deepcopy(observability.get("eligible")),
            "status": copy.deepcopy(observability.get("status")),
            "exclusion_reason": copy.deepcopy(observability.get("exclusion_reason")),
        },
        "expected": {
            "project_ground_truth": copy.deepcopy(expected.get("project_ground_truth")),
            "candidate_expected": copy.deepcopy(expected.get("candidate_expected")),
        },
        "request": {"raw_request_target": copy.deepcopy(request.get("request_target"))},
    }


def _not_scored_case_result(case: Mapping[str, Any]) -> dict[str, Any]:
    result = _base_case_result(case)
    result["actual"] = {
        "execution_status": "not_run",
        "candidate_selected": None,
        "candidate_count_for_request": None,
        "prepare_verdict_hint": None,
        "prepare_reason_hints": [],
        "candidate_score": None,
        "filtered_out": None,
        "filtered_reasons": [],
        "source_table": None,
        "raw_request_target": None,
    }
    result["result"] = {
        "candidate_selection": "not_scored_observability",
        "diagnostic_category": "not_scored_observability",
    }
    return result


def _error_case_result(
    case: Mapping[str, Any],
    *,
    category: str,
    message: str,
) -> dict[str, Any]:
    result = _base_case_result(case)
    result["actual"] = {
        "execution_status": "error",
        "candidate_selected": None,
        "candidate_count_for_request": None,
        "prepare_verdict_hint": None,
        "prepare_reason_hints": [],
        "candidate_score": None,
        "filtered_out": None,
        "filtered_reasons": [],
        "source_table": SOURCE_TABLE,
        "raw_request_target": result["request"]["raw_request_target"],
    }
    result["result"] = {
        "candidate_selection": "error",
        "diagnostic_category": category,
        "error": message,
    }
    return result


def _matching_filtered_reasons(payload: Mapping[str, Any], request_id: str) -> list[str]:
    excluded = payload.get("excluded", [])
    if not isinstance(excluded, list):
        return []
    return sorted(
        {
            item.get("reason")
            for item in excluded
            if isinstance(item, Mapping)
            and item.get("request_id") == request_id
            and isinstance(item.get("reason"), str)
        }
    )


def evaluate_prepare_case(
    case: Mapping[str, Any],
    *,
    sequence_index: int = 0,
    prepare_builder: PrepareBuilder = build_outputs,
) -> dict[str, Any]:
    """Run one direct normalized case through an isolated production Prepare call."""

    base = _base_case_result(case)
    if base["observability"] != {
        "eligible": True,
        "status": "direct",
        "exclusion_reason": None,
    }:
        raise BenchmarkPrepareContractError("evaluate_prepare_case requires a directly eligible case")
    candidate_expected = base["expected"]["candidate_expected"]
    if not isinstance(candidate_expected, bool):
        raise BenchmarkPrepareContractError("direct case expected.candidate_expected must be boolean")

    try:
        row = build_synthetic_security_row(case, sequence_index=sequence_index)
    except SyntheticRowAdapterError as exc:
        return _error_case_result(case, category="adapter_error", message=str(exc))

    payload = build_prepare_export_payload(row)
    try:
        _llm_input, candidates, _noise, filtered_reasons_payload, filtered_rows = prepare_builder(
            payload,
            min_score=PREPARE_MIN_SCORE,
            min_repeat_aggregate=PREPARE_MIN_REPEAT_AGGREGATE,
            source_tables=[SOURCE_TABLE],
        )
    except ValueError as exc:
        # ValueError is the production in-memory input/normalization failure
        # boundary.  Unexpected programming errors remain visible to callers.
        return _error_case_result(case, category="prepare_error", message=str(exc))

    request_id = row["request_id"]
    candidate_matches = [item for item in candidates if item.get("request_id") == request_id]
    filtered_matches = [item for item in filtered_rows if item.get("request_id") == request_id]
    candidate_count = len(candidate_matches)
    filtered_out = bool(filtered_matches) or bool(
        _matching_filtered_reasons(filtered_reasons_payload, request_id)
    )

    if candidate_count > 1 or (candidate_count and filtered_out):
        base["actual"] = {
            "execution_status": "error",
            "candidate_selected": candidate_count > 0,
            "candidate_count_for_request": candidate_count,
            "prepare_verdict_hint": None,
            "prepare_reason_hints": [],
            "candidate_score": None,
            "filtered_out": filtered_out,
            "filtered_reasons": _matching_filtered_reasons(
                filtered_reasons_payload, request_id
            ),
            "source_table": SOURCE_TABLE,
            "raw_request_target": base["request"]["raw_request_target"],
            "candidate_diagnostics": copy.deepcopy(candidate_matches),
        }
        base["result"] = {
            "candidate_selection": "error",
            "diagnostic_category": "duplicate_or_ambiguous_prepare_output",
        }
        return base

    candidate = candidate_matches[0] if candidate_matches else None
    selected = candidate is not None
    filtered_reason_hints = sorted(
        {
            hint
            for item in filtered_matches
            for hint in item.get("reason_hints", [])
            if isinstance(hint, str)
        }
    )
    base["actual"] = {
        "execution_status": "completed",
        "candidate_selected": selected,
        "candidate_count_for_request": candidate_count,
        "prepare_verdict_hint": candidate.get("verdict_hint") if candidate else None,
        "prepare_reason_hints": (
            copy.deepcopy(candidate.get("reason_hints", [])) if candidate else []
        ),
        "candidate_score": candidate.get("score") if candidate else None,
        "filtered_out": filtered_out,
        "filtered_reasons": _matching_filtered_reasons(
            filtered_reasons_payload, request_id
        ),
        "filtered_reason_hints": filtered_reason_hints,
        "source_table": candidate.get("source_table") if candidate else SOURCE_TABLE,
        "raw_request_target": (
            candidate.get("raw_request_target")
            if candidate
            else base["request"]["raw_request_target"]
        ),
    }

    passed = selected == candidate_expected
    if passed:
        category = None
    elif selected:
        category = "unexpected_candidate"
    elif filtered_out:
        category = "candidate_miss"
    else:
        category = "candidate_miss_not_selected"
    base["result"] = {
        "candidate_selection": "pass" if passed else "fail",
        "diagnostic_category": category,
    }
    return base


def _fraction(passed: int, total: int, *, complete: bool = True) -> dict[str, Any] | None:
    if total == 0:
        return None
    return {
        "passed": passed,
        "total": total,
        "rate": (passed / total) if complete else None,
    }


def calculate_prepare_metrics(
    case_results: Sequence[Mapping[str, Any]],
    *,
    complete: bool = True,
) -> dict[str, Any]:
    """Calculate Prepare gate metrics from project expectation fields only."""

    direct = [
        item
        for item in case_results
        if item.get("observability", {}).get("eligible") is True
        and item.get("observability", {}).get("status") == "direct"
    ]
    positives = [
        item
        for item in direct
        if item.get("expected", {}).get("candidate_expected") is True
    ]
    negatives = [
        item
        for item in direct
        if item.get("expected", {}).get("project_ground_truth") == "project_negative"
    ]
    positive_passed = sum(
        item.get("actual", {}).get("candidate_selected") is True for item in positives
    )
    negative_passed = sum(
        item.get("actual", {}).get("candidate_selected") is False for item in negatives
    )
    return {
        "candidate_recall_on_expected_candidates": _fraction(
            positive_passed, len(positives), complete=complete
        ),
        "negative_candidate_suppression_rate": _fraction(
            negative_passed, len(negatives), complete=complete
        ),
    }


def _build_family_metrics(
    case_results: Sequence[Mapping[str, Any]], *, complete: bool
) -> dict[str, Any]:
    indexed = {item.get("case_id"): item for item in case_results}
    summaries: dict[str, Any] = {}
    for family, configured_ids in PREPARE_REPORT_FAMILIES.items():
        selected_ids = sorted(case_id for case_id in configured_ids if case_id in indexed)
        family_cases = [indexed[case_id] for case_id in selected_ids]
        if family == "negative_controls":
            passed = sum(
                item.get("actual", {}).get("candidate_selected") is False
                for item in family_cases
            )
        else:
            passed = sum(
                item.get("actual", {}).get("candidate_selected") is True
                for item in family_cases
            )
        summary = _fraction(passed, len(family_cases), complete=complete)
        summaries[family] = {
            "case_ids": selected_ids,
            "passed": 0 if summary is None else summary["passed"],
            "total": 0 if summary is None else summary["total"],
            "rate": None if summary is None else summary["rate"],
        }
    return summaries


def run_prepare_benchmark(
    cases: Sequence[Mapping[str, Any]],
    *,
    prepare_builder: PrepareBuilder = build_outputs,
) -> dict[str, Any]:
    """Evaluate all direct cases independently while preserving full accounting."""

    case_copies = copy.deepcopy(list(cases))
    if any(not isinstance(case, Mapping) for case in case_copies):
        raise BenchmarkPrepareContractError("all normalized cases must be objects")
    ids = [case.get("case_id") for case in case_copies]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise BenchmarkPrepareContractError("all normalized cases need non-empty case_id values")
    duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise BenchmarkPrepareContractError(f"duplicate normalized case IDs: {duplicates!r}")

    ordered = sorted(
        case_copies,
        key=lambda item: (
            item.get("source", {}).get("rule_id", 0),
            item.get("source", {}).get("test_id", 0),
            item["case_id"],
        ),
    )
    results: list[dict[str, Any]] = []
    direct_index = 0
    for case in ordered:
        observability = _require_mapping(case.get("observability"), "observability")
        if observability.get("status") == "direct" and observability.get("eligible") is True:
            results.append(
                evaluate_prepare_case(
                    case,
                    sequence_index=direct_index,
                    prepare_builder=prepare_builder,
                )
            )
            direct_index += 1
        else:
            results.append(_not_scored_case_result(case))

    status_counts = Counter(item["observability"]["status"] for item in results)
    direct_results = [item for item in results if item["observability"]["status"] == "direct"]
    errors = [
        {"case_id": item["case_id"], "category": item["result"]["diagnostic_category"]}
        for item in direct_results
        if item["actual"]["execution_status"] == "error"
    ]
    complete = (
        len(results) == len(case_copies)
        and len({item["case_id"] for item in results}) == len(results)
        and len(direct_results) == direct_index
        and not errors
    )
    counts = {
        "source_cases_total": len(results),
        "directly_eligible_cases": status_counts["direct"],
        "partial_capability_cases": status_counts["partial"],
        "out_of_scope_cases": status_counts["out_of_scope"],
        "expected_candidate_cases": sum(
            item["expected"]["candidate_expected"] is True for item in direct_results
        ),
        "project_negative_cases": sum(
            item["expected"]["project_ground_truth"] == "project_negative"
            for item in direct_results
        ),
        "evaluated_direct_cases": sum(
            item["actual"]["execution_status"] == "completed" for item in direct_results
        ),
    }
    revisions = {
        case.get("source", {}).get("revision")
        for case in ordered
        if case.get("source", {}).get("revision") is not None
    }
    if len(revisions) != 1:
        raise BenchmarkPrepareContractError("normalized cases must have one source revision")

    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "benchmark": BENCHMARK_NAME,
        "source_revision": next(iter(revisions)),
        "run": {
            "level": "level_1_normalized_row",
            "stage": "prepare_only",
            "complete": complete,
            "case_isolation": "one_build_outputs_call_per_direct_case",
            "prepare_parameters": {
                "min_score": PREPARE_MIN_SCORE,
                "min_repeat_aggregate": PREPARE_MIN_REPEAT_AGGREGATE,
                "source_tables": [SOURCE_TABLE],
            },
        },
        "counts": counts,
        "metrics": calculate_prepare_metrics(results, complete=complete),
        "family_metrics": _build_family_metrics(results, complete=complete),
        "diagnostics": {
            "errors": errors,
            "failure_inventory": [
                {
                    "case_id": item["case_id"],
                    "category": item["result"]["diagnostic_category"],
                }
                for item in direct_results
                if item["result"]["candidate_selection"] == "fail"
            ],
        },
        "cases": results,
    }
    return result


def validate_prepare_benchmark_result(result: Mapping[str, Any]) -> list[str]:
    """Perform lightweight semantic checks without a runtime jsonschema dependency."""

    errors: list[str] = []
    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RESULT_SCHEMA_VERSION}")
    if result.get("benchmark") != BENCHMARK_NAME:
        errors.append(f"benchmark must be {BENCHMARK_NAME}")
    run = result.get("run")
    counts = result.get("counts")
    cases = result.get("cases")
    if not isinstance(run, Mapping) or run.get("stage") != "prepare_only":
        errors.append("run.stage must be prepare_only")
    if not isinstance(counts, Mapping):
        errors.append("counts must be an object")
        counts = {}
    if not isinstance(cases, list):
        errors.append("cases must be an array")
        cases = []
    case_ids = [item.get("case_id") for item in cases if isinstance(item, Mapping)]
    if len(case_ids) != len(cases) or len(case_ids) != len(set(case_ids)):
        errors.append("result cases must have unique case_id values")
    if counts.get("source_cases_total") != len(cases):
        errors.append("counts.source_cases_total must equal result case count")
    status_counts = Counter(
        item.get("observability", {}).get("status")
        for item in cases
        if isinstance(item, Mapping)
    )
    for field, status in (
        ("directly_eligible_cases", "direct"),
        ("partial_capability_cases", "partial"),
        ("out_of_scope_cases", "out_of_scope"),
    ):
        if counts.get(field) != status_counts[status]:
            errors.append(f"counts.{field} does not match cases")
    return errors


def write_prepare_benchmark_result(result: Mapping[str, Any], output_path: str | Path) -> None:
    """Validate and serialize a deterministic Prepare benchmark artifact."""

    errors = validate_prepare_benchmark_result(result)
    if errors:
        raise BenchmarkPrepareContractError("invalid Prepare benchmark result:\n- " + "\n- ".join(errors))
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OWASP CRS Prepare-only benchmark")
    parser.add_argument("--source-dir", required=True, help="Pinned OWASP CRS source directory")
    parser.add_argument("--manifest", required=True, help="Frozen project benchmark manifest")
    parser.add_argument("--output", required=True, help="Prepare-only result JSON path")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source_cases = load_owasp_crs_cases(args.source_dir)
        manifest = load_benchmark_manifest(args.manifest)
        normalized_cases = build_normalized_benchmark_cases(source_cases, manifest)
        result = run_prepare_benchmark(normalized_cases)
        write_prepare_benchmark_result(result, args.output)
    except (BenchmarkContractError, BenchmarkPrepareContractError, OSError, UnicodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    recall = result["metrics"]["candidate_recall_on_expected_candidates"]
    suppression = result["metrics"]["negative_candidate_suppression_rate"]
    print(f"[OK] output: {args.output}")
    print(f"[OK] candidate recall: {recall['passed']}/{recall['total']} ({recall['rate']})")
    print(f"[OK] negative suppression: {suppression['passed']}/{suppression['total']} ({suppression['rate']})")
    return 0 if result["run"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
