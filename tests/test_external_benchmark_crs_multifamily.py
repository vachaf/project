from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import pytest

import src.external_benchmark_crs_multifamily as module
from src.external_benchmark_crs_multifamily import (
    MultiFamilyBenchmarkContractError,
    join_family_manifest,
    load_family_benchmark_manifest,
    load_multifamily_crs_cases,
    validate_family_benchmark_manifest,
    verify_multifamily_crs_source_integrity,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "benchmarks/sources/owasp_crs/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a/multi_family"
MANIFESTS = {
    name: ROOT / f"benchmarks/manifests/owasp_crs_{name}.v1.json"
    for name in ("cmdi", "xss", "sqli")
}


@pytest.fixture(scope="module")
def source_cases() -> list[dict]:
    return load_multifamily_crs_cases(SOURCE_DIR)


def by_id(cases: list[dict], case_id: str) -> dict:
    return next(case for case in cases if case["case_id"] == case_id)


def test_pinned_bundle_integrity_and_inventory(source_cases: list[dict]) -> None:
    metadata = verify_multifamily_crs_source_integrity(SOURCE_DIR)
    assert metadata["bundle"] == "multi_family"
    assert metadata["notice_files"] == []
    assert len(metadata["files"]) == 24
    assert len(source_cases) == 456
    assert Counter(case["source_family"] for case in source_cases) == {"932": 179, "941": 145, "942": 132}
    assert [(case["source_rule_id"], case["source_test_id"]) for case in source_cases] == sorted(
        (case["source_rule_id"], case["source_test_id"]) for case in source_cases
    )
    assert source_cases[0]["case_id"] == "owasp_crs.932125.1"
    assert source_cases[-1]["case_id"] == "owasp_crs.942550.49"


def test_source_facts_preserve_raw_target_headers_body_and_no_project_labels(source_cases: list[dict]) -> None:
    assert by_id(source_cases, "owasp_crs.932230.34")["request"]["request_target"] == "/get?'cmd%3Da%3B%20sh%24XX%20-c%20whoami"
    assert by_id(source_cases, "owasp_crs.941110.3")["request"]["headers"]["User-Agent"] == "&#60;script+&#62;alert(1);&#60;/script&#62;=value"
    assert by_id(source_cases, "owasp_crs.942350.7")["request"]["request_target"] == "/get?test=1%3BINSERT%20%2F%2Atest%2A%2FINTO%20category%28id%29%20VALUES%20%283%29--%20-"
    assert "verify_sign=" in by_id(source_cases, "owasp_crs.941120.11")["request"]["body"]["text"]
    assert by_id(source_cases, "owasp_crs.932230.59")["request"]["request_target"] is None
    assert by_id(source_cases, "owasp_crs.942350.2")["source_expectation"] == {"kind": "no_expect_ids", "ids": [942350]}
    forbidden = {"observability", "expected", "project_ground_truth", "verdict", "suite_groups"}
    assert all(forbidden.isdisjoint(case) for case in source_cases)


def test_integrity_lock_rejects_source_metadata_drift(tmp_path: Path) -> None:
    copied = tmp_path / "bundle"
    copied.mkdir()
    for path in SOURCE_DIR.rglob("*"):
        destination = copied / path.relative_to(SOURCE_DIR)
        if path.is_dir():
            destination.mkdir()
        else:
            destination.write_bytes(path.read_bytes())
    metadata_path = copied / "SOURCE.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["files"][0]["sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(MultiFamilyBenchmarkContractError, match="SOURCE.json sha256 mismatch"):
        verify_multifamily_crs_source_integrity(copied)


def test_family_manifests_are_reviewed_source_subsets(source_cases: list[dict]) -> None:
    expected_counts = {"cmdi": 18, "xss": 19, "sqli": 20}
    for name, path in MANIFESTS.items():
        manifest = load_family_benchmark_manifest(path)
        assert len(manifest["cases"]) == expected_counts[name]
        assert validate_family_benchmark_manifest(manifest, source_cases) == []
        joined = join_family_manifest(manifest, source_cases)
        assert len(joined) == expected_counts[name]
        assert all(item["source"]["source_family"] == manifest["annotation"]["source_family"] for item in joined)
    xss = load_family_benchmark_manifest(MANIFESTS["xss"])
    body_control = next(case for case in xss["cases"] if case["case_id"] == "owasp_crs.941120.11")
    assert body_control["observability"]["status"] == "out_of_scope"
    assert body_control["expected"]["classification_policy"] == "not_scored"


def test_family_validator_rejects_unknown_duplicate_and_cross_family_case(source_cases: list[dict]) -> None:
    manifest = load_family_benchmark_manifest(MANIFESTS["cmdi"])
    unknown = copy.deepcopy(manifest)
    unknown["cases"][0]["case_id"] = "owasp_crs.932125.999"
    assert any("unknown source" in error for error in validate_family_benchmark_manifest(unknown, source_cases))
    duplicate = copy.deepcopy(manifest)
    duplicate["cases"].append(copy.deepcopy(duplicate["cases"][0]))
    assert any("duplicate manifest" in error for error in validate_family_benchmark_manifest(duplicate, source_cases))
    cross = copy.deepcopy(manifest)
    cross["cases"][0]["case_id"] = "owasp_crs.941100.1"
    assert any("another source family" in error for error in validate_family_benchmark_manifest(cross, source_cases))


def test_source_loader_rejects_unregistered_family_and_multistage(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(MultiFamilyBenchmarkContractError, match="families"):
        load_multifamily_crs_cases(SOURCE_DIR, families=["913"])
    first = SOURCE_DIR / "932/932125.yaml"
    document = module.yaml.safe_load(first.read_text())
    document["tests"][0]["stages"].append(copy.deepcopy(document["tests"][0]["stages"][0]))
    monkeypatch.setattr(module.yaml, "safe_load", lambda _text: document)
    with pytest.raises(MultiFamilyBenchmarkContractError, match="exactly one stage"):
        load_multifamily_crs_cases(SOURCE_DIR, families=["932"])
