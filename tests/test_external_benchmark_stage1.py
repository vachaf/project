from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import src.external_benchmark_stage1 as stage1_benchmark
from src.external_benchmark_crs import (
    PINNED_REVISION,
    build_normalized_benchmark_cases,
    load_benchmark_manifest,
    load_owasp_crs_cases,
)
from src.external_benchmark_prepare import benchmark_request_id, run_prepare_benchmark
from src.external_benchmark_stage1 import (
    RESULT_SCHEMA_VERSION,
    BenchmarkStage1ContractError,
    evaluate_stage1_benchmark,
    run_live_stage1_benchmark,
    validate_stage1_benchmark_result,
    write_stage1_benchmark_result,
)
from src.llm_client import LLMConfig
from src.security_standards_mapping import build_security_standards_mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "benchmarks" / "sources" / "owasp_crs" / PINNED_REVISION
MANIFEST_PATH = ROOT / "benchmarks" / "manifests" / "owasp_crs_path_file_access.v1.json"
SCHEMA_PATH = (
    ROOT
    / "benchmarks"
    / "schemas"
    / "external_security_benchmark_stage1_result.v1.schema.json"
)
SCRIPT = ROOT / "src" / "external_benchmark_stage1.py"


@pytest.fixture(scope="module")
def normalized_cases() -> list[dict]:
    return build_normalized_benchmark_cases(
        load_owasp_crs_cases(SOURCE_DIR), load_benchmark_manifest(MANIFEST_PATH)
    )


@pytest.fixture(scope="module")
def prepare_result(normalized_cases: list[dict]) -> dict:
    return run_prepare_benchmark(normalized_cases)


def by_id(items: list[dict], case_id: str) -> dict:
    return next(item for item in items if item["case_id"] == case_id)


def prepare_with_selected(
    normalized_cases: list[dict], prepare_result: dict, selected_ids: set[str]
) -> dict:
    result = copy.deepcopy(prepare_result)
    case_index = {case["case_id"]: case for case in normalized_cases}
    for item in result["cases"]:
        if item["observability"]["status"] != "direct":
            continue
        case_id = item["case_id"]
        selected = case_id in selected_ids
        actual = item["actual"]
        actual["candidate_selected"] = selected
        actual["candidate_count_for_request"] = int(selected)
        actual["raw_request_target"] = case_index[case_id]["request"]["request_target"]
        if selected and actual.get("candidate_score") is None:
            actual["candidate_score"] = 4
            actual["prepare_verdict_hint"] = "suspicious"
            actual["prepare_reason_hints"] = ["controlled:test"]
        if not selected:
            actual["candidate_score"] = None
            actual["prepare_verdict_hint"] = None
            actual["prepare_reason_hints"] = []
    return result


def candidate_input(prepare_result: dict, case_id: str) -> dict:
    actual = by_id(prepare_result["cases"], case_id)["actual"]
    return {
        "request_id": benchmark_request_id(case_id),
        "raw_request_target": actual["raw_request_target"],
        "verdict_hint": actual["prepare_verdict_hint"],
        "reason_hints": copy.deepcopy(actual["prepare_reason_hints"]),
        "score": actual["candidate_score"],
    }


def mapping_payload(*ids: str) -> dict:
    return {
        "schema_version": "security_standards_mapping.v1",
        "source": "controlled",
        "observability": "attempt_only",
        "items": [{"id": value} for value in ids],
        "unmapped_reason": "",
    }


def stage1_record(
    prepare_result: dict,
    case_id: str,
    verdict: str,
    *mapping_ids: str,
    reasoning_summary: str = "관찰된 요청 패턴을 분류했다.",
) -> dict:
    input_fields = candidate_input(prepare_result, case_id)
    return {
        "case_id": case_id,
        "request_id": input_fields["request_id"],
        "execution_status": "completed",
        "mode": "controlled",
        "model": "controlled-model",
        "candidate_input": input_fields,
        "stage1": {
            "verdict": verdict,
            "severity": "medium",
            "confidence": "high",
            "false_positive_possible": False,
            "reasoning_summary": reasoning_summary,
            "evidence_fields": ["query_string"],
            "recommended_actions": ["review_raw_log"],
        },
        "standards_mapping": mapping_payload(*mapping_ids),
    }


