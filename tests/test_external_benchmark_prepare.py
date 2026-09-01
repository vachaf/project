from __future__ import annotations

import copy
import ipaddress
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from src.external_benchmark_crs import (
    PINNED_REVISION,
    build_normalized_benchmark_cases,
    load_benchmark_manifest,
    load_owasp_crs_cases,
)
from src.external_benchmark_prepare import (
    RESULT_SCHEMA_VERSION,
    BenchmarkPrepareContractError,
    benchmark_request_id,
    build_prepare_export_payload,
    build_synthetic_security_row,
    calculate_prepare_metrics,
    evaluate_prepare_case,
    run_prepare_benchmark,
    validate_prepare_benchmark_result,
    write_prepare_benchmark_result,
)
from src.prepare_llm_input import build_outputs, extract_raw_request_target


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "benchmarks" / "sources" / "owasp_crs" / PINNED_REVISION
MANIFEST_PATH = ROOT / "benchmarks" / "manifests" / "owasp_crs_path_file_access.v1.json"
SCHEMA_PATH = (
    ROOT
    / "benchmarks"
    / "schemas"
    / "external_security_benchmark_prepare_result.v1.schema.json"
)
SCRIPT = ROOT / "src" / "external_benchmark_prepare.py"


@pytest.fixture(scope="module")
def normalized_cases() -> list[dict]:
    return build_normalized_benchmark_cases(
        load_owasp_crs_cases(SOURCE_DIR),
        load_benchmark_manifest(MANIFEST_PATH),
    )


@pytest.fixture(scope="module")
def prepare_result(normalized_cases: list[dict]) -> dict:
    return run_prepare_benchmark(normalized_cases)


def by_id(items: list[dict], case_id: str) -> dict:
    return next(item for item in items if item["case_id"] == case_id)


def fake_candidate(row: dict, *, score: int = 9, verdict_hint: str = "path_traversal") -> dict:
    return {
        "request_id": row["request_id"],
        "source_table": "security",
        "score": score,
        "verdict_hint": verdict_hint,
        "reason_hints": ["production:test-signal"],
        "raw_request_target": extract_raw_request_target(row["raw_request"]),
    }


def filtered_builder(payload, **_kwargs):
    row = payload["data"]["security"][0]
    filtered = {
        "request_id": row["request_id"],
        "reason_hints": ["context:below-threshold"],
    }
    reasons = {
        "excluded": [
            {"request_id": row["request_id"], "reason": "low_signal_request"}
        ]
    }
    return {}, [], [], reasons, [filtered]


def selected_builder(payload, **_kwargs):
    row = payload["data"]["security"][0]
    return {}, [fake_candidate(row)], [], {"excluded": []}, []


def test_get_row_uses_neutral_security_export_contract(normalized_cases: list[dict]) -> None:
    case = by_id(normalized_cases, "owasp_crs.930110.2")
    row = build_synthetic_security_row(case)

    assert row["method"] == "GET"
    assert row["raw_request"] == "GET /get?arg=../../../etc/passwd HTTP/1.1"
    assert row["uri"] == "/get"
    assert row["query_string"] == "?arg=../../../etc/passwd"
    assert row["status_code"] == row["original_status_code"] == 200
    assert row["response_body_bytes"] == row["duration_us"] == row["ttfb_us"] == 0
    assert row["resp_content_type"] == row["raw_log"] == ""


@pytest.mark.parametrize(
    ("case_id", "request_target", "query_string"),
    [
        (
            "owasp_crs.930100.3",
            "/get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini",
            "?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini",
        ),
        ("owasp_crs.930110.8", "/get?arg=..\\pineapple", "?arg=..\\pineapple"),
        ("owasp_crs.930110.12", "/get?a=..;.\\.;\\.", "?a=..;.\\.;\\."),
        (
            "owasp_crs.930120.1",
            "/get/index.php?file=News&op=../../../../../boot.ini%00",
            "?file=News&op=../../../../../boot.ini%00",
        ),
    ],
)
def test_raw_target_percent_backslash_and_semicolon_fidelity(
    normalized_cases: list[dict], case_id: str, request_target: str, query_string: str
) -> None:
    case = by_id(normalized_cases, case_id)
    row = build_synthetic_security_row(case)

    assert case["request"]["request_target"] == request_target
    assert extract_raw_request_target(row["raw_request"]) == request_target
    assert row["query_string"] == query_string


def test_path_without_query_has_empty_query_string(normalized_cases: list[dict]) -> None:
    row = build_synthetic_security_row(by_id(normalized_cases, "owasp_crs.930110.7"))
    assert row["uri"] == "/get/.."
    assert row["query_string"] == ""


