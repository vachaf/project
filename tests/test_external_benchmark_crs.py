from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

import src.external_benchmark_crs as benchmark_module
from src.external_benchmark_crs import (
    BenchmarkContractError,
    PINNED_FILES,
    PINNED_REVISION,
    build_normalized_benchmark_cases,
    load_benchmark_manifest,
    load_owasp_crs_cases,
    validate_benchmark_manifest,
    verify_owasp_crs_source_integrity,
)
from src.llm_stage1_classifier import build_schema as build_stage1_schema
from src.security_standards_mapping import KNOWN_VERDICTS
from src.security_standards_mapping import build_security_standards_mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "benchmarks" / "sources" / "owasp_crs" / PINNED_REVISION
MANIFEST_PATH = ROOT / "benchmarks" / "manifests" / "owasp_crs_path_file_access.v1.json"
SCHEMA_DIR = ROOT / "benchmarks" / "schemas"

SENSITIVE_TARGET_TRAVERSAL_CASES = {
    "owasp_crs.930100.2",
    "owasp_crs.930100.3",
    "owasp_crs.930110.2",
    "owasp_crs.930110.9",
}
PURE_TRAVERSAL_CASES = {
    "owasp_crs.930110.8",
    "owasp_crs.930110.12",
    "owasp_crs.930120.1",
    "owasp_crs.930120.3",
    "owasp_crs.930120.15",
}


@pytest.fixture(scope="module")
def source_cases() -> list[dict]:
    return load_owasp_crs_cases(SOURCE_DIR)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return load_benchmark_manifest(MANIFEST_PATH)


def by_id(items: list[dict], case_id: str) -> dict:
    return next(item for item in items if item["case_id"] == case_id)


def test_source_metadata_and_license_contract() -> None:
    metadata = verify_owasp_crs_source_integrity(SOURCE_DIR)

    assert metadata["source"] == "owasp_crs"
    assert metadata["repository"] == "https://github.com/coreruleset/coreruleset"
    assert metadata["revision"] == PINNED_REVISION
    assert metadata["retrieved_at"] == "2026-09-01"
    assert metadata["license"] == "Apache-2.0"
    assert (SOURCE_DIR / "LICENSE").is_file()
    assert (SOURCE_DIR / "LICENSE").stat().st_size > 0


def test_source_raw_checksums_match_pinned_values() -> None:
    metadata = json.loads((SOURCE_DIR / "SOURCE.json").read_text(encoding="utf-8"))
    assert {item["name"] for item in metadata["files"]} == set(PINNED_FILES)

    for item in metadata["files"]:
        raw_sha256 = hashlib.sha256((SOURCE_DIR / item["name"]).read_bytes()).hexdigest()
        assert raw_sha256 == PINNED_FILES[item["name"]]["sha256"] == item["sha256"]
        assert item["upstream_path"] == PINNED_FILES[item["name"]]["upstream_path"]


def test_integrity_rejects_metadata_checksum_drift(tmp_path: Path) -> None:
    copied = tmp_path / "source"
    copied.mkdir()
    for path in SOURCE_DIR.iterdir():
        if not path.is_file():
            continue
        (copied / path.name).write_bytes(path.read_bytes())
    metadata = json.loads((copied / "SOURCE.json").read_text(encoding="utf-8"))
    metadata["files"][0]["sha256"] = "0" * 64
    (copied / "SOURCE.json").write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(BenchmarkContractError, match="metadata SHA-256"):
        verify_owasp_crs_source_integrity(copied)


def test_source_inventory_count_and_order(source_cases: list[dict]) -> None:
    assert len(source_cases) == 36
    assert Counter(case["source_rule_id"] for case in source_cases) == {
        930100: 5,
        930110: 13,
        930120: 18,
    }
    assert [(case["source_rule_id"], case["source_test_id"]) for case in source_cases] == [
        *[(930100, test_id) for test_id in range(1, 6)],
        *[(930110, test_id) for test_id in range(1, 14)],
        *[(930120, test_id) for test_id in range(1, 19)],
    ]


def test_source_case_ids_are_stable_unique_and_revision_is_separate(source_cases: list[dict]) -> None:
    case_ids = [case["case_id"] for case in source_cases]
    assert len(case_ids) == len(set(case_ids))
    assert case_ids[0] == "owasp_crs.930100.1"
    assert case_ids[-1] == "owasp_crs.930120.18"
    assert all(PINNED_REVISION not in case_id for case_id in case_ids)
    assert {case["source_revision"] for case in source_cases} == {PINNED_REVISION}