def evaluate_one(
    normalized_cases: list[dict],
    prepare_result: dict,
    case_id: str,
    verdict: str,
    *mapping_ids: str,
) -> dict:
    prepared = prepare_with_selected(normalized_cases, prepare_result, {case_id})
    result = evaluate_stage1_benchmark(
        normalized_cases,
        prepared,
        [stage1_record(prepared, case_id, verdict, *mapping_ids)],
        execution_mode="controlled",
        model="controlled-model",
    )
    return by_id(result["cases"], case_id)


def test_exact_policy_pass(normalized_cases: list[dict], prepare_result: dict) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.8",
        "suspicious_path_traversal",
        "A01:2025",
        "CWE-22",
        "WSTG-ATHZ-01",
    )
    assert case["classification"] == {"status": "pass", "reason": None}


def test_exact_policy_fail(normalized_cases: list[dict], prepare_result: dict) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.8",
        "suspicious_file_disclosure",
    )
    assert case["classification"]["status"] == "fail"
    assert case["end_to_end"]["status"] == "fail_stage1_verdict"


def test_compatible_set_policy_pass(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930120.4",
        "suspicious_scan",
    )
    assert case["classification"]["status"] == "pass"
    assert case["mapping"]["status"] == "not_scored_no_mapping_contract"


def test_compatible_set_policy_fail(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930120.4",
        "suspicious_path_traversal",
        "CWE-22",
    )
    assert case["classification"] == {
        "status": "fail",
        "reason": "actual_verdict_forbidden",
    }


def test_forbidden_only_policy_pass(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.4",
        "likely_false_positive",
    )
    assert case["classification"]["status"] == "pass"
    assert case["end_to_end"]["status"] == "pass"


def test_forbidden_only_policy_fail(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.4",
        "suspicious_path_traversal",
        "CWE-22",
    )
    assert case["classification"]["reason"] == "actual_verdict_forbidden"


def test_allowed_forbidden_overlap_fails_contract_safely(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    cases = copy.deepcopy(normalized_cases)
    case = by_id(cases, "owasp_crs.930110.8")
    case["expected"]["forbidden_stage1_verdicts"].append(
        "suspicious_path_traversal"
    )
    with pytest.raises(BenchmarkStage1ContractError, match="overlap"):
        evaluate_stage1_benchmark(cases, prepare_result, [])


def test_not_scored_cases_are_preserved_and_omitted_from_denominators(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(normalized_cases, prepare_result, set())
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [], execution_mode="controlled"
    )
    partial = by_id(result["cases"], "owasp_crs.930100.1")
    assert partial["stage1"]["execution_status"] == "not_run_observability"
    assert partial["classification"]["status"] == "not_scored_observability"
    assert result["metrics"]["end_to_end_verdict_compatibility"]["total"] == 27


def test_positive_candidate_miss_is_not_run_and_e2e_fail(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(normalized_cases, prepare_result, set())
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [], execution_mode="controlled"
    )
    case = by_id(result["cases"], "owasp_crs.930120.4")
    assert case["stage1"] == {"execution_status": "not_run_candidate_miss"}
    assert case["end_to_end"]["status"] == "fail_candidate_miss"


def test_positive_selected_enters_stage1_score_lane(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930110.8"}
    )
    record = stage1_record(
        prepared,
        "owasp_crs.930110.8",
        "suspicious_path_traversal",
        "A01:2025",
        "CWE-22",
        "WSTG-ATHZ-01",
    )
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [record], execution_mode="controlled"
    )
    assert result["metrics"]["stage1_verdict_compatibility_given_candidate"] == {
        "passed": 1,
        "total": 1,
        "rate": 1.0,
    }


def test_negative_prepare_suppression_is_end_to_end_pass(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(normalized_cases, prepare_result, set())
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [], execution_mode="controlled"
    )
    case = by_id(result["cases"], "owasp_crs.930110.4")
    assert case["stage1"]["execution_status"] == "not_run_prepare_suppression"
    assert case["end_to_end"]["status"] == "passed_by_prepare_suppression"
    assert result["metrics"]["negative_control_pass_rate"]["passed"] == 8


