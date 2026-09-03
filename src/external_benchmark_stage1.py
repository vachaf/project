#!/usr/bin/env python3
"""Stage1 and standards-mapping evaluator for the external CRS benchmark.

The evaluator is deliberately pure: it joins normalized benchmark cases, a
saved Prepare-only result, and normalized Stage1 records without performing
network calls.  The live executor is a separate layer which regenerates the
production Prepare candidate, verifies its identity, calls the existing
Stage1 classifier, and applies the existing deterministic mapping function.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.external_benchmark_crs import (
    BenchmarkContractError,
    build_normalized_benchmark_cases,
    load_benchmark_manifest,
    load_owasp_crs_cases,
)
from src.external_benchmark_prepare import (
    BENCHMARK_NAME,
    PREPARE_MIN_REPEAT_AGGREGATE,
    PREPARE_MIN_SCORE,
    SOURCE_TABLE,
    BenchmarkPrepareContractError,
    benchmark_request_id,
    build_prepare_export_payload,
    build_synthetic_security_row,
    validate_prepare_benchmark_result,
)
from src.llm_client import provider_api_key_error, resolve_llm_config
from src.llm_stage1_classifier import (
    ALLOWED_MODES,
    DEFAULT_MODE,
    DEFAULT_TIMEOUT_SEC,
    Stage1Error,
    Stage1Result,
    choose_model,
    classify_candidate,
)
from src.prepare_llm_input import build_outputs
from src.security_standards_mapping import (
    KNOWN_VERDICTS,
    build_security_standards_mapping,
)


RESULT_SCHEMA_VERSION = "external_security_benchmark_stage1_result.v1"
REPLAY_SCHEMA_VERSION = "external_security_benchmark_stage1_replay.v1"
STAGE1_STAGE = "stage1"
EXECUTION_MODES = {"controlled", "replay", "live"}
SUCCESS_AUDIT_PHRASES = (
    "파일 노출 성공",
    "파일을 읽었다",
    "공격 성공",
    "침해 성공",
    "명령 실행 성공",
)

FIDELITY_FIELDS = (
    "request_id",
    "raw_request_target",
    "verdict_hint",
    "reason_hints",
    "score",
)

RUNTIME_ERROR_STATUSES = {
    "stage1_api_error",
    "stage1_parse_error",
    "stage1_validation_error",
    "stage1_runtime_error",
    "prepare_candidate_contract_error",
    "live_execution_unavailable",
}

Stage1Classifier = Callable[..., tuple[Stage1Result | None, Stage1Error | None]]


class BenchmarkStage1ContractError(ValueError):
    """Raised when evaluator, replay, or candidate-fidelity input is invalid."""


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BenchmarkStage1ContractError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BenchmarkStage1ContractError(f"{label} must be a non-empty string")
    return value


def _fraction(passed: int, total: int, *, complete: bool = True) -> dict[str, Any]:
    return {
        "passed": passed,
        "total": total,
        "rate": (passed / total) if total and complete else None,
    }


def _case_sort_key(case: Mapping[str, Any]) -> tuple[int, int, str]:
    source = case.get("source")
    if not isinstance(source, Mapping):
        source = {}
    return (
        int(source.get("rule_id") or 0),
        int(source.get("test_id") or 0),
        str(case.get("case_id") or ""),
    )


def _validate_case_policy(case: Mapping[str, Any]) -> None:
    case_id = _require_string(case.get("case_id"), "case.case_id")
    expected = _require_mapping(case.get("expected"), f"{case_id}.expected")
    policy = expected.get("classification_policy")
    allowed = expected.get("allowed_stage1_verdicts")
    forbidden = expected.get("forbidden_stage1_verdicts")
    if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
        raise BenchmarkStage1ContractError(
            f"{case_id}.expected.allowed_stage1_verdicts must be a string array"
        )
    if not isinstance(forbidden, list) or any(
        not isinstance(item, str) for item in forbidden
    ):
        raise BenchmarkStage1ContractError(
            f"{case_id}.expected.forbidden_stage1_verdicts must be a string array"
        )
    if len(allowed) != len(set(allowed)) or len(forbidden) != len(set(forbidden)):
        raise BenchmarkStage1ContractError(f"{case_id}: verdict lists must be unique")
    overlap = sorted(set(allowed) & set(forbidden))
    if overlap:
        raise BenchmarkStage1ContractError(
            f"{case_id}: allowed/forbidden verdicts overlap: {overlap!r}"
        )
    unknown = sorted((set(allowed) | set(forbidden)) - KNOWN_VERDICTS)
    if unknown:
        raise BenchmarkStage1ContractError(
            f"{case_id}: unknown Stage1 verdicts: {unknown!r}"
        )
    if policy == "exact" and len(allowed) != 1:
        raise BenchmarkStage1ContractError(
            f"{case_id}: exact policy requires exactly one allowed verdict"
        )
    if policy == "compatible_set" and not allowed:
        raise BenchmarkStage1ContractError(
            f"{case_id}: compatible_set policy requires allowed verdicts"
        )
    if policy == "forbidden_only" and not forbidden:
        raise BenchmarkStage1ContractError(
            f"{case_id}: forbidden_only policy requires forbidden verdicts"
        )
    if policy == "not_scored" and (allowed or forbidden):
        raise BenchmarkStage1ContractError(
            f"{case_id}: not_scored policy requires empty verdict lists"
        )
    if policy not in {"exact", "compatible_set", "forbidden_only", "not_scored"}:
        raise BenchmarkStage1ContractError(
            f"{case_id}: unsupported classification policy: {policy!r}"
        )

    mappings = expected.get("mapping_by_verdict")
    if not isinstance(mappings, Mapping):
        raise BenchmarkStage1ContractError(
            f"{case_id}.expected.mapping_by_verdict must be an object"
        )
    for verdict, contract in mappings.items():
        if verdict not in allowed:
            raise BenchmarkStage1ContractError(
                f"{case_id}: mapping contract verdict is not allowed: {verdict!r}"
            )
        contract = _require_mapping(contract, f"{case_id}.mapping_by_verdict[{verdict!r}]")
        required = contract.get("required_ids")
        forbidden_ids = contract.get("forbidden_ids")
        if not isinstance(required, list) or any(
            not isinstance(item, str) for item in required
        ):
            raise BenchmarkStage1ContractError(
                f"{case_id}: mapping required_ids must be a string array"
            )
        if not isinstance(forbidden_ids, list) or any(
            not isinstance(item, str) for item in forbidden_ids
        ):
            raise BenchmarkStage1ContractError(
                f"{case_id}: mapping forbidden_ids must be a string array"
            )
        mapping_overlap = sorted(set(required) & set(forbidden_ids))
        if mapping_overlap:
            raise BenchmarkStage1ContractError(
                f"{case_id}: required/forbidden mapping IDs overlap: {mapping_overlap!r}"
            )


def _index_inputs(
    cases: Sequence[Mapping[str, Any]], prepare_result: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    case_copies = copy.deepcopy(list(cases))
    if any(not isinstance(case, Mapping) for case in case_copies):
        raise BenchmarkStage1ContractError("all normalized cases must be objects")
    case_ids = [case.get("case_id") for case in case_copies]
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
        raise BenchmarkStage1ContractError("all normalized cases need non-empty case IDs")
    duplicate_cases = sorted(
        str(case_id) for case_id, count in Counter(case_ids).items() if count > 1
    )
    if duplicate_cases:
        raise BenchmarkStage1ContractError(
            f"duplicate normalized case IDs: {duplicate_cases!r}"
        )
    for case in case_copies:
        _validate_case_policy(case)

    prepare_errors = validate_prepare_benchmark_result(prepare_result)
    if prepare_errors:
        raise BenchmarkStage1ContractError(
            "invalid Prepare benchmark result:\n- " + "\n- ".join(prepare_errors)
        )
    if prepare_result.get("benchmark") != BENCHMARK_NAME:
        raise BenchmarkStage1ContractError("Prepare benchmark identity mismatch")
    prepare_cases = prepare_result.get("cases")
    assert isinstance(prepare_cases, list)  # established by validation above
    prepare_index = {
        item["case_id"]: item for item in prepare_cases if isinstance(item, Mapping)
    }
    if set(prepare_index) != set(case_ids):
        raise BenchmarkStage1ContractError(
            "normalized case IDs and Prepare result case IDs must match exactly"
        )
    revisions = {
        case.get("source", {}).get("revision")
        for case in case_copies
        if isinstance(case.get("source"), Mapping)
    }
    if len(revisions) != 1 or prepare_result.get("source_revision") not in revisions:
        raise BenchmarkStage1ContractError(
            "normalized cases and Prepare result source revision must match"
        )
    return sorted(case_copies, key=_case_sort_key), prepare_index


def _expected_candidate_input(
    case_id: str, prepare_case: Mapping[str, Any]
) -> dict[str, Any]:
    actual = _require_mapping(prepare_case.get("actual"), f"{case_id}.prepare.actual")
    return {
        "request_id": benchmark_request_id(case_id),
        "raw_request_target": actual.get("raw_request_target"),
        "verdict_hint": actual.get("prepare_verdict_hint"),
        "reason_hints": copy.deepcopy(actual.get("prepare_reason_hints")),
        "score": actual.get("candidate_score"),
    }


def _normalize_record_candidate_input(
    record: Mapping[str, Any], case_id: str
) -> Mapping[str, Any]:
    candidate_input = record.get("candidate_input")
    if not isinstance(candidate_input, Mapping):
        stage1 = record.get("stage1")
        if isinstance(stage1, Mapping) and all(field in stage1 for field in FIDELITY_FIELDS):
            candidate_input = {field: stage1.get(field) for field in FIDELITY_FIELDS}
        else:
            raise BenchmarkStage1ContractError(
                f"{case_id}: Stage1 record must preserve candidate_input fidelity fields"
            )
    return candidate_input


def _validate_stage1_records(
    records: Sequence[Mapping[str, Any]],
    prepare_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise BenchmarkStage1ContractError("stage1_records must be an array")
    copied = copy.deepcopy(list(records))
    if any(not isinstance(record, Mapping) for record in copied):
        raise BenchmarkStage1ContractError("all Stage1 records must be objects")
    ids = [record.get("case_id") for record in copied]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise BenchmarkStage1ContractError("all Stage1 records need non-empty case_id values")
    duplicates = sorted(
        str(case_id) for case_id, count in Counter(ids).items() if count > 1
    )
    if duplicates:
        raise BenchmarkStage1ContractError(
            f"duplicate Stage1 record case IDs: {duplicates!r}"
        )

    result: dict[str, Mapping[str, Any]] = {}
    for record in copied:
        case_id = record["case_id"]
        prepare_case = prepare_index.get(case_id)
        if prepare_case is None:
            raise BenchmarkStage1ContractError(
                f"Stage1 record references unknown case: {case_id}"
            )
        prepare_actual = _require_mapping(
            prepare_case.get("actual"), f"{case_id}.prepare.actual"
        )
        if prepare_actual.get("candidate_selected") is not True:
            raise BenchmarkStage1ContractError(
                f"{case_id}: Stage1 record exists for a case not selected by Prepare"
            )
        status = record.get("execution_status")
        if status != "completed" and status not in RUNTIME_ERROR_STATUSES:
            raise BenchmarkStage1ContractError(
                f"{case_id}: invalid Stage1 execution_status: {status!r}"
            )
        expected_input = _expected_candidate_input(case_id, prepare_case)
        actual_input = _normalize_record_candidate_input(record, case_id)
        mismatches = [
            field
            for field in FIDELITY_FIELDS
            if actual_input.get(field) != expected_input.get(field)
        ]
        if mismatches:
            raise BenchmarkStage1ContractError(
                f"{case_id}: candidate input fidelity mismatch: {mismatches!r}"
            )
        if record.get("request_id") != expected_input["request_id"]:
            raise BenchmarkStage1ContractError(
                f"{case_id}: record request_id does not match benchmark request ID"
            )
        if status == "completed":
            stage1 = _require_mapping(record.get("stage1"), f"{case_id}.stage1")
            verdict = stage1.get("verdict")
            if verdict not in KNOWN_VERDICTS:
                raise BenchmarkStage1ContractError(
                    f"{case_id}: completed Stage1 record has invalid verdict {verdict!r}"
                )
            mapping = _require_mapping(
                record.get("standards_mapping"), f"{case_id}.standards_mapping"
            )
            items = mapping.get("items")
            if not isinstance(items, list):
                raise BenchmarkStage1ContractError(
                    f"{case_id}: standards_mapping.items must be an array"
                )
        result[case_id] = record
    return result


def _evaluate_verdict(expected: Mapping[str, Any], actual: str) -> dict[str, Any]:
    policy = expected["classification_policy"]
    allowed = expected["allowed_stage1_verdicts"]
    forbidden = expected["forbidden_stage1_verdicts"]
    if actual in forbidden:
        return {"status": "fail", "reason": "actual_verdict_forbidden"}
    if policy == "exact":
        passed = actual == allowed[0]
        return {
            "status": "pass" if passed else "fail",
            "reason": None if passed else "exact_verdict_mismatch",
        }
    if policy == "compatible_set":
        passed = actual in allowed
        return {
            "status": "pass" if passed else "fail",
            "reason": None if passed else "actual_verdict_not_in_compatible_set",
        }
    if policy == "forbidden_only":
        return {"status": "pass", "reason": None}
    return {"status": "not_scored_observability", "reason": None}


def _mapping_ids(mapping: Mapping[str, Any], case_id: str) -> list[str]:
    items = mapping.get("items")
    if not isinstance(items, list):
        raise BenchmarkStage1ContractError(
            f"{case_id}: standards_mapping.items must be an array"
        )
    ids: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            raise BenchmarkStage1ContractError(
                f"{case_id}: standards_mapping.items[{index}].id must be a string"
            )
        ids.append(item["id"])
    return sorted(set(ids))


def _evaluate_mapping(
    expected: Mapping[str, Any],
    actual_verdict: str,
    mapping: Mapping[str, Any],
    case_id: str,
) -> dict[str, Any]:
    contract = expected["mapping_by_verdict"].get(actual_verdict)
    actual_ids = _mapping_ids(mapping, case_id)
    if contract is None:
        return {
            "status": "not_scored_no_mapping_contract",
            "actual_ids": actual_ids,
            "missing_required_ids": [],
            "present_forbidden_ids": [],
        }
    required = set(contract["required_ids"])
    forbidden = set(contract["forbidden_ids"])
    actual_set = set(actual_ids)
    missing = sorted(required - actual_set)
    forbidden_present = sorted(forbidden & actual_set)
    passed = not missing and not forbidden_present
    return {
        "status": "pass" if passed else "fail",
        "actual_ids": actual_ids,
        "missing_required_ids": missing,
        "present_forbidden_ids": forbidden_present,
    }


def _manual_audit_flags(stage1: Mapping[str, Any]) -> list[str]:
    summary = stage1.get("reasoning_summary")
    if not isinstance(summary, str):
        return []
    return [phrase for phrase in SUCCESS_AUDIT_PHRASES if phrase in summary]


def _base_case_result(
    case: Mapping[str, Any], prepare_case: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "source": copy.deepcopy(case["source"]),
        "observability": copy.deepcopy(case["observability"]),
        "expected": copy.deepcopy(case["expected"]),
        "request": {"raw_request_target": case["request"]["request_target"]},
        "prepare": copy.deepcopy(prepare_case["actual"]),
    }


def evaluate_stage1_benchmark(
    cases: Sequence[Mapping[str, Any]],
    prepare_result: Mapping[str, Any],
    stage1_records: Sequence[Mapping[str, Any]],
    *,
    execution_mode: str = "replay",
    provider: str | None = None,
    model: str | None = None,
    run_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Purely evaluate normalized Stage1 records against the frozen manifest."""

    if execution_mode not in EXECUTION_MODES:
        raise BenchmarkStage1ContractError(
            f"execution_mode must be one of {sorted(EXECUTION_MODES)!r}"
        )
    ordered_cases, prepare_index = _index_inputs(cases, prepare_result)
    record_index = _validate_stage1_records(stage1_records, prepare_index)

    results: list[dict[str, Any]] = []
    for case in ordered_cases:
        case_id = case["case_id"]
        expected = case["expected"]
        observability = case["observability"]
        prepare_case = prepare_index[case_id]
        prepare_actual = prepare_case["actual"]
        result = _base_case_result(case, prepare_case)

        if observability.get("status") != "direct" or observability.get("eligible") is not True:
            result.update(
                {
                    "stage1": {"execution_status": "not_run_observability"},
                    "classification": {
                        "status": "not_scored_observability",
                        "reason": None,
                    },
                    "end_to_end": {
                        "status": "not_scored_observability",
                        "reason": None,
                    },
                    "mapping": {
                        "status": "not_scored_observability",
                        "actual_ids": [],
                    },
                    "manual_audit_flags": [],
                }
            )
            results.append(result)
            continue

        selected = prepare_actual.get("candidate_selected") is True
        ground_truth = expected["project_ground_truth"]
        if not selected:
            if ground_truth == "attack_positive":
                stage1_status = "not_run_candidate_miss"
                end_status = "fail_candidate_miss"
                end_reason = "positive_case_not_selected_by_prepare"
            else:
                stage1_status = "not_run_prepare_suppression"
                end_status = "passed_by_prepare_suppression"
                end_reason = None
            result.update(
                {
                    "stage1": {"execution_status": stage1_status},
                    "classification": {"status": stage1_status, "reason": None},
                    "end_to_end": {"status": end_status, "reason": end_reason},
                    "mapping": {
                        "status": "not_scored_stage1_not_run",
                        "actual_ids": [],
                    },
                    "manual_audit_flags": [],
                }
            )
            results.append(result)
            continue

        record = record_index.get(case_id)
        if record is None:
            result.update(
                {
                    "stage1": {"execution_status": "missing_required_stage1_record"},
                    "classification": {
                        "status": "stage1_unavailable",
                        "reason": "missing_required_stage1_record",
                    },
                    "end_to_end": {
                        "status": "stage1_unavailable",
                        "reason": "missing_required_stage1_record",
                    },
                    "mapping": {
                        "status": "not_scored_stage1_unavailable",
                        "actual_ids": [],
                    },
                    "manual_audit_flags": [],
                }
            )
            results.append(result)
            continue

        execution_status = record["execution_status"]
        if execution_status != "completed":
            stage1_payload = {"execution_status": execution_status}
            if "error" in record:
                stage1_payload["error"] = copy.deepcopy(record["error"])
            result.update(
                {
                    "stage1": stage1_payload,
                    "classification": {
                        "status": "stage1_unavailable",
                        "reason": execution_status,
                    },
                    "end_to_end": {
                        "status": "stage1_unavailable",
                        "reason": execution_status,
                    },
                    "mapping": {
                        "status": "not_scored_stage1_unavailable",
                        "actual_ids": [],
                    },
                    "manual_audit_flags": [],
                }
            )
            results.append(result)
            continue

        stage1 = copy.deepcopy(record["stage1"])
        stage1["execution_status"] = "completed"
        verdict = stage1["verdict"]
        classification = _evaluate_verdict(expected, verdict)
        mapping_payload = record["standards_mapping"]
        actual_ids = _mapping_ids(mapping_payload, case_id)
        if classification["status"] == "pass":
            mapping_result = _evaluate_mapping(
                expected, verdict, mapping_payload, case_id
            )
        else:
            mapping_result = {
                "status": "not_scored_due_to_classification",
                "actual_ids": actual_ids,
                "missing_required_ids": [],
                "present_forbidden_ids": [],
            }
        if classification["status"] == "pass":
            end_to_end = {"status": "pass", "reason": None}
        else:
            end_to_end = {
                "status": "fail_stage1_verdict",
                "reason": classification["reason"],
            }
        result.update(
            {
                "stage1": stage1,
                "classification": classification,
                "end_to_end": end_to_end,
                "mapping": mapping_result,
                "manual_audit_flags": _manual_audit_flags(stage1),
            }
        )
        results.append(result)

    direct = [item for item in results if item["observability"]["status"] == "direct"]
    positives = [
        item
        for item in direct
        if item["expected"]["project_ground_truth"] == "attack_positive"
    ]
    expected_candidates = [
        item
        for item in direct
        if item["expected"]["candidate_expected"] is True
    ]
    negatives = [
        item
        for item in direct
        if item["expected"]["project_ground_truth"] == "project_negative"
    ]
    selected = [item for item in direct if item["prepare"]["candidate_selected"] is True]
    completed = [
        item for item in selected if item["stage1"]["execution_status"] == "completed"
    ]
    attempted = [
        item
        for item in selected
        if item["stage1"]["execution_status"]
        not in {
            "missing_required_stage1_record",
            "live_execution_unavailable",
            "prepare_candidate_contract_error",
        }
    ]
    failed = [item for item in attempted if item not in completed]
    prepare_complete = prepare_result.get("run", {}).get("complete") is True
    complete = prepare_complete and len(completed) == len(selected)

    classification_passed = sum(
        item["classification"]["status"] == "pass" for item in completed
    )
    positive_passed = sum(item["end_to_end"]["status"] == "pass" for item in positives)
    negative_passed = sum(
        item["end_to_end"]["status"] in {"pass", "passed_by_prepare_suppression"}
        for item in negatives
    )
    overall_passed = positive_passed + negative_passed
    mapping_scored = [
        item for item in completed if item["mapping"]["status"] in {"pass", "fail"}
    ]
    mapping_passed = sum(item["mapping"]["status"] == "pass" for item in mapping_scored)
    negative_control_complete = all(
        item["end_to_end"]["status"] != "stage1_unavailable" for item in negatives
    )

    status_counts = Counter(item["observability"]["status"] for item in results)
    counts = {
        "source_cases_total": len(results),
        "directly_eligible_cases": status_counts["direct"],
        "partial_capability_cases": status_counts["partial"],
        "out_of_scope_cases": status_counts["out_of_scope"],
        "expected_candidate_cases": len(expected_candidates),
        "project_negative_cases": len(negatives),
        "candidate_selected_cases": len(selected),
        "stage1_attempted_cases": len(attempted),
        "stage1_completed_cases": len(completed),
        "stage1_failed_cases": len(failed),
    }
    dependent_complete = complete
    metrics = {
        "candidate_recall_on_expected_candidates": _fraction(
            sum(
                item["prepare"]["candidate_selected"] is True
                for item in expected_candidates
            ),
            len(expected_candidates),
            complete=prepare_complete,
        ),
        "stage1_verdict_compatibility_given_candidate": _fraction(
            classification_passed, len(completed), complete=dependent_complete
        ),
        "end_to_end_positive_verdict_compatibility": _fraction(
            positive_passed, len(positives), complete=dependent_complete
        ),
        "negative_control_pass_rate": _fraction(
            negative_passed, len(negatives), complete=negative_control_complete
        ),
        "negative_candidate_suppression_rate": _fraction(
            sum(item["prepare"]["candidate_selected"] is False for item in negatives),
            len(negatives),
            complete=prepare_complete,
        ),
        "mapping_consistency_given_compatible_classification": _fraction(
            mapping_passed, len(mapping_scored), complete=dependent_complete
        ),
        "end_to_end_verdict_compatibility": _fraction(
            overall_passed, len(direct), complete=dependent_complete
        ),
    }

    revisions = {case["source"]["revision"] for case in ordered_cases}
    metadata = copy.deepcopy(dict(run_metadata or {}))
    run = {
        "level": "level_1_normalized_row",
        "stage": STAGE1_STAGE,
        "execution_mode": execution_mode,
        "provider": provider,
        "model": model,
        "complete": complete,
        "prepare_result_complete": prepare_complete,
        "candidate_input_fidelity": (
            "failed"
            if any(
                item["stage1"]["execution_status"]
                == "prepare_candidate_contract_error"
                for item in selected
            )
            else "verified"
        ),
    }
    run.update(metadata)
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "benchmark": BENCHMARK_NAME,
        "source_revision": next(iter(revisions)),
        "run": run,
        "counts": counts,
        "metrics": metrics,
        "diagnostics": {
            "stage1_unavailable_cases": [
                item["case_id"]
                for item in selected
                if item["stage1"]["execution_status"] != "completed"
            ],
            "classification_failed_cases": [
                item["case_id"]
                for item in completed
                if item["classification"]["status"] == "fail"
            ],
            "mapping_not_scored_due_to_classification_cases": [
                item["case_id"]
                for item in completed
                if item["mapping"]["status"] == "not_scored_due_to_classification"
            ],
            "mapping_not_scored_no_contract_cases": [
                item["case_id"]
                for item in completed
                if item["mapping"]["status"] == "not_scored_no_mapping_contract"
            ],
            "manual_audit_flagged_cases": [
                item["case_id"] for item in results if item["manual_audit_flags"]
            ],
        },
        "cases": results,
    }
    return result


