from __future__ import annotations

import copy
import ipaddress
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.prepare_llm_input import extract_raw_request_target
from src.external_benchmark_prepare_multifamily import (
    RESULT_SCHEMA_VERSION,
    MultiFamilyPrepareContractError,
    build_multifamily_synthetic_security_row,
    calculate_multifamily_prepare_metrics,
    evaluate_multifamily_prepare_case,
    load_resolved_suite,
    multifamily_benchmark_source_ip,
    run_multifamily_prepare_benchmark,
    validate_multifamily_prepare_result,
    write_multifamily_prepare_result,
)


ROOT = Path(__file__).resolve().parents[1]
REVISION = "96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a"
SOURCE_ROOT = ROOT / "benchmarks" / "sources" / "owasp_crs" / REVISION
SUITE = ROOT / "benchmarks" / "suites" / "owasp_crs_multi_family.v1.json"
SCHEMA = ROOT / "benchmarks" / "schemas" / "external_security_benchmark_multifamily_prepare_result.v1.schema.json"
SCRIPT = ROOT / "src" / "external_benchmark_prepare_multifamily.py"


@pytest.fixture(scope="module")
def resolved() -> dict:
    return load_resolved_suite(SOURCE_ROOT, SUITE)


@pytest.fixture(scope="module")
def production_result(resolved: dict) -> dict:
    return run_multifamily_prepare_benchmark(resolved)


def case_by_id(resolved: dict, case_id: str) -> dict:
    return next(case for case in resolved["cases"] if case["case_id"] == case_id)


def candidate(row: dict, *, score: int = 9, hint: str = "suspicious") -> dict:
    return {
        "request_id": row["request_id"],
        "source_table": "security",
        "score": score,
        "verdict_hint": hint,
        "reason_hints": ["production:test-signal"],
        "raw_request_target": extract_raw_request_target(row["raw_request"]),
    }


def filtered(payload, **_kwargs):
    row = payload["data"]["security"][0]
    return {}, [], [], {"excluded": [{"request_id": row["request_id"], "reason": "low_signal_request"}]}, [{"request_id": row["request_id"], "reason_hints": ["context:below-threshold"]}]


def test_suite_accounting_and_group_membership_are_frozen(resolved: dict) -> None:
    cases = resolved["cases"]
    assert len(cases) == len({case["case_id"] for case in cases}) == 93
    assert sum(case["observability"]["eligible"] for case in cases) == 83
    assert sum(case["expected"]["project_ground_truth"] == "attack_positive" for case in cases) == 55
    assert sum(case["expected"]["project_ground_truth"] == "project_negative" for case in cases) == 28
    exact = resolved["suite_manifest"]["groups"]["exact_core"]
    assert {name: len(ids) for name, ids in exact.items()} == {"traversal": 9, "cmdi": 9, "xss": 9, "sqli": 9}
    assert len(resolved["suite_manifest"]["groups"]["path_file_boundary_addendum"]) == 10
    assert "exact_core.cmdi" in case_by_id(resolved, "owasp_crs.932125.1")["suite_groups"]
    assert case_by_id(resolved, "owasp_crs.941120.11")["suite_groups"] == ["xss_out_of_scope"]


@pytest.mark.parametrize(
    ("case_id", "needle", "field"),
    [
        ("owasp_crs.932230.34", "%3Da%3B%20sh%24XX%20-c%20whoami", "raw_request"),
        ("owasp_crs.941110.3", "&#60;script+&#62;alert(1);&#60;/script&#62;=value", "user_agent"),
        ("owasp_crs.942350.7", "1%3BINSERT%20%2F%2Atest%2A%2F", "raw_request"),
    ],
)
def test_new_family_adapter_preserves_raw_syntax(resolved: dict, case_id: str, needle: str, field: str) -> None:
    row = build_multifamily_synthetic_security_row(case_by_id(resolved, case_id))
    assert needle in row[field]
    assert extract_raw_request_target(row["raw_request"]) == case_by_id(resolved, case_id)["source"]["request"]["request_target"]
    if "?" in row["raw_request"]:
        assert row["query_string"].startswith("?")
    assert row["status_code"] == row["original_status_code"] == 200
    assert row["response_body_bytes"] == row["duration_us"] == row["ttfb_us"] == 0


