#!/usr/bin/env python3
"""Network-free controlled/replay Stage1 evaluator for canonical CSIC review.

This evaluator deliberately never imports or invokes the Stage1 classifier.
It reuses the CSIC raw parser, Apache projection, and isolated production
Prepare path solely to verify the reviewed-subset execution contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.external_benchmark_csic2010 import FILE_SPECS, RawHttpRequest, parse_raw_http_stream, scan_source_file
from src.external_benchmark_csic2010_prepare import evaluate_isolated_request, project_request
from src.security_standards_mapping import KNOWN_VERDICTS, build_security_standards_mapping


RESULT_SCHEMA_VERSION = "external_security_benchmark_csic2010_stage1_result.v1"
REPLAY_SCHEMA_VERSION = "external_security_benchmark_csic2010_stage1_replay.v1"
MODES = frozenset({"controlled", "replay"})
STRICT_FAMILIES = ("sqli", "xss", "command_injection", "path_traversal")
FAMILY_VERDICTS = {
    "sqli": "suspicious_sqli",
    "xss": "suspicious_xss",
    "command_injection": "suspicious_command_injection",
    "path_traversal": "suspicious_path_traversal",
}
MAPPING_REQUIRED = {
    "sqli": {"A05:2025", "CWE-89", "WSTG-INPV-05"},
    "xss": {"A05:2025", "CWE-79", "WSTG-INPV-01"},
    "command_injection": {"A05:2025", "CWE-78", "WSTG-INPV-12"},
    "path_traversal": {"A01:2025", "CWE-22", "WSTG-ATHZ-01"},
}
NEGATIVE_COMPATIBLE_VERDICTS = frozenset({"likely_false_positive"})


class CsicStage1ContractError(ValueError):
    """Raised when source, fidelity, or controlled/replay contracts fail."""


def identity(item: Mapping[str, Any]) -> tuple[str, int, str]:
    return (str(item["source_file"]), int(item["request_index"]), str(item["raw_request_sha256"]))


def _fraction(passed: int, total: int) -> dict[str, Any]:
    return {"passed": passed, "total": total, "rate": passed / total if total else None}


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CsicStage1ContractError(f"{path}: expected JSON object")
    return value


def load_canonical_manifest(path: Path, expected_sha256: str | None = None) -> dict[str, Any]:
    payload = _load_object(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise CsicStage1ContractError("reviewed manifest SHA-256 mismatch")
    if payload.get("schema_version") != "csic2010_reviewed_semantic_subset.v1" or not isinstance(payload.get("cases"), list):
        raise CsicStage1ContractError("invalid canonical reviewed manifest")
    cases = payload["cases"]
    if len(cases) != 222 or len({identity(case) for case in cases}) != 222:
        raise CsicStage1ContractError("canonical manifest must contain 222 unique identities")
    return payload | {"_sha256": digest}


def stage1_eligible(case: Mapping[str, Any]) -> bool:
    return (
        case.get("review_status") in {"validated_agreement", "adjudicated"}
        and case.get("project_semantic") == "project_attack_positive"
        and case.get("prepare_selected") is True
        and case.get("classification_policy") in {"exact", "compatible_set"}
        and case.get("reviewed_family") in STRICT_FAMILIES
    )


def exact_positive(case: Mapping[str, Any]) -> bool:
    return (
        case.get("review_status") in {"validated_agreement", "adjudicated"}
        and case.get("project_semantic") == "project_attack_positive"
        and case.get("classification_policy") == "exact"
        and case.get("reviewed_family") in STRICT_FAMILIES
    )


def negative_control(case: Mapping[str, Any]) -> bool:
    return case.get("review_status") in {"validated_agreement", "adjudicated"} and case.get("project_semantic") == "project_negative" and case.get("prepare_selected") is True


def eligibility_counts(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    selected = [case for case in cases if stage1_eligible(case) and case.get("classification_policy") == "exact"]
    full = [case for case in cases if exact_positive(case)]
    by_family = {family: {"selected_exact": sum(case.get("reviewed_family") == family for case in selected), "suppressed_exact": sum(case.get("reviewed_family") == family and not case.get("prepare_selected") for case in full)} for family in STRICT_FAMILIES}
    counts = {"selected_exact": len(selected), "full_exact": len(full), "negative_controls": sum(negative_control(case) for case in cases), "by_family": by_family}
    expected = {"sqli": (44, 2), "xss": (40, 0), "command_injection": (27, 0), "path_traversal": (0, 0)}
    if counts["selected_exact"] != 111 or counts["full_exact"] != 113 or counts["negative_controls"] != 2 or any((by_family[k]["selected_exact"], by_family[k]["suppressed_exact"]) != value for k, value in expected.items()):
        raise CsicStage1ContractError("frozen CSIC eligibility counts differ from 111/113/2 contract")
    return counts


def _source_gate(source_manifest: Mapping[str, Any], cache_dir: Path) -> list[dict[str, Any]]:
    locked = {item["filename"]: item for item in source_manifest["canonical_acquisition"]["files"]}
    facts = []
    for spec in FILE_SPECS:
        filename = str(spec["filename"])
        observed = scan_source_file(cache_dir / "primary" / filename, source_label=str(spec["source_label"]))
        expected = locked.get(filename, {})
        if (observed["sha256"], observed["byte_size"], observed["parsed_requests"], observed["parse_error_count"], observed["byte_consumption"]["unaccounted_bytes"]) != (expected.get("sha256"), expected.get("byte_size"), expected.get("parsed_request_count"), 0, 0):
            raise CsicStage1ContractError(f"frozen source gate failed for {filename}")
        facts.append({key: observed[key] for key in ("filename", "sha256", "byte_size", "parsed_requests") if key in observed} | {"filename": filename})
    return facts


def _rehydrate(cases: Sequence[Mapping[str, Any]], cache_dir: Path) -> dict[tuple[str, int, str], RawHttpRequest]:
    wanted = {identity(case) for case in cases}
    found: dict[tuple[str, int, str], RawHttpRequest] = {}
    for spec in FILE_SPECS:
        filename, label = str(spec["filename"]), str(spec["source_label"])
        path = cache_dir / "primary" / filename
        with path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
            def visit(request: RawHttpRequest) -> None:
                key = (filename, request.request_index, request.raw_request_sha256)
                if key in wanted:
                    found[key] = request
            parse_raw_http_stream(data, source_file=filename, source_label=label, on_request=visit)
    if set(found) != wanted:
        raise CsicStage1ContractError("canonical identity could not be rehydrated from frozen source")
    return found


def _frozen_prepare_index(path: Path) -> dict[tuple[str, int, str], dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    index = {identity(row): row for row in rows}
    if len(index) != len(rows):
        raise CsicStage1ContractError("frozen Prepare index has duplicate identities")
    return index


def _check_fidelity(cases: Sequence[Mapping[str, Any]], requests: Mapping[tuple[str, int, str], RawHttpRequest], frozen: Mapping[tuple[str, int, str], Mapping[str, Any]]) -> None:
    for case in cases:
        key, request = identity(case), requests[identity(case)]
        baseline = frozen.get(key)
        if baseline is None:
            raise CsicStage1ContractError("canonical identity missing from frozen Prepare index")
        if request.method != baseline.get("method") or request.raw_request_sha256 != baseline.get("raw_request_sha256") or bool(case.get("prepare_selected")) != bool(baseline.get("selected")):
            raise CsicStage1ContractError("canonical request/Prepare index fidelity mismatch")


def _regenerate(case: Mapping[str, Any], request: RawHttpRequest, frozen: Mapping[str, Any]) -> dict[str, Any]:
    actual = evaluate_isolated_request(request)
    keys = ("selected", "score", "verdict_hint", "reason_hints")
    if any(actual.get(key) != frozen.get(key) for key in keys) or bool(actual.get("selected")) != bool(case.get("prepare_selected")):
        raise CsicStage1ContractError("production Prepare regeneration fidelity failure")
    return actual


def _candidate(case_number: int, request: RawHttpRequest, prepare: Mapping[str, Any]) -> dict[str, Any]:
    row, _loss = project_request(request)
    # No source label, review state, family, policy, digest, or CSIC identity is
    # present in this classifier-facing shape.
    return {"request_id": f"stage1-candidate-{case_number:03d}", "method": row["method"], "uri": row["uri"], "query_string": row["query_string"], "raw_request_target": row["raw_request_target"], "req_content_type": row["req_content_type"], "req_content_length": row["req_content_length"], "verdict_hint": prepare.get("verdict_hint"), "reason_hints": list(prepare.get("reason_hints", []))}


def controlled_records(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for case in sorted(cases, key=identity):
        if stage1_eligible(case):
            verdict = FAMILY_VERDICTS[str(case["reviewed_family"])]
        elif negative_control(case):
            verdict = "likely_false_positive"
        else:
            continue
        records.append({"source_file": case["source_file"], "request_index": case["request_index"], "raw_request_sha256": case["raw_request_sha256"], "execution_status": "completed", "verdict": verdict, "confidence": 1.0, "reasoning": "controlled deterministic fixture", "evidence": []})
    return records


def load_replay(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict) or payload.get("schema_version") not in {None, REPLAY_SCHEMA_VERSION} or not isinstance(payload.get("records"), list):
        raise CsicStage1ContractError("invalid replay artifact")
    return payload["records"]


def _record_index(records: Sequence[Mapping[str, Any]], expected: set[tuple[str, int, str]]) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise CsicStage1ContractError("replay record must be an object")
        key = identity(record)
        if key not in expected:
            raise CsicStage1ContractError("replay record references unknown or ineligible identity")
        if key in indexed:
            raise CsicStage1ContractError("duplicate replay identity")
        if record.get("execution_status", "completed") != "completed" or record.get("verdict") not in KNOWN_VERDICTS or not isinstance(record.get("confidence"), (int, float)):
            raise CsicStage1ContractError("replay record needs completed known verdict and confidence")
        indexed[key] = record
    if set(indexed) != expected:
        raise CsicStage1ContractError("missing replay identity")
    return indexed


def _classification(case: Mapping[str, Any], verdict: str) -> dict[str, Any]:
    policy, allowed = case["classification_policy"], set(case.get("allowed_stage1_verdicts", []))
    if policy == "exact":
        return {"compatible": verdict in allowed and len(allowed) == 1, "result": "pass" if verdict in allowed and len(allowed) == 1 else "exact_verdict_mismatch"}
    if policy == "compatible_set":
        return {"compatible": verdict in allowed, "result": "pass" if verdict in allowed else "actual_verdict_not_in_compatible_set"}
    raise CsicStage1ContractError("positive Stage1 record has unsupported policy")


def _mapping(case: Mapping[str, Any], verdict: str, candidate: Mapping[str, Any]) -> dict[str, Any]:
    output = build_security_standards_mapping({"verdict": verdict}, candidate)
    actual = sorted({item.get("id") for item in output.get("items", []) if isinstance(item, Mapping) and isinstance(item.get("id"), str)})
    required = MAPPING_REQUIRED[str(case["reviewed_family"])]
    return {"result": "pass" if required <= set(actual) else "fail", "actual_ids": actual, "missing_required_ids": sorted(required - set(actual))}


def _matrix(rows: Sequence[Mapping[str, Any]], *, e2e: bool) -> dict[str, Any]:
    labels = [FAMILY_VERDICTS[family] for family in STRICT_FAMILIES]
    extras = sorted({row["prediction"] for row in rows} - set(labels), key=str)
    columns = labels + extras
    values = {label: {column: 0 for column in columns} for label in labels}
    for row in rows:
        values[row["expected"]][row["prediction"]] += 1
    return {"kind": "end_to_end" if e2e else "stage1_conditioned", "row_labels": labels, "column_labels": columns, "rows": values, "denominator": len(rows)}


def _git_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=Path(__file__).resolve().parents[1]).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def evaluate(canonical_path: Path, source_path: Path, cache_dir: Path, prepare_index_path: Path, *, mode: str, replay_records: Sequence[Mapping[str, Any]] | None = None, expected_reviewed_sha256: str | None = None) -> dict[str, Any]:
    if mode not in MODES:
        raise CsicStage1ContractError("mode must be controlled or replay; live is intentionally unavailable")
    canonical = load_canonical_manifest(canonical_path, expected_reviewed_sha256)
    cases = canonical["cases"]
    frozen_counts = eligibility_counts(cases)
    source = _load_object(source_path)
    source_facts = _source_gate(source, cache_dir)
    requests = _rehydrate(cases, cache_dir)
    frozen = _frozen_prepare_index(prepare_index_path)
    _check_fidelity(cases, requests, frozen)
    evaluated = [case for case in cases if exact_positive(case) or negative_control(case)]
    regenerated = {identity(case): _regenerate(case, requests[identity(case)], frozen[identity(case)]) for case in evaluated}
    selected_expected = {identity(case) for case in cases if stage1_eligible(case) or negative_control(case)}
    records = controlled_records(cases) if mode == "controlled" else list(replay_records or [])
    record_by_id = _record_index(records, selected_expected)

    result_records, stage_rows, e2e_rows = [], [], []
    candidate_counter = 0
    mapping_counts = Counter()
    negative_results = []
    for case in sorted(evaluated, key=identity):
        key, family = identity(case), case.get("reviewed_family")
        selected = bool(case["prepare_selected"])
        record: dict[str, Any] = {"source_file": key[0], "request_index": key[1], "raw_request_sha256": key[2], "review_status": case["review_status"], "reviewed_family": family, "classification_policy": case["classification_policy"], "prepare_selected": selected}
        if exact_positive(case) and not selected:
            record.update(actual_stage1_verdict="NOT_SELECTED", classification_result="NOT_SELECTED", mapping_result="not_scored_due_to_not_selected")
            e2e_rows.append({"expected": FAMILY_VERDICTS[str(family)], "prediction": "NOT_SELECTED"})
        else:
            candidate_counter += 1
            supplied = record_by_id[key]
            verdict = str(supplied["verdict"])
            record["actual_stage1_verdict"] = verdict
            if negative_control(case):
                compatible = verdict in NEGATIVE_COMPATIBLE_VERDICTS
                record.update(classification_result="pass" if compatible else "negative_control_incompatible", mapping_result="not_scored_negative_control")
                negative_results.append(compatible)
            else:
                candidate = _candidate(candidate_counter, requests[key], regenerated[key])
                classified = _classification(case, verdict)
                record["classification_result"] = classified["result"]
                expected = FAMILY_VERDICTS[str(family)]
                stage_rows.append({"expected": expected, "prediction": verdict})
                e2e_rows.append({"expected": expected, "prediction": verdict})
                if classified["compatible"]:
                    mapped = _mapping(case, verdict, candidate)
                    record["mapping_result"] = mapped["result"]
                    record["mapping_ids"] = mapped["actual_ids"]
                    mapping_counts[mapped["result"]] += 1
                else:
                    record["mapping_result"] = "not_scored_due_to_classification"
                    mapping_counts["not_scored_due_to_classification"] += 1
        result_records.append(record)
    stage_matrix, e2e_matrix = _matrix(stage_rows, e2e=False), _matrix(e2e_rows, e2e=True)
    compatible = sum(row["expected"] == row["prediction"] for row in stage_rows)
    e2e_compatible = sum(row["expected"] == row["prediction"] for row in e2e_rows)
    cross = sum(row["prediction"] in set(FAMILY_VERDICTS.values()) and row["prediction"] != row["expected"] for row in stage_rows)
    stage_by_family = {family: _fraction(sum(row["expected"] == row["prediction"] == FAMILY_VERDICTS[family] for row in stage_rows), sum(row["expected"] == FAMILY_VERDICTS[family] for row in stage_rows)) for family in STRICT_FAMILIES}
    e2e_by_family = {family: _fraction(sum(row["expected"] == row["prediction"] == FAMILY_VERDICTS[family] for row in e2e_rows), sum(row["expected"] == FAMILY_VERDICTS[family] for row in e2e_rows)) for family in STRICT_FAMILIES}
    complete = len(stage_rows) == 111 and len(e2e_rows) == 113 and len(negative_results) == 2 and all(negative_results) and compatible == 111 and mapping_counts["fail"] == 0
    return {
        "schema_version": RESULT_SCHEMA_VERSION, "mode": mode, "complete": complete, "git_revision": _git_revision(),
        "source_manifest": str(source_path), "reviewed_manifest": str(canonical_path), "reviewed_manifest_sha256": canonical["_sha256"],
        "eligibility": frozen_counts | {"provisional_unvalidated_excluded": 83, "ambiguous_excluded": 4, "not_scored_excluded": 10},
        "source_integrity": {"complete": True, "files": source_facts},
        "prepare_fidelity": {"complete": True, "canonical_identities_rehydrated": 222, "regenerated_cases": len(evaluated), "selected_state_matches": True},
        "stage1_accounting": {"expected": 111, "completed": len(stage_rows), "errors": 0, "not_selected_exact": 2},
        "classification": {"stage1_compatibility_given_reviewed_prepare_selected_case": _fraction(compatible, 111), "by_family": stage_by_family, "cross_family_confusion": cross, "matrix": stage_matrix},
        "e2e": {"reviewed_exact_compatibility": _fraction(e2e_compatible, 113), "by_family": e2e_by_family, "matrix": e2e_matrix},
        "negative_controls": {"metric_name": "reviewed_negative_control_compatibility", "policy": {"compatible_verdicts": sorted(NEGATIVE_COMPATIBLE_VERDICTS)}, "compatibility": _fraction(sum(negative_results), 2)},
        "mapping": {"metric_name": "mapping_consistency_among_classification_compatible_scored_positives", "passed": mapping_counts["pass"], "failed": mapping_counts["fail"], "not_scored_due_to_classification": mapping_counts["not_scored_due_to_classification"]},
        "records": result_records,
    }


def validate_result(result: Mapping[str, Any]) -> list[str]:
    errors = []
    required = {"schema_version", "mode", "complete", "git_revision", "source_manifest", "reviewed_manifest", "reviewed_manifest_sha256", "eligibility", "prepare_fidelity", "stage1_accounting", "classification", "e2e", "negative_controls", "mapping", "records"}
    if result.get("schema_version") != RESULT_SCHEMA_VERSION or not required <= set(result): errors.append("invalid result root")
    if result.get("mode") not in MODES: errors.append("invalid mode")
    if not isinstance(result.get("records"), list) or len(result.get("records", [])) != 115: errors.append("invalid record count")
    serialized = json.dumps(result, ensure_ascii=False)
    if any(token in serialized for token in ("body_for_observability_review", "request_line", "Cookie:", "Authorization:")): errors.append("raw content leaked")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CSIC reviewed Stage1 controlled/replay evaluator (network-free)")
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    parser.add_argument("--replay-input")
    parser.add_argument("--output", default="/tmp/csic2010_stage1_controlled.json")
    parser.add_argument("--cache-dir", type=Path, default=Path("benchmarks/cache/csic2010"))
    parser.add_argument("--source-manifest", type=Path, default=Path("benchmarks/manifests/csic2010_source.v1.json"))
    parser.add_argument("--reviewed-manifest", type=Path, default=Path("benchmarks/manifests/csic2010_reviewed_semantic_subset.v1.json"))
    parser.add_argument("--prepare-index", type=Path, default=Path("/tmp/csic2010_prepare_request_index.jsonl"))
    parser.add_argument("--reviewed-manifest-sha256", default="30c67e6d1ddeb6cb890cd1446ea0e2da87e4c61c3ff9144bee7c3596e6d846bf")
    args = parser.parse_args(argv)
    try:
        if args.mode == "controlled" and args.replay_input: raise CsicStage1ContractError("--replay-input is replay-only")
        if args.mode == "replay" and not args.replay_input: raise CsicStage1ContractError("--replay-input is required for replay")
        replay = load_replay(Path(args.replay_input)) if args.replay_input else None
        result = evaluate(args.reviewed_manifest, args.source_manifest, args.cache_dir, args.prepare_index, mode=args.mode, replay_records=replay, expected_reviewed_sha256=args.reviewed_manifest_sha256)
        errors = validate_result(result)
        if errors: raise CsicStage1ContractError("invalid result: " + "; ".join(errors))
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, CsicStage1ContractError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr); return 1
    print(f"[OK] output: {args.output}")
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
