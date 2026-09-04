from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.external_benchmark_prepare import benchmark_request_id
from src.external_benchmark_prepare_multifamily import load_resolved_suite
from src.external_benchmark_stage1_multifamily import (
    EXACT_LABELS,
    MultiFamilyStage1ContractError,
    _mapping_result,
    _policy,
    controlled_records,
    evaluate_multifamily_stage1,
    validate_multifamily_stage1_result,
)

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "benchmarks/suites/owasp_crs_multi_family.v1.json"
SOURCE = ROOT / "benchmarks/sources/owasp_crs/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a"
PREPARE = Path("/tmp/owasp_crs_multifamily_prepare_after_6b2f.json")
SCHEMA = ROOT / "benchmarks/schemas/external_security_benchmark_multifamily_stage1_result.v1.schema.json"


@pytest.fixture(scope="module")
def inputs() -> tuple[dict, dict]:
    if not PREPARE.exists():
        pytest.skip("frozen 6B-2F artifact is not available")
    return load_resolved_suite(SOURCE, SUITE), json.loads(PREPARE.read_text())


@pytest.fixture()
def controlled(inputs: tuple[dict, dict]) -> tuple[dict, dict, list[dict], dict]:
    suite, prepare = copy.deepcopy(inputs[0]), copy.deepcopy(inputs[1])
    records = controlled_records(suite, prepare)
    return suite, prepare, records, evaluate_multifamily_stage1(suite, prepare, records, execution_mode="controlled")


def by_id(items: list[dict], case_id: str) -> dict:
    return next(item for item in items if item["case_id"] == case_id)


def test_controlled_frozen_accounting_and_matrices(controlled: tuple[dict, dict, list[dict], dict]) -> None:
    _, _, _, result = controlled
    assert result["counts"] == {"reviewed_cases": 93, "direct_cases": 83, "not_scored_cases": 10, "attack_positive": 55, "project_negative": 28, "candidate_selected_positive": 36, "candidate_missed_positive": 19, "stage1_expected": 36, "stage1_completed": 36, "stage1_missing": 0, "stage1_error": 0, "exact_core_cases": 36, "exact_core_selected": 29}
    stage, e2e = result["confusion_matrices"].values()
    assert stage["row_labels"] == list(EXACT_LABELS)
    assert stage["column_labels"] == list(EXACT_LABELS)
    assert [stage["rows"][label][label] for label in EXACT_LABELS] == [8, 9, 5, 7]
    assert e2e["rows"]["suspicious_path_traversal"]["NOT_SELECTED"] == 1
    assert e2e["rows"]["suspicious_xss"]["NOT_SELECTED"] == 4
    assert e2e["rows"]["suspicious_sqli"]["NOT_SELECTED"] == 2
    assert result["metrics"]["exact_core_stage1"]["compatibility"] == {"passed": 29, "total": 29, "rate": 1.0}
    assert result["metrics"]["exact_core_end_to_end"]["compatibility"]["passed"] == 29
    assert result["metrics"]["negative_control_pass"] == {"passed": 28, "total": 28, "rate": 1.0}
    assert validate_multifamily_stage1_result(result) == []


def test_policy_exact_compatible_forbidden_and_not_scored() -> None:
    exact = {"classification_policy": "exact", "allowed_stage1_verdicts": ["suspicious_xss"], "forbidden_stage1_verdicts": []}
    compatible = {"classification_policy": "compatible_set", "allowed_stage1_verdicts": ["suspicious_scan", "likely_false_positive"], "forbidden_stage1_verdicts": ["suspicious_xss"]}
    forbidden = {"classification_policy": "forbidden_only", "allowed_stage1_verdicts": [], "forbidden_stage1_verdicts": ["suspicious_xss"]}
    assert _policy(exact, "suspicious_xss")["compatible"] is True
    assert _policy(exact, "suspicious_sqli")["compatible"] is False
    assert _policy(compatible, "suspicious_scan")["compatible"] is True
    assert _policy(compatible, "suspicious_xss")["result"] == "actual_verdict_forbidden"
    assert _policy(forbidden, "likely_false_positive")["compatible"] is True
    assert _policy(forbidden, "suspicious_xss")["compatible"] is False
    assert _policy({"classification_policy": "not_scored", "allowed_stage1_verdicts": [], "forbidden_stage1_verdicts": []}, "inconclusive")["compatible"] is None


def test_cross_family_and_other_verdict_columns(controlled: tuple[dict, dict, list[dict], dict]) -> None:
    suite, prepare, records, _ = controlled
    sql = next(record for record in records if record["case_id"] == "owasp_crs.942160.1")
    sql["verdict"] = "suspicious_xss"
    result = evaluate_multifamily_stage1(suite, prepare, records, execution_mode="controlled")
    matrix = result["confusion_matrices"]["stage1_conditioned_exact_core"]
    assert matrix["rows"]["suspicious_sqli"]["suspicious_xss"] == 1
    assert result["metrics"]["cross_family_confusion_rate"]["passed"] == 1
    xss = next(record for record in records if record["case_id"] == "owasp_crs.941110.2")
    xss["verdict"] = "inconclusive"
    result = evaluate_multifamily_stage1(suite, prepare, records, execution_mode="controlled")
    matrix = result["confusion_matrices"]["stage1_conditioned_exact_core"]
    assert matrix["rows"]["suspicious_xss"]["inconclusive"] == 1
    assert result["metrics"]["cross_family_confusion_rate"]["passed"] == 1