def test_supported_headers_are_copied_without_arbitrary_headers(normalized_cases: list[dict]) -> None:
    case = copy.deepcopy(by_id(normalized_cases, "owasp_crs.930100.1"))
    case["request"]["headers"]["Referer"] = "https://example.test/source"
    row = build_synthetic_security_row(case)

    assert row["user_agent"] == "OWASP CRS test agent"
    assert row["referer"] == "https://example.test/source"
    assert row["req_host"] == "localhost"
    assert "FoobarHeader" not in row
    assert "0x5c0x2e.%00/" not in json.dumps(row)


def test_request_body_never_leaks_into_synthetic_row(normalized_cases: list[dict]) -> None:
    case = by_id(normalized_cases, "owasp_crs.930110.3")
    body_text = case["request"]["body"]["text"]
    row = build_synthetic_security_row(case)

    assert body_text not in json.dumps(row, ensure_ascii=False)
    assert row["raw_request"] == "POST /post HTTP/1.1"
    assert row["uri"] == "/post"
    assert row["query_string"] == ""


def test_request_id_is_stable_sanitized_and_order_independent(normalized_cases: list[dict]) -> None:
    case = by_id(normalized_cases, "owasp_crs.930110.2")
    assert benchmark_request_id(case["case_id"]) == "bench-owasp-crs-930110-2"
    assert build_synthetic_security_row(case, sequence_index=0)["request_id"] == (
        build_synthetic_security_row(case, sequence_index=99)["request_id"]
    )


def test_all_case_source_ips_are_unique_deterministic_documentation_addresses(
    normalized_cases: list[dict],
) -> None:
    ips = [build_synthetic_security_row(case)["src_ip"] for case in normalized_cases]
    allowed = [
        ipaddress.ip_network("192.0.2.0/24"),
        ipaddress.ip_network("198.51.100.0/24"),
        ipaddress.ip_network("203.0.113.0/24"),
    ]
    assert len(ips) == len(set(ips)) == 36
    assert all(any(ipaddress.ip_address(ip) in network for network in allowed) for ip in ips)
    assert build_synthetic_security_row(normalized_cases[0])["src_ip"] == ips[0]


def test_synthetic_timestamps_are_deterministic_and_hour_isolated(normalized_cases: list[dict]) -> None:
    first = build_synthetic_security_row(normalized_cases[0], sequence_index=0)["log_time"]
    second = build_synthetic_security_row(normalized_cases[1], sequence_index=1)["log_time"]
    repeated = build_synthetic_security_row(normalized_cases[1], sequence_index=1)["log_time"]
    assert (datetime.fromisoformat(second) - datetime.fromisoformat(first)).total_seconds() == 3600
    assert second == repeated


def test_adapter_and_payload_do_not_mutate_inputs(normalized_cases: list[dict]) -> None:
    case = copy.deepcopy(by_id(normalized_cases, "owasp_crs.930110.2"))
    before = copy.deepcopy(case)
    row = build_synthetic_security_row(case)
    row_before = copy.deepcopy(row)
    payload = build_prepare_export_payload(row)
    payload["data"]["security"][0]["uri"] = "/changed"
    assert case == before
    assert row == row_before


def test_export_payload_matches_production_shape(normalized_cases: list[dict]) -> None:
    row = build_synthetic_security_row(by_id(normalized_cases, "owasp_crs.930110.2"))
    payload = build_prepare_export_payload(row)
    assert payload["meta"]["table_option"] == "security"
    assert payload["counts"] == {"access": 0, "security": 1, "error": 0}
    assert payload["data"] == {"security": [row]}


def test_strict_traversal_runs_through_actual_build_outputs(normalized_cases: list[dict]) -> None:
    result = evaluate_prepare_case(by_id(normalized_cases, "owasp_crs.930110.2"))
    assert result["actual"]["candidate_selected"] is True
    assert result["actual"]["candidate_count_for_request"] == 1
    assert result["result"]["candidate_selection"] == "pass"


def test_candidate_matching_uses_request_id_not_list_position(normalized_cases: list[dict]) -> None:
    case = by_id(normalized_cases, "owasp_crs.930110.2")

    def builder(payload, **_kwargs):
        row = payload["data"]["security"][0]
        wrong = fake_candidate({**row, "request_id": "different-request"}, score=100)
        right = fake_candidate(row, score=7, verdict_hint="matched")
        return {}, [wrong, right], [], {"excluded": []}, []

    result = evaluate_prepare_case(case, prepare_builder=builder)
    assert result["actual"]["candidate_score"] == 7
    assert result["actual"]["prepare_verdict_hint"] == "matched"


