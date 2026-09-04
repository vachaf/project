#!/usr/bin/env python3
"""Prepare-only baseline runner for the reviewed OWASP CRS multi-family suite.

This is orchestration code.  It does not add detection rules or reinterpret CRS
expectations: every direct case is represented by one neutral Apache security
row and sent to production ``build_outputs`` exactly once.  The frozen 930
adapter/evaluator remains the authority for 930 cases.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.external_benchmark_crs import (
    PINNED_REVISION,
    build_normalized_benchmark_cases,
    load_benchmark_manifest,
    load_owasp_crs_cases,
)
from src.external_benchmark_crs_multifamily import (
    MultiFamilyBenchmarkContractError,
    join_family_manifest,
    load_benchmark_suite,
    load_family_benchmark_manifest,
    load_multifamily_crs_cases,
    resolve_benchmark_suite,
)
from src.external_benchmark_prepare import (
    PREPARE_MIN_REPEAT_AGGREGATE,
    PREPARE_MIN_SCORE,
    SOURCE_TABLE,
    BenchmarkPrepareContractError,
    _not_scored_case_result as legacy_not_scored_case_result,
    benchmark_request_id,
    build_prepare_export_payload,
    evaluate_prepare_case as evaluate_legacy_prepare_case,
)
from src.prepare_llm_input import build_outputs


RESULT_SCHEMA_VERSION = "external_security_benchmark_multifamily_prepare_result.v1"
SUITE_NAME = "owasp_crs_multi_family.v1"
SYNTHETIC_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=9)))
SYNTHETIC_INTERVAL = timedelta(hours=1)
DOCUMENTATION_NETWORKS = {"932": "192.0.2", "941": "198.51.100", "942": "203.0.113"}
COMPONENT_LABELS = {
    "owasp_crs_path_file_access.v1": "Traversal",
    "owasp_crs_cmdi.v1": "CMDi",
    "owasp_crs_xss.v1": "XSS",
    "owasp_crs_sqli.v1": "SQLi",
}

PrepareBuilder = Callable[..., tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]]


class MultiFamilyPrepareContractError(ValueError):
    """Raised when suite inputs or a Prepare observation violates this runner's contract."""


