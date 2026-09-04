#!/usr/bin/env python3
"""Pure Stage1 evaluator for the reviewed OWASP CRS multi-family suite.

There is deliberately no provider, credential, or classifier invocation in
this module.  It consumes normalized records produced elsewhere (or the
deterministic controlled fixture) and evaluates them against the frozen suite,
Prepare observation, and production standards mapper.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.external_benchmark_crs_multifamily import PINNED_REVISION
from src.external_benchmark_prepare import benchmark_request_id
from src.external_benchmark_prepare_multifamily import (
    SUITE_NAME,
    load_resolved_suite,
    validate_multifamily_prepare_result,
)
from src.security_standards_mapping import KNOWN_VERDICTS, build_security_standards_mapping

RESULT_SCHEMA_VERSION = "external_security_benchmark_multifamily_stage1_result.v1"
REPLAY_SCHEMA_VERSION = "external_security_benchmark_multifamily_stage1_replay.v1"
# ``live`` still consumes the same normalized-record contract.  Provider
# orchestration deliberately remains in external_benchmark_stage1_multifamily_live.
EXECUTION_MODES = frozenset({"controlled", "replay", "live"})
EXACT_LABELS = (
    "suspicious_path_traversal",
    "suspicious_command_injection",
    "suspicious_xss",
    "suspicious_sqli",
)
GROUP_TO_LABEL = dict(zip(("traversal", "cmdi", "xss", "sqli"), EXACT_LABELS))
ERROR_STATUSES = frozenset({"stage1_api_error", "stage1_parse_error", "stage1_validation_error", "stage1_runtime_error"})
CLASSIFICATION_POLICIES = frozenset({"exact", "compatible_set", "forbidden_only", "not_scored"})


class MultiFamilyStage1ContractError(ValueError):
    """A normalized evaluator input violates the controlled/replay contract."""


def _fraction(passed: int, total: int, complete: bool = True) -> dict[str, Any]:
    return {"passed": passed, "total": total, "rate": passed / total if total and complete else None}


def _case_key(case: Mapping[str, Any]) -> tuple[int, int, str]:
    source = case.get("source") if isinstance(case.get("source"), Mapping) else {}
    return (int(source.get("rule_id", 0)), int(source.get("test_id", 0)), str(case.get("case_id", "")))


def _direct(case: Mapping[str, Any]) -> bool:
    obs = case.get("observability", {})
    return isinstance(obs, Mapping) and obs.get("eligible") is True and obs.get("status") == "direct"


def _raw_request_target(case: Mapping[str, Any]) -> Any:
    """Read the normalized legacy or family-joined request target."""

    request = case.get("request")
    if isinstance(request, Mapping):
        return request.get("request_target")
    source = case.get("source")
    if isinstance(source, Mapping) and isinstance(source.get("request"), Mapping):
        return source["request"].get("request_target")
    return None


def _validate_case_contract(case: Mapping[str, Any]) -> None:
    """Validate the evaluator-relevant, manifest-owned part of one case.

    The suite loader validates its own schema, but this evaluator must not turn
    a malformed policy into a score.  In particular, exact-core class labels
    are derived from the suite, never from a provider record.
    """

    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise MultiFamilyStage1ContractError("resolved case needs a non-empty case_id")
    expected = case.get("expected")
    if not isinstance(expected, Mapping):
        raise MultiFamilyStage1ContractError(f"{case_id}: expected must be an object")
    policy = expected.get("classification_policy")
    allowed = expected.get("allowed_stage1_verdicts")
    forbidden = expected.get("forbidden_stage1_verdicts")
    if policy not in CLASSIFICATION_POLICIES:
        raise MultiFamilyStage1ContractError(f"{case_id}: unsupported classification policy: {policy!r}")
    if not isinstance(allowed, list) or not all(isinstance(value, str) for value in allowed):
        raise MultiFamilyStage1ContractError(f"{case_id}: allowed_stage1_verdicts must be a string array")
    if not isinstance(forbidden, list) or not all(isinstance(value, str) for value in forbidden):
        raise MultiFamilyStage1ContractError(f"{case_id}: forbidden_stage1_verdicts must be a string array")
    if len(allowed) != len(set(allowed)) or len(forbidden) != len(set(forbidden)):
        raise MultiFamilyStage1ContractError(f"{case_id}: Stage1 verdict lists must be unique")
    if set(allowed) & set(forbidden):
        raise MultiFamilyStage1ContractError(f"{case_id}: allowed and forbidden Stage1 verdicts overlap")
    unknown = sorted((set(allowed) | set(forbidden)) - KNOWN_VERDICTS)
    if unknown:
        raise MultiFamilyStage1ContractError(f"{case_id}: unknown Stage1 verdicts: {unknown!r}")
    if policy == "exact" and len(allowed) != 1:
        raise MultiFamilyStage1ContractError(f"{case_id}: exact policy requires one allowed verdict")
    if policy == "compatible_set" and not allowed:
        raise MultiFamilyStage1ContractError(f"{case_id}: compatible_set policy requires allowed verdicts")
    # Frozen 930 negative controls retain informative allowed benign verdicts,
    # but forbidden_only scoring is intentionally governed only by its
    # forbidden set.
    if policy == "forbidden_only" and not forbidden:
        raise MultiFamilyStage1ContractError(f"{case_id}: forbidden_only policy requires at least one forbidden verdict")
    if policy == "not_scored" and (allowed or forbidden):
        raise MultiFamilyStage1ContractError(f"{case_id}: not_scored policy requires empty verdict lists")
    mappings = expected.get("mapping_by_verdict")
    if not isinstance(mappings, Mapping) or any(key not in allowed for key in mappings):
        raise MultiFamilyStage1ContractError(f"{case_id}: invalid mapping_by_verdict contract")
    for verdict, contract in mappings.items():
        if not isinstance(contract, Mapping):
            raise MultiFamilyStage1ContractError(f"{case_id}: mapping contract for {verdict} must be an object")
        required, forbidden_ids = contract.get("required_ids"), contract.get("forbidden_ids")
        if not isinstance(required, list) or not all(isinstance(value, str) for value in required):
            raise MultiFamilyStage1ContractError(f"{case_id}: mapping required_ids must be a string array")
        if not isinstance(forbidden_ids, list) or not all(isinstance(value, str) for value in forbidden_ids):
            raise MultiFamilyStage1ContractError(f"{case_id}: mapping forbidden_ids must be a string array")
        if set(required) & set(forbidden_ids):
            raise MultiFamilyStage1ContractError(f"{case_id}: mapping required and forbidden IDs overlap")


def _exact_core_labels(resolved_suite: Mapping[str, Any], cases: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """Return the fixed-order exact-core rows after checking their invariants."""

    suite = resolved_suite.get("suite_manifest")
    groups = suite.get("groups") if isinstance(suite, Mapping) else None
    exact_core = groups.get("exact_core") if isinstance(groups, Mapping) else None
    if not isinstance(exact_core, Mapping) or set(exact_core) != set(GROUP_TO_LABEL):
        raise MultiFamilyStage1ContractError("suite exact_core must contain traversal, cmdi, xss, and sqli")
    labels: dict[str, str] = {}
    for group, label in GROUP_TO_LABEL.items():
        ids = exact_core.get(group)
        if not isinstance(ids, list):
            raise MultiFamilyStage1ContractError(f"suite exact_core.{group} must be an array")
        for case_id in ids:
            if not isinstance(case_id, str) or case_id in labels or case_id not in cases:
                raise MultiFamilyStage1ContractError("suite exact_core case IDs must be known and unique")
            case, expected = cases[case_id], cases[case_id].get("expected", {})
            if (not _direct(case) or expected.get("project_ground_truth") != "attack_positive"
                    or expected.get("classification_policy") != "exact"
                    or expected.get("allowed_stage1_verdicts") != [label]):
                raise MultiFamilyStage1ContractError(f"{case_id}: exact_core membership does not match its strict class contract")
            labels[case_id] = label
    return labels


def _validate_prepare_case_fidelity(cases: Mapping[str, Mapping[str, Any]], prepares: Mapping[str, Mapping[str, Any]]) -> None:
    """Ensure the saved Prepare observation belongs to the resolved request."""

    for case_id, case in cases.items():
        prepare = prepares[case_id]
        actual = prepare.get("actual")
        if not isinstance(actual, Mapping):
            raise MultiFamilyStage1ContractError(f"{case_id}: Prepare actual must be an object")
        if not _direct(case):
            if actual.get("candidate_selected") is not None:
                raise MultiFamilyStage1ContractError(f"{case_id}: not-scored case has a Prepare candidate state")
            continue
        expected_request_id = benchmark_request_id(case_id)
        target = _raw_request_target(case)
        if actual.get("request_id") != expected_request_id:
            raise MultiFamilyStage1ContractError(f"{case_id}: Prepare request ID mismatch")
        if actual.get("raw_request_target") != target:
            raise MultiFamilyStage1ContractError(f"{case_id}: Prepare raw request target mismatch")
        if actual.get("candidate_selected") is not True and actual.get("candidate_selected") is not False:
            raise MultiFamilyStage1ContractError(f"{case_id}: Prepare candidate_selected must be boolean")


def _policy(expected: Mapping[str, Any], verdict: str) -> dict[str, Any]:
    policy = expected.get("classification_policy")
    allowed = expected.get("allowed_stage1_verdicts", [])
    forbidden = expected.get("forbidden_stage1_verdicts", [])
    if verdict in forbidden:
        return {"policy": policy, "compatible": False, "result": "actual_verdict_forbidden"}
    if policy == "exact":
        ok = len(allowed) == 1 and verdict == allowed[0]
        return {"policy": policy, "compatible": ok, "result": "pass" if ok else "exact_verdict_mismatch"}
    if policy == "compatible_set":
        ok = verdict in allowed
        return {"policy": policy, "compatible": ok, "result": "pass" if ok else "actual_verdict_not_in_compatible_set"}
    if policy == "forbidden_only":
        return {"policy": policy, "compatible": True, "result": "pass"}
    if policy == "not_scored":
        return {"policy": policy, "compatible": None, "result": "not_scored_observability"}
    raise MultiFamilyStage1ContractError(f"unsupported classification policy: {policy!r}")


def _ids(mapping: Mapping[str, Any]) -> list[str]:
    items = mapping.get("items", [])
    if not isinstance(items, list):
        raise MultiFamilyStage1ContractError("standards mapping items must be an array")
    return sorted({item["id"] for item in items if isinstance(item, Mapping) and isinstance(item.get("id"), str)})


def _mapping_result(expected: Mapping[str, Any], verdict: str, mapping: Mapping[str, Any]) -> dict[str, Any]:
    actual_ids = _ids(mapping)
    contract = expected.get("mapping_by_verdict", {}).get(verdict)
    if not isinstance(contract, Mapping):
        return {"execution_status": "not_scored_no_mapping_contract", "actual_ids": actual_ids, "result": "not_scored_no_mapping_contract"}
    required, forbidden = set(contract.get("required_ids", [])), set(contract.get("forbidden_ids", []))
    missing, present = sorted(required - set(actual_ids)), sorted(forbidden & set(actual_ids))
    return {"execution_status": "completed", "actual_ids": actual_ids, "missing_required_ids": missing, "present_forbidden_ids": present, "result": "pass" if not missing and not present else "fail"}


def _candidate(case: Mapping[str, Any], prepare: Mapping[str, Any]) -> dict[str, Any]:
    actual = prepare["actual"]
    target = actual.get("raw_request_target") or case.get("request", {}).get("request_target")
    return {"request_id": benchmark_request_id(case["case_id"]), "raw_request_target": target,
            "verdict_hint": actual.get("prepare_verdict_hint"), "reason_hints": copy.deepcopy(actual.get("prepare_reason_hints", [])), "score": actual.get("candidate_score")}


def _record_index(records: Sequence[Mapping[str, Any]], cases: Mapping[str, Mapping[str, Any]], prepares: Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise MultiFamilyStage1ContractError("stage1 records must be an array")
    index: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping): raise MultiFamilyStage1ContractError("stage1 record must be an object")
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or case_id not in cases: raise MultiFamilyStage1ContractError("Stage1 record references unknown case")
        if case_id in index: raise MultiFamilyStage1ContractError(f"duplicate Stage1 record: {case_id}")
        case, prep = cases[case_id], prepares[case_id]
        if not _direct(case) or prep["actual"].get("candidate_selected") is not True:
            raise MultiFamilyStage1ContractError(f"unexpected_stage1_result: {case_id}")
        candidate = _candidate(case, prep)
        if record.get("request_id") != candidate["request_id"]:
            raise MultiFamilyStage1ContractError(f"{case_id}: request ID mismatch")
        candidate_input = record.get("candidate_input")
        if candidate_input is not None:
            if not isinstance(candidate_input, Mapping): raise MultiFamilyStage1ContractError(f"{case_id}: candidate_input must be object")
            bad = [key for key in candidate if candidate_input.get(key) != candidate[key]]
            if bad: raise MultiFamilyStage1ContractError(f"{case_id}: candidate input fidelity mismatch: {bad!r}")
        status = record.get("execution_status")
        if status not in {"completed", *ERROR_STATUSES}: raise MultiFamilyStage1ContractError(f"{case_id}: invalid execution_status")
        if status == "completed":
            verdict = record.get("verdict")
            if verdict is None and isinstance(record.get("stage1"), Mapping): verdict = record["stage1"].get("verdict")
            if verdict not in KNOWN_VERDICTS: raise MultiFamilyStage1ContractError(f"{case_id}: invalid completed verdict")
        index[case_id] = copy.deepcopy(dict(record))
    return index


def _record_stage1(record: Mapping[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(dict(record.get("stage1", {}))) if isinstance(record.get("stage1"), Mapping) else {}
    for key in ("verdict", "severity", "confidence", "reasoning", "evidence"):
        if key in record and key not in row: row[key] = copy.deepcopy(record[key])
    row["execution_status"] = "completed"
    return row


def _matrix(rows: Sequence[Mapping[str, Any]], *, e2e: bool) -> dict[str, Any]:
    observed = {row["prediction"] for row in rows}
    extras = sorted(observed - set(EXACT_LABELS), key=lambda x: (x not in {"NOT_SELECTED", "STAGE1_ERROR"}, x))
    columns = list(EXACT_LABELS) + extras
    values = {label: {column: 0 for column in columns} for label in EXACT_LABELS}
    for row in rows: values[row["expected"]][row["prediction"]] += 1
    return {"row_labels": list(EXACT_LABELS), "column_labels": columns, "rows": values,
            "denominator": len(rows), "kind": "end_to_end" if e2e else "stage1_conditioned"}


def _prf(matrix: Mapping[str, Any]) -> dict[str, Any]:
    rows, columns = matrix["rows"], matrix["column_labels"]
    per: dict[str, Any] = {}
    for label in EXACT_LABELS:
        support = sum(rows[label].values())
        tp = rows[label].get(label, 0)
        fp = sum(rows[other].get(label, 0) for other in EXACT_LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / support if support else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
        per[label] = {"tp": tp, "fp": fp, "fn": support - tp, "support": support, "precision": precision, "recall": recall, "f1": f1}
    def macro(key: str) -> float | None:
        values = [per[label][key] for label in EXACT_LABELS if per[label][key] is not None]
        return sum(values) / len(values) if values else None
    return {"per_class": per, "macro": {"precision": macro("precision"), "recall": macro("recall"), "f1": macro("f1")}}


def _unavailable_prf(prf: Mapping[str, Any]) -> dict[str, Any]:
    """Retain diagnostic counts but never publish partial-run score rates."""
    out = copy.deepcopy(dict(prf))
    for values in out.get("per_class", {}).values():
        if isinstance(values, Mapping):
            for name in ("precision", "recall", "f1"):
                values[name] = None
    if isinstance(out.get("macro"), Mapping):
        for name in ("precision", "recall", "f1"):
            out["macro"][name] = None
    return out


def controlled_records(resolved_suite: Mapping[str, Any], prepare_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Create deterministic approved-verdict records; this is not model output."""
    prepares = {x["case_id"]: x for x in prepare_result["cases"]}
    records = []
    for case in sorted(resolved_suite["cases"], key=_case_key):
        prep = prepares[case["case_id"]]
        if not _direct(case) or prep["actual"].get("candidate_selected") is not True: continue
        expected = case["expected"]
        allowed = expected.get("allowed_stage1_verdicts", [])
        if expected.get("classification_policy") == "forbidden_only": verdict = "likely_false_positive"
        elif allowed: verdict = sorted(allowed)[0]
        else: continue
        candidate = _candidate(case, prep)
        records.append({"case_id": case["case_id"], "request_id": candidate["request_id"], "candidate_input": candidate,
                        "execution_status": "completed", "verdict": verdict, "severity": "medium", "confidence": 1.0,
                        "reasoning": "controlled evaluator fixture", "evidence": []})
    return records