def test_negative_selected_requires_stage1_record(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930110.4"}
    )
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [], execution_mode="controlled"
    )
    case = by_id(result["cases"], "owasp_crs.930110.4")
    assert case["stage1"]["execution_status"] == "missing_required_stage1_record"
    assert result["run"]["complete"] is False
    assert result["metrics"]["negative_control_pass_rate"]["rate"] is None


def test_missing_positive_stage1_record_is_incomplete_not_inconclusive(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930110.8"}
    )
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [], execution_mode="controlled"
    )
    case = by_id(result["cases"], "owasp_crs.930110.8")
    assert case["classification"]["status"] == "stage1_unavailable"
    assert "verdict" not in case["stage1"]
    assert result["run"]["complete"] is False


def test_duplicate_stage1_record_is_contract_error(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930110.8"}
    )
    record = stage1_record(
        prepared, "owasp_crs.930110.8", "suspicious_path_traversal", "CWE-22"
    )
    with pytest.raises(BenchmarkStage1ContractError, match="duplicate Stage1"):
        evaluate_stage1_benchmark(normalized_cases, prepared, [record, record])


def test_record_for_suppressed_case_is_contract_error(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared_selected = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930110.4"}
    )
    record = stage1_record(
        prepared_selected, "owasp_crs.930110.4", "likely_false_positive"
    )
    prepared_suppressed = prepare_with_selected(normalized_cases, prepare_result, set())
    with pytest.raises(BenchmarkStage1ContractError, match="not selected"):
        evaluate_stage1_benchmark(normalized_cases, prepared_suppressed, [record])


def test_candidate_input_fidelity_mismatch_is_contract_error(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930110.8"}
    )
    record = stage1_record(
        prepared, "owasp_crs.930110.8", "suspicious_path_traversal", "CWE-22"
    )
    record["candidate_input"]["score"] += 1
    with pytest.raises(BenchmarkStage1ContractError, match="fidelity mismatch"):
        evaluate_stage1_benchmark(normalized_cases, prepared, [record])


def test_compatible_classification_required_mapping_ids_pass(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.8",
        "suspicious_path_traversal",
        "A01:2025",
        "CWE-22",
        "WSTG-ATHZ-01",
    )
    assert case["mapping"]["status"] == "pass"


def test_required_mapping_id_missing_fails(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.8",
        "suspicious_path_traversal",
        "A01:2025",
        "CWE-22",
    )
    assert case["mapping"]["status"] == "fail"
    assert case["mapping"]["missing_required_ids"] == ["WSTG-ATHZ-01"]


def test_forbidden_mapping_id_present_fails(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930120.2",
        "suspicious_file_disclosure",
        "CWE-22",
    )
    assert case["mapping"]["status"] == "fail"
    assert case["mapping"]["present_forbidden_ids"] == ["CWE-22"]


def test_classification_failure_gates_mapping_score(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930120.2",
        "suspicious_path_traversal",
        "CWE-22",
    )
    assert case["classification"]["status"] == "fail"
    assert case["mapping"]["status"] == "not_scored_due_to_classification"


def test_additional_non_forbidden_mapping_is_accepted(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.8",
        "suspicious_path_traversal",
        "A01:2025",
        "CWE-22",
        "WSTG-ATHZ-01",
        "EXTRA-VALID-ID",
    )
    assert case["mapping"]["status"] == "pass"


def test_empty_mapping_obeys_manifest_contract(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    no_required = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930120.2",
        "suspicious_file_disclosure",
    )
    required = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.8",
        "suspicious_path_traversal",
    )
    assert no_required["mapping"]["status"] == "pass"
    assert required["mapping"]["status"] == "fail"


def test_930110_8_traversal_classification_and_mapping_regression(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930110.8",
        "suspicious_path_traversal",
        "A01:2025",
        "CWE-22",
        "WSTG-ATHZ-01",
    )
    assert case["prepare"]["candidate_selected"] is True
    assert "traversal:dotdot_slash(+4)" in case["prepare"]["prepare_reason_hints"]
    assert case["classification"]["status"] == case["mapping"]["status"] == "pass"


