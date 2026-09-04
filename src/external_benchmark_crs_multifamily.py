"""Pinned OWASP CRS multi-family source, annotation, and suite contracts.

This module is intentionally separate from :mod:`external_benchmark_crs`.
The latter remains the frozen, full-inventory 930 adapter; this module supports
an upstream-source superset with reviewed family-manifest subsets.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from src.security_standards_mapping import KNOWN_VERDICTS


BENCHMARK_SOURCE = "owasp_crs"
PINNED_REVISION = "96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a"
MULTIFAMILY_BUNDLE = "multi_family"
FAMILIES = frozenset({"932", "941", "942"})
FAMILY_BENCHMARKS = {
    "932": "owasp_crs_cmdi.v1",
    "941": "owasp_crs_xss.v1",
    "942": "owasp_crs_sqli.v1",
}
SUITE_MANIFEST_PATHS = {
    "owasp_crs_path_file_access.v1": "../manifests/owasp_crs_path_file_access.v1.json",
    "owasp_crs_cmdi.v1": "../manifests/owasp_crs_cmdi.v1.json",
    "owasp_crs_xss.v1": "../manifests/owasp_crs_xss.v1.json",
    "owasp_crs_sqli.v1": "../manifests/owasp_crs_sqli.v1.json",
}
OBSERVABILITY_STATUSES = {"direct", "partial", "out_of_scope"}
GROUND_TRUTHS = {"attack_positive", "project_negative", "not_scored"}
CLASSIFICATION_POLICIES = {"exact", "compatible_set", "forbidden_only", "not_scored"}
BOUNDARY_TOKENS = {
    "request_pattern_only",
    "no_command_execution_success_inference",
    "no_db_execution_or_data_exposure_inference",
    "no_xss_execution_or_reflection_inference",
}

# A checked-in lock prevents a simultaneous edit of YAML and SOURCE.json from
# silently redefining the pinned bundle.  SOURCE.json remains machine-readable
# provenance; this index is the runtime integrity authority.
PINNED_MULTIFAMILY_FILES: dict[str, dict[str, Any]] = {
    "932/932125.yaml": {"family": "932", "rule_id": 932125, "sha256": "df417538a5d3587c8bd0674eff67f84c21dcaeea5538abb8613e1641e6aa38f9", "case_count": 7},
    "932/932130.yaml": {"family": "932", "rule_id": 932130, "sha256": "a5ea0e6627ed8f286ecb8c46afe502cd7f4ed9d5c81c69e9517698526b93f40d", "case_count": 41},
    "932/932230.yaml": {"family": "932", "rule_id": 932230, "sha256": "e1140034a7040aa310f62c50507d03e5832609b9bd45a0dda6ae890f8fa864d4", "case_count": 67},
    "932/932340.yaml": {"family": "932", "rule_id": 932340, "sha256": "3627e7588983b6b78037f0c896d7adc13b028ec0c5f38cda1cee23e4305308ad", "case_count": 29},
    "932/932370.yaml": {"family": "932", "rule_id": 932370, "sha256": "1a7abd2b20e77cc229cd1d72afde6a807a31f18d549aab6ef09fc46c5600263e", "case_count": 8},
    "932/932380.yaml": {"family": "932", "rule_id": 932380, "sha256": "ed5ef150ccd0de8bdacf458ac69006cd554defbd2553b7629e077b5037755901", "case_count": 27},
    "941/941100.yaml": {"family": "941", "rule_id": 941100, "sha256": "81f35e7346b9992a73ddd79ab703cbc34c2ecf41842206a65592277abd8975bf", "case_count": 9},
    "941/941110.yaml": {"family": "941", "rule_id": 941110, "sha256": "f0dd2bddea90d29453a10c6ce07129db0bc3e91bb15d24c2161b788b75eabb5e", "case_count": 13},
    "941/941120.yaml": {"family": "941", "rule_id": 941120, "sha256": "4e2b1c3656cbb7347f1680e82142a87fcd163e8d3401815b95a6181df88f3aed", "case_count": 52},
    "941/941140.yaml": {"family": "941", "rule_id": 941140, "sha256": "c011fad3e385b95baa919eec5a4cd5b64e97d6f5af5ef56064e1cfc77a3332b7", "case_count": 15},
    "941/941160.yaml": {"family": "941", "rule_id": 941160, "sha256": "5f6d9d76b965e61e87827e1e20e6fe9c94a13a68db1a35fd04b4a7bc14c6bab0", "case_count": 18},
    "941/941170.yaml": {"family": "941", "rule_id": 941170, "sha256": "d057a2a48f64f506be834b9dc43db3c2352e4820bda2efbc4c7072b52de7fbd2", "case_count": 8},
    "941/941180.yaml": {"family": "941", "rule_id": 941180, "sha256": "aea55da17851dad5a2e7c63e5788805e14292a76cd582e4a7f4f41ab02a59746", "case_count": 10},
    "941/941390.yaml": {"family": "941", "rule_id": 941390, "sha256": "09cdc3d93575e3a45deb8d1b572e3efbc71ed6aeec5b1bfe0ab9aba8cc477b6f", "case_count": 12},
    "941/941400.yaml": {"family": "941", "rule_id": 941400, "sha256": "ceb193107dad237b3041724d28d6209196e475b1f009d8d9675c94c11e382473", "case_count": 8},
    "942/942160.yaml": {"family": "942", "rule_id": 942160, "sha256": "1ca1e8ab7951f4ff362506fed7b60f10d0645647ca622d788244c4b90a0f2bba", "case_count": 27},
    "942/942170.yaml": {"family": "942", "rule_id": 942170, "sha256": "762be2329555d550b4cbaad75cf6ba13eef120e60b91801f42f55add39deef25", "case_count": 5},
    "942/942230.yaml": {"family": "942", "rule_id": 942230, "sha256": "1a349ccd30f8e814533929b603bb136bf60c2c4dec68f3d02d4e84a132cf592b", "case_count": 13},
    "942/942270.yaml": {"family": "942", "rule_id": 942270, "sha256": "4db3b09e588b7fb0a84265f95bdfa557d4bc68b87a8179c188025605ea7d4e65", "case_count": 3},
    "942/942280.yaml": {"family": "942", "rule_id": 942280, "sha256": "4b970b532f23fe988371ef843c312a62d00b2b6b6b97609fd38cd2193c082c87", "case_count": 5},
    "942/942320.yaml": {"family": "942", "rule_id": 942320, "sha256": "cdb5b46c7a09d2149359887d6622b707479c728d06f16738b5a8974be5c4106e", "case_count": 14},
    "942/942350.yaml": {"family": "942", "rule_id": 942350, "sha256": "5a68113dd7bed02fc7f691f7468e98a8dc5230e14ca8a9f40231505be976c162", "case_count": 10},
    "942/942500.yaml": {"family": "942", "rule_id": 942500, "sha256": "6c22086da1ee694d9515fad3c9144d59027747861d02190eddf874c7c2e237b2", "case_count": 6},
    "942/942550.yaml": {"family": "942", "rule_id": 942550, "sha256": "ba8d0a41f8493bf37e12d2df35a83d0bfca16cfa609ba4e87011ec5bec7827d3", "case_count": 49},
}


class MultiFamilyBenchmarkContractError(ValueError):
    """Raised when a pinned source, family annotation, or suite is invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MultiFamilyBenchmarkContractError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MultiFamilyBenchmarkContractError(f"JSON root must be an object: {path}")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MultiFamilyBenchmarkContractError(f"{label} must be a non-empty string")
    return value


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MultiFamilyBenchmarkContractError(f"{label} must be an integer")
    return value


