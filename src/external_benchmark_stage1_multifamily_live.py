#!/usr/bin/env python3
"""One-shot live Stage1 runner for the frozen OWASP CRS multi-family suite.

This module owns only live orchestration: it regenerates production Prepare
candidates, checks them against the frozen Prepare observation, invokes the
production :func:`classify_candidate` once per eligible candidate, and writes
normalized records.  All scoring remains in
``external_benchmark_stage1_multifamily``.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from src.external_benchmark_crs_multifamily import PINNED_REVISION
from src.external_benchmark_prepare import (
    PREPARE_MIN_REPEAT_AGGREGATE,
    PREPARE_MIN_SCORE,
    SOURCE_TABLE,
    benchmark_request_id,
    build_prepare_export_payload,
    build_synthetic_security_row,
)
from src.external_benchmark_prepare_multifamily import (
    SUITE_NAME,
    build_multifamily_synthetic_security_row,
    load_resolved_suite,
)
from src.external_benchmark_stage1_multifamily import (
    ERROR_STATUSES,
    MultiFamilyStage1ContractError,
    evaluate_multifamily_stage1,
    validate_multifamily_stage1_result,
)
from src.llm_client import combine_llm_usage, resolve_llm_config
from src.llm_stage1_classifier import (
    DEFAULT_MODE,
    DEFAULT_TIMEOUT_SEC,
    choose_model,
    classify_candidate,
)
from src.prepare_llm_input import build_outputs

LIVE_RECORDS_SCHEMA_VERSION = "external_security_benchmark_multifamily_stage1_live_records.v1"
CANONICAL_PREPARE_SHA256 = "7743860a7d97b48660efe1bcdddc7c78b3c7d970ca572a1610a42259a73c50a6"
FidelityFields = ("request_id", "raw_request_target", "candidate_selected", "candidate_score", "prepare_verdict_hint", "prepare_reason_hints", "source_table")
Classifier = Callable[..., tuple[Any | None, Any | None]]


class LiveStage1ContractError(ValueError):
    """Raised before a provider call when live-run invariants do not hold."""


def _case_key(case: Mapping[str, Any]) -> tuple[int, int, str]:
    source = case.get("source") if isinstance(case.get("source"), Mapping) else {}
    return (int(source.get("rule_id") or source.get("source_rule_id") or 0), int(source.get("test_id") or source.get("source_test_id") or 0), str(case.get("case_id") or ""))


def _direct(case: Mapping[str, Any]) -> bool:
    obs = case.get("observability")
    return isinstance(obs, Mapping) and obs.get("eligible") is True and obs.get("status") == "direct"


def _is_positive(case: Mapping[str, Any]) -> bool:
    expected = case.get("expected")
    return isinstance(expected, Mapping) and expected.get("project_ground_truth") == "attack_positive"


def _sequence_indexes(cases: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Reproduce the two frozen Prepare runner sequence counters."""
    legacy = new = 0
    indexes: dict[str, int] = {}
    for case in sorted(cases, key=_case_key):
        if not _direct(case):
            continue
        case_id = str(case["case_id"])
        if case.get("component_benchmark") == "owasp_crs_path_file_access.v1":
            indexes[case_id] = legacy
            legacy += 1
        else:
            indexes[case_id] = new
            new += 1
    return indexes