def _regenerate_candidate(
    case: Mapping[str, Any],
    prepare_case: Mapping[str, Any],
    *,
    sequence_index: int,
    prepare_builder: Callable[..., Any] = build_outputs,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = build_synthetic_security_row(case, sequence_index=sequence_index)
    payload = build_prepare_export_payload(row)
    try:
        llm_input, candidates, _noise, _reasons, _filtered = prepare_builder(
            payload,
            min_score=PREPARE_MIN_SCORE,
            min_repeat_aggregate=PREPARE_MIN_REPEAT_AGGREGATE,
            source_tables=[SOURCE_TABLE],
        )
    except ValueError as exc:
        raise BenchmarkStage1ContractError(
            f"{case['case_id']}: Prepare candidate regeneration failed: {exc}"
        ) from exc
    request_id = benchmark_request_id(case["case_id"])
    matches = [item for item in candidates if item.get("request_id") == request_id]
    if len(matches) != 1:
        raise BenchmarkStage1ContractError(
            f"{case['case_id']}: regenerated candidate count must be 1; got {len(matches)}"
        )
    candidate = matches[0]
    expected = _expected_candidate_input(case["case_id"], prepare_case)
    actual = {field: copy.deepcopy(candidate.get(field)) for field in FIDELITY_FIELDS}
    mismatches = [field for field in FIDELITY_FIELDS if actual[field] != expected[field]]
    if mismatches:
        raise BenchmarkStage1ContractError(
            f"{case['case_id']}: regenerated candidate differs from Prepare artifact: {mismatches!r}"
        )
    return copy.deepcopy(llm_input["meta"]), copy.deepcopy(candidate)


def _candidate_input(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {field: copy.deepcopy(candidate.get(field)) for field in FIDELITY_FIELDS}


def _normalized_success_record(
    case_id: str,
    candidate: Mapping[str, Any],
    result: Stage1Result | Mapping[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    if is_dataclass(result):
        row = asdict(result)
    elif isinstance(result, Mapping):
        row = copy.deepcopy(dict(result))
    else:
        raise BenchmarkStage1ContractError(
            f"{case_id}: classifier success must be Stage1Result or object"
        )
    stage1 = {
        key: copy.deepcopy(row.get(key))
        for key in (
            "verdict",
            "severity",
            "confidence",
            "false_positive_possible",
            "reasoning_summary",
            "evidence_fields",
            "recommended_actions",
        )
    }
    mapping = build_security_standards_mapping(row, candidate)
    return {
        "case_id": case_id,
        "request_id": candidate["request_id"],
        "execution_status": "completed",
        "mode": mode,
        "model": row.get("model"),
        "candidate_input": _candidate_input(candidate),
        "stage1": stage1,
        "standards_mapping": mapping,
        "response_id": row.get("response_id"),
        "llm_usage": copy.deepcopy(row.get("llm_usage")),
    }


def _error_status(error_type: str) -> str:
    if error_type in {"json_decode_error", "empty_output"}:
        return "stage1_parse_error"
    if "validation" in error_type:
        return "stage1_validation_error"
    if error_type in {"http_error", "url_error"}:
        return "stage1_api_error"
    return "stage1_runtime_error"


def _normalized_error_record(
    case_id: str,
    candidate: Mapping[str, Any],
    error: Stage1Error | Mapping[str, Any],
    *,
    mode: str,
    model: str,
) -> dict[str, Any]:
    if is_dataclass(error):
        row = asdict(error)
    elif isinstance(error, Mapping):
        row = copy.deepcopy(dict(error))
    else:
        raise BenchmarkStage1ContractError(
            f"{case_id}: classifier error must be Stage1Error or object"
        )
    error_type = str(row.get("error_type") or "unexpected_error")
    return {
        "case_id": case_id,
        "request_id": candidate["request_id"],
        "execution_status": _error_status(error_type),
        "mode": mode,
        "model": model,
        "candidate_input": _candidate_input(candidate),
        "error": {
            "type": error_type,
            "message": str(row.get("error_message") or ""),
            "response_id": row.get("response_id"),
        },
        "llm_usage": copy.deepcopy(row.get("llm_usage")),
    }


def run_live_stage1_benchmark(
    cases: Sequence[Mapping[str, Any]],
    prepare_result: Mapping[str, Any],
    *,
    provider: str | None = None,
    model: str | None = None,
    mode: str = DEFAULT_MODE,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    store: bool = False,
    reasoning_effort: str = "none",
    max_evidence_items: int = 8,
    sleep_sec: float = 0.0,
    classifier: Stage1Classifier = classify_candidate,
    prepare_builder: Callable[..., Any] = build_outputs,
) -> dict[str, Any]:
    """Run production Stage1 for candidate-selected direct cases only."""

    ordered_cases, prepare_index = _index_inputs(cases, prepare_result)
    llm_config = resolve_llm_config(provider)
    selected_model = choose_model(llm_config.provider, mode, model)
    selected_cases = [
        case
        for case in ordered_cases
        if case["observability"]["status"] == "direct"
        and prepare_index[case["case_id"]]["actual"]["candidate_selected"] is True
    ]
    records: list[dict[str, Any]] = []
    direct_positions: dict[str, int] = {}
    direct_index = 0
    for case in ordered_cases:
        if case["observability"]["status"] == "direct":
            direct_positions[case["case_id"]] = direct_index
            direct_index += 1

    regenerated: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    regeneration_errors: dict[str, str] = {}
    for case in selected_cases:
        case_id = case["case_id"]
        try:
            regenerated[case_id] = _regenerate_candidate(
                case,
                prepare_index[case_id],
                sequence_index=direct_positions[case_id],
                prepare_builder=prepare_builder,
            )
        except BenchmarkStage1ContractError as exc:
            regeneration_errors[case_id] = str(exc)

    if not llm_config.api_key:
        for case in selected_cases:
            case_id = case["case_id"]
            if case_id in regeneration_errors:
                expected_input = _expected_candidate_input(
                    case_id, prepare_index[case_id]
                )
                records.append(
                    {
                        "case_id": case_id,
                        "request_id": expected_input["request_id"],
                        "execution_status": "prepare_candidate_contract_error",
                        "mode": mode,
                        "model": selected_model,
                        "candidate_input": expected_input,
                        "error": {
                            "type": "candidate_fidelity_error",
                            "message": regeneration_errors[case_id],
                        },
                    }
                )
                continue
            _meta, regenerated_candidate = regenerated[case_id]
            verified_input = _candidate_input(regenerated_candidate)
            records.append(
                {
                    "case_id": case_id,
                    "request_id": verified_input["request_id"],
                    "execution_status": "live_execution_unavailable",
                    "mode": mode,
                    "model": selected_model,
                    "candidate_input": verified_input,
                    "error": {
                        "type": "missing_api_credential",
                        "message": provider_api_key_error(llm_config.provider),
                    },
                }
            )
        return evaluate_stage1_benchmark(
            ordered_cases,
            prepare_result,
            records,
            execution_mode="live",
            provider=llm_config.provider,
            model=selected_model,
            run_metadata={
                "execution_availability": "live_execution_unavailable",
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )

    selected_position = 0
    for case in selected_cases:
        case_id = case["case_id"]
        prepare_case = prepare_index[case_id]
        if case_id in regeneration_errors:
            expected_input = _expected_candidate_input(case_id, prepare_case)
            records.append(
                {
                    "case_id": case_id,
                    "request_id": expected_input["request_id"],
                    "execution_status": "prepare_candidate_contract_error",
                    "mode": mode,
                    "model": selected_model,
                    "candidate_input": expected_input,
                    "error": {
                        "type": "candidate_fidelity_error",
                        "message": regeneration_errors[case_id],
                    },
                }
            )
            selected_position += 1
            continue

        meta, candidate = regenerated[case_id]

        result, error = classifier(
            llm_config=llm_config,
            model=selected_model,
            meta=meta,
            candidate=candidate,
            timeout_sec=timeout_sec,
            store=store,
            reasoning_effort=reasoning_effort,
            max_evidence_items=max_evidence_items,
            candidate_index=selected_position,
        )
        if (result is None) == (error is None):
            raise BenchmarkStage1ContractError(
                f"{case_id}: classifier must return exactly one of result or error"
            )
        if result is not None:
            records.append(
                _normalized_success_record(case_id, candidate, result, mode=mode)
            )
        else:
            assert error is not None
            records.append(
                _normalized_error_record(
                    case_id, candidate, error, mode=mode, model=selected_model
                )
            )
        selected_position += 1
        if sleep_sec > 0 and selected_position < len(selected_cases):
            time.sleep(sleep_sec)

    return evaluate_stage1_benchmark(
        ordered_cases,
        prepare_result,
        records,
        execution_mode="live",
        provider=llm_config.provider,
        model=selected_model,
        run_metadata={
            "execution_availability": "available",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )


def load_stage1_replay(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkStage1ContractError(f"cannot load Stage1 replay {path}: {exc}") from exc
    if isinstance(payload, list):
        return payload, {}
    if not isinstance(payload, Mapping):
        raise BenchmarkStage1ContractError("Stage1 replay root must be an object or array")
    records = payload.get("records")
    if not isinstance(records, list):
        raise BenchmarkStage1ContractError("Stage1 replay object must contain records array")
    if payload.get("schema_version") not in {None, REPLAY_SCHEMA_VERSION}:
        raise BenchmarkStage1ContractError("unsupported Stage1 replay schema_version")
    metadata = {
        key: copy.deepcopy(payload.get(key))
        for key in (
            "benchmark",
            "source_revision",
            "manifest_version",
            "prepare_contract",
            "stage1_production_revision",
            "provider",
            "model",
            "created_at",
        )
        if key in payload
    }
    return records, metadata


def validate_stage1_benchmark_result(result: Mapping[str, Any]) -> list[str]:
    """Return lightweight semantic validation errors without jsonschema runtime."""

    errors: list[str] = []
    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RESULT_SCHEMA_VERSION}")
    if result.get("benchmark") != BENCHMARK_NAME:
        errors.append(f"benchmark must be {BENCHMARK_NAME}")
    run = result.get("run")
    counts = result.get("counts")
    metrics = result.get("metrics")
    cases = result.get("cases")
    if not isinstance(run, Mapping) or run.get("stage") != STAGE1_STAGE:
        errors.append(f"run.stage must be {STAGE1_STAGE}")
    if not isinstance(counts, Mapping):
        errors.append("counts must be an object")
        counts = {}
    if not isinstance(metrics, Mapping):
        errors.append("metrics must be an object")
    if not isinstance(cases, list):
        errors.append("cases must be an array")
        cases = []
    ids = [item.get("case_id") for item in cases if isinstance(item, Mapping)]
    if len(ids) != len(cases) or len(ids) != len(set(ids)):
        errors.append("result cases must have unique case IDs")
    if counts.get("source_cases_total") != len(cases):
        errors.append("counts.source_cases_total must equal result case count")
    if ids != sorted(ids, key=lambda value: tuple(int(x) for x in value.split(".")[-2:])):
        errors.append("result cases must use deterministic numeric ordering")
    return errors


def write_stage1_benchmark_result(
    result: Mapping[str, Any], output_path: str | Path
) -> None:
    errors = validate_stage1_benchmark_result(result)
    if errors:
        raise BenchmarkStage1ContractError(
            "invalid Stage1 benchmark result:\n- " + "\n- ".join(errors)
        )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json_object(path: str | Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkStage1ContractError(f"cannot load {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkStage1ContractError(f"{label} root must be an object")
    return value


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate production Stage1 on the OWASP CRS external benchmark"
    )
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--prepare-result", required=True)
    parser.add_argument("--mode", choices=["live", "replay"], required=True)
    parser.add_argument("--stage1-results", help="Normalized replay JSON (replay mode)")
    parser.add_argument("--provider", choices=["openai", "anthropic"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--llm-mode", choices=sorted(ALLOWED_MODES), default=DEFAULT_MODE)
    parser.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument("--store", action="store_true")
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "low", "medium", "high", "xhigh"],
        default="none",
    )
    parser.add_argument("--max-evidence-items", type=int, default=8)
    parser.add_argument("--sleep-sec", type=float, default=0.0)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source_cases = load_owasp_crs_cases(args.source_dir)
        manifest = load_benchmark_manifest(args.manifest)
        cases = build_normalized_benchmark_cases(source_cases, manifest)
        prepare_result = _load_json_object(args.prepare_result, "Prepare result")
        if args.mode == "live":
            if args.stage1_results:
                raise BenchmarkStage1ContractError(
                    "--stage1-results is only valid with --mode replay"
                )
            result = run_live_stage1_benchmark(
                cases,
                prepare_result,
                provider=args.provider,
                model=args.model,
                mode=args.llm_mode,
                timeout_sec=args.timeout_sec,
                store=args.store,
                reasoning_effort=args.reasoning_effort,
                max_evidence_items=args.max_evidence_items,
                sleep_sec=args.sleep_sec,
            )
        else:
            if not args.stage1_results:
                raise BenchmarkStage1ContractError(
                    "--stage1-results is required with --mode replay"
                )
            records, replay_metadata = load_stage1_replay(args.stage1_results)
            if replay_metadata.get("benchmark") not in {None, BENCHMARK_NAME}:
                raise BenchmarkStage1ContractError("replay benchmark identity mismatch")
            source_revision = cases[0]["source"]["revision"] if cases else None
            if replay_metadata.get("source_revision") not in {None, source_revision}:
                raise BenchmarkStage1ContractError("replay source revision mismatch")
            result = evaluate_stage1_benchmark(
                cases,
                prepare_result,
                records,
                execution_mode="replay",
                provider=replay_metadata.get("provider") or args.provider,
                model=replay_metadata.get("model") or args.model,
                run_metadata={"replay_provenance": replay_metadata},
            )
        write_stage1_benchmark_result(result, args.output)
    except (
        BenchmarkContractError,
        BenchmarkPrepareContractError,
        BenchmarkStage1ContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    counts = result["counts"]
    print(f"[OK] output: {args.output}")
    if result["run"].get("execution_availability") == "live_execution_unavailable":
        print(
            "[UNAVAILABLE] live Stage1 execution: provider credential is not configured",
            file=sys.stderr,
        )
    print(
        f"[{'OK' if result['run']['complete'] else 'INCOMPLETE'}] Stage1 completed: "
        f"{counts['stage1_completed_cases']}/{counts['stage1_attempted_cases']}"
    )
    metric = result["metrics"]["stage1_verdict_compatibility_given_candidate"]
    print(
        f"[{'OK' if result['run']['complete'] else 'INCOMPLETE'}] "
        "Stage1 compatibility given candidate: "
        f"{metric['passed']}/{metric['total']} ({metric['rate']})"
    )
    return 0 if result["run"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