def evaluate_multifamily_stage1(resolved_suite: Mapping[str, Any], prepare_result: Mapping[str, Any], stage1_records: Sequence[Mapping[str, Any]], *, execution_mode: str, prepare_path: str | None = None) -> dict[str, Any]:
    if execution_mode not in EXECUTION_MODES: raise MultiFamilyStage1ContractError("execution_mode must be controlled, replay, or live")
    errors = validate_multifamily_prepare_result(prepare_result)
    if errors: raise MultiFamilyStage1ContractError("invalid Prepare result: " + "; ".join(errors))
    if prepare_result.get("complete") is not True: raise MultiFamilyStage1ContractError("Prepare artifact must be complete")
    if resolved_suite.get("suite") != SUITE_NAME or prepare_result.get("suite") != SUITE_NAME: raise MultiFamilyStage1ContractError("suite mismatch")
    if prepare_result.get("source_revision") != PINNED_REVISION: raise MultiFamilyStage1ContractError("Prepare source revision mismatch")
    cases = {case["case_id"]: copy.deepcopy(case) for case in resolved_suite.get("cases", [])}
    prepares = {case["case_id"]: case for case in prepare_result.get("cases", []) if isinstance(case, Mapping)}
    if set(cases) != set(prepares): raise MultiFamilyStage1ContractError("suite and Prepare case IDs must match")
    prepare_counts = prepare_result.get("counts", {})
    derived_direct = sum(_direct(case) for case in cases.values())
    derived_positive = sum(_direct(case) and case.get("expected", {}).get("project_ground_truth") == "attack_positive" for case in cases.values())
    derived_negative = sum(_direct(case) and case.get("expected", {}).get("project_ground_truth") == "project_negative" for case in cases.values())
    required_prepare_counts = {"reviewed_cases_total": len(cases), "direct_cases": derived_direct,
                               "not_scored_cases": len(cases) - derived_direct,
                               "attack_positive_cases": derived_positive,
                               "project_negative_cases": derived_negative}
    if not isinstance(prepare_counts, Mapping) or any(prepare_counts.get(key) != value for key, value in required_prepare_counts.items()):
        raise MultiFamilyStage1ContractError("Prepare artifact accounting does not match resolved suite")
    records = _record_index(stage1_records, cases, prepares)
    for case in cases.values():
        _validate_case_contract(case)
    _validate_prepare_case_fidelity(cases, prepares)
    exact_ids = _exact_core_labels(resolved_suite, cases)
    results, conditioned, e2e = [], [], []
    complete = True
    for case in sorted(cases.values(), key=_case_key):
        case_id, prep, expected = case["case_id"], prepares[case["case_id"]], case["expected"]
        actual = prep["actual"]
        out = {"case_id": case_id, "component_benchmark": case.get("component_benchmark"), "suite_groups": sorted(case.get("suite_groups", [])),
               "source": copy.deepcopy(case.get("source")), "observability": copy.deepcopy(case.get("observability")), "expected": copy.deepcopy(expected),
               "prepare": {"candidate_selected": actual.get("candidate_selected"), "score": actual.get("candidate_score"), "verdict_hint": actual.get("prepare_verdict_hint"), "reason_hints": copy.deepcopy(actual.get("prepare_reason_hints", []))}}
        if not _direct(case):
            out.update(stage1={"execution_status": "not_run_observability"}, classification={"policy": expected.get("classification_policy"), "compatible": None, "result": "not_scored_observability"}, mapping={"execution_status": "not_scored_observability", "actual_ids": [], "result": "not_scored_observability"}, end_to_end={"result": "not_scored_observability"})
        elif actual.get("candidate_selected") is not True:
            positive = expected.get("project_ground_truth") == "attack_positive"
            out.update(stage1={"execution_status": "not_run_candidate_miss" if positive else "not_run_prepare_suppressed"}, classification={"policy": expected.get("classification_policy"), "compatible": None, "result": "not_scored_stage1"}, mapping={"execution_status": "not_scored_stage1_not_run", "actual_ids": [], "result": "not_scored_stage1_not_run"}, end_to_end={"result": "failed_by_prepare_miss" if positive else "passed_by_prepare_suppression"})
            if case_id in exact_ids: e2e.append({"expected": exact_ids[case_id], "prediction": "NOT_SELECTED"})
        elif case_id not in records:
            complete = False
            out.update(stage1={"execution_status": "stage1_missing_result"}, classification={"policy": expected.get("classification_policy"), "compatible": None, "result": "stage1_missing_result"}, mapping={"execution_status": "not_scored_stage1_unavailable", "actual_ids": [], "result": "not_scored_stage1_unavailable"}, end_to_end={"result": "stage1_missing_result"})
            if case_id in exact_ids: e2e.append({"expected": exact_ids[case_id], "prediction": "STAGE1_ERROR"})
        elif records[case_id]["execution_status"] != "completed":
            complete = False
            out.update(stage1={"execution_status": records[case_id]["execution_status"]}, classification={"policy": expected.get("classification_policy"), "compatible": None, "result": "stage1_error"}, mapping={"execution_status": "not_scored_stage1_unavailable", "actual_ids": [], "result": "not_scored_stage1_unavailable"}, end_to_end={"result": "stage1_error"})
            if case_id in exact_ids: e2e.append({"expected": exact_ids[case_id], "prediction": "STAGE1_ERROR"})
        else:
            stage1 = _record_stage1(records[case_id]); verdict = stage1["verdict"]; classification = _policy(expected, verdict)
            if classification["compatible"]:
                mapping = _mapping_result(expected, verdict, build_security_standards_mapping(stage1, _candidate(case, prep)))
            else:
                # Classification is the mapping gate.  Do not call the
                # production mapper for an incompatible verdict and then make
                # its output look like a mapping failure.
                mapping = {"execution_status": "not_scored_due_to_classification", "actual_ids": [], "result": "not_scored_due_to_classification"}
            out.update(stage1=stage1, classification=classification, mapping=mapping, end_to_end={"result": "pass" if classification["compatible"] else "failed_by_stage1_classification"})
            if case_id in exact_ids:
                e2e.append({"expected": exact_ids[case_id], "prediction": verdict})
                if expected.get("classification_policy") == "exact": conditioned.append({"expected": exact_ids[case_id], "prediction": verdict})
        results.append(out)
    direct = [x for x in results if x["observability"].get("status") == "direct"]
    positives = [x for x in direct if x["expected"].get("project_ground_truth") == "attack_positive"]
    negatives = [x for x in direct if x["expected"].get("project_ground_truth") == "project_negative"]
    selected_positive = [x for x in positives if x["prepare"]["candidate_selected"] is True]
    completed_positive = [x for x in selected_positive if x["stage1"]["execution_status"] == "completed"]
    compatible_positive = [x for x in completed_positive if x["classification"]["compatible"] is True]
    mapping_scored = [x for x in results if x["mapping"]["result"] in {"pass", "fail"}]
    stage_matrix, e2e_matrix = _matrix(conditioned, e2e=False), _matrix(e2e, e2e=True)
    stage_prf, e2e_prf = _prf(stage_matrix), _prf(e2e_matrix)
    if not complete:
        stage_prf, e2e_prf = _unavailable_prf(stage_prf), _unavailable_prf(e2e_prf)
    cross = sum(row["prediction"] in EXACT_LABELS and row["prediction"] != row["expected"] for row in conditioned)
    candidate_recall_by_class = {}
    compatibility_by_class = {}
    end_to_end_by_class = {}
    mapping_by_class = {}
    for label in EXACT_LABELS:
        cp = [x for x in completed_positive if x["expected"].get("allowed_stage1_verdicts") == [label]]
        allp = [x for x in positives if x["expected"].get("allowed_stage1_verdicts") == [label]]
        selected = [x for x in allp if x["prepare"]["candidate_selected"] is True]
        candidate_recall_by_class[label] = _fraction(len(selected), len(allp), complete)
        compatibility_by_class[label] = _fraction(sum(x["classification"]["compatible"] is True for x in cp), len(cp), complete)
        end_to_end_by_class[label] = _fraction(sum(x["end_to_end"]["result"] == "pass" for x in allp), len(allp), complete)
        mapped = [x for x in results if x["classification"].get("compatible") is True and x["expected"].get("allowed_stage1_verdicts") == [label] and x["mapping"]["result"] in {"pass", "fail"}]
        mapping_by_class[label] = _fraction(sum(x["mapping"]["result"] == "pass" for x in mapped), len(mapped), complete)
    counts = {"reviewed_cases": len(results), "direct_cases": len(direct), "not_scored_cases": len(results)-len(direct), "attack_positive": len(positives), "project_negative": len(negatives), "candidate_selected_positive": len(selected_positive), "candidate_missed_positive": len(positives)-len(selected_positive), "stage1_expected": sum(x["prepare"]["candidate_selected"] is True for x in direct), "stage1_completed": sum(x["stage1"]["execution_status"] == "completed" for x in direct), "stage1_missing": sum(x["stage1"]["execution_status"] == "stage1_missing_result" for x in direct), "stage1_error": sum(x["stage1"]["execution_status"] in ERROR_STATUSES for x in direct), "exact_core_cases": len(exact_ids), "exact_core_selected": sum(x["prepare"]["candidate_selected"] is True for x in results if x["case_id"] in exact_ids)}
    metrics = {"candidate_recall": _fraction(len(selected_positive), len(positives)), "candidate_recall_by_class": candidate_recall_by_class, "stage1_compatibility_given_candidate": _fraction(len(compatible_positive), len(completed_positive), complete), "stage1_compatibility_by_class": compatibility_by_class, "positive_end_to_end_compatibility": _fraction(sum(x["end_to_end"]["result"] == "pass" for x in positives), len(positives), complete), "positive_end_to_end_by_class": end_to_end_by_class, "negative_candidate_suppression": _fraction(sum(x["prepare"]["candidate_selected"] is False for x in negatives), len(negatives)), "negative_control_pass": _fraction(sum(x["end_to_end"]["result"] == "passed_by_prepare_suppression" or x["end_to_end"]["result"] == "pass" for x in negatives), len(negatives), complete), "mapping_consistency_given_compatible_classification": _fraction(sum(x["mapping"]["result"] == "pass" for x in mapping_scored), len(mapping_scored), complete), "mapping_consistency_by_class": mapping_by_class, "cross_family_confusion_rate": _fraction(cross, len(conditioned), complete), "other_classification_failure_rate": _fraction(sum(r["prediction"] not in EXACT_LABELS for r in conditioned), len(conditioned), complete), "exact_core_stage1": {"compatibility": _fraction(sum(r["prediction"] == r["expected"] for r in conditioned), len(conditioned), complete), **stage_prf}, "exact_core_end_to_end": {"compatibility": _fraction(sum(r["prediction"] == r["expected"] for r in e2e), len(e2e), complete), **e2e_prf}, "stage1_conditioned_macro": stage_prf["macro"], "end_to_end_macro": e2e_prf["macro"]}
    provenance = {"path": prepare_path, "sha256": hashlib.sha256(Path(prepare_path).read_bytes()).hexdigest() if prepare_path else None}
    addendum_ids = resolved_suite["suite_manifest"]["groups"].get("path_file_boundary_addendum", [])
    result_by_id = {item["case_id"]: item for item in results}
    addendum = [result_by_id[case_id] for case_id in addendum_ids if case_id in result_by_id]
    return {"schema_version": RESULT_SCHEMA_VERSION, "suite": SUITE_NAME, "source_revision": PINNED_REVISION, "execution_mode": execution_mode, "complete": complete, "prepare_artifact": provenance, "counts": counts, "metrics": metrics, "confusion_matrices": {"stage1_conditioned_exact_core": stage_matrix, "end_to_end_exact_core": e2e_matrix}, "path_file_boundary_addendum": addendum, "cases": results}


