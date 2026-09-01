"""Deterministic OWASP CRS source adapter and project-manifest contract.

This module preserves upstream source facts.  It deliberately does not infer a
project verdict from a CRS rule ID or from ``expect_ids``/``no_expect_ids``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from src.security_standards_mapping import KNOWN_VERDICTS, NON_SECURITY_VERDICTS


BENCHMARK_SOURCE = "owasp_crs"
PINNED_REVISION = "96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a"
PINNED_FILES = {
    "930100.yaml": {
        "rule_id": 930100,
        "upstream_path": "tests/regression/tests/REQUEST-930-APPLICATION-ATTACK-LFI/930100.yaml",
        "sha256": "ba821dc9e205e932da60af2f5e9a9afe69597e8d2a07820ed264aba4bd1baa10",
        "case_count": 5,
    },
    "930110.yaml": {
        "rule_id": 930110,
        "upstream_path": "tests/regression/tests/REQUEST-930-APPLICATION-ATTACK-LFI/930110.yaml",
        "sha256": "d53c1f718a044bf5773b9efa77fd7d01f6b0c94ef152d9398df2aeb2762329f8",
        "case_count": 13,
    },
    "930120.yaml": {
        "rule_id": 930120,
        "upstream_path": "tests/regression/tests/REQUEST-930-APPLICATION-ATTACK-LFI/930120.yaml",
        "sha256": "333adb7b8264897893d6ce58ee46f5c8ab7e44fbde5dbb21f933dc27589abdd3",
        "case_count": 18,
    },
}
EXPECTED_TOTAL_CASES = 36
MANIFEST_SCHEMA_VERSION = "external_security_benchmark_manifest.v1"
CASE_SCHEMA_VERSION = "external_security_benchmark_case.v1"

OBSERVABILITY_STATUSES = {"direct", "partial", "out_of_scope"}
EXCLUSION_REASONS = {
    "post_body_not_logged",
    "xml_body_not_logged",
    "multipart_body_not_logged",
    "multipart_filename_not_logged",
    "header_not_available",
    "apache_normalization_not_preserved",
    "unsupported_input_surface",
    "requires_response_body",
    "ambiguous_project_taxonomy",
}
GROUND_TRUTHS = {"attack_positive", "project_negative", "not_scored"}
CLASSIFICATION_POLICIES = {"exact", "compatible_set", "forbidden_only", "not_scored"}
BOUNDARY_TOKENS = {
    "request_pattern_only",
    "attempt_pattern_only_no_file_read_or_exploit_success",
    "no_file_read_success_inference",
    "no_command_execution_success_inference",
}


class BenchmarkContractError(ValueError):
    """Raised when pinned source or a checked-in manifest violates its contract."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkContractError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkContractError(f"JSON root must be an object: {path}")
    return value


def verify_owasp_crs_source_integrity(source_dir: str | Path) -> dict[str, Any]:
    """Validate pinned provenance and raw-byte checksums, returning metadata copy."""

    root = Path(source_dir)
    metadata = _load_json(root / "SOURCE.json")
    errors: list[str] = []

    if metadata.get("source") != BENCHMARK_SOURCE:
        errors.append(f"SOURCE.json source must be {BENCHMARK_SOURCE!r}")
    if metadata.get("repository") != "https://github.com/coreruleset/coreruleset":
        errors.append("SOURCE.json repository does not match the canonical upstream")
    if metadata.get("revision") != PINNED_REVISION:
        errors.append(f"SOURCE.json revision must be {PINNED_REVISION}")
    if metadata.get("retrieved_at") != "2026-09-01":
        errors.append("SOURCE.json retrieved_at must be 2026-09-01")
    if metadata.get("license") != "Apache-2.0":
        errors.append("SOURCE.json license must be Apache-2.0")

    license_path = root / "LICENSE"
    if not license_path.is_file() or license_path.stat().st_size == 0:
        errors.append("vendored upstream LICENSE is missing or empty")

    raw_files = metadata.get("files")
    if not isinstance(raw_files, list):
        errors.append("SOURCE.json files must be an array")
        raw_files = []

    indexed: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(raw_files):
        if not isinstance(item, Mapping):
            errors.append(f"SOURCE.json files[{index}] must be an object")
            continue
        name = item.get("name")
        if not isinstance(name, str):
            errors.append(f"SOURCE.json files[{index}].name must be a string")
            continue
        if name in indexed:
            errors.append(f"SOURCE.json has duplicate file metadata for {name}")
            continue
        indexed[name] = item

    expected_names = set(PINNED_FILES)
    if set(indexed) != expected_names:
        errors.append(
            "SOURCE.json file set mismatch: "
            f"expected={sorted(expected_names)!r}, actual={sorted(indexed)!r}"
        )

    for name, expected in PINNED_FILES.items():
        item = indexed.get(name)
        if item is None:
            continue
        if item.get("upstream_path") != expected["upstream_path"]:
            errors.append(f"{name}: upstream_path mismatch")
        if item.get("sha256") != expected["sha256"]:
            errors.append(f"{name}: metadata SHA-256 differs from pinned checksum")
        path = root / name
        if not path.is_file():
            errors.append(f"{name}: vendored source file is missing")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected["sha256"]:
            errors.append(f"{name}: raw SHA-256 mismatch: expected={expected['sha256']}, actual={actual}")

    if errors:
        raise BenchmarkContractError("OWASP CRS source integrity failure:\n- " + "\n- ".join(errors))
    return copy.deepcopy(metadata)


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BenchmarkContractError(f"{label} must be an integer")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise BenchmarkContractError(f"{label} must be a string")
    return value