class MultiFamilySyntheticRowAdapterError(MultiFamilyPrepareContractError):
    """Raised when a 932/941/942 case cannot be faithfully represented."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MultiFamilySyntheticRowAdapterError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MultiFamilySyntheticRowAdapterError(f"{label} must be a non-empty string")
    return value


def _header(headers: Mapping[str, Any], name: str) -> str:
    values = [value for key, value in headers.items() if isinstance(key, str) and key.casefold() == name.casefold()]
    if len(values) > 1:
        raise MultiFamilySyntheticRowAdapterError(f"duplicate case-insensitive request header: {name}")
    if not values:
        return ""
    if not isinstance(values[0], str):
        raise MultiFamilySyntheticRowAdapterError(f"request.headers.{name} must be a string")
    return values[0]


def _case_request(case: Mapping[str, Any]) -> Mapping[str, Any]:
    """Read the request from either frozen-930 or family join shape."""

    request = case.get("request")
    if isinstance(request, Mapping):
        return request
    source = case.get("source")
    if isinstance(source, Mapping) and isinstance(source.get("request"), Mapping):
        return source["request"]
    raise MultiFamilySyntheticRowAdapterError("request must be an object")


def multifamily_benchmark_source_ip(case: Mapping[str, Any]) -> str:
    """Return a deterministic RFC-5737 address without Python hash randomization."""

    source = _mapping(case.get("source"), "source")
    family = source.get("source_family")
    network = DOCUMENTATION_NETWORKS.get(family)
    if network is None:
        raise MultiFamilySyntheticRowAdapterError(f"unsupported source family: {family!r}")
    case_id = _string(case.get("case_id"), "case_id")
    # 1..254 avoids network/broadcast values. Isolated calls make collisions harmless.
    octet = int.from_bytes(hashlib.sha256(case_id.encode("utf-8")).digest()[:2], "big") % 254 + 1
    return f"{network}.{octet}"


def build_multifamily_synthetic_security_row(case: Mapping[str, Any], *, sequence_index: int = 0) -> dict[str, Any]:
    """Build a neutral row for a new-family direct case; no decoding occurs."""

    if isinstance(sequence_index, bool) or not isinstance(sequence_index, int) or sequence_index < 0:
        raise MultiFamilySyntheticRowAdapterError("sequence_index must be a non-negative integer")
    request = _case_request(case)
    target = _string(request.get("request_target"), "request.request_target")
    method = _string(request.get("method"), "request.method")
    version = _string(request.get("http_version"), "request.http_version")
    headers = _mapping(request.get("headers"), "request.headers")
    if "?" in target:
        uri, query = target.split("?", 1)
        query_string = f"?{query}"
    else:
        uri, query_string = target, ""
    if not uri:
        raise MultiFamilySyntheticRowAdapterError("request.request_target must have a non-empty path portion")
    timestamp = SYNTHETIC_BASE_TIME + sequence_index * SYNTHETIC_INTERVAL
    return {
        "id": sequence_index + 1,
        "request_id": benchmark_request_id(_string(case.get("case_id"), "case_id")),
        "log_time": timestamp.isoformat(timespec="seconds"),
        "src_ip": multifamily_benchmark_source_ip(case),
        "method": method,
        "uri": uri,
        "query_string": query_string,
        "protocol": version,
        "raw_request": f"{method} {target} {version}",
        "raw_log": "",
        "status_code": 200,
        "original_status_code": 200,
        "response_body_bytes": 0,
        "duration_us": 0,
        "ttfb_us": 0,
        "referer": _header(headers, "Referer"),
        "user_agent": _header(headers, "User-Agent"),
        "req_host": _header(headers, "Host"),
        "req_content_type": _header(headers, "Content-Type"),
        "resp_content_type": "",
    }


def _case_sort_key(case: Mapping[str, Any]) -> tuple[int, int, str]:
    source = case.get("source") if isinstance(case.get("source"), Mapping) else {}
    return (int(source.get("rule_id") or source.get("source_rule_id") or 0), int(source.get("test_id") or source.get("source_test_id") or 0), str(case.get("case_id") or ""))


def _base_new_case_result(case: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(case.get("source"), "source")
    expected = _mapping(case.get("expected"), "expected")
    observability = _mapping(case.get("observability"), "observability")
    return {
        "case_id": _string(case.get("case_id"), "case_id"), "component_benchmark": case.get("component_benchmark"),
        "suite_groups": sorted(copy.deepcopy(case.get("suite_groups", []))),
        "source": {"family": source.get("source_family"), "rule_id": source.get("source_rule_id"), "test_id": source.get("source_test_id"), "expectation": copy.deepcopy(source.get("source_expectation"))},
        "observability": {"eligible": observability.get("eligible"), "status": observability.get("status"), "exclusion_reason": observability.get("exclusion_reason")},
        "expected": {"project_ground_truth": expected.get("project_ground_truth"), "candidate_expected": expected.get("candidate_expected"), "classification_policy": expected.get("classification_policy")},
        "request": {"raw_request_target": copy.deepcopy(_case_request(case).get("request_target"))},
    }


def _not_scored_new_case_result(case: Mapping[str, Any]) -> dict[str, Any]:
    result = _base_new_case_result(case)
    result["actual"] = {"execution_status": "not_run", "request_id": None, "candidate_selected": None, "candidate_count_for_request": None, "prepare_verdict_hint": None, "prepare_reason_hints": [], "candidate_score": None, "filtered_out": None, "filtered_reasons": [], "filtered_reason_hints": [], "source_table": None, "raw_request_target": None}
    result["result"] = {"candidate_selection": "not_scored_observability", "diagnostic_category": "not_scored_observability"}
    return result


def _error_new_case_result(case: Mapping[str, Any], category: str, message: str) -> dict[str, Any]:
    result = _base_new_case_result(case)
    result["actual"] = {"execution_status": "error", "request_id": benchmark_request_id(result["case_id"]), "candidate_selected": None, "candidate_count_for_request": None, "prepare_verdict_hint": None, "prepare_reason_hints": [], "candidate_score": None, "filtered_out": None, "filtered_reasons": [], "filtered_reason_hints": [], "source_table": SOURCE_TABLE, "raw_request_target": result["request"]["raw_request_target"]}
    result["result"] = {"candidate_selection": "error", "diagnostic_category": category, "error": message}
    return result


def _filtered_reasons(payload: Mapping[str, Any], request_id: str) -> list[str]:
    excluded = payload.get("excluded", [])
    if not isinstance(excluded, list):
        return []
    return sorted({item.get("reason") for item in excluded if isinstance(item, Mapping) and item.get("request_id") == request_id and isinstance(item.get("reason"), str)})


def evaluate_multifamily_prepare_case(case: Mapping[str, Any], *, sequence_index: int = 0, prepare_builder: PrepareBuilder = build_outputs) -> dict[str, Any]:
    """Evaluate one directly eligible 932/941/942 case in one production call."""

    result = _base_new_case_result(case)
    if result["observability"] != {"eligible": True, "status": "direct", "exclusion_reason": None}:
        raise MultiFamilyPrepareContractError("evaluate_multifamily_prepare_case requires a directly eligible case")
    if not isinstance(result["expected"]["candidate_expected"], bool):
        raise MultiFamilyPrepareContractError("direct case expected.candidate_expected must be boolean")
    try:
        row = build_multifamily_synthetic_security_row(case, sequence_index=sequence_index)
    except MultiFamilySyntheticRowAdapterError as exc:
        return _error_new_case_result(case, "adapter_error", str(exc))
    payload = build_prepare_export_payload(row)
    try:
        _input, candidates, _noise, filtered_payload, filtered_rows = prepare_builder(payload, min_score=PREPARE_MIN_SCORE, min_repeat_aggregate=PREPARE_MIN_REPEAT_AGGREGATE, source_tables=[SOURCE_TABLE])
    except ValueError as exc:
        return _error_new_case_result(case, "prepare_error", str(exc))
    request_id = row["request_id"]
    foreign = [item for item in candidates if isinstance(item, Mapping) and isinstance(item.get("request_id"), str) and item.get("request_id", "").startswith("bench-owasp-crs-") and item.get("request_id") != request_id]
    matches = [item for item in candidates if isinstance(item, Mapping) and item.get("request_id") == request_id]
    filtered_matches = [item for item in filtered_rows if isinstance(item, Mapping) and item.get("request_id") == request_id]
    reasons = _filtered_reasons(filtered_payload, request_id)
    filtered_out = bool(filtered_matches) or bool(reasons)
    if len(matches) > 1 or (matches and filtered_out) or foreign:
        result["actual"] = {"execution_status": "error", "request_id": request_id, "candidate_selected": bool(matches), "candidate_count_for_request": len(matches), "prepare_verdict_hint": None, "prepare_reason_hints": [], "candidate_score": None, "filtered_out": filtered_out, "filtered_reasons": reasons, "filtered_reason_hints": [], "source_table": SOURCE_TABLE, "raw_request_target": result["request"]["raw_request_target"], "foreign_candidate_request_ids": sorted(item["request_id"] for item in foreign)}
        result["result"] = {"candidate_selection": "error", "diagnostic_category": "duplicate_or_ambiguous_prepare_output"}
        return result
    candidate = matches[0] if matches else None
    filtered_hints = sorted({hint for item in filtered_matches for hint in item.get("reason_hints", []) if isinstance(hint, str)})
    selected = candidate is not None
    result["actual"] = {"execution_status": "completed", "request_id": request_id, "candidate_selected": selected, "candidate_count_for_request": len(matches), "prepare_verdict_hint": candidate.get("verdict_hint") if candidate else None, "prepare_reason_hints": copy.deepcopy(candidate.get("reason_hints", [])) if candidate else [], "candidate_score": candidate.get("score") if candidate else None, "filtered_out": filtered_out, "filtered_reasons": reasons, "filtered_reason_hints": filtered_hints, "source_table": candidate.get("source_table") if candidate else SOURCE_TABLE, "raw_request_target": candidate.get("raw_request_target") if candidate else result["request"]["raw_request_target"]}
    passed = selected == result["expected"]["candidate_expected"]
    result["result"] = {"candidate_selection": "pass" if passed else "fail", "diagnostic_category": None if passed else ("unexpected_prepare_candidate" if selected else "candidate_miss")}
    return result


def _enrich_legacy_case_result(case: Mapping[str, Any], legacy: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve frozen legacy observation fields while adding suite provenance."""

    result = copy.deepcopy(dict(legacy))
    expected = _mapping(case.get("expected"), "expected")
    result["component_benchmark"] = case.get("component_benchmark")
    result["suite_groups"] = sorted(copy.deepcopy(case.get("suite_groups", [])))
    result["source"]["family"] = "930"
    result["expected"]["classification_policy"] = expected.get("classification_policy")
    result["actual"]["request_id"] = benchmark_request_id(result["case_id"]) if result["actual"]["execution_status"] != "not_run" else None
    if result.get("result", {}).get("diagnostic_category") == "unexpected_candidate":
        result["result"]["diagnostic_category"] = "unexpected_prepare_candidate"
    return result