def validate_multifamily_stage1_result(result: Mapping[str, Any]) -> list[str]:
    """Perform lightweight semantic validation without a jsonschema runtime.

    The checked-in JSON schema describes the portable wire format.  These
    checks additionally protect the arithmetic and fixed strict-label contract
    when an evaluator result is written or consumed by tests.
    """

    errors = []
    if result.get("schema_version") != RESULT_SCHEMA_VERSION: errors.append("invalid schema_version")
    if result.get("suite") != SUITE_NAME: errors.append("invalid suite")
    if result.get("execution_mode") not in EXECUTION_MODES: errors.append("invalid execution_mode")
    if not isinstance(result.get("complete"), bool): errors.append("complete must be boolean")
    provenance = result.get("prepare_artifact")
    if not isinstance(provenance, Mapping):
        errors.append("prepare_artifact must be an object")
    elif not isinstance(provenance.get("path"), (str, type(None))) or not isinstance(provenance.get("sha256"), (str, type(None))):
        errors.append("prepare_artifact path and sha256 must be string or null")
    counts = result.get("counts")
    required_counts = ("reviewed_cases", "direct_cases", "not_scored_cases", "attack_positive", "project_negative", "candidate_selected_positive", "candidate_missed_positive", "stage1_expected", "stage1_completed", "stage1_missing", "stage1_error", "exact_core_cases", "exact_core_selected")
    if not isinstance(counts, Mapping):
        errors.append("counts must be an object")
        counts = {}
    else:
        for name in required_counts:
            if isinstance(counts.get(name), bool) or not isinstance(counts.get(name), int) or counts[name] < 0:
                errors.append(f"counts.{name} must be a non-negative integer")
    cases = result.get("cases")
    if not isinstance(cases, list): errors.append("cases must be an array")
    else:
        ids = [item.get("case_id") for item in cases if isinstance(item, Mapping)]
        if len(ids) != len(cases) or any(not isinstance(case_id, str) for case_id in ids) or len(set(ids)) != len(ids):
            errors.append("cases must have unique string case IDs")
        if counts.get("reviewed_cases") != len(cases): errors.append("reviewed_cases mismatch")
    for name in ("stage1_conditioned_exact_core", "end_to_end_exact_core"):
        matrix = result.get("confusion_matrices", {}).get(name, {})
        if matrix.get("row_labels") != list(EXACT_LABELS): errors.append(f"{name} has invalid row labels")
        columns, rows = matrix.get("column_labels"), matrix.get("rows")
        if not isinstance(columns, list) or columns[:len(EXACT_LABELS)] != list(EXACT_LABELS) or len(columns) != len(set(columns)):
            errors.append(f"{name} has invalid column labels")
            continue
        if not isinstance(rows, Mapping):
            errors.append(f"{name} rows must be an object")
            continue
        total = 0
        for label in EXACT_LABELS:
            row = rows.get(label)
            if not isinstance(row, Mapping) or set(row) != set(columns):
                errors.append(f"{name}.{label} does not match column labels")
                continue
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in row.values()):
                errors.append(f"{name}.{label} cells must be non-negative integers")
            total += sum(value for value in row.values() if isinstance(value, int) and not isinstance(value, bool))
        if matrix.get("denominator") != total:
            errors.append(f"{name} denominator mismatch")
    return errors


