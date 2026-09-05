from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.external_benchmark_stage1_csic2010 import (
    CsicStage1ContractError,
    _record_index,
    controlled_records,
    eligibility_counts,
    evaluate,
    identity,
    load_canonical_manifest,
    stage1_eligible,
    validate_result,
)


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "benchmarks/manifests/csic2010_reviewed_semantic_subset.v1.json"
SOURCE = ROOT / "benchmarks/manifests/csic2010_source.v1.json"
CACHE = ROOT / "benchmarks/cache/csic2010"
PREPARE = Path("/tmp/csic2010_prepare_request_index.jsonl")


@pytest.fixture(scope="module")
def canonical() -> dict:
    return load_canonical_manifest(CANONICAL, "30c67e6d1ddeb6cb890cd1446ea0e2da87e4c61c3ff9144bee7c3596e6d846bf")


@pytest.fixture(scope="module")
def controlled(canonical: dict) -> dict:
    if not CACHE.exists() or not PREPARE.exists():
        pytest.skip("local frozen CSIC source/Prepare artifacts are unavailable")
    return evaluate(CANONICAL, SOURCE, CACHE, PREPARE, mode="controlled", expected_reviewed_sha256=canonical["_sha256"])


def test_frozen_eligibility_contract_and_exclusions(canonical: dict) -> None:
    counts = eligibility_counts(canonical["cases"])
    assert counts["selected_exact"] == 111
    assert counts["full_exact"] == 113
    assert counts["negative_controls"] == 2
    assert counts["by_family"]["sqli"] == {"selected_exact": 44, "suppressed_exact": 2}
    assert counts["by_family"]["xss"] == {"selected_exact": 40, "suppressed_exact": 0}
    assert counts["by_family"]["command_injection"] == {"selected_exact": 27, "suppressed_exact": 0}
    assert counts["by_family"]["path_traversal"] == {"selected_exact": 0, "suppressed_exact": 0}
    assert not any(stage1_eligible(case) for case in canonical["cases"] if case["review_status"] == "provisional_unvalidated")
    assert not any(stage1_eligible(case) for case in canonical["cases"] if case["project_semantic"] in {"ambiguous", "not_scored_observability"})


def test_controlled_accounting_mapping_and_zero_support(controlled: dict) -> None:
    assert controlled["complete"] is True
    assert validate_result(controlled) == []
    assert controlled["prepare_fidelity"] == {"complete": True, "canonical_identities_rehydrated": 222, "regenerated_cases": 115, "selected_state_matches": True}
    assert controlled["stage1_accounting"] == {"expected": 111, "completed": 111, "errors": 0, "not_selected_exact": 2}
    assert controlled["classification"]["stage1_compatibility_given_reviewed_prepare_selected_case"] == {"passed": 111, "total": 111, "rate": 1.0}
    assert controlled["e2e"]["reviewed_exact_compatibility"] == {"passed": 111, "total": 113, "rate": 111 / 113}
    assert controlled["classification"]["by_family"]["path_traversal"] == {"passed": 0, "total": 0, "rate": None}
    assert controlled["e2e"]["by_family"]["path_traversal"] == {"passed": 0, "total": 0, "rate": None}
    assert controlled["mapping"] == {"metric_name": "mapping_consistency_among_classification_compatible_scored_positives", "passed": 111, "failed": 0, "not_scored_due_to_classification": 0}
    assert controlled["negative_controls"]["compatibility"] == {"passed": 2, "total": 2, "rate": 1.0}
    assert controlled["classification"]["cross_family_confusion"] == 0
    assert controlled["e2e"]["matrix"]["rows"]["suspicious_sqli"]["NOT_SELECTED"] == 2


def test_replay_contract_rejects_missing_duplicate_and_unknown(canonical: dict) -> None:
    records = controlled_records(canonical["cases"])
    expected = {identity(case) for case in canonical["cases"] if stage1_eligible(case) or (case["project_semantic"] == "project_negative" and case["prepare_selected"])}
    _record_index(records, expected)
    with pytest.raises(CsicStage1ContractError, match="missing"):
        _record_index(records[:-1], expected)
    with pytest.raises(CsicStage1ContractError, match="duplicate"):
        _record_index(records + [copy.deepcopy(records[0])], expected)
    unknown = copy.deepcopy(records)
    unknown[0]["raw_request_sha256"] = "0" * 64
    with pytest.raises(CsicStage1ContractError, match="unknown"):
        _record_index(unknown, expected)


def test_wrong_replay_classification_gates_mapping(controlled: dict, canonical: dict) -> None:
    replay = controlled_records(canonical["cases"])
    wrong = next(record for record in replay if record["raw_request_sha256"] == next(case["raw_request_sha256"] for case in canonical["cases"] if case.get("reviewed_family") == "sqli" and stage1_eligible(case)))
    wrong["verdict"] = "suspicious_xss"
    result = evaluate(CANONICAL, SOURCE, CACHE, PREPARE, mode="replay", replay_records=replay, expected_reviewed_sha256=canonical["_sha256"])
    record = next(item for item in result["records"] if item["raw_request_sha256"] == wrong["raw_request_sha256"])
    assert record["classification_result"] == "exact_verdict_mismatch"
    assert record["mapping_result"] == "not_scored_due_to_classification"
    assert result["classification"]["cross_family_confusion"] == 1


def test_result_records_do_not_store_raw_request_or_body(controlled: dict) -> None:
    serialized = json.dumps(controlled, ensure_ascii=False)
    for forbidden in ("request_line", "body_for_observability_review", "Cookie:", "Authorization:"):
        assert forbidden not in serialized