def regenerate_candidate(case: Mapping[str, Any], sequence_index: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Run the production Prepare builder for precisely one normalized row."""
    if case.get("component_benchmark") == "owasp_crs_path_file_access.v1":
        row = build_synthetic_security_row(case, sequence_index=sequence_index)
    else:
        row = build_multifamily_synthetic_security_row(case, sequence_index=sequence_index)
    payload = build_prepare_export_payload(row)
    _, candidates, _, _, _ = build_outputs(
        payload,
        min_score=PREPARE_MIN_SCORE,
        min_repeat_aggregate=PREPARE_MIN_REPEAT_AGGREGATE,
        source_tables=[SOURCE_TABLE],
    )
    request_id = row["request_id"]
    matches = [dict(item) for item in candidates if isinstance(item, Mapping) and item.get("request_id") == request_id]
    if len(matches) > 1:
        raise LiveStage1ContractError(f"{case['case_id']}: regenerated Prepare produced duplicate candidates")
    return (matches[0] if matches else None), row


def candidate_fidelity(case_id: str, frozen_actual: Mapping[str, Any], candidate: Mapping[str, Any] | None, row: Mapping[str, Any]) -> dict[str, Any]:
    """Compare all frozen Stage1-relevant Prepare facts before model access."""
    actual = {
        "request_id": candidate.get("request_id") if candidate else row.get("request_id"),
        "raw_request_target": candidate.get("raw_request_target") if candidate else row.get("raw_request").split(" ", 2)[1],
        "candidate_selected": candidate is not None,
        "candidate_score": candidate.get("score") if candidate else None,
        "prepare_verdict_hint": candidate.get("verdict_hint") if candidate else None,
        "prepare_reason_hints": copy.deepcopy(candidate.get("reason_hints", [])) if candidate else [],
        "source_table": candidate.get("source_table") if candidate else SOURCE_TABLE,
    }
    mismatches = [name for name in FidelityFields if frozen_actual.get(name) != actual[name]]
    return {"case_id": case_id, "matched": not mismatches, "mismatches": mismatches, "expected": {name: copy.deepcopy(frozen_actual.get(name)) for name in FidelityFields}, "actual": actual}


def _evaluator_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_id": candidate.get("request_id"),
        "raw_request_target": candidate.get("raw_request_target"),
        "verdict_hint": candidate.get("verdict_hint"),
        "reason_hints": copy.deepcopy(candidate.get("reason_hints", [])),
        "score": candidate.get("score"),
    }


def _stage1_candidate(candidate: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    """Keep ordinary evidence while removing synthetic benchmark identifiers.

    request IDs and the pinned CRS test user-agent are correlation aids, not
    attack evidence.  They encode suite identity, so the production classifier
    receives neutral equivalents; no expected labels, case IDs, rule IDs, or
    source-test IDs are ever supplied to its unchanged prompt builder.
    """
    clean = copy.deepcopy(dict(candidate))
    clean["request_id"] = f"live-row-{ordinal:03d}"
    clean["incident_group_key"] = f"rid:live-row-{ordinal:03d}"
    # The pinned source fixture prefixes its synthetic UA with this exact
    # marker.  Remove only that fixture metadata: a suffix can itself contain
    # decisive SQLi/CMDi/XSS syntax and must reach the production classifier
    # unchanged.  Ordinary upstream User-Agents are left byte-for-byte intact.
    user_agent = clean.get("user_agent")
    marker = "OWASP CRS test agent"
    if isinstance(user_agent, str) and user_agent.startswith(marker):
        clean["user_agent"] = "Mozilla/5.0" + user_agent[len(marker):]
    return clean


def _status_for_error(error_obj: Any) -> str:
    kind = str(getattr(error_obj, "error_type", "runtime_error"))
    if kind in {"json_decode_error", "empty_output"}:
        return "stage1_parse_error"
    if kind in {"http_error", "url_error"}:
        return "stage1_api_error"
    return "stage1_runtime_error"


def _normalized_completed(case_id: str, candidate: Mapping[str, Any], result: Any) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "request_id": candidate["request_id"],
        "candidate_input": _evaluator_candidate(candidate),
        "execution_status": "completed",
        "stage1": {
            "verdict": result.verdict,
            "severity": result.severity,
            "confidence": result.confidence,
            "reasoning": result.reasoning_summary,
            "evidence": list(result.evidence_fields),
        },
        "llm_usage": copy.deepcopy(getattr(result, "llm_usage", None)),
    }


def _normalized_error(case_id: str, candidate: Mapping[str, Any], error_obj: Any) -> dict[str, Any]:
    # Do not serialize provider bodies or error strings: either can contain
    # request diagnostics, and neither is needed by the evaluator.
    return {"case_id": case_id, "request_id": candidate["request_id"], "candidate_input": _evaluator_candidate(candidate), "execution_status": _status_for_error(error_obj), "error_type": str(getattr(error_obj, "error_type", "runtime_error")), "llm_usage": copy.deepcopy(getattr(error_obj, "llm_usage", None))}


def _records_payload(provider: str, model: str, reasoning_effort: str, timeout_sec: int, max_evidence_items: int, prepare_sha: str, records: list[dict[str, Any]], state: str) -> dict[str, Any]:
    return {"schema_version": LIVE_RECORDS_SCHEMA_VERSION, "suite": SUITE_NAME, "source_revision": PINNED_REVISION, "execution_mode": "live", "availability": state, "provider": provider, "model": model, "reasoning_effort": reasoning_effort, "timeout_sec": timeout_sec, "candidate_limit": 0, "max_evidence_items": max_evidence_items, "prepare_artifact_sha256": prepare_sha, "records": records}


def _write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_live_baseline(resolved_suite: Mapping[str, Any], prepare: Mapping[str, Any], *, prepare_path: str, provider: str, model: str, reasoning_effort: str = "none", timeout_sec: int = DEFAULT_TIMEOUT_SEC, max_evidence_items: int = 8, sleep_sec: float = 0.0, llm_config: Any = None, classifier: Classifier = classify_candidate, dry_run: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute one live plan, or produce an API-free dry-run/availability result."""
    if resolved_suite.get("suite") != SUITE_NAME or prepare.get("suite") != SUITE_NAME:
        raise LiveStage1ContractError("suite mismatch")
    prepare_sha = hashlib.sha256(Path(prepare_path).read_bytes()).hexdigest()
    cases = [copy.deepcopy(case) for case in resolved_suite.get("cases", [])]
    frozen = {item.get("case_id"): item for item in prepare.get("cases", []) if isinstance(item, Mapping)}
    if len(frozen) != len(cases) or {case.get("case_id") for case in cases} != set(frozen):
        raise LiveStage1ContractError("suite and Prepare case IDs must match")
    indexes = _sequence_indexes(cases)
    selected = [case for case in sorted(cases, key=_case_key) if _direct(case) and _is_positive(case) and frozen[case["case_id"]]["actual"].get("candidate_selected") is True]
    fidelity: list[dict[str, Any]] = []
    regenerated: dict[str, dict[str, Any]] = {}
    for case in selected:
        candidate, row = regenerate_candidate(case, indexes[case["case_id"]])
        checked = candidate_fidelity(case["case_id"], frozen[case["case_id"]]["actual"], candidate, row)
        fidelity.append(checked)
        if checked["matched"] and candidate is not None:
            regenerated[case["case_id"]] = candidate

    fidelity_failed = [item for item in fidelity if not item["matched"]]
    state = "dry_run" if dry_run else ("candidate_fidelity_error" if fidelity_failed else "available")
    records: list[dict[str, Any]] = []
    attempted = completed = failed = 0
    if not dry_run and not fidelity_failed and (llm_config is None or not getattr(llm_config, "api_key", "")):
        state = "live_execution_unavailable"
    elif not dry_run and not fidelity_failed:
        for ordinal, case in enumerate(selected, start=1):
            candidate = regenerated[case["case_id"]]
            attempted += 1
            result, error_obj = classifier(
                llm_config=llm_config, model=model, meta={"query_timezone": "Asia/Seoul", "analysis_window": {"start": None, "end_exclusive": None}, "pipeline_policy": {"db_raw_preserved": True, "send_raw_full_export_to_llm": False}}, candidate=_stage1_candidate(candidate, ordinal), timeout_sec=timeout_sec, store=False, reasoning_effort=reasoning_effort, max_evidence_items=max_evidence_items, candidate_index=ordinal - 1,
            )
            if result is not None and error_obj is None:
                records.append(_normalized_completed(case["case_id"], candidate, result)); completed += 1
            else:
                records.append(_normalized_error(case["case_id"], candidate, error_obj)); failed += 1
            if sleep_sec > 0 and ordinal < len(selected):
                time.sleep(sleep_sec)

    records_payload = _records_payload(provider, model, reasoning_effort, timeout_sec, max_evidence_items, prepare_sha, records, state)
    evaluation = evaluate_multifamily_stage1(resolved_suite, prepare, records, execution_mode="live", prepare_path=prepare_path)
    if dry_run or state == "live_execution_unavailable" or fidelity_failed:
        evaluation["complete"] = False
    evaluation["provider"] = provider
    evaluation["model"] = model
    evaluation["reasoning_effort"] = reasoning_effort
    evaluation["timeout_sec"] = timeout_sec
    evaluation["candidate_evidence_limits"] = {"candidate_limit": 0, "max_evidence_items": max_evidence_items}
    # Keep the required call accounting at the result root as well as in the
    # live provenance envelope, so a consumer need not infer it from cases.
    evaluation["calls_attempted"] = attempted
    evaluation["calls_completed"] = completed
    evaluation["calls_failed"] = failed
    evaluation["calls_skipped_candidate_miss"] = sum(_direct(c) and _is_positive(c) and frozen[c["case_id"]]["actual"].get("candidate_selected") is False for c in cases)
    evaluation["calls_skipped_negative_suppression"] = sum(_direct(c) and not _is_positive(c) and frozen[c["case_id"]]["actual"].get("candidate_selected") is False for c in cases)
    evaluation["calls_skipped_observability"] = sum(not _direct(c) for c in cases)
    evaluation["live_execution"] = {"availability": state, "calls_attempted": attempted, "calls_completed": completed, "calls_failed": failed, "calls_skipped_candidate_miss": sum(_direct(c) and _is_positive(c) and frozen[c["case_id"]]["actual"].get("candidate_selected") is False for c in cases), "calls_skipped_negative_suppression": sum(_direct(c) and not _is_positive(c) and frozen[c["case_id"]]["actual"].get("candidate_selected") is False for c in cases), "calls_skipped_observability": sum(not _direct(c) for c in cases), "candidate_fidelity": {"expected": len(selected), "matched": len(fidelity) - len(fidelity_failed), "failed": len(fidelity_failed), "failures": fidelity_failed}, "prepare_artifact_is_canonical_6b2f": prepare_sha == CANONICAL_PREPARE_SHA256, "usage": combine_llm_usage([x.get("llm_usage") for x in records if isinstance(x.get("llm_usage"), Mapping)])}
    # The evaluator's generic semantic checks still apply after the live
    # provenance envelope is attached.
    errors = validate_multifamily_stage1_result(evaluation)
    if errors:
        raise LiveStage1ContractError("invalid evaluator result: " + "; ".join(errors))
    return records_payload, evaluation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one live Stage1 baseline using production classifier semantics")
    parser.add_argument("--source-root", default=str(Path("benchmarks/sources/owasp_crs") / PINNED_REVISION))
    parser.add_argument("--suite", required=True); parser.add_argument("--prepare-result", required=True)
    parser.add_argument("--provider", default=None); parser.add_argument("--model", default=None)
    parser.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh"], default="none")
    parser.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC); parser.add_argument("--max-evidence-items", type=int, default=8)
    parser.add_argument("--sleep-sec", type=float, default=0.0); parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-records", required=True); parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        resolved = load_resolved_suite(args.source_root, args.suite)
        prepare = json.loads(Path(args.prepare_result).read_text(encoding="utf-8"))
        config = resolve_llm_config(args.provider)
        model = choose_model(config.provider, DEFAULT_MODE, args.model, dry_run=bool(args.dry_run))
        prepare_sha = hashlib.sha256(Path(args.prepare_result).read_bytes()).hexdigest()
        print(f"provider={config.provider} model={model} reasoning_effort={args.reasoning_effort} timeout_sec={args.timeout_sec}")
        print(f"suite={SUITE_NAME} revision={PINNED_REVISION} prepare_sha256={prepare_sha}")
        records, result = run_live_baseline(resolved, prepare, prepare_path=args.prepare_result, provider=config.provider, model=model, reasoning_effort=args.reasoning_effort, timeout_sec=args.timeout_sec, max_evidence_items=args.max_evidence_items, sleep_sec=args.sleep_sec, llm_config=config, dry_run=bool(args.dry_run))
        print(f"expected_calls={result['counts']['candidate_selected_positive']} exact_core_selected={result['counts']['exact_core_selected']} fidelity={result['live_execution']['candidate_fidelity']['matched']}/{result['live_execution']['candidate_fidelity']['expected']}")
        _write_json(args.output_records, records); records_sha = hashlib.sha256(Path(args.output_records).read_bytes()).hexdigest()
        result["live_records"] = {"path": args.output_records, "sha256": records_sha}
        _write_json(args.output, result)
        print(f"availability={result['live_execution']['availability']} attempted={result['live_execution']['calls_attempted']} completed={result['live_execution']['calls_completed']} failed={result['live_execution']['calls_failed']}")
        print(f"records={args.output_records} sha256={records_sha}")
        print(f"output={args.output} sha256={hashlib.sha256(Path(args.output).read_bytes()).hexdigest()}")
        return 0 if result["complete"] else 1
    except (OSError, UnicodeError, ValueError, LiveStage1ContractError, MultiFamilyStage1ContractError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