def _load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise MultiFamilyStage1ContractError("JSON root must be an object")
    return value


def _load_replay(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise MultiFamilyStage1ContractError("replay array must contain objects")
        return payload
    if not isinstance(payload, Mapping):
        raise MultiFamilyStage1ContractError("replay root must be an object or array")
    if payload.get("schema_version") not in {None, REPLAY_SCHEMA_VERSION}: raise MultiFamilyStage1ContractError("unsupported replay schema")
    records = payload.get("records")
    if not isinstance(records, list): raise MultiFamilyStage1ContractError("replay records must be an array")
    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate normalized Stage1 records for the OWASP CRS multi-family suite (no network)")
    parser.add_argument("--source-root", default=str(Path("benchmarks/sources/owasp_crs") / PINNED_REVISION))
    parser.add_argument("--suite", required=True); parser.add_argument("--prepare-result", required=True)
    parser.add_argument("--mode", choices=sorted(EXECUTION_MODES), required=True); parser.add_argument("--stage1-results")
    parser.add_argument("--output", required=True); args = parser.parse_args(argv)
    try:
        resolved, prepare = load_resolved_suite(args.source_root, args.suite), _load_json(args.prepare_result)
        if args.mode == "controlled":
            if args.stage1_results: raise MultiFamilyStage1ContractError("--stage1-results is replay-only")
            records = controlled_records(resolved, prepare)
        else:
            if not args.stage1_results: raise MultiFamilyStage1ContractError("--stage1-results is required for replay")
            records = _load_replay(args.stage1_results)
        result = evaluate_multifamily_stage1(resolved, prepare, records, execution_mode=args.mode, prepare_path=args.prepare_result)
        errors = validate_multifamily_stage1_result(result)
        if errors: raise MultiFamilyStage1ContractError("invalid result: " + "; ".join(errors))
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError, MultiFamilyStage1ContractError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr); return 1
    print(f"[OK] output: {args.output}")
    print(f"[{ 'OK' if result['complete'] else 'INCOMPLETE'}] exact-core E2E: {result['metrics']['exact_core_end_to_end']['compatibility']['passed']}/{result['metrics']['exact_core_end_to_end']['compatibility']['total']}")
    return 0 if result["complete"] else 1


if __name__ == "__main__": raise SystemExit(main())