def _normalize_expectation(log: Mapping[str, Any], label: str) -> dict[str, Any]:
    present = [key for key in ("expect_ids", "no_expect_ids") if key in log]
    if len(present) != 1:
        raise BenchmarkContractError(
            f"{label} must contain exactly one of expect_ids or no_expect_ids"
        )
    key = present[0]
    raw_ids = log[key]
    if not isinstance(raw_ids, list) or not raw_ids:
        raise BenchmarkContractError(f"{label}.{key} must be a non-empty integer array")
    ids = [_require_int(value, f"{label}.{key}") for value in raw_ids]
    if len(ids) != len(set(ids)):
        raise BenchmarkContractError(f"{label}.{key} contains duplicate IDs")
    return {"kind": key, "ids": ids}


def _load_source_file(path: Path, revision: str) -> list[dict[str, Any]]:
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise BenchmarkContractError(f"cannot parse YAML source {path}: {exc}") from exc
    documents = [document for document in documents if document is not None]
    if len(documents) != 1 or not isinstance(documents[0], Mapping):
        raise BenchmarkContractError(f"{path.name} must contain exactly one YAML mapping document")

    document = documents[0]
    rule_id = _require_int(document.get("rule_id"), f"{path.name}.rule_id")
    expected_rule = PINNED_FILES[path.name]["rule_id"]
    if rule_id != expected_rule or path.stem != str(rule_id):
        raise BenchmarkContractError(f"{path.name}: rule_id/file-name mismatch")
    tests = document.get("tests")
    if not isinstance(tests, list):
        raise BenchmarkContractError(f"{path.name}.tests must be an array")

    cases: list[dict[str, Any]] = []
    for index, test in enumerate(tests):
        label = f"{path.name}.tests[{index}]"
        if not isinstance(test, Mapping):
            raise BenchmarkContractError(f"{label} must be an object")
        test_id = _require_int(test.get("test_id"), f"{label}.test_id")
        description = _require_string(test.get("desc"), f"{label}.desc")
        stages = test.get("stages")
        if not isinstance(stages, list) or len(stages) != 1:
            count = len(stages) if isinstance(stages, list) else "non-array"
            raise BenchmarkContractError(
                f"{label}.stages must contain exactly one stage for this pinned adapter; got {count}"
            )
        stage = stages[0]
        if not isinstance(stage, Mapping):
            raise BenchmarkContractError(f"{label}.stages[0] must be an object")
        input_value = stage.get("input")
        output_value = stage.get("output")
        if not isinstance(input_value, Mapping) or not isinstance(output_value, Mapping):
            raise BenchmarkContractError(f"{label}.stages[0] input/output must be objects")
        log = output_value.get("log")
        if not isinstance(log, Mapping):
            raise BenchmarkContractError(f"{label}.stages[0].output.log must be an object")

        raw_headers = input_value.get("headers", {})
        if not isinstance(raw_headers, Mapping):
            raise BenchmarkContractError(f"{label}.headers must be an object")
        headers: dict[str, str] = {}
        for key, value in raw_headers.items():
            header_name = _require_string(key, f"{label}.header name")
            headers[header_name] = _require_string(value, f"{label}.headers[{header_name!r}]")

        data = input_value.get("data")
        if data is not None and not isinstance(data, str):
            raise BenchmarkContractError(f"{label}.input.data must be a string when present")
        body = None if data is None else {"present": True, "text": data}
        source_expectation = _normalize_expectation(log, f"{label}.output.log")
        if source_expectation["ids"] != [rule_id]:
            raise BenchmarkContractError(
                f"{label}.output.log IDs must exactly match source rule_id {rule_id}"
            )
        case_id = f"{BENCHMARK_SOURCE}.{rule_id}.{test_id}"
        cases.append(
            {
                "case_id": case_id,
                "benchmark_source": BENCHMARK_SOURCE,
                "source_revision": revision,
                "source_rule_id": rule_id,
                "source_test_id": test_id,
                "description": description,
                "request": {
                    "method": _require_string(input_value.get("method"), f"{label}.input.method"),
                    "request_target": _require_string(input_value.get("uri"), f"{label}.input.uri"),
                    "http_version": _require_string(input_value.get("version"), f"{label}.input.version"),
                    "headers": headers,
                    "body": body,
                },
                "source_expectation": source_expectation,
            }
        )
    return cases