def test_filtered_out_negative_case_is_matched_and_suppressed(normalized_cases: list[dict]) -> None:
    result = evaluate_prepare_case(
        by_id(normalized_cases, "owasp_crs.930110.6"), prepare_builder=filtered_builder
    )
    assert result["actual"]["candidate_selected"] is False
    assert result["actual"]["filtered_out"] is True
    assert result["actual"]["filtered_reasons"] == ["low_signal_request"]
    assert result["result"]["candidate_selection"] == "pass"


def test_candidate_selected_negative_is_candidate_gate_failure(normalized_cases: list[dict]) -> None:
    result = evaluate_prepare_case(
        by_id(normalized_cases, "owasp_crs.930110.4"), prepare_builder=selected_builder
    )
    assert result["actual"]["candidate_selected"] is True
    assert result["result"] == {
        "candidate_selection": "fail",
        "diagnostic_category": "unexpected_candidate",
    }


def test_candidate_diagnostics_are_preserved(normalized_cases: list[dict]) -> None:
    result = evaluate_prepare_case(
        by_id(normalized_cases, "owasp_crs.930110.2"), prepare_builder=selected_builder
    )
    actual = result["actual"]
    assert actual["candidate_score"] == 9
    assert actual["prepare_verdict_hint"] == "path_traversal"
    assert actual["prepare_reason_hints"] == ["production:test-signal"]
    assert actual["source_table"] == "security"
    assert actual["raw_request_target"] == "/get?arg=../../../etc/passwd"


def test_duplicate_candidates_are_diagnostic_error_not_arbitrarily_selected(
    normalized_cases: list[dict],
) -> None:
    def builder(payload, **_kwargs):
        row = payload["data"]["security"][0]
        return {}, [fake_candidate(row), fake_candidate(row, score=10)], [], {"excluded": []}, []

    result = evaluate_prepare_case(
        by_id(normalized_cases, "owasp_crs.930110.2"), prepare_builder=builder
    )
    assert result["actual"]["candidate_count_for_request"] == 2
    assert result["actual"]["execution_status"] == "error"
    assert result["result"]["candidate_selection"] == "error"


def test_isolated_runner_calls_prepare_once_per_direct_case_with_one_row(
    normalized_cases: list[dict],
) -> None:
    observed: list[dict] = []

    def builder(payload, **kwargs):
        assert kwargs == {
            "min_score": 4,
            "min_repeat_aggregate": 3,
            "source_tables": ["security"],
        }
        assert list(payload["data"]) == ["security"]
        assert len(payload["data"]["security"]) == 1
        observed.append(copy.deepcopy(payload["data"]["security"][0]))
        return filtered_builder(payload, **kwargs)

    result = run_prepare_benchmark(normalized_cases, prepare_builder=builder)
    assert len(observed) == 27
    assert len({row["src_ip"] for row in observed}) == 27
    assert len({row["log_time"] for row in observed}) == 27
    assert result["counts"]["evaluated_direct_cases"] == 27


def test_adapter_injects_no_expectation_or_benchmark_detection_hint(
    normalized_cases: list[dict],
) -> None:
    observed: dict = {}

    def builder(payload, **kwargs):
        observed.update(payload["data"]["security"][0])
        return selected_builder(payload, **kwargs)

    evaluate_prepare_case(
        by_id(normalized_cases, "owasp_crs.930110.2"), prepare_builder=builder
    )
    assert "expected" not in observed
    assert "source_rule_id" not in observed
    assert "candidate_expected" not in json.dumps(observed)
    assert observed["raw_log"] == ""


def test_production_prepare_function_source_is_unchanged_module() -> None:
    assert build_outputs.__module__ == "src.prepare_llm_input"
    assert Path(build_outputs.__code__.co_filename).resolve() == (
        ROOT / "src" / "prepare_llm_input.py"
    )


def test_prepare_value_error_is_case_level_error_and_runner_continues(
    normalized_cases: list[dict],
) -> None:
    subset = [
        by_id(normalized_cases, "owasp_crs.930110.2"),
        by_id(normalized_cases, "owasp_crs.930110.8"),
    ]

    def builder(payload, **kwargs):
        row = payload["data"]["security"][0]
        if row["request_id"].endswith("930110-2"):
            raise ValueError("synthetic parser rejection")
        return selected_builder(payload, **kwargs)

    result = run_prepare_benchmark(subset, prepare_builder=builder)
    assert result["run"]["complete"] is False
    assert result["counts"]["evaluated_direct_cases"] == 1
    assert by_id(result["cases"], "owasp_crs.930110.2")["result"][
        "diagnostic_category"
    ] == "prepare_error"
    assert by_id(result["cases"], "owasp_crs.930110.8")["actual"][
        "execution_status"
    ] == "completed"
    assert result["metrics"]["candidate_recall_on_expected_candidates"]["rate"] is None