def test_methods_test_ids_and_descriptions_are_preserved(source_cases: list[dict]) -> None:
    case = by_id(source_cases, "owasp_crs.930100.5")
    assert case["source_test_id"] == 5
    assert case["description"] == "GHSA: 930100 payload via XML attribute injection (verifies XML://@* coverage)"
    assert case["request"]["method"] == "POST"
    assert by_id(source_cases, "owasp_crs.930110.7")["description"].endswith("`REQUEST_URI``\n")


@pytest.mark.parametrize(
    ("case_id", "request_target"),
    [
        ("owasp_crs.930100.3", "/get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini"),
        ("owasp_crs.930110.8", "/get?arg=..\\pineapple"),
        ("owasp_crs.930110.12", "/get?a=..;.\\.;\\."),
        ("owasp_crs.930120.1", "/get/index.php?file=News&op=../../../../../boot.ini%00"),
    ],
)
def test_critical_request_targets_are_byte_for_byte_text_preserved(
    source_cases: list[dict], case_id: str, request_target: str
) -> None:
    assert by_id(source_cases, case_id)["request"]["request_target"] == request_target


def test_header_names_case_and_arbitrary_values_are_preserved(source_cases: list[dict]) -> None:
    headers = by_id(source_cases, "owasp_crs.930100.1")["request"]["headers"]
    assert list(headers) == ["Host", "FoobarHeader", "User-Agent", "Accept"]
    assert headers["FoobarHeader"] == "0x5c0x2e.%00/"
    assert headers["User-Agent"] == "OWASP CRS test agent"


def test_post_xml_and_multipart_bodies_are_preserved(source_cases: list[dict]) -> None:
    body_ids = {
        case["case_id"]
        for case in source_cases
        if case["request"]["body"] is not None
    }
    assert body_ids == {
        "owasp_crs.930100.5",
        "owasp_crs.930110.3",
        "owasp_crs.930110.10",
        "owasp_crs.930110.11",
        "owasp_crs.930110.13",
        "owasp_crs.930120.17",
    }
    assert by_id(source_cases, "owasp_crs.930110.3")["request"]["body"] == {
        "present": True,
        "text": "arg=../../../etc/passwd&foo=var",
    }
    assert 'filename="../1.7z"' in by_id(source_cases, "owasp_crs.930110.10")["request"]["body"]["text"]
    assert 'probe="/etc/passwd"' in by_id(source_cases, "owasp_crs.930120.17")["request"]["body"]["text"]


def test_source_expectations_are_normalized_without_project_semantics(source_cases: list[dict]) -> None:
    counts = Counter(case["source_expectation"]["kind"] for case in source_cases)
    assert counts == {"expect_ids": 28, "no_expect_ids": 8}
    assert by_id(source_cases, "owasp_crs.930110.2")["source_expectation"] == {
        "kind": "expect_ids",
        "ids": [930110],
    }
    assert by_id(source_cases, "owasp_crs.930110.4")["source_expectation"] == {
        "kind": "no_expect_ids",
        "ids": [930110],
    }
    forbidden_project_keys = {"observability", "expected", "project_ground_truth", "verdict"}
    assert all(forbidden_project_keys.isdisjoint(case) for case in source_cases)


@pytest.mark.parametrize(
    "log",
    [
        {},
        {"expect_ids": [930110], "no_expect_ids": [930110]},
    ],
)
def test_source_expectation_requires_exactly_one_upstream_semantic(log: dict) -> None:
    with pytest.raises(BenchmarkContractError, match="exactly one"):
        benchmark_module._normalize_expectation(log, "test.log")


@pytest.mark.parametrize(
    "case_id",
    [
        "owasp_crs.930110.4",
        "owasp_crs.930110.5",
        "owasp_crs.930110.6",
        "owasp_crs.930110.7",
        "owasp_crs.930120.10",
        "owasp_crs.930120.11",
        "owasp_crs.930120.12",
        "owasp_crs.930120.16",
    ],
)
def test_negative_source_expectations_remain_no_expect_ids(source_cases: list[dict], case_id: str) -> None:
    assert by_id(source_cases, case_id)["source_expectation"]["kind"] == "no_expect_ids"


