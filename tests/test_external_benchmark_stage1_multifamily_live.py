from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.external_benchmark_stage1_multifamily_live as live
from src.external_benchmark_crs_multifamily import PINNED_REVISION
from src.external_benchmark_prepare_multifamily import load_resolved_suite


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "benchmarks/suites/owasp_crs_multi_family.v1.json"
SOURCE = ROOT / "benchmarks/sources/owasp_crs" / PINNED_REVISION
PREPARE = Path("/tmp/owasp_crs_multifamily_prepare_after_6b2f.json")


@pytest.fixture(scope="module")
def inputs() -> tuple[dict, dict]:
    if not PREPARE.exists():
        pytest.skip("frozen 6B-2F artifact is not available")
    return load_resolved_suite(SOURCE, SUITE), json.loads(PREPARE.read_text())


def _selected(suite: dict, prepare: dict) -> list[dict]:
    prepared = {item["case_id"]: item for item in prepare["cases"]}
    return [case for case in sorted(suite["cases"], key=live._case_key) if live._direct(case) and live._is_positive(case) and prepared[case["case_id"]]["actual"]["candidate_selected"] is True]


def _perfect_classifier(suite: dict, prepare: dict, captured: list[dict]):
    selected = _selected(suite, prepare)
    verdicts = []
    for case in selected:
        expected = case["expected"]
        verdicts.append("likely_false_positive" if expected["classification_policy"] == "forbidden_only" else expected["allowed_stage1_verdicts"][0])

    def classifier(**kwargs):
        captured.append(copy.deepcopy(kwargs["candidate"]))
        return SimpleNamespace(verdict=verdicts[kwargs["candidate_index"]], severity="medium", confidence="high", reasoning_summary="fake", evidence_fields=["fake"], llm_usage={"available": False, "unavailable_reason": "fake"}), None

    return classifier


def test_dry_run_regenerates_and_fidelity_checks_without_calls(inputs: tuple[dict, dict]) -> None:
    suite, prepare = inputs
    records, result = live.run_live_baseline(suite, prepare, prepare_path=str(PREPARE), provider="openai", model="gpt-5.4-mini", dry_run=True)
    assert records["availability"] == "dry_run"
    assert records["records"] == []
    assert result["complete"] is False
    assert result["live_execution"]["calls_attempted"] == 0
    assert result["counts"]["candidate_selected_positive"] == 36
    assert result["counts"]["exact_core_selected"] == 29
    assert result["live_execution"]["candidate_fidelity"] == {"expected": 36, "matched": 36, "failed": 0, "failures": []}


def test_credential_unavailable_is_not_zero_percent(inputs: tuple[dict, dict]) -> None:
    suite, prepare = inputs
    records, result = live.run_live_baseline(suite, prepare, prepare_path=str(PREPARE), provider="openai", model="gpt-5.4-mini", llm_config=SimpleNamespace(api_key=""))
    assert records["availability"] == "live_execution_unavailable"
    assert result["complete"] is False
    assert result["live_execution"]["calls_attempted"] == 0
    assert result["metrics"]["stage1_compatibility_given_candidate"]["rate"] is None
    assert result["metrics"]["exact_core_stage1"]["compatibility"]["rate"] is None


def test_fake_perfect_run_uses_only_selected_positive_and_same_evaluator(inputs: tuple[dict, dict]) -> None:
    suite, prepare = inputs
    captured: list[dict] = []
    records, result = live.run_live_baseline(suite, prepare, prepare_path=str(PREPARE), provider="openai", model="gpt-5.4-mini", llm_config=SimpleNamespace(api_key="test-key"), classifier=_perfect_classifier(suite, prepare, captured))
    assert result["complete"] is True
    assert result["live_execution"]["calls_attempted"] == 36
    assert result["live_execution"]["calls_completed"] == 36
    assert result["live_execution"]["calls_failed"] == 0
    assert len(records["records"]) == 36
    assert result["metrics"]["exact_core_stage1"]["compatibility"] == {"passed": 29, "total": 29, "rate": 1.0}
    assert result["metrics"]["exact_core_end_to_end"]["compatibility"] == {"passed": 29, "total": 36, "rate": 29 / 36}
    assert result["metrics"]["stage1_compatibility_given_candidate"] == {"passed": 36, "total": 36, "rate": 1.0}
    assert result["metrics"]["positive_end_to_end_compatibility"] == {"passed": 36, "total": 55, "rate": 36 / 55}
    assert result["metrics"]["mapping_consistency_given_compatible_classification"]["rate"] == 1.0
    assert all("crs" not in json.dumps(candidate).casefold() for candidate in captured)
    assert all("case_id" not in candidate for candidate in captured)


@pytest.mark.parametrize("field, changed", [
    ("request_id", "wrong-request-id"),
    ("raw_request_target", "/wrong-target"),
    ("score", 999),
    ("verdict_hint", "wrong-hint"),
    ("reason_hints", ["wrong:hint"]),
    ("source_table", "wrong-source"),
])
def test_fidelity_error_prevents_provider_call(field: str, changed: object, monkeypatch: pytest.MonkeyPatch, inputs: tuple[dict, dict]) -> None:
    suite, prepare = inputs
    original = live.regenerate_candidate
    first = _selected(suite, prepare)[0]["case_id"]

    def wrong(case: dict, index: int):
        candidate, row = original(case, index)
        if case["case_id"] == first:
            candidate[field] = changed
        return candidate, row

    called = False
    def classifier(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("must not be invoked")

    monkeypatch.setattr(live, "regenerate_candidate", wrong)
    _, result = live.run_live_baseline(suite, prepare, prepare_path=str(PREPARE), provider="openai", model="gpt-5.4-mini", llm_config=SimpleNamespace(api_key="test-key"), classifier=classifier)
    assert called is False
    assert result["live_execution"]["availability"] == "candidate_fidelity_error"
    assert result["live_execution"]["candidate_fidelity"]["failed"] == 1


def test_cross_family_record_is_scored_as_classification_not_mapping_failure(inputs: tuple[dict, dict]) -> None:
    suite, prepare = inputs
    selected = _selected(suite, prepare)
    sql_index = next(index for index, case in enumerate(selected) if case["case_id"] == "owasp_crs.942160.1")
    captured: list[dict] = []
    base = _perfect_classifier(suite, prepare, captured)

    def classifier(**kwargs):
        result, error = base(**kwargs)
        if kwargs["candidate_index"] == sql_index:
            result.verdict = "suspicious_command_injection"
        return result, error

    _, result = live.run_live_baseline(suite, prepare, prepare_path=str(PREPARE), provider="openai", model="gpt-5.4-mini", llm_config=SimpleNamespace(api_key="test-key"), classifier=classifier)
    matrix = result["confusion_matrices"]["stage1_conditioned_exact_core"]
    assert matrix["rows"]["suspicious_sqli"]["suspicious_command_injection"] == 1
    failed = next(case for case in result["cases"] if case["case_id"] == "owasp_crs.942160.1")
    assert failed["mapping"]["result"] == "not_scored_due_to_classification"