def load_owasp_crs_cases(source_dir: str | Path) -> list[dict[str, Any]]:
    """Load all pinned tests as source-only facts in stable numeric order."""

    root = Path(source_dir)
    metadata = verify_owasp_crs_source_integrity(root)
    revision = metadata["revision"]
    cases: list[dict[str, Any]] = []
    for name in sorted(PINNED_FILES, key=lambda value: int(Path(value).stem)):
        cases.extend(_load_source_file(root / name, revision))
    cases.sort(key=lambda case: (case["source_rule_id"], case["source_test_id"]))

    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise BenchmarkContractError("source case IDs are not unique")
    actual_counts = Counter(case["source_rule_id"] for case in cases)
    expected_counts = {
        value["rule_id"]: value["case_count"] for value in PINNED_FILES.values()
    }
    if dict(actual_counts) != expected_counts or len(cases) != EXPECTED_TOTAL_CASES:
        raise BenchmarkContractError(
            f"source inventory mismatch: expected={expected_counts}, actual={dict(actual_counts)}"
        )
    return cases


def _string_list_errors(value: Any, label: str, *, allow_empty: bool = True) -> tuple[list[str], list[str]]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return [], [f"{label} must be an array of non-empty strings"]
    errors: list[str] = []
    if not allow_empty and not value:
        errors.append(f"{label} must not be empty")
    if len(value) != len(set(value)):
        errors.append(f"{label} must not contain duplicates")
    return list(value), errors