def test_unexpected_multistage_source_fails_instead_of_using_first_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copied = tmp_path / "source"
    copied.mkdir()
    for path in SOURCE_DIR.iterdir():
        if not path.is_file():
            continue
        (copied / path.name).write_bytes(path.read_bytes())
    path = copied / "930100.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document["tests"][0]["stages"].append(copy.deepcopy(document["tests"][0]["stages"][0]))
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        benchmark_module,
        "verify_owasp_crs_source_integrity",
        lambda _source_dir: {"revision": PINNED_REVISION},
    )

    with pytest.raises(BenchmarkContractError, match="exactly one stage"):
        load_owasp_crs_cases(copied)


def test_manifest_is_complete_valid_and_same_case_set(source_cases: list[dict], manifest: dict) -> None:
    assert validate_benchmark_manifest(manifest, source_cases) == []
    assert len(manifest["cases"]) == 36
    assert {case["case_id"] for case in source_cases} == {
        case["case_id"] for case in manifest["cases"]
    }


def test_manifest_observability_counts_total_and_per_rule(manifest: dict) -> None:
    statuses = Counter(case["observability"]["status"] for case in manifest["cases"])
    assert statuses == {"direct": 27, "partial": 3, "out_of_scope": 6}
    expected = {
        930100: {"direct": 2, "partial": 2, "out_of_scope": 1},
        930110: {"direct": 8, "partial": 1, "out_of_scope": 4},
        930120: {"direct": 17, "partial": 0, "out_of_scope": 1},
    }
    for rule_id, counts in expected.items():
        actual = Counter(
            case["observability"]["status"]
            for case in manifest["cases"]
            if case["case_id"].startswith(f"owasp_crs.{rule_id}.")
        )
        assert {status: actual[status] for status in counts} == counts


def test_manifest_partial_and_out_of_scope_inventory_is_exact(manifest: dict) -> None:
    partial = {
        case["case_id"]: case["observability"]["exclusion_reason"]
        for case in manifest["cases"]
        if case["observability"]["status"] == "partial"
    }
    out_of_scope = {
        case["case_id"]: case["observability"]["exclusion_reason"]
        for case in manifest["cases"]
        if case["observability"]["status"] == "out_of_scope"
    }
    assert partial == {
        "owasp_crs.930100.1": "header_not_available",
        "owasp_crs.930100.4": "header_not_available",
        "owasp_crs.930110.1": "header_not_available",
    }
    assert out_of_scope == {
        "owasp_crs.930100.5": "xml_body_not_logged",
        "owasp_crs.930110.3": "post_body_not_logged",
        "owasp_crs.930110.10": "multipart_filename_not_logged",
        "owasp_crs.930110.11": "multipart_filename_not_logged",
        "owasp_crs.930110.13": "xml_body_not_logged",
        "owasp_crs.930120.17": "xml_body_not_logged",
    }


def test_manifest_classification_policy_counts(manifest: dict) -> None:
    assert Counter(case["expected"]["classification_policy"] for case in manifest["cases"]) == {
        "exact": 10,
        "compatible_set": 9,
        "forbidden_only": 8,
        "not_scored": 9,
    }


def test_strict_traversal_cases_are_exact_with_mapping(manifest: dict) -> None:
    for case_id in SENSITIVE_TARGET_TRAVERSAL_CASES | PURE_TRAVERSAL_CASES:
        expected = by_id(manifest["cases"], case_id)["expected"]
        assert expected["classification_policy"] == "exact"
        assert expected["candidate_expected"] is True
        assert expected["allowed_stage1_verdicts"] == ["suspicious_path_traversal"]
        assert expected["mapping_by_verdict"]["suspicious_path_traversal"]["required_ids"] == [
            "A01:2025",
            "CWE-22",
            "WSTG-ATHZ-01",
        ]


def test_sensitive_target_traversal_allows_optional_cwe_552(manifest: dict) -> None:
    for case_id in SENSITIVE_TARGET_TRAVERSAL_CASES:
        expected = by_id(manifest["cases"], case_id)["expected"]
        mapping = expected["mapping_by_verdict"]["suspicious_path_traversal"]
        assert expected["classification_policy"] == "exact"
        assert expected["allowed_stage1_verdicts"] == ["suspicious_path_traversal"]
        assert mapping["required_ids"] == ["A01:2025", "CWE-22", "WSTG-ATHZ-01"]
        assert mapping["forbidden_ids"] == []