def test_missing_and_error_are_incomplete_and_e2e_error(controlled: tuple[dict, dict, list[dict], dict]) -> None:
    suite, prepare, records, _ = controlled
    records[:] = [record for record in records if record["case_id"] != "owasp_crs.932125.1"]
    result = evaluate_multifamily_stage1(suite, prepare, records, execution_mode="controlled")
    assert result["complete"] is False
    assert result["confusion_matrices"]["end_to_end_exact_core"]["rows"]["suspicious_command_injection"]["STAGE1_ERROR"] == 1
    records = controlled_records(suite, prepare)
    next(record for record in records if record["case_id"] == "owasp_crs.932125.1").update(execution_status="stage1_api_error")
    result = evaluate_multifamily_stage1(suite, prepare, records, execution_mode="controlled")
    assert result["counts"]["stage1_error"] == 1
    assert result["complete"] is False


def test_contract_errors_and_immutability(controlled: tuple[dict, dict, list[dict], dict]) -> None:
    suite, prepare, records, _ = controlled
    original = copy.deepcopy(records)
    records.append(copy.deepcopy(records[0]))
    with pytest.raises(MultiFamilyStage1ContractError, match="duplicate"):
        evaluate_multifamily_stage1(suite, prepare, records, execution_mode="replay")
    records = copy.deepcopy(original)
    records[0]["request_id"] = "wrong"
    with pytest.raises(MultiFamilyStage1ContractError, match="request ID"):
        evaluate_multifamily_stage1(suite, prepare, records, execution_mode="replay")
    records = copy.deepcopy(original)
    missed = by_id(prepare["cases"], "owasp_crs.930100.1")
    assert missed["actual"]["candidate_selected"] is None  # not-scored records are forbidden
    records.append({"case_id": missed["case_id"], "request_id": benchmark_request_id(missed["case_id"]), "execution_status": "completed", "verdict": "inconclusive"})
    with pytest.raises(MultiFamilyStage1ContractError, match="unexpected_stage1_result"):
        evaluate_multifamily_stage1(suite, prepare, records, execution_mode="replay")
    assert original == controlled_records(suite, prepare)


def test_compatible_and_file_disclosure_excluded_from_strict_matrix(controlled: tuple[dict, dict, list[dict], dict]) -> None:
    suite, prepare, records, result = controlled
    assert "owasp_crs.930120.2" not in {case["case_id"] for case in result["cases"] if case["case_id"] in suite["suite_manifest"]["groups"]["exact_core"]["traversal"]}
    addendum = result["path_file_boundary_addendum"][0]
    assert addendum["stage1"]["verdict"] == "suspicious_file_disclosure"
    assert addendum["mapping"]["result"] == "pass"
    # A selected compatible-set record contributes to compatibility, but cannot alter a strict exact matrix.
    compatible = next(case for case in suite["cases"] if case["expected"]["classification_policy"] == "compatible_set")
    assert compatible["case_id"] not in {cid for ids in suite["suite_manifest"]["groups"]["exact_core"].values() for cid in ids}
    actual = by_id(prepare["cases"], compatible["case_id"])["actual"]
    actual.update(candidate_selected=True, candidate_count_for_request=1, candidate_score=4,
                  prepare_verdict_hint="controlled", prepare_reason_hints=["controlled:test"],
                  request_id=benchmark_request_id(compatible["case_id"]),
                  raw_request_target=compatible["request"]["request_target"])
    result = evaluate_multifamily_stage1(suite, prepare, controlled_records(suite, prepare), execution_mode="controlled")
    assert result["confusion_matrices"]["stage1_conditioned_exact_core"]["denominator"] == 29


def test_mapping_contract_required_forbidden_and_extra() -> None:
    expected = {"mapping_by_verdict": {"suspicious_xss": {"required_ids": ["A05:2025", "CWE-79"], "forbidden_ids": ["CWE-89"]}}}
    def mapping(*ids: str) -> dict: return {"items": [{"id": item} for item in ids]}
    assert _mapping_result(expected, "suspicious_xss", mapping("A05:2025", "CWE-79", "WSTG-INPV-01"))["result"] == "pass"
    assert _mapping_result(expected, "suspicious_xss", mapping("A05:2025", "CWE-79", "CWE-89"))["result"] == "fail"


def test_prepare_hash_is_recorded(controlled: tuple[dict, dict, list[dict], dict]) -> None:
    suite, prepare, records, _ = controlled
    result = evaluate_multifamily_stage1(suite, prepare, records, execution_mode="controlled", prepare_path=str(PREPARE))
    assert result["prepare_artifact"]["sha256"] == hashlib.sha256(PREPARE.read_bytes()).hexdigest()


def test_result_schema_parses_and_declares_result_contract() -> None:
    schema = json.loads(SCHEMA.read_text())
    assert schema["properties"]["schema_version"]["const"] == "external_security_benchmark_multifamily_stage1_result.v1"
    assert {"counts", "metrics", "confusion_matrices", "cases"} <= set(schema["required"])