def test_new_family_adapter_header_body_and_ip_contract(resolved: dict) -> None:
    case = copy.deepcopy(case_by_id(resolved, "owasp_crs.941110.3"))
    request = case["source"]["request"]
    request["headers"].update({"referer": "https://example.test/r", "Content-Type": "text/plain", "Cookie": "secret=not-copied", "X-Arbitrary": "not-copied"})
    request["body"] = {"present": True, "text": "body-must-not-leak"}
    row = build_multifamily_synthetic_security_row(case)
    assert row["user_agent"] == "&#60;script+&#62;alert(1);&#60;/script&#62;=value"
    assert row["referer"] == "https://example.test/r"
    assert row["req_content_type"] == "text/plain"
    assert "Cookie" not in row and "X-Arbitrary" not in row
    assert "body-must-not-leak" not in json.dumps(row)
    assert row["request_id"] == "bench-owasp-crs-941110-3"
    assert multifamily_benchmark_source_ip(case) == multifamily_benchmark_source_ip(copy.deepcopy(case))
    assert ipaddress.ip_address(row["src_ip"]) in ipaddress.ip_network("198.51.100.0/24")


def test_direct_evaluator_links_candidate_and_filtered_rows_by_request_id(resolved: dict) -> None:
    case = case_by_id(resolved, "owasp_crs.932125.1")

    def builder(payload, **kwargs):
        assert kwargs == {"min_score": 4, "min_repeat_aggregate": 3, "source_tables": ["security"]}
        row = payload["data"]["security"][0]
        wrong = {**candidate(row), "request_id": "different-request"}
        return {}, [wrong, candidate(row, score=7, hint="matched")], [], {"excluded": []}, []

    selected = evaluate_multifamily_prepare_case(case, prepare_builder=builder)
    assert selected["actual"]["candidate_score"] == 7
    assert selected["actual"]["prepare_verdict_hint"] == "matched"
    suppressed = evaluate_multifamily_prepare_case(case_by_id(resolved, "owasp_crs.932130.10"), prepare_builder=filtered)
    assert suppressed["actual"]["filtered_out"] is True
    assert suppressed["actual"]["filtered_reasons"] == ["low_signal_request"]
    assert suppressed["result"]["candidate_selection"] == "pass"


def test_duplicate_or_foreign_benchmark_candidate_is_contract_error(resolved: dict) -> None:
    case = case_by_id(resolved, "owasp_crs.932125.1")

    def duplicate(payload, **_kwargs):
        row = payload["data"]["security"][0]
        return {}, [candidate(row), candidate(row, score=10)], [], {"excluded": []}, []

    assert evaluate_multifamily_prepare_case(case, prepare_builder=duplicate)["result"]["diagnostic_category"] == "duplicate_or_ambiguous_prepare_output"

    def contaminated(payload, **_kwargs):
        row = payload["data"]["security"][0]
        return {}, [candidate(row), {**candidate(row), "request_id": "bench-owasp-crs-942350-7"}], [], {"excluded": []}, []

    assert evaluate_multifamily_prepare_case(case, prepare_builder=contaminated)["actual"]["execution_status"] == "error"


def test_runner_isolates_all_direct_cases_and_never_executes_out_of_scope(resolved: dict) -> None:
    observed: list[dict] = []

    def builder(payload, **kwargs):
        assert kwargs == {"min_score": 4, "min_repeat_aggregate": 3, "source_tables": ["security"]}
        assert list(payload["data"]) == ["security"]
        assert len(payload["data"]["security"]) == 1
        row = copy.deepcopy(payload["data"]["security"][0])
        assert not {"source_family", "source_rule_id", "candidate_expected", "expected", "suite_groups"} & set(row)
        observed.append(row)
        return filtered(payload, **kwargs)

    result = run_multifamily_prepare_benchmark(resolved, prepare_builder=builder)
    assert len(observed) == 83
    assert result["counts"]["evaluated_direct_cases"] == 83
    assert next(case for case in result["cases"] if case["case_id"] == "owasp_crs.941120.11")["actual"]["execution_status"] == "not_run"
    assert result["complete"] is True