def test_pure_traversal_keeps_cwe_552_forbidden(manifest: dict) -> None:
    for case_id in PURE_TRAVERSAL_CASES:
        mapping = by_id(manifest["cases"], case_id)["expected"]["mapping_by_verdict"]
        assert "CWE-552" in mapping["suspicious_path_traversal"]["forbidden_ids"]


def test_930100_3_exact_classification_and_observability_are_frozen(manifest: dict) -> None:
    case = by_id(manifest["cases"], "owasp_crs.930100.3")
    assert case["observability"]["eligible"] is True
    assert case["observability"]["status"] == "direct"
    assert case["expected"]["project_ground_truth"] == "attack_positive"
    assert case["expected"]["candidate_expected"] is True
    assert case["expected"]["classification_policy"] == "exact"
    assert case["expected"]["allowed_stage1_verdicts"] == [
        "suspicious_path_traversal"
    ]
    assert case["expected"]["forbidden_stage1_verdicts"] == [
        "suspicious_sqli",
        "suspicious_xss",
        "suspicious_file_disclosure",
    ]


def test_direct_etc_passwd_guardrail_matches_current_hint_boundary(manifest: dict) -> None:
    case = by_id(manifest["cases"], "owasp_crs.930120.2")
    expected = case["expected"]
    assert expected["classification_policy"] == "exact"
    assert expected["allowed_stage1_verdicts"] == ["suspicious_file_disclosure"]
    assert expected["forbidden_stage1_verdicts"] == ["suspicious_path_traversal"]
    assert expected["mapping_by_verdict"]["suspicious_file_disclosure"] == {
        "required_ids": [],
        "forbidden_ids": ["CWE-22"],
    }
    assert "traversal hint" in case["review"]["note"]


def test_direct_etc_passwd_guardrail_records_current_mapping_mismatch() -> None:
    mapping = build_security_standards_mapping(
        {
            "verdict": "suspicious_file_disclosure",
            "reason_hints": ["traversal:etc_passwd(+5)"],
        }
    )
    mapped_ids = {item["id"] for item in mapping["items"]}
    assert "CWE-22" in mapped_ids
    assert "CWE-552" not in mapped_ids


def test_compatible_resource_and_command_cases_are_case_specific(manifest: dict) -> None:
    file_or_scan = [4, 5, 6, 13, 14, 18]
    for test_id in file_or_scan:
        expected = by_id(manifest["cases"], f"owasp_crs.930120.{test_id}")["expected"]
        assert expected["allowed_stage1_verdicts"] == [
            "suspicious_file_disclosure",
            "suspicious_scan",
        ]
        assert expected["forbidden_stage1_verdicts"] == ["suspicious_path_traversal"]
    assert by_id(manifest["cases"], "owasp_crs.930120.7")["expected"]["allowed_stage1_verdicts"] == [
        "suspicious_command_injection",
        "suspicious_file_disclosure",
        "suspicious_scan",
    ]
    assert by_id(manifest["cases"], "owasp_crs.930120.8")["expected"]["allowed_stage1_verdicts"] == [
        "suspicious_command_injection",
        "suspicious_file_disclosure",
        "suspicious_scan",
    ]
    assert by_id(manifest["cases"], "owasp_crs.930120.9")["expected"]["allowed_stage1_verdicts"] == [
        "suspicious_command_injection",
        "suspicious_scan",
    ]


def test_negative_controls_are_forbidden_only_and_candidate_optional(manifest: dict) -> None:
    negative_ids = {
        *[f"owasp_crs.930110.{test_id}" for test_id in range(4, 8)],
        *[f"owasp_crs.930120.{test_id}" for test_id in (10, 11, 12, 16)],
    }
    for case_id in negative_ids:
        expected = by_id(manifest["cases"], case_id)["expected"]
        assert expected["project_ground_truth"] == "project_negative"
        assert expected["candidate_expected"] is False
        assert expected["classification_policy"] == "forbidden_only"
        assert expected["forbidden_stage1_verdicts"]
        assert expected["allowed_stage1_verdicts"] == [
            "benign_normal",
            "likely_false_positive",
            "inconclusive",
        ]