def test_adapter_error_is_case_level_error_and_runner_continues(
    normalized_cases: list[dict],
) -> None:
    invalid = copy.deepcopy(by_id(normalized_cases, "owasp_crs.930110.2"))
    invalid["source"]["rule_id"] = 999999
    following = by_id(normalized_cases, "owasp_crs.930110.8")

    result = run_prepare_benchmark(
        [invalid, following], prepare_builder=selected_builder
    )

    assert result["run"]["complete"] is False
    assert result["counts"]["evaluated_direct_cases"] == 1
    assert by_id(result["cases"], "owasp_crs.930110.2")["result"][
        "diagnostic_category"
    ] == "adapter_error"
    assert by_id(result["cases"], "owasp_crs.930110.8")["actual"][
        "execution_status"
    ] == "completed"


def test_full_inventory_accounts_for_36_but_executes_only_27(prepare_result: dict) -> None:
    assert prepare_result["counts"] == {
        "source_cases_total": 36,
        "directly_eligible_cases": 27,
        "partial_capability_cases": 3,
        "out_of_scope_cases": 6,
        "expected_candidate_cases": 19,
        "project_negative_cases": 8,
        "evaluated_direct_cases": 27,
    }
    assert len(prepare_result["cases"]) == 36
    assert sum(
        case["actual"]["execution_status"] == "not_run"
        for case in prepare_result["cases"]
    ) == 9
    assert prepare_result["run"]["complete"] is True


def test_metric_fractions_and_zero_denominators() -> None:
    def result(expected: bool, selected: bool, truth: str) -> dict:
        return {
            "observability": {"eligible": True, "status": "direct"},
            "expected": {
                "candidate_expected": expected,
                "project_ground_truth": truth,
            },
            "actual": {"candidate_selected": selected},
        }

    cases = [
        result(True, True, "attack_positive"),
        result(True, True, "attack_positive"),
        result(True, False, "attack_positive"),
        result(False, False, "project_negative"),
        result(False, True, "project_negative"),
    ]
    metrics = calculate_prepare_metrics(cases)
    assert metrics["candidate_recall_on_expected_candidates"] == {
        "passed": 2,
        "total": 3,
        "rate": 2 / 3,
    }
    assert metrics["negative_candidate_suppression_rate"] == {
        "passed": 1,
        "total": 2,
        "rate": 1 / 2,
    }
    assert calculate_prepare_metrics([]) == {
        "candidate_recall_on_expected_candidates": None,
        "negative_candidate_suppression_rate": None,
    }


def test_source_expectation_does_not_change_project_metrics() -> None:
    base = {
        "observability": {"eligible": True, "status": "direct"},
        "expected": {
            "candidate_expected": True,
            "project_ground_truth": "attack_positive",
        },
        "actual": {"candidate_selected": True},
        "source": {"expectation": {"kind": "no_expect_ids", "ids": [999999]}},
    }
    changed = copy.deepcopy(base)
    changed["source"]["expectation"] = {"kind": "expect_ids", "ids": [930110]}
    assert calculate_prepare_metrics([base]) == calculate_prepare_metrics([changed])


def test_runner_is_logically_deterministic_and_does_not_mutate_cases(
    normalized_cases: list[dict], prepare_result: dict
) -> None:
    before = copy.deepcopy(normalized_cases)
    repeated = run_prepare_benchmark(list(reversed(normalized_cases)))
    assert repeated == prepare_result
    assert normalized_cases == before


def test_result_schema_parse_semantic_validation_and_write(
    tmp_path: Path, prepare_result: dict
) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == RESULT_SCHEMA_VERSION
    assert validate_prepare_benchmark_result(prepare_result) == []

    output = tmp_path / "nested" / "result.json"
    write_prepare_benchmark_result(prepare_result, output)
    assert json.loads(output.read_text(encoding="utf-8")) == prepare_result


def test_duplicate_normalized_case_ids_are_rejected(normalized_cases: list[dict]) -> None:
    with pytest.raises(BenchmarkPrepareContractError, match="duplicate normalized case IDs"):
        run_prepare_benchmark([normalized_cases[0], copy.deepcopy(normalized_cases[0])])


def test_cli_writes_complete_result_and_uses_score_independent_exit_zero(tmp_path: Path) -> None:
    output = tmp_path / "prepare.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-dir",
            str(SOURCE_DIR),
            "--manifest",
            str(MANIFEST_PATH),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["run"]["complete"] is True
    assert result["run"]["stage"] == "prepare_only"
    assert "candidate recall:" in completed.stdout