def test_production_baseline_metrics_and_legacy_930_compatibility(production_result: dict) -> None:
    assert production_result["complete"] is True
    assert production_result["counts"] == {"reviewed_cases_total": 93, "direct_cases": 83, "not_scored_cases": 10, "attack_positive_cases": 55, "project_negative_cases": 28, "exact_core_cases": 36, "evaluated_direct_cases": 83}
    metrics = production_result["metrics"]
    assert metrics["candidate_recall_on_expected_candidates"] == {"passed": 27, "total": 55, "rate": 27 / 55}
    assert metrics["negative_candidate_suppression_rate"] == {"passed": 24, "total": 28, "rate": 24 / 28}
    assert metrics["candidate_recall_by_class"] == {"Traversal": {"passed": 9, "total": 19, "rate": 9 / 19}, "CMDi": {"passed": 3, "total": 12, "rate": 3 / 12}, "XSS": {"passed": 7, "total": 12, "rate": 7 / 12}, "SQLi": {"passed": 8, "total": 12, "rate": 8 / 12}}
    assert metrics["exact_core_candidate_recall_by_class"] == {"Traversal": {"passed": 8, "total": 9, "rate": 8 / 9}, "CMDi": {"passed": 2, "total": 9, "rate": 2 / 9}, "XSS": {"passed": 5, "total": 9, "rate": 5 / 9}, "SQLi": {"passed": 7, "total": 9, "rate": 7 / 9}}
    assert metrics["exact_core_macro_candidate_recall"] == {"class_count": 4, "rate": (8 / 9 + 2 / 9 + 5 / 9 + 7 / 9) / 4}
    assert metrics["negative_suppression_by_family"] == {"path_file_negative": {"passed": 8, "total": 8, "rate": 1.0}, "cmdi_negative": {"passed": 5, "total": 6, "rate": 5 / 6}, "xss_negative": {"passed": 3, "total": 6, "rate": 0.5}, "sqli_negative": {"passed": 8, "total": 8, "rate": 1.0}}
    path = production_result["component_counts"]["owasp_crs_path_file_access.v1"]
    assert path["candidate_selected"] == 9 and path["positive"] == 19 and path["negative"] == 8
    cases = {case["case_id"]: case for case in production_result["cases"]}
    assert cases["owasp_crs.930110.4"]["actual"]["candidate_selected"] is False
    assert cases["owasp_crs.930110.5"]["actual"]["candidate_selected"] is False
    assert cases["owasp_crs.930110.8"]["actual"]["candidate_selected"] is True
    assert cases["owasp_crs.930120.2"]["actual"]["prepare_verdict_hint"] == "suspicious_file_disclosure"
    assert cases["owasp_crs.930100.3"]["actual"]["candidate_selected"] is True


def test_metrics_zero_denominator_and_input_immutability(resolved: dict) -> None:
    before = copy.deepcopy(resolved)
    metrics = calculate_multifamily_prepare_metrics([], resolved["suite_manifest"])
    assert metrics["candidate_recall_on_expected_candidates"] == {"passed": 0, "total": 0, "rate": None}
    assert metrics["exact_core_macro_candidate_recall"] == {"class_count": 4, "rate": None}
    run_multifamily_prepare_benchmark(resolved, prepare_builder=filtered)
    assert resolved == before


def test_schema_writer_cli_and_determinism(tmp_path: Path, resolved: dict, production_result: dict) -> None:
    schema = json.loads(SCHEMA.read_text())
    assert schema["properties"]["schema_version"]["const"] == RESULT_SCHEMA_VERSION
    assert validate_multifamily_prepare_result(production_result) == []
    output = tmp_path / "result.json"
    write_multifamily_prepare_result(production_result, output)
    assert json.loads(output.read_text()) == production_result
    repeated = run_multifamily_prepare_benchmark(copy.deepcopy(resolved))
    assert repeated == production_result
    cli_output = tmp_path / "cli.json"
    completed = subprocess.run([sys.executable, str(SCRIPT), "--source-root", str(SOURCE_ROOT), "--suite", str(SUITE), "--output", str(cli_output)], cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(cli_output.read_text())["complete"] is True


def test_runner_rejects_design_accounting_drift(resolved: dict) -> None:
    bad = copy.deepcopy(resolved)
    bad["cases"].pop()
    with pytest.raises(MultiFamilyPrepareContractError, match="accounting mismatch"):
        run_multifamily_prepare_benchmark(bad)