def verify_multifamily_crs_source_integrity(source_dir: str | Path) -> dict[str, Any]:
    """Verify provenance, lock metadata, and raw vendored bytes without network."""

    root = Path(source_dir)
    metadata = _load_json(root / "SOURCE.json")
    errors: list[str] = []
    expected_root = {
        "source": BENCHMARK_SOURCE,
        "repository": "https://github.com/coreruleset/coreruleset",
        "revision": PINNED_REVISION,
        "license": "Apache-2.0",
        "bundle": MULTIFAMILY_BUNDLE,
    }
    for key, expected in expected_root.items():
        if metadata.get(key) != expected:
            errors.append(f"SOURCE.json {key} must be {expected!r}")
    if not isinstance(metadata.get("retrieved_at"), str) or not metadata["retrieved_at"]:
        errors.append("SOURCE.json retrieved_at must be a non-empty string")
    license_path = root / "LICENSE"
    if not license_path.is_file() or hashlib.sha256(license_path.read_bytes()).hexdigest() != "676a192d3fc5205a288934ee02c5f934b782b91604a4b93589ba64520a4fec13":
        errors.append("upstream Apache-2.0 LICENSE is missing or differs from pinned bytes")

    raw_files = metadata.get("files")
    indexed: dict[str, Mapping[str, Any]] = {}
    if not isinstance(raw_files, list):
        errors.append("SOURCE.json files must be an array")
        raw_files = []
    for index, item in enumerate(raw_files):
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            errors.append(f"SOURCE.json files[{index}] must be an object with name")
            continue
        if item["name"] in indexed:
            errors.append(f"SOURCE.json duplicate file {item['name']}")
        indexed[item["name"]] = item
    if set(indexed) != set(PINNED_MULTIFAMILY_FILES):
        errors.append("SOURCE.json file set differs from the pinned multi-family lock")
    for name, expected in PINNED_MULTIFAMILY_FILES.items():
        item = indexed.get(name)
        if item is None:
            continue
        upstream = f"tests/regression/tests/REQUEST-{expected['family']}-APPLICATION-ATTACK-"
        family_suffix = {"932": "RCE", "941": "XSS", "942": "SQLI"}[expected["family"]]
        expected_path = f"{upstream}{family_suffix}/{Path(name).name}"
        for key, value in (("family", expected["family"]), ("rule_id", expected["rule_id"]), ("sha256", expected["sha256"]), ("case_count", expected["case_count"]), ("upstream_path", expected_path)):
            if item.get(key) != value:
                errors.append(f"{name}: SOURCE.json {key} mismatch")
        path = root / name
        if not path.is_file():
            errors.append(f"{name}: vendored YAML missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            errors.append(f"{name}: raw SHA-256 mismatch")
    registered = {Path(name) for name in PINNED_MULTIFAMILY_FILES}
    actual = {path.relative_to(root) for path in root.glob("*/*.yaml")}
    if actual != registered:
        errors.append("unregistered or missing YAML files in multi-family bundle")
    if errors:
        raise MultiFamilyBenchmarkContractError("multi-family source integrity failure:\n- " + "\n- ".join(errors))
    return copy.deepcopy(metadata)


def _normalize_expectation(log: Mapping[str, Any], label: str) -> dict[str, Any]:
    keys = [key for key in ("expect_ids", "no_expect_ids") if key in log]
    if len(keys) != 1:
        raise MultiFamilyBenchmarkContractError(f"{label} must contain exactly one source expectation")
    values = log[keys[0]]
    if not isinstance(values, list) or not values:
        raise MultiFamilyBenchmarkContractError(f"{label}.{keys[0]} must be a non-empty array")
    ids = [_require_int(value, f"{label}.{keys[0]}") for value in values]
    if len(ids) != len(set(ids)):
        raise MultiFamilyBenchmarkContractError(f"{label}.{keys[0]} has duplicate IDs")
    return {"kind": keys[0], "ids": ids}


def _load_source_file(path: Path, source_root: Path, revision: str) -> list[dict[str, Any]]:
    name = str(path.relative_to(source_root))
    expected = PINNED_MULTIFAMILY_FILES[name]
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise MultiFamilyBenchmarkContractError(f"cannot parse YAML {name}: {exc}") from exc
    if not isinstance(document, Mapping):
        raise MultiFamilyBenchmarkContractError(f"{name} root must be an object")
    rule_id = _require_int(document.get("rule_id"), f"{name}.rule_id")
    if rule_id != expected["rule_id"]:
        raise MultiFamilyBenchmarkContractError(f"{name} rule_id differs from source lock")
    tests = document.get("tests")
    if not isinstance(tests, list) or len(tests) != expected["case_count"]:
        raise MultiFamilyBenchmarkContractError(f"{name} test count differs from source lock")
    cases: list[dict[str, Any]] = []
    for index, test in enumerate(tests):
        if not isinstance(test, Mapping):
            raise MultiFamilyBenchmarkContractError(f"{name}.tests[{index}] must be an object")
        test_id = _require_int(test.get("test_id"), f"{name}.tests[{index}].test_id")
        stages = test.get("stages")
        if not isinstance(stages, list) or len(stages) != 1 or not isinstance(stages[0], Mapping):
            raise MultiFamilyBenchmarkContractError(f"{name}.{test_id} must have exactly one stage")
        stage = stages[0]
        input_value = stage.get("input")
        output_value = stage.get("output")
        if not isinstance(input_value, Mapping) or not isinstance(output_value, Mapping):
            raise MultiFamilyBenchmarkContractError(f"{name}.{test_id} stage input/output must be objects")
        log = output_value.get("log")
        if not isinstance(log, Mapping):
            raise MultiFamilyBenchmarkContractError(f"{name}.{test_id}.output.log must be an object")
        headers = input_value.get("headers")
        if not isinstance(headers, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()):
            raise MultiFamilyBenchmarkContractError(f"{name}.{test_id}.headers must be string map")
        body = input_value.get("data")
        if body is not None and not isinstance(body, str):
            raise MultiFamilyBenchmarkContractError(f"{name}.{test_id}.data must be string when present")
        request_target = input_value.get("uri")
        if request_target is not None and not isinstance(request_target, str):
            raise MultiFamilyBenchmarkContractError(f"{name}.{test_id}.uri must be string when present")
        cases.append({
            "case_id": f"owasp_crs.{rule_id}.{test_id}",
            "benchmark_source": BENCHMARK_SOURCE,
            "source_revision": revision,
            "source_family": expected["family"],
            "source_rule_id": rule_id,
            "source_test_id": test_id,
            "description": str(test.get("desc", "")),
            "request": {
                "method": _require_string(input_value.get("method"), f"{name}.{test_id}.method"),
                # FTW permits a body-only request with no explicit URI.  Keep
                # that upstream absence as None; never invent a route.
                "request_target": request_target,
                "http_version": _require_string(input_value.get("version"), f"{name}.{test_id}.version"),
                "headers": dict(headers),
                "body": None if body is None else {"present": True, "text": body},
            },
            "source_expectation": _normalize_expectation(log, f"{name}.{test_id}.output.log"),
        })
    return cases


def load_multifamily_crs_cases(source_dir: str | Path, *, families: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Load raw source facts only, in numeric rule/test order, without network."""

    root = Path(source_dir)
    metadata = verify_multifamily_crs_source_integrity(root)
    selected = set(FAMILIES if families is None else families)
    if not selected or not selected <= FAMILIES:
        raise MultiFamilyBenchmarkContractError(f"families must be a non-empty subset of {sorted(FAMILIES)!r}")
    cases: list[dict[str, Any]] = []
    for name, info in PINNED_MULTIFAMILY_FILES.items():
        if info["family"] in selected:
            cases.extend(_load_source_file(root / name, root, metadata["revision"]))
    cases.sort(key=lambda item: (item["source_rule_id"], item["source_test_id"]))
    if len({item["case_id"] for item in cases}) != len(cases):
        raise MultiFamilyBenchmarkContractError("source bundle contains duplicate case IDs")
    return cases


def load_family_benchmark_manifest(path: str | Path) -> dict[str, Any]:
    return _load_json(Path(path))


def _string_set(value: Any, label: str, errors: list[str], *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{label} must be a string array")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{label} must not contain duplicates")
    if not allow_empty and not value:
        errors.append(f"{label} must not be empty")
    return list(value)


def validate_family_benchmark_manifest(manifest: Mapping[str, Any], source_cases: Sequence[Mapping[str, Any]]) -> list[str]:
    """Validate a reviewed manifest subset; deliberately does not require full source coverage."""

    errors: list[str] = []
    if not isinstance(manifest, Mapping):
        return ["manifest must be an object"]
    if manifest.get("schema_version") != "external_security_benchmark_family_manifest.v1":
        errors.append("invalid family manifest schema_version")
    benchmark = manifest.get("benchmark")
    source = manifest.get("source")
    annotation = manifest.get("annotation")
    if not isinstance(benchmark, str) or benchmark not in set(FAMILY_BENCHMARKS.values()):
        errors.append("unknown family benchmark")
    if not isinstance(source, Mapping) or source.get("benchmark_source") != BENCHMARK_SOURCE or source.get("revision") != PINNED_REVISION:
        errors.append("source must identify the pinned OWASP CRS revision")
    if not isinstance(annotation, Mapping):
        errors.append("annotation must be an object")
        family = None
    else:
        family = annotation.get("source_family")
        if annotation.get("version") != benchmark:
            errors.append("annotation.version must equal benchmark")
        if family not in FAMILIES or FAMILY_BENCHMARKS.get(family) != benchmark:
            errors.append("annotation.source_family does not match benchmark")
    source_by_id = {item.get("case_id"): item for item in source_cases}
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a non-empty array"]
    seen: set[str] = set()
    for index, case in enumerate(cases):
        label = f"cases[{index}]"
        if not isinstance(case, Mapping):
            errors.append(f"{label} must be an object")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str):
            errors.append(f"{label}.case_id must be string")
            continue
        if case_id in seen:
            errors.append(f"duplicate manifest case {case_id}")
        seen.add(case_id)
        source_case = source_by_id.get(case_id)
        if source_case is None:
            errors.append(f"unknown source case {case_id}")
        elif family is not None and source_case.get("source_family") != family:
            errors.append(f"{case_id} belongs to another source family")
        observability = case.get("observability")
        expected = case.get("expected")
        review = case.get("review")
        if not isinstance(observability, Mapping) or observability.get("status") not in OBSERVABILITY_STATUSES:
            errors.append(f"{case_id} has invalid observability")
        elif observability.get("eligible") != (observability.get("status") == "direct"):
            errors.append(f"{case_id} observability eligible must match direct status")
        if not isinstance(expected, Mapping):
            errors.append(f"{case_id} expected must be an object")
            continue
        truth = expected.get("project_ground_truth")
        policy = expected.get("classification_policy")
        if truth not in GROUND_TRUTHS or policy not in CLASSIFICATION_POLICIES:
            errors.append(f"{case_id} has invalid ground truth or classification policy")
        allowed = _string_set(expected.get("allowed_stage1_verdicts"), f"{case_id}.allowed", errors)
        forbidden = _string_set(expected.get("forbidden_stage1_verdicts"), f"{case_id}.forbidden", errors)
        if set(allowed) & set(forbidden):
            errors.append(f"{case_id} allowed and forbidden verdicts overlap")
        if any(value not in KNOWN_VERDICTS for value in allowed + forbidden):
            errors.append(f"{case_id} has unknown Stage1 verdict")
        if expected.get("boundary") not in BOUNDARY_TOKENS:
            errors.append(f"{case_id} has invalid boundary token")
        mappings = expected.get("mapping_by_verdict")
        if not isinstance(mappings, Mapping):
            errors.append(f"{case_id} mapping_by_verdict must be an object")
        else:
            for verdict, mapping in mappings.items():
                if verdict not in KNOWN_VERDICTS or not isinstance(mapping, Mapping):
                    errors.append(f"{case_id} invalid mapping entry")
                    continue
                required = _string_set(mapping.get("required_ids"), f"{case_id}.{verdict}.required_ids", errors)
                forbidden_ids = _string_set(mapping.get("forbidden_ids"), f"{case_id}.{verdict}.forbidden_ids", errors)
                if set(required) & set(forbidden_ids):
                    errors.append(f"{case_id}.{verdict} required and forbidden IDs overlap")
        if not isinstance(review, Mapping) or review.get("status") != "approved" or not isinstance(review.get("note"), str):
            errors.append(f"{case_id} must have approved review")
    return errors


def join_family_manifest(manifest: Mapping[str, Any], source_cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    errors = validate_family_benchmark_manifest(manifest, source_cases)
    if errors:
        raise MultiFamilyBenchmarkContractError("family manifest invalid:\n- " + "\n- ".join(errors))
    source_by_id = {item["case_id"]: item for item in source_cases}
    result: list[dict[str, Any]] = []
    for annotation in manifest["cases"]:
        source = source_by_id[annotation["case_id"]]
        result.append({
            "case_id": source["case_id"],
            "component_benchmark": manifest["benchmark"],
            "source": copy.deepcopy(source),
            "observability": copy.deepcopy(annotation["observability"]),
            "expected": copy.deepcopy(annotation["expected"]),
            "annotation": {"version": manifest["annotation"]["version"], "review": copy.deepcopy(annotation["review"])},
        })
    return result


def load_benchmark_suite(path: str | Path) -> dict[str, Any]:
    return _load_json(Path(path))


def validate_benchmark_suite(suite: Mapping[str, Any], manifests_by_name: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not isinstance(suite, Mapping):
        return ["suite must be an object"]
    if suite.get("schema_version") != "external_security_benchmark_suite.v1" or suite.get("suite") != "owasp_crs_multi_family.v1":
        errors.append("invalid suite identity")
    components = suite.get("components")
    if not isinstance(components, list) or len(components) != 4:
        return errors + ["suite must have exactly four components"]
    component_cases: dict[str, set[str]] = {}
    seen_benchmarks: set[str] = set()
    for index, component in enumerate(components):
        if not isinstance(component, Mapping):
            errors.append(f"components[{index}] must be object")
            continue
        benchmark = component.get("benchmark")
        manifest_name = component.get("manifest")
        ids = component.get("case_ids")
        if not isinstance(benchmark, str) or benchmark in seen_benchmarks:
            errors.append(f"components[{index}] invalid or duplicate benchmark")
            continue
        seen_benchmarks.add(benchmark)
        manifest = manifests_by_name.get(benchmark)
        if manifest is None or not isinstance(manifest_name, str) or manifest_name != SUITE_MANIFEST_PATHS.get(benchmark):
            errors.append(f"components[{index}] unresolved manifest")
            continue
        manifest_ids = {case.get("case_id") for case in manifest.get("cases", []) if isinstance(case, Mapping)}
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or any(case_id not in manifest_ids for case_id in ids):
            errors.append(f"components[{index}] has duplicate or unknown case ID")
        component_cases[benchmark] = manifest_ids
    groups = suite.get("groups")
    if not isinstance(groups, Mapping):
        return errors + ["groups must be object"]
    resolved: dict[str, Mapping[str, Any]] = {}
    for benchmark, manifest in manifests_by_name.items():
        for case in manifest.get("cases", []):
            if isinstance(case, Mapping):
                resolved[case.get("case_id")] = case
    for name, ids in groups.items():
        if name == "exact_core":
            continue
        if not isinstance(name, str) or not isinstance(ids, list) or len(ids) != len(set(ids)):
            errors.append(f"group {name!r} must be unique string IDs")
        elif any(case_id not in resolved for case_id in ids):
            errors.append(f"group {name!r} contains unknown case")
    exact_core = groups.get("exact_core")
    if not isinstance(exact_core, Mapping):
        return errors + ["groups.exact_core must be object"]
    expected_classes = {
        "traversal": "suspicious_path_traversal",
        "cmdi": "suspicious_command_injection",
        "xss": "suspicious_xss",
        "sqli": "suspicious_sqli",
    }
    total = 0
    for group, verdict in expected_classes.items():
        ids = exact_core.get(group)
        if not isinstance(ids, list) or len(ids) != 9 or len(ids) != len(set(ids)):
            errors.append(f"exact_core.{group} must contain exactly nine unique cases")
            continue
        total += len(ids)
        for case_id in ids:
            case = resolved.get(case_id)
            expected = case.get("expected") if isinstance(case, Mapping) else None
            if not isinstance(expected, Mapping) or expected.get("project_ground_truth") != "attack_positive" or expected.get("classification_policy") != "exact" or expected.get("allowed_stage1_verdicts") != [verdict]:
                errors.append(f"exact_core.{group} contains non-exact {verdict} case {case_id}")
    if total != 36:
        errors.append("exact core total must be 36")
    return errors


def resolve_benchmark_suite(suite: Mapping[str, Any], manifests_by_name: Mapping[str, Mapping[str, Any]], normalized_cases_by_benchmark: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    errors = validate_benchmark_suite(suite, manifests_by_name)
    if errors:
        raise MultiFamilyBenchmarkContractError("suite invalid:\n- " + "\n- ".join(errors))
    case_lookup = {benchmark: {case["case_id"]: case for case in cases} for benchmark, cases in normalized_cases_by_benchmark.items()}
    resolved: list[dict[str, Any]] = []
    memberships: dict[str, list[str]] = defaultdict(list)
    for name, ids in suite["groups"].items():
        if isinstance(ids, list):
            for case_id in ids:
                memberships[case_id].append(name)
    for group, ids in suite["groups"]["exact_core"].items():
        for case_id in ids:
            memberships[case_id].append(f"exact_core.{group}")
    for component in suite["components"]:
        benchmark = component["benchmark"]
        for case_id in component["case_ids"]:
            case = case_lookup.get(benchmark, {}).get(case_id)
            if case is None:
                raise MultiFamilyBenchmarkContractError(f"normalized case missing for suite resolution: {benchmark}/{case_id}")
            value = copy.deepcopy(case)
            value["component_benchmark"] = benchmark
            value["suite_groups"] = sorted(memberships.get(case_id, []))
            resolved.append(value)
    return {"suite": suite["suite"], "cases": resolved}