def _fraction(passed: int, total: int, *, complete: bool) -> dict[str, Any]:
    return {"passed": passed, "total": total, "rate": (passed / total) if total and complete else None}


def _case_fraction(cases: Sequence[Mapping[str, Any]], *, selected: bool, complete: bool) -> dict[str, Any]:
    return _fraction(sum(item.get("actual", {}).get("candidate_selected") is selected for item in cases), len(cases), complete=complete)


def _by_ids(index: Mapping[str, Mapping[str, Any]], ids: Sequence[str]) -> list[Mapping[str, Any]]:
    return [index[case_id] for case_id in ids if case_id in index]


def calculate_multifamily_prepare_metrics(case_results: Sequence[Mapping[str, Any]], suite: Mapping[str, Any], *, complete: bool = True) -> dict[str, Any]:
    """Calculate selection-gate metrics only; verdict hints remain diagnostics."""

    direct = [item for item in case_results if item.get("observability", {}).get("eligible") is True and item.get("observability", {}).get("status") == "direct"]
    positives = [item for item in direct if item.get("expected", {}).get("project_ground_truth") == "attack_positive"]
    negatives = [item for item in direct if item.get("expected", {}).get("project_ground_truth") == "project_negative"]
    index = {str(item.get("case_id")): item for item in case_results}
    by_class: dict[str, Any] = {}
    for benchmark, label in COMPONENT_LABELS.items():
        by_class[label] = _case_fraction([item for item in positives if item.get("component_benchmark") == benchmark], selected=True, complete=complete)
    exact = suite["groups"]["exact_core"]
    exact_metrics = {"Traversal": _case_fraction(_by_ids(index, exact["traversal"]), selected=True, complete=complete), "CMDi": _case_fraction(_by_ids(index, exact["cmdi"]), selected=True, complete=complete), "XSS": _case_fraction(_by_ids(index, exact["xss"]), selected=True, complete=complete), "SQLi": _case_fraction(_by_ids(index, exact["sqli"]), selected=True, complete=complete)}
    exact_rates = [value["rate"] for value in exact_metrics.values()]
    addendum = _by_ids(index, suite["groups"]["path_file_boundary_addendum"])
    file_addendum = [item for item in addendum if item.get("case_id") == "owasp_crs.930120.2"]
    negative_groups = {name: _case_fraction(_by_ids(index, suite["groups"][name]), selected=False, complete=complete) for name in ("path_file_negative", "cmdi_negative", "xss_negative", "sqli_negative")}
    component_metrics = {benchmark: {"candidate_recall": _case_fraction([item for item in positives if item.get("component_benchmark") == benchmark], selected=True, complete=complete), "negative_suppression": _case_fraction([item for item in negatives if item.get("component_benchmark") == benchmark], selected=False, complete=complete)} for benchmark in COMPONENT_LABELS}
    return {"candidate_recall_on_expected_candidates": _case_fraction(positives, selected=True, complete=complete), "candidate_recall_by_class": by_class, "component_candidate_metrics": component_metrics, "full_family_macro_candidate_recall": {"class_count": len(by_class), "rate": (sum(value["rate"] for value in by_class.values() if value["rate"] is not None) / len(by_class)) if complete and all(value["rate"] is not None for value in by_class.values()) else None}, "exact_core_candidate_recall_by_class": exact_metrics, "exact_core_macro_candidate_recall": {"class_count": 4, "rate": (sum(exact_rates) / 4) if complete and all(rate is not None for rate in exact_rates) else None}, "path_file_boundary_addendum_candidate_recall": _case_fraction(addendum, selected=True, complete=complete), "file_disclosure_addendum_candidate_recall": _case_fraction(file_addendum, selected=True, complete=complete), "negative_candidate_suppression_rate": _case_fraction(negatives, selected=False, complete=complete), "negative_suppression_by_family": negative_groups, "negative_unexpected_candidate_rate": _case_fraction(negatives, selected=True, complete=complete)}