@pytest.mark.parametrize(
    ("mutation", "error_fragment"),
    [
        (lambda value: value["cases"].append(copy.deepcopy(value["cases"][0])), "duplicate manifest"),
        (lambda value: value["cases"][0].update({"case_id": "owasp_crs.999999.1"}), "unknown cases"),
        (lambda value: value["source"].update({"revision": "0" * 40}), "source revision"),
        (lambda value: value["cases"][1]["observability"].update({"eligible": False}), "eligible must be true iff"),
        (lambda value: value["cases"][1]["expected"]["allowed_stage1_verdicts"].append("suspicious_typo"), "unknown Stage1 verdicts"),
        (lambda value: value["cases"][1]["expected"]["mapping_by_verdict"]["suspicious_path_traversal"]["forbidden_ids"].append("CWE-22"), "required/forbidden IDs overlap"),
    ],
)
def test_manifest_validator_rejects_identity_and_semantic_mutations(
    source_cases: list[dict], manifest: dict, mutation, error_fragment: str
) -> None:
    invalid = copy.deepcopy(manifest)
    mutation(invalid)
    assert any(error_fragment in error for error in validate_benchmark_manifest(invalid, source_cases))


def test_manifest_validator_and_join_do_not_mutate_inputs(source_cases: list[dict], manifest: dict) -> None:
    source_before = copy.deepcopy(source_cases)
    manifest_before = copy.deepcopy(manifest)

    assert validate_benchmark_manifest(manifest, source_cases) == []
    build_normalized_benchmark_cases(source_cases, manifest)

    assert source_cases == source_before
    assert manifest == manifest_before


def test_joined_cases_keep_source_and_project_expectations_separate(
    source_cases: list[dict], manifest: dict
) -> None:
    joined = build_normalized_benchmark_cases(source_cases, manifest)
    assert len(joined) == 36
    assert [case["case_id"] for case in joined] == [case["case_id"] for case in source_cases]

    traversal = by_id(joined, "owasp_crs.930110.2")
    assert traversal["source"]["expectation"] == {"kind": "expect_ids", "ids": [930110]}
    assert traversal["request"]["request_target"] == "/get?arg=../../../etc/passwd"
    assert traversal["expected"]["allowed_stage1_verdicts"] == ["suspicious_path_traversal"]

    disclosure = by_id(joined, "owasp_crs.930120.2")
    assert disclosure["source"]["expectation"] == {"kind": "expect_ids", "ids": [930120]}
    assert disclosure["expected"]["allowed_stage1_verdicts"] == ["suspicious_file_disclosure"]
    assert "suspicious_path_traversal" in disclosure["expected"]["forbidden_stage1_verdicts"]

    negative = by_id(joined, "owasp_crs.930110.4")
    assert negative["source"]["expectation"] == {"kind": "no_expect_ids", "ids": [930110]}
    assert negative["expected"]["project_ground_truth"] == "project_negative"
    assert negative["expected"]["classification_policy"] == "forbidden_only"


def test_joined_request_is_an_independent_copy(source_cases: list[dict], manifest: dict) -> None:
    joined = build_normalized_benchmark_cases(source_cases, manifest)
    joined[0]["request"]["headers"]["Host"] = "changed.invalid"
    assert source_cases[0]["request"]["headers"]["Host"] == "localhost"


def test_json_schemas_and_checked_in_json_parse() -> None:
    manifest_schema = json.loads(
        (SCHEMA_DIR / "external_security_benchmark_manifest.v1.schema.json").read_text(encoding="utf-8")
    )
    case_schema = json.loads(
        (SCHEMA_DIR / "external_security_benchmark_case.v1.schema.json").read_text(encoding="utf-8")
    )
    json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert case_schema["properties"]["schema_version"]["const"] == "external_security_benchmark_case.v1"


def test_manifest_schema_verdict_enum_does_not_drift_from_stage1() -> None:
    manifest_schema = json.loads(
        (SCHEMA_DIR / "external_security_benchmark_manifest.v1.schema.json").read_text(encoding="utf-8")
    )
    schema_verdicts = set(manifest_schema["$defs"]["verdict_set"]["items"]["enum"])
    stage1_verdicts = set(build_stage1_schema()["properties"]["verdict"]["enum"])
    assert schema_verdicts == stage1_verdicts == KNOWN_VERDICTS
