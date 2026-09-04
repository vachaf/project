from __future__ import annotations

import copy
from pathlib import Path

from src.external_benchmark_crs import build_normalized_benchmark_cases, load_benchmark_manifest, load_owasp_crs_cases
from src.external_benchmark_crs_multifamily import (
    join_family_manifest,
    load_benchmark_suite,
    load_family_benchmark_manifest,
    load_multifamily_crs_cases,
    resolve_benchmark_suite,
    validate_benchmark_suite,
)


ROOT = Path(__file__).resolve().parents[1]
REVISION = "96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a"
LEGACY_SOURCE = ROOT / f"benchmarks/sources/owasp_crs/{REVISION}"
MULTI_SOURCE = LEGACY_SOURCE / "multi_family"
SUITE_PATH = ROOT / "benchmarks/suites/owasp_crs_multi_family.v1.json"


def manifests() -> dict[str, dict]:
    legacy = load_benchmark_manifest(ROOT / "benchmarks/manifests/owasp_crs_path_file_access.v1.json")
    return {
        legacy["benchmark"]: legacy,
        **{
            manifest["benchmark"]: manifest
            for manifest in (
                load_family_benchmark_manifest(ROOT / "benchmarks/manifests/owasp_crs_cmdi.v1.json"),
                load_family_benchmark_manifest(ROOT / "benchmarks/manifests/owasp_crs_xss.v1.json"),
                load_family_benchmark_manifest(ROOT / "benchmarks/manifests/owasp_crs_sqli.v1.json"),
            )
        },
    }


def test_suite_exact_core_and_groups_are_valid() -> None:
    suite = load_benchmark_suite(SUITE_PATH)
    assert validate_benchmark_suite(suite, manifests()) == []
    exact = suite["groups"]["exact_core"]
    assert {name: len(ids) for name, ids in exact.items()} == {"traversal": 9, "cmdi": 9, "xss": 9, "sqli": 9}
    assert sum(len(ids) for ids in exact.values()) == 36
    assert len(suite["groups"]["path_file_boundary_addendum"]) == 10
    assert suite["groups"]["path_file_boundary_addendum"][-1] == "owasp_crs.930120.2"


def test_suite_rejects_unknown_group_case_and_wrong_exact_core() -> None:
    suite = load_benchmark_suite(SUITE_PATH)
    bad_group = copy.deepcopy(suite)
    bad_group["groups"]["cmdi_negative"].append("owasp_crs.999999.1")
    assert any("unknown case" in error for error in validate_benchmark_suite(bad_group, manifests()))
    bad_core = copy.deepcopy(suite)
    bad_core["groups"]["exact_core"]["cmdi"][0] = "owasp_crs.932130.10"
    assert any("non-exact" in error for error in validate_benchmark_suite(bad_core, manifests()))


def test_suite_rejects_missing_duplicate_component_and_group_duplicate() -> None:
    suite = load_benchmark_suite(SUITE_PATH)
    missing = copy.deepcopy(suite)
    missing["components"].pop()
    assert any("exactly four" in error for error in validate_benchmark_suite(missing, manifests()))
    duplicate_component = copy.deepcopy(suite)
    duplicate_component["components"][1]["benchmark"] = "owasp_crs_path_file_access.v1"
    assert any("duplicate benchmark" in error for error in validate_benchmark_suite(duplicate_component, manifests()))
    duplicate_group = copy.deepcopy(suite)
    duplicate_group["groups"]["cmdi_negative"].append(duplicate_group["groups"]["cmdi_negative"][0])
    assert any("must be unique" in error for error in validate_benchmark_suite(duplicate_group, manifests()))
    unknown_path = copy.deepcopy(suite)
    unknown_path["components"][1]["manifest"] = "../manifests/not-a-manifest.json"
    assert any("unresolved manifest" in error for error in validate_benchmark_suite(unknown_path, manifests()))


def test_suite_resolution_keeps_component_provenance_without_mutation() -> None:
    suite = load_benchmark_suite(SUITE_PATH)
    source = load_multifamily_crs_cases(MULTI_SOURCE)
    legacy_source = load_owasp_crs_cases(LEGACY_SOURCE)
    manifest_map = manifests()
    normalized = {
        "owasp_crs_path_file_access.v1": build_normalized_benchmark_cases(legacy_source, manifest_map["owasp_crs_path_file_access.v1"]),
        "owasp_crs_cmdi.v1": join_family_manifest(manifest_map["owasp_crs_cmdi.v1"], source),
        "owasp_crs_xss.v1": join_family_manifest(manifest_map["owasp_crs_xss.v1"], source),
        "owasp_crs_sqli.v1": join_family_manifest(manifest_map["owasp_crs_sqli.v1"], source),
    }
    before = copy.deepcopy(normalized["owasp_crs_cmdi.v1"][0])
    resolved = resolve_benchmark_suite(suite, manifest_map, normalized)
    assert resolved["suite"] == "owasp_crs_multi_family.v1"
    assert any(case["component_benchmark"] == "owasp_crs_cmdi.v1" for case in resolved["cases"])
    assert normalized["owasp_crs_cmdi.v1"][0] == before