def _component_counts(case_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for benchmark in COMPONENT_LABELS:
        cases = [item for item in case_results if item.get("component_benchmark") == benchmark]
        direct = [item for item in cases if item["observability"]["status"] == "direct"]
        output[benchmark] = {"cases": len(cases), "direct": len(direct), "positive": sum(item["expected"]["project_ground_truth"] == "attack_positive" for item in direct), "negative": sum(item["expected"]["project_ground_truth"] == "project_negative" for item in direct), "not_scored": sum(item["expected"]["project_ground_truth"] == "not_scored" for item in cases), "candidate_selected": sum(item.get("actual", {}).get("candidate_selected") is True for item in direct)}
    return output


def _diagnostics(case_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    hints: dict[str, Counter[str]] = defaultdict(Counter)
    filtered = Counter()
    scores: list[float] = []
    misses: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unexpected: dict[str, list[dict[str, Any]]] = defaultdict(list)
    errors: list[dict[str, str]] = []
    for item in case_results:
        actual, expected = item.get("actual", {}), item.get("expected", {})
        label = COMPONENT_LABELS.get(item.get("component_benchmark"), str(item.get("component_benchmark")))
        if isinstance(actual.get("candidate_score"), (int, float)):
            scores.append(actual["candidate_score"])
        filtered.update(actual.get("filtered_reasons", []))
        if expected.get("project_ground_truth") == "attack_positive":
            hints[label][actual.get("prepare_verdict_hint") or "none"] += 1
            if actual.get("candidate_selected") is False:
                misses[label].append({"case_id": item["case_id"], "raw_request_target": item["request"]["raw_request_target"], "filtered_out": actual.get("filtered_out"), "filtered_reasons": actual.get("filtered_reasons", []), "reason_hints": actual.get("prepare_reason_hints", []) or actual.get("filtered_reason_hints", []), "candidate_score": actual.get("candidate_score")})
        if expected.get("project_ground_truth") == "project_negative" and actual.get("candidate_selected") is True:
            unexpected[label].append({"case_id": item["case_id"], "raw_request_target": item["request"]["raw_request_target"], "candidate_score": actual.get("candidate_score"), "verdict_hint": actual.get("prepare_verdict_hint"), "reason_hints": actual.get("prepare_reason_hints", [])})
        if actual.get("execution_status") == "error":
            errors.append({"case_id": item["case_id"], "category": str(item.get("result", {}).get("diagnostic_category"))})
    return {"errors": errors, "prepare_verdict_hint_distribution": {key: dict(sorted(value.items())) for key, value in sorted(hints.items())}, "candidate_score_summary": {"count": len(scores), "min": min(scores) if scores else None, "max": max(scores) if scores else None, "mean": (sum(scores) / len(scores)) if scores else None}, "filtered_reason_distribution": dict(sorted(filtered.items())), "candidate_misses": dict(sorted(misses.items())), "unexpected_prepare_candidates": dict(sorted(unexpected.items()))}


def _validate_resolved_cases(cases: Sequence[Mapping[str, Any]], suite: Mapping[str, Any]) -> None:
    ids = [item.get("case_id") for item in cases]
    if len(ids) != len(set(ids)):
        raise MultiFamilyPrepareContractError("resolved suite contains duplicate case IDs")
    expected = {"reviewed_cases_total": 93, "direct_cases": 83, "not_scored_cases": 10, "attack_positive_cases": 55, "project_negative_cases": 28, "exact_core_cases": 36}
    direct = [item for item in cases if item.get("observability", {}).get("eligible") is True and item.get("observability", {}).get("status") == "direct"]
    actual = {"reviewed_cases_total": len(cases), "direct_cases": len(direct), "not_scored_cases": len(cases) - len(direct), "attack_positive_cases": sum(item.get("expected", {}).get("project_ground_truth") == "attack_positive" for item in direct), "project_negative_cases": sum(item.get("expected", {}).get("project_ground_truth") == "project_negative" for item in direct), "exact_core_cases": sum(len(ids) for ids in suite["groups"]["exact_core"].values())}
    if actual != expected:
        raise MultiFamilyPrepareContractError(f"suite/design accounting mismatch: expected={expected}, actual={actual}")


def run_multifamily_prepare_benchmark(resolved_suite: Mapping[str, Any], *, prepare_builder: PrepareBuilder = build_outputs) -> dict[str, Any]:
    """Evaluate every direct reviewed case independently and retain all 93 records."""

    if resolved_suite.get("suite") != SUITE_NAME or not isinstance(resolved_suite.get("suite_manifest"), Mapping):
        raise MultiFamilyPrepareContractError("resolved suite must include the frozen suite manifest")
    suite = resolved_suite["suite_manifest"]
    cases = copy.deepcopy(list(resolved_suite.get("cases", [])))
    if any(not isinstance(case, Mapping) for case in cases):
        raise MultiFamilyPrepareContractError("resolved suite cases must be objects")
    _validate_resolved_cases(cases, suite)
    legacy_direct_index = new_direct_index = 0
    results: list[dict[str, Any]] = []
    for case in sorted(cases, key=_case_sort_key):
        direct = case.get("observability", {}).get("eligible") is True and case.get("observability", {}).get("status") == "direct"
        benchmark = case.get("component_benchmark")
        if not direct:
            legacy_result = legacy_not_scored_case_result(case) if benchmark == "owasp_crs_path_file_access.v1" else _not_scored_new_case_result(case)
            results.append(_enrich_legacy_case_result(case, legacy_result) if benchmark == "owasp_crs_path_file_access.v1" else legacy_result)
        elif benchmark == "owasp_crs_path_file_access.v1":
            results.append(_enrich_legacy_case_result(case, evaluate_legacy_prepare_case(case, sequence_index=legacy_direct_index, prepare_builder=prepare_builder)))
            legacy_direct_index += 1
        else:
            results.append(evaluate_multifamily_prepare_case(case, sequence_index=new_direct_index, prepare_builder=prepare_builder))
            new_direct_index += 1
    complete = not any(item.get("actual", {}).get("execution_status") == "error" for item in results)
    direct_results = [item for item in results if item["observability"]["status"] == "direct"]
    counts = {"reviewed_cases_total": len(results), "direct_cases": len(direct_results), "not_scored_cases": len(results) - len(direct_results), "attack_positive_cases": sum(item["expected"]["project_ground_truth"] == "attack_positive" for item in direct_results), "project_negative_cases": sum(item["expected"]["project_ground_truth"] == "project_negative" for item in direct_results), "exact_core_cases": 36, "evaluated_direct_cases": sum(item["actual"]["execution_status"] == "completed" for item in direct_results)}
    return {"schema_version": RESULT_SCHEMA_VERSION, "suite": SUITE_NAME, "source_revision": PINNED_REVISION, "stage": "prepare_only", "complete": complete, "run": {"level": "level_1_normalized_row", "case_isolation": "one_build_outputs_call_per_direct_case", "prepare_parameters": {"min_score": PREPARE_MIN_SCORE, "min_repeat_aggregate": PREPARE_MIN_REPEAT_AGGREGATE, "source_tables": [SOURCE_TABLE]}}, "counts": counts, "component_counts": _component_counts(results), "metrics": calculate_multifamily_prepare_metrics(results, suite, complete=complete), "diagnostics": _diagnostics(results), "cases": results}


def validate_multifamily_prepare_result(result: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        errors.append("invalid schema_version")
    if result.get("suite") != SUITE_NAME or result.get("stage") != "prepare_only":
        errors.append("invalid suite or stage")
    cases = result.get("cases")
    if not isinstance(cases, list):
        return errors + ["cases must be an array"]
    ids = [item.get("case_id") for item in cases if isinstance(item, Mapping)]
    if len(ids) != len(cases) or len(ids) != len(set(ids)):
        errors.append("cases must have unique case IDs")
    counts = result.get("counts")
    if not isinstance(counts, Mapping) or counts.get("reviewed_cases_total") != len(cases):
        errors.append("counts.reviewed_cases_total must match cases")
    return errors


def write_multifamily_prepare_result(result: Mapping[str, Any], output: str | Path) -> None:
    errors = validate_multifamily_prepare_result(result)
    if errors:
        raise MultiFamilyPrepareContractError("invalid multi-family Prepare result:\n- " + "\n- ".join(errors))
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_resolved_suite(source_root: str | Path, suite_path: str | Path) -> dict[str, Any]:
    """Load the suite entry point and resolve only its checked-in component paths."""

    source_root, suite_file = Path(source_root), Path(suite_path)
    suite = load_benchmark_suite(suite_file)
    benchmark_root = suite_file.resolve().parent.parent
    manifests: dict[str, dict[str, Any]] = {}
    for component in suite.get("components", []):
        if not isinstance(component, Mapping) or not isinstance(component.get("benchmark"), str) or not isinstance(component.get("manifest"), str):
            raise MultiFamilyPrepareContractError("suite component must identify benchmark and relative manifest")
        relative = Path(component["manifest"])
        if relative.is_absolute():
            raise MultiFamilyPrepareContractError("suite component manifest must be relative")
        candidate = (suite_file.parent / relative).resolve()
        if benchmark_root not in candidate.parents:
            raise MultiFamilyPrepareContractError("suite component manifest escapes benchmark root")
        manifests[component["benchmark"]] = load_benchmark_manifest(candidate) if component["benchmark"] == "owasp_crs_path_file_access.v1" else load_family_benchmark_manifest(candidate)
    legacy_source = load_owasp_crs_cases(source_root)
    multi_source = load_multifamily_crs_cases(source_root / "multi_family")
    normalized: dict[str, list[dict[str, Any]]] = {"owasp_crs_path_file_access.v1": build_normalized_benchmark_cases(legacy_source, manifests["owasp_crs_path_file_access.v1"])}
    for benchmark in ("owasp_crs_cmdi.v1", "owasp_crs_xss.v1", "owasp_crs_sqli.v1"):
        normalized[benchmark] = join_family_manifest(manifests[benchmark], multi_source)
    resolved = resolve_benchmark_suite(suite, manifests, normalized)
    resolved["suite_manifest"] = copy.deepcopy(suite)
    return resolved


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OWASP CRS multi-family Prepare-only baseline")
    parser.add_argument("--source-root", required=True, help="Pinned OWASP CRS source revision root")
    parser.add_argument("--suite", required=True, help="Suite manifest entry point")
    parser.add_argument("--output", required=True, help="Result JSON path")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run_multifamily_prepare_benchmark(load_resolved_suite(args.source_root, args.suite))
        write_multifamily_prepare_result(result, args.output)
    except (MultiFamilyBenchmarkContractError, BenchmarkPrepareContractError, MultiFamilyPrepareContractError, OSError, UnicodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    recall, suppression = result["metrics"]["candidate_recall_on_expected_candidates"], result["metrics"]["negative_candidate_suppression_rate"]
    print(f"[OK] output: {args.output}")
    print(f"[OK] candidate recall: {recall['passed']}/{recall['total']} ({recall['rate']})")
    print(f"[OK] negative suppression: {suppression['passed']}/{suppression['total']} ({suppression['rate']})")
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