def validate_benchmark_manifest(
    manifest: Mapping[str, Any], source_cases: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Return deterministic validation errors without mutating either input."""

    errors: list[str] = []
    if not isinstance(manifest, Mapping):
        return ["manifest root must be an object"]
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if manifest.get("benchmark") != "owasp_crs_path_file_access.v1":
        errors.append("benchmark must be owasp_crs_path_file_access.v1")

    source_root = manifest.get("source")
    if not isinstance(source_root, Mapping):
        errors.append("source must be an object")
        source_root = {}
    if source_root.get("benchmark_source") != BENCHMARK_SOURCE:
        errors.append(f"source.benchmark_source must be {BENCHMARK_SOURCE}")
    revisions = {
        case.get("source_revision") for case in source_cases if isinstance(case, Mapping)
    }
    if len(revisions) != 1 or source_root.get("revision") not in revisions:
        errors.append("manifest source revision must exactly match all adapted source cases")

    annotation_root = manifest.get("annotation")
    if not isinstance(annotation_root, Mapping) or annotation_root.get("version") != "owasp_crs_path_file_access.v1":
        errors.append("annotation.version must be owasp_crs_path_file_access.v1")

    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list):
        return errors + ["cases must be an array"]
    source_ids = [case.get("case_id") for case in source_cases if isinstance(case, Mapping)]
    manifest_ids = [case.get("case_id") if isinstance(case, Mapping) else None for case in raw_cases]
    duplicate_ids = sorted(
        str(case_id) for case_id, count in Counter(manifest_ids).items() if count > 1
    )
    if duplicate_ids:
        errors.append(f"duplicate manifest case_id values: {duplicate_ids!r}")
    missing = sorted(set(source_ids) - set(manifest_ids))
    unknown = sorted(str(value) for value in set(manifest_ids) - set(source_ids))
    if missing:
        errors.append(f"manifest is missing source cases: {missing!r}")
    if unknown:
        errors.append(f"manifest contains unknown cases: {unknown!r}")

    for index, case in enumerate(raw_cases):
        label = f"cases[{index}]"
        if not isinstance(case, Mapping):
            errors.append(f"{label} must be an object")
            continue
        case_id = case.get("case_id")
        label = str(case_id) if isinstance(case_id, str) else label
        observability = case.get("observability")
        expected = case.get("expected")
        review = case.get("review")
        if not isinstance(observability, Mapping):
            errors.append(f"{label}.observability must be an object")
            continue
        if not isinstance(expected, Mapping):
            errors.append(f"{label}.expected must be an object")
            continue

        status = observability.get("status")
        eligible = observability.get("eligible")
        reason = observability.get("exclusion_reason")
        if status not in OBSERVABILITY_STATUSES:
            errors.append(f"{label}: invalid observability status {status!r}")
        if not isinstance(eligible, bool):
            errors.append(f"{label}: observability.eligible must be boolean")
        elif eligible != (status == "direct"):
            errors.append(f"{label}: eligible must be true iff status is direct")
        if status == "direct" and reason is not None:
            errors.append(f"{label}: direct case exclusion_reason must be null")
        if status in {"partial", "out_of_scope"} and reason not in EXCLUSION_REASONS:
            errors.append(f"{label}: non-direct case needs a stable exclusion_reason")
        _, value_errors = _string_list_errors(
            observability.get("required_capabilities"),
            f"{label}.observability.required_capabilities",
        )
        errors.extend(value_errors)
        if not isinstance(observability.get("surface"), str) or not observability.get("surface"):
            errors.append(f"{label}: observability.surface must be a non-empty string")

        ground_truth = expected.get("project_ground_truth")
        policy = expected.get("classification_policy")
        candidate_expected = expected.get("candidate_expected")
        if ground_truth not in GROUND_TRUTHS:
            errors.append(f"{label}: invalid project_ground_truth {ground_truth!r}")
        if policy not in CLASSIFICATION_POLICIES:
            errors.append(f"{label}: invalid classification_policy {policy!r}")
        allowed, allowed_errors = _string_list_errors(
            expected.get("allowed_stage1_verdicts"), f"{label}.allowed_stage1_verdicts"
        )
        forbidden, forbidden_errors = _string_list_errors(
            expected.get("forbidden_stage1_verdicts"), f"{label}.forbidden_stage1_verdicts"
        )
        errors.extend(allowed_errors + forbidden_errors)
        unknown_verdicts = sorted((set(allowed) | set(forbidden)) - KNOWN_VERDICTS)
        if unknown_verdicts:
            errors.append(f"{label}: unknown Stage1 verdicts {unknown_verdicts!r}")
        overlap = sorted(set(allowed) & set(forbidden))
        if overlap:
            errors.append(f"{label}: allowed/forbidden verdicts overlap: {overlap!r}")

        if policy == "exact":
            if ground_truth == "not_scored" or len(allowed) != 1:
                errors.append(f"{label}: exact policy requires one allowed verdict and scored ground truth")
        elif policy == "compatible_set":
            if ground_truth != "attack_positive" or not allowed:
                errors.append(f"{label}: compatible_set requires attack_positive and allowed verdicts")
        elif policy == "forbidden_only":
            if ground_truth != "project_negative" or not forbidden:
                errors.append(f"{label}: forbidden_only requires project_negative and forbidden verdicts")
            if not set(allowed).issubset(NON_SECURITY_VERDICTS):
                errors.append(f"{label}: forbidden_only allowed verdicts must be non-security verdicts")
        elif policy == "not_scored":
            if ground_truth != "not_scored" or candidate_expected is not None:
                errors.append(f"{label}: not_scored requires not_scored ground truth and null candidate_expected")
            if allowed or forbidden:
                errors.append(f"{label}: not_scored verdict lists must be empty")

        if ground_truth == "project_negative" and policy != "forbidden_only":
            errors.append(f"{label}: project_negative must use forbidden_only")
        if ground_truth == "not_scored" and policy != "not_scored":
            errors.append(f"{label}: not_scored ground truth must use not_scored policy")
        if ground_truth != "not_scored" and not isinstance(candidate_expected, bool):
            errors.append(f"{label}: scored candidate_expected must be boolean")
        if status != "direct" and ground_truth != "not_scored":
            errors.append(f"{label}: non-direct case must be not_scored")
        if status == "direct" and ground_truth == "not_scored":
            errors.append(f"{label}: frozen direct case must be scored")

        mappings = expected.get("mapping_by_verdict")
        if not isinstance(mappings, Mapping):
            errors.append(f"{label}: mapping_by_verdict must be an object")
            mappings = {}
        if policy == "not_scored" and mappings:
            errors.append(f"{label}: not_scored mapping_by_verdict must be empty")
        mapping_keys = set(mappings)
        if any(not isinstance(key, str) for key in mapping_keys):
            errors.append(f"{label}: mapping_by_verdict keys must be strings")
        unexpected_keys = sorted(str(key) for key in mapping_keys - set(allowed))
        if unexpected_keys:
            errors.append(f"{label}: mapping keys are not allowed verdicts: {unexpected_keys!r}")
        for verdict, contract in mappings.items():
            mapping_label = f"{label}.mapping_by_verdict[{verdict!r}]"
            if not isinstance(contract, Mapping):
                errors.append(f"{mapping_label} must be an object")
                continue
            required, required_errors = _string_list_errors(
                contract.get("required_ids"), f"{mapping_label}.required_ids"
            )
            forbidden_ids, mapping_forbidden_errors = _string_list_errors(
                contract.get("forbidden_ids"), f"{mapping_label}.forbidden_ids"
            )
            errors.extend(required_errors + mapping_forbidden_errors)
            id_overlap = sorted(set(required) & set(forbidden_ids))
            if id_overlap:
                errors.append(f"{mapping_label}: required/forbidden IDs overlap: {id_overlap!r}")

        if expected.get("boundary") not in BOUNDARY_TOKENS:
            errors.append(f"{label}: expected.boundary must be a known stable token")
        if not isinstance(review, Mapping) or review.get("status") != "approved":
            errors.append(f"{label}: review.status must be approved in the frozen manifest")
        elif not isinstance(review.get("note"), str):
            errors.append(f"{label}: review.note must be a string")
    return errors


def load_benchmark_manifest(path: str | Path) -> dict[str, Any]:
    """Load a manifest JSON object.  Semantic validation requires source cases."""

    return _load_json(Path(path))


def build_normalized_benchmark_cases(
    source_cases: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Join source facts with annotations without allowing annotation overwrite."""

    errors = validate_benchmark_manifest(manifest, source_cases)
    if errors:
        raise BenchmarkContractError("invalid benchmark manifest:\n- " + "\n- ".join(errors))
    annotation_version = manifest["annotation"]["version"]
    annotations = {case["case_id"]: case for case in manifest["cases"]}
    joined: list[dict[str, Any]] = []
    for source_case in sorted(
        source_cases,
        key=lambda case: (case["source_rule_id"], case["source_test_id"]),
    ):
        annotation = annotations[source_case["case_id"]]
        joined.append(
            {
                "schema_version": CASE_SCHEMA_VERSION,
                "case_id": source_case["case_id"],
                "source": {
                    "benchmark": source_case["benchmark_source"],
                    "revision": source_case["source_revision"],
                    "rule_id": source_case["source_rule_id"],
                    "test_id": source_case["source_test_id"],
                    "description": copy.deepcopy(source_case["description"]),
                    "expectation": copy.deepcopy(source_case["source_expectation"]),
                },
                "request": copy.deepcopy(source_case["request"]),
                "observability": copy.deepcopy(annotation["observability"]),
                "expected": copy.deepcopy(annotation["expected"]),
                "annotation": {
                    "version": annotation_version,
                    "review": copy.deepcopy(annotation["review"]),
                },
            }
        )
    return joined