def test_930120_2_exact_file_disclosure_and_cwe22_forbidden_regression(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930120.2"}
    )
    actual = by_id(prepared["cases"], "owasp_crs.930120.2")["actual"]
    production_mapping = build_security_standards_mapping(
        {
            "verdict": "suspicious_file_disclosure",
            "reason_hints": actual["prepare_reason_hints"],
            "raw_request_target": actual["raw_request_target"],
        }
    )
    ids = {item["id"] for item in production_mapping["items"]}
    assert {"A02:2025", "CWE-552", "WSTG-CONF-03", "WSTG-CONF-04"} <= ids
    assert "CWE-22" not in ids
    record = stage1_record(
        prepared, "owasp_crs.930120.2", "suspicious_file_disclosure", *sorted(ids)
    )
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [record], execution_mode="controlled"
    )
    case = by_id(result["cases"], "owasp_crs.930120.2")
    assert case["classification"]["status"] == case["mapping"]["status"] == "pass"


def test_930100_3_frozen_exact_expectation_is_preserved(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    case = evaluate_one(
        normalized_cases,
        prepare_result,
        "owasp_crs.930100.3",
        "suspicious_file_disclosure",
    )
    assert case["prepare"]["prepare_verdict_hint"] == "suspicious_file_disclosure"
    assert case["expected"]["allowed_stage1_verdicts"] == [
        "suspicious_path_traversal"
    ]
    assert case["classification"]["status"] == "fail"


def test_candidate_miss_resource_case_never_fabricates_stage1(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(normalized_cases, prepare_result, set())
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [], execution_mode="controlled"
    )
    case = by_id(result["cases"], "owasp_crs.930120.13")
    assert case["stage1"] == {"execution_status": "not_run_candidate_miss"}
    assert "verdict" not in case["stage1"]


def compatible_records_for_current_baseline(
    normalized_cases: list[dict], prepare_result: dict
) -> list[dict]:
    case_index = {case["case_id"]: case for case in normalized_cases}
    records: list[dict] = []
    for prepared in prepare_result["cases"]:
        if prepared["actual"]["candidate_selected"] is not True:
            continue
        case_id = prepared["case_id"]
        verdict = case_index[case_id]["expected"]["allowed_stage1_verdicts"][0]
        mapping = build_security_standards_mapping(
            {
                "verdict": verdict,
                "reason_hints": prepared["actual"]["prepare_reason_hints"],
                "raw_request_target": prepared["actual"]["raw_request_target"],
            }
        )
        records.append(
            stage1_record(
                prepare_result,
                case_id,
                verdict,
                *(item["id"] for item in mapping["items"]),
            )
        )
    return records


@pytest.fixture(scope="module")
def controlled_full_result(
    normalized_cases: list[dict], prepare_result: dict
) -> dict:
    return evaluate_stage1_benchmark(
        normalized_cases,
        prepare_result,
        compatible_records_for_current_baseline(normalized_cases, prepare_result),
        execution_mode="controlled",
        model="controlled-model",
    )


def test_full_result_preserves_36_case_accounting(controlled_full_result: dict) -> None:
    assert len(controlled_full_result["cases"]) == 36
    assert controlled_full_result["counts"] == {
        "source_cases_total": 36,
        "directly_eligible_cases": 27,
        "partial_capability_cases": 3,
        "out_of_scope_cases": 6,
        "expected_candidate_cases": 19,
        "project_negative_cases": 8,
        "candidate_selected_cases": 9,
        "stage1_attempted_cases": 9,
        "stage1_completed_cases": 9,
        "stage1_failed_cases": 0,
    }


def test_manifest_candidate_denominators_are_used(controlled_full_result: dict) -> None:
    assert controlled_full_result["metrics"][
        "candidate_recall_on_expected_candidates"
    ] == {"passed": 9, "total": 19, "rate": 9 / 19}
    assert controlled_full_result["metrics"][
        "negative_candidate_suppression_rate"
    ] == {"passed": 8, "total": 8, "rate": 1.0}


def test_positive_and_negative_headlines_are_separate(controlled_full_result: dict) -> None:
    metrics = controlled_full_result["metrics"]
    assert metrics["end_to_end_positive_verdict_compatibility"] == {
        "passed": 9,
        "total": 19,
        "rate": 9 / 19,
    }
    assert metrics["negative_control_pass_rate"] == {
        "passed": 8,
        "total": 8,
        "rate": 1.0,
    }
    assert metrics["end_to_end_verdict_compatibility"]["total"] == 27


def test_stage1_attempt_count_equals_selected_scored_cases(
    controlled_full_result: dict,
) -> None:
    counts = controlled_full_result["counts"]
    assert counts["stage1_attempted_cases"] == counts["candidate_selected_cases"] == 9


def test_zero_denominator_uses_null_rate(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    non_direct = [
        case for case in normalized_cases if case["observability"]["status"] != "direct"
    ]
    non_direct_ids = {case["case_id"] for case in non_direct}
    prepared = copy.deepcopy(prepare_result)
    prepared["cases"] = [
        item for item in prepared["cases"] if item["case_id"] in non_direct_ids
    ]
    prepared["counts"].update(
        {
            "source_cases_total": 9,
            "directly_eligible_cases": 0,
            "partial_capability_cases": 3,
            "out_of_scope_cases": 6,
        }
    )
    result = evaluate_stage1_benchmark(
        non_direct, prepared, [], execution_mode="controlled"
    )
    assert result["metrics"]["stage1_verdict_compatibility_given_candidate"] == {
        "passed": 0,
        "total": 0,
        "rate": None,
    }
    assert result["metrics"]["mapping_consistency_given_compatible_classification"][
        "rate"
    ] is None


def test_deterministic_ordering_and_pure_input_immutability(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    cases = copy.deepcopy(normalized_cases)
    prepared = copy.deepcopy(prepare_result)
    records = compatible_records_for_current_baseline(cases, prepared)
    before = copy.deepcopy((cases, prepared, records))
    result = evaluate_stage1_benchmark(
        list(reversed(cases)), prepared, list(reversed(records)), execution_mode="controlled"
    )
    assert [item["case_id"] for item in result["cases"]] == [
        item["case_id"] for item in normalized_cases
    ]
    assert (cases, prepared, records) == before


def test_mapping_metric_counts_only_compatible_cases_with_contract(
    controlled_full_result: dict,
) -> None:
    metric = controlled_full_result["metrics"][
        "mapping_consistency_given_compatible_classification"
    ]
    # The controlled verdicts are all compatible, but current production
    # mapping also attaches CWE-552 to four traversal cases carrying a direct
    # sensitive-resource hint.  The frozen manifest forbids that extra ID.
    assert metric == {"passed": 5, "total": 9, "rate": 5 / 9}
    assert controlled_full_result["diagnostics"][
        "mapping_not_scored_due_to_classification_cases"
    ] == []


def test_manual_success_overclaim_audit_is_diagnostic_only(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930110.8"}
    )
    record = stage1_record(
        prepared,
        "owasp_crs.930110.8",
        "suspicious_path_traversal",
        "A01:2025",
        "CWE-22",
        "WSTG-ATHZ-01",
        reasoning_summary="파일 노출 성공 여부는 확인할 수 없다.",
    )
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [record], execution_mode="controlled"
    )
    case = by_id(result["cases"], "owasp_crs.930110.8")
    assert case["manual_audit_flags"] == ["파일 노출 성공"]
    assert case["classification"]["status"] == "pass"


def test_stage1_runtime_error_is_not_a_classification_result(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    prepared = prepare_with_selected(
        normalized_cases, prepare_result, {"owasp_crs.930110.8"}
    )
    input_fields = candidate_input(prepared, "owasp_crs.930110.8")
    record = {
        "case_id": "owasp_crs.930110.8",
        "request_id": input_fields["request_id"],
        "execution_status": "stage1_api_error",
        "candidate_input": input_fields,
        "error": {"type": "http_error", "message": "HTTP 500"},
    }
    result = evaluate_stage1_benchmark(
        normalized_cases, prepared, [record], execution_mode="controlled"
    )
    case = by_id(result["cases"], "owasp_crs.930110.8")
    assert case["classification"]["status"] == "stage1_unavailable"
    assert case["stage1"]["execution_status"] == "stage1_api_error"
    assert result["counts"]["stage1_failed_cases"] == 1
    assert result["metrics"]["stage1_verdict_compatibility_given_candidate"]["rate"] is None


def test_live_missing_credential_is_reported_as_unavailable_not_score(
    normalized_cases: list[dict],
    prepare_result: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stage1_benchmark,
        "resolve_llm_config",
        lambda _provider: LLMConfig(
            provider="openai", api_key="", base_url="https://example.invalid"
        ),
    )
    result = run_live_stage1_benchmark(normalized_cases, prepare_result)
    assert result["run"]["execution_availability"] == "live_execution_unavailable"
    assert result["run"]["complete"] is False
    assert result["counts"]["stage1_attempted_cases"] == 0
    assert result["counts"]["stage1_completed_cases"] == 0
    assert result["metrics"]["stage1_verdict_compatibility_given_candidate"]["rate"] is None


def test_live_executor_regenerates_candidate_and_uses_production_mapping(
    normalized_cases: list[dict],
    prepare_result: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_id = "owasp_crs.930120.2"
    prepared = prepare_with_selected(normalized_cases, prepare_result, {selected_id})
    monkeypatch.setattr(
        stage1_benchmark,
        "resolve_llm_config",
        lambda _provider: LLMConfig(
            provider="openai", api_key="test-key", base_url="https://example.invalid"
        ),
    )
    observed: list[dict] = []

    def classifier(**kwargs):
        candidate = kwargs["candidate"]
        observed.append(copy.deepcopy(candidate))
        return (
            {
                "model": kwargs["model"],
                "verdict": "suspicious_file_disclosure",
                "severity": "medium",
                "confidence": "high",
                "false_positive_possible": False,
                "reasoning_summary": "직접 파일 접근 시도다.",
                "evidence_fields": ["query_string"],
                "recommended_actions": ["review_raw_log"],
                "response_id": "controlled-response",
                "llm_usage": {"available": False},
            },
            None,
        )

    result = run_live_stage1_benchmark(
        normalized_cases, prepared, classifier=classifier
    )
    assert len(observed) == 1
    assert observed[0]["request_id"] == benchmark_request_id(selected_id)
    assert observed[0]["score"] == by_id(prepared["cases"], selected_id)["actual"][
        "candidate_score"
    ]
    case = by_id(result["cases"], selected_id)
    assert "CWE-22" not in case["mapping"]["actual_ids"]
    assert case["mapping"]["status"] == "pass"


def test_production_stage1_and_mapping_functions_are_reused() -> None:
    assert stage1_benchmark.classify_candidate.__module__ == "src.llm_stage1_classifier"
    assert build_security_standards_mapping.__module__ == "src.security_standards_mapping"


def test_result_schema_semantic_validation_and_write(
    tmp_path: Path, controlled_full_result: dict
) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == RESULT_SCHEMA_VERSION
    assert validate_stage1_benchmark_result(controlled_full_result) == []
    output = tmp_path / "nested" / "stage1.json"
    write_stage1_benchmark_result(controlled_full_result, output)
    assert json.loads(output.read_text(encoding="utf-8")) == controlled_full_result


def test_replay_cli_writes_complete_result_and_low_score_is_exit_zero(
    tmp_path: Path,
    normalized_cases: list[dict],
    prepare_result: dict,
) -> None:
    prepare_path = tmp_path / "prepare.json"
    replay_path = tmp_path / "replay.json"
    output = tmp_path / "stage1.json"
    prepare_path.write_text(json.dumps(prepare_result), encoding="utf-8")
    replay_path.write_text(
        json.dumps(
            {
                "schema_version": "external_security_benchmark_stage1_replay.v1",
                "benchmark": "owasp_crs_path_file_access.v1",
                "source_revision": PINNED_REVISION,
                "provider": "controlled",
                "model": "controlled-model",
                "records": compatible_records_for_current_baseline(
                    normalized_cases, prepare_result
                ),
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-dir",
            str(SOURCE_DIR),
            "--manifest",
            str(MANIFEST_PATH),
            "--prepare-result",
            str(prepare_path),
            "--mode",
            "replay",
            "--stage1-results",
            str(replay_path),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["run"]["execution_mode"] == "replay"
    assert result["run"]["complete"] is True
    assert "Stage1 compatibility given candidate" in completed.stdout
