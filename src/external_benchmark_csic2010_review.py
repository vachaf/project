#!/usr/bin/env python3
"""Deterministic CSIC review sampling, local rehydration, and manifest checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.external_benchmark_csic2010 import FILE_SPECS, RawHttpRequest, parse_raw_http_stream


SAMPLE_SCHEMA_VERSION = "csic2010_review_sample.v1"
REVIEW_SCHEMA_VERSION = "csic2010_reviewed_semantic_subset.v1"
STRICT_FAMILIES = {"sqli": "suspicious_sqli", "xss": "suspicious_xss", "path_traversal": "suspicious_path_traversal", "command_injection": "suspicious_command_injection"}
SEMANTICS = {"project_attack_positive", "project_negative", "not_scored_observability", "ambiguous"}
FAMILIES = set(STRICT_FAMILIES) | {"file_disclosure", "crlf_header_injection", "information_gathering", "parameter_tampering", "other_security"}


def semantic_review_view(worksheet_item: Mapping[str, Any]) -> dict[str, Any]:
    """Blind first-pass view: source identity/evidence only, never Prepare data."""
    return {key: worksheet_item.get(key) for key in ("source_file", "request_index", "raw_request_sha256", "method", "request_line", "headers_present", "body_for_observability_review", "cookie_value_redacted")}


def validation_review_view(worksheet_item: Mapping[str, Any]) -> dict[str, Any]:
    """Return an evidence-only second-pass view without label/review leakage.

    ``case_token`` is deliberately the request digest rather than the source
    filename/index, whose names can disclose source-normal/anomalous status.
    Body content stays out of this view and is revealed separately only when
    the reviewer needs to decide observability.
    """
    request_line = str(worksheet_item.get("request_line") or "")
    parts = request_line.split(" ")
    target = parts[1] if len(parts) >= 2 else ""
    path_and_query = target.split("://", 1)[-1]
    if "/" in path_and_query:
        path_and_query = "/" + path_and_query.split("/", 1)[1]
    elif not path_and_query.startswith("/"):
        path_and_query = "/"
    uri, separator, query = path_and_query.partition("?")
    header_names = [str(name) for name in worksheet_item.get("headers_present") or []]
    lowered = {name.lower() for name in header_names}
    return {
        "case_token": worksheet_item.get("raw_request_sha256"),
        "method": worksheet_item.get("method"),
        "raw_request_target": target,
        "uri": uri,
        "query_string": f"?{query}" if separator else "",
        "apache_observable_logged_fields": ["method", "raw_request_target", "uri", "query_string", "headers_present"],
        "headers_present": header_names,
        "content_type_metadata": "present" if "content-type" in lowered else "absent",
        "content_length_metadata": "present" if "content-length" in lowered else "absent",
        "body_present": bool(worksheet_item.get("body_for_observability_review")),
    }


def review_identity(item: Mapping[str, Any]) -> tuple[str, int, str]:
    """Stable review identity used by queue, comparison, and canonicalization."""
    return (str(item["source_file"]), int(item["request_index"]), str(item["raw_request_sha256"]))


def validation_queue_identity_sets(primary_queue: Sequence[Mapping[str, Any]], audit_queues: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, set[tuple[str, int, str]]]:
    """Return queue sets for deterministic overlap/union integrity checks."""
    primary = {
        (str(item["identity"]["source_file"]), int(item["identity"]["request_index"]), str(item["identity"]["raw_request_sha256"]))
        for item in primary_queue
    }
    audit = {
        review_identity(item)
        for entries in audit_queues.values()
        for item in entries
    }
    return {"primary": primary, "audit": audit, "overlap": primary & audit, "union": primary | audit}


def review_agreement_category(provisional: Mapping[str, Any], validation: Mapping[str, Any]) -> str:
    """Classify a frozen two-review comparison without looking at Prepare data."""
    first_semantic = provisional.get("project_semantic")
    second_semantic = validation.get("project_semantic")
    if first_semantic != second_semantic:
        if "not_scored_observability" in {first_semantic, second_semantic} and "project_attack_positive" in {first_semantic, second_semantic}:
            return "observability_disagreement"
        return "semantic_disagreement"
    if first_semantic == "project_attack_positive" and provisional.get("reviewed_family") != validation.get("reviewed_family"):
        return "family_disagreement"
    if provisional.get("classification_policy") != validation.get("classification_policy"):
        return "semantic_agreement_policy_disagreement"
    return "full_agreement"


def review_requires_adjudication(provisional: Mapping[str, Any], validation: Mapping[str, Any]) -> bool:
    """Apply the 6C-3C adjudication routing policy."""
    category = review_agreement_category(provisional, validation)
    if category != "full_agreement":
        return True
    if provisional.get("review_confidence") == "low" or validation.get("validation_confidence") == "low":
        return True
    return provisional.get("project_semantic") == "ambiguous" or validation.get("project_semantic") == "ambiguous"


def stage1_eligible_canonical_case(item: Mapping[str, Any]) -> bool:
    """Keep unvalidated provisional records out of future scored Stage1 subsets."""
    return (
        item.get("review_status") in {"validated_agreement", "adjudicated"}
        and item.get("project_semantic") == "project_attack_positive"
        and bool(item.get("prepare_selected"))
        and item.get("classification_policy") in {"exact", "compatible_set"}
    )


def post_review_prepare_join(annotation: Mapping[str, Any], sample_item: Mapping[str, Any]) -> dict[str, Any]:
    """Attach Prepare metadata only after an explicit provisional decision exists."""
    return dict(annotation) | {f"prepare_{key}": sample_item.get(key) for key in ("selected", "score", "verdict_hint", "reason_hints", "filtered_reasons")}


def _load_index(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _choose(records: Iterable[Mapping[str, Any]], quota: int, selected: set[str]) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: str(item["raw_request_sha256"])):
        digest = str(record["raw_request_sha256"])
        if digest in selected:
            continue
        selected.add(digest)
        chosen.append(dict(record))
        if len(chosen) == quota:
            break
    return chosen


def _hint_stratum(record: Mapping[str, Any], family: str) -> str:
    hints = set(record.get("reason_hints") or [])
    if family == "sqli":
        for name, needle in (("waitfor_delay", "waitfor"), ("sql_comment", "sql_comment"), ("quote_termination", "quote_termination"), ("encoding", "encoding:")):
            if any(needle in hint for hint in hints):
                return name
    if family == "xss":
        for name, needle in (("javascript_uri", "javascript"), ("script_tag", "script_tag"), ("alert_call", "alert_call"), ("encoding", "encoding:")):
            if any(needle in hint for hint in hints):
                return name
    return "other"


def build_sample(index_path: Path) -> dict[str, Any]:
    records = _load_index(index_path)
    selected_hashes: set[str] = set()
    cases: list[dict[str, Any]] = []
    pool_a = [r for r in records if r["source_label"] == "source_normal" and r["selected"]]
    for record in _choose(pool_a, len(pool_a), selected_hashes):
        cases.append(_sample_record(record, "selected_source_normal", "all"))
    pool_b = [r for r in records if r["source_label"] == "source_anomalous" and r["selected"]]
    for verdict, quota in (("sqli", 40), ("xss", 40), ("suspicious", 40)):
        group = [r for r in pool_b if r.get("verdict_hint") == verdict]
        strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in group:
            strata[_hint_stratum(item, verdict)].append(item)
        remaining = quota
        for name in sorted(strata):
            take = min((quota + len(strata) - 1) // len(strata), remaining)
            picked = _choose(strata[name], take, selected_hashes)
            cases.extend(_sample_record(item, "selected_source_anomalous", f"verdict={verdict};hint={name}") for item in picked)
            remaining -= len(picked)
        if remaining:
            picked = _choose(group, remaining, selected_hashes)
            cases.extend(_sample_record(item, "selected_source_anomalous", f"verdict={verdict};hint=fill") for item in picked)
    pool_c = [r for r in records if r["source_label"] == "source_anomalous" and not r["selected"]]
    lows = [r for r in pool_c if "low_signal_request" in (r.get("filtered_reasons") or [])]
    for item in _choose(lows, len(lows), selected_hashes):
        cases.append(_sample_record(item, "suppressed_source_anomalous", "forced=low_signal_request"))
    for method, has_body, quota in (("GET", False, 40), ("POST", True, 40), ("PUT", True, 20)):
        group = [r for r in pool_c if r["method"] == method and bool(r["has_body"]) is has_body]
        existing = sum(1 for item in cases if item["sampling_pool"] == "suppressed_source_anomalous" and item["method"] == method and bool(item["has_body"]) is has_body)
        picked = _choose(group, max(0, quota - existing), selected_hashes)
        cases.extend(_sample_record(item, "suppressed_source_anomalous", f"method={method};has_body={str(has_body).lower()}") for item in picked)
    cases.sort(key=lambda item: (item["sampling_pool"], item["sampling_stratum"], item["raw_request_sha256"]))
    return {"schema_version": SAMPLE_SCHEMA_VERSION, "source_index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(), "sampling_policy": "fixed quotas; lexical raw_request_sha256 ordering within stratum; low_signal_request forced before pool-C quotas", "cases": cases}


def _sample_record(record: Mapping[str, Any], pool: str, stratum: str) -> dict[str, Any]:
    return {key: record.get(key) for key in ("source_file", "request_index", "raw_request_sha256", "source_label", "method", "has_body", "selected", "score", "verdict_hint", "reason_hints", "filtered_reasons", "filtered_reason_hints")} | {"sampling_pool": pool, "sampling_stratum": stratum}


def rehydrate_worksheet(sample: Mapping[str, Any], cache_dir: Path) -> list[dict[str, Any]]:
    wanted = {(item["source_file"], int(item["request_index"]), item["raw_request_sha256"]): item for item in sample["cases"]}
    rows: list[dict[str, Any]] = []
    for spec in FILE_SPECS:
        source_file, label = str(spec["filename"]), str(spec["source_label"])
        path = cache_dir / "primary" / source_file
        with path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
            def visit(request: RawHttpRequest) -> None:
                key = (source_file, request.request_index, request.raw_request_sha256)
                item = wanted.get(key)
                if item is None:
                    return
                header_names = [header.name.decode("latin-1") for header in request.headers]
                rows.append({**item, "request_line": request.request_line.decode("latin-1"), "headers_present": header_names, "body_for_observability_review": request.body_bytes.decode("latin-1") if request.body_bytes else "", "cookie_value_redacted": any(header.name.lower() == b"cookie" for header in request.headers)})
            parse_raw_http_stream(data, source_file=source_file, source_label=label, on_request=visit)
    if len(rows) != len(wanted):
        raise ValueError("sample identity could not be rehydrated")
    return sorted(rows, key=lambda item: (item["sampling_pool"], item["sampling_stratum"], item["raw_request_sha256"]))


def validate_reviewed_manifest(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != REVIEW_SCHEMA_VERSION or not isinstance(value.get("cases"), list):
        return ["invalid reviewed manifest root"]
    identities: set[tuple[str, int, str]] = set()
    for item in value["cases"]:
        identity = (str(item.get("source_file")), int(item.get("request_index", 0)), str(item.get("raw_request_sha256")))
        if identity in identities:
            errors.append("duplicate review identity")
        identities.add(identity)
        semantic = item.get("project_semantic")
        policy = item.get("classification_policy")
        family = item.get("reviewed_family")
        if semantic not in SEMANTICS:
            errors.append("invalid project semantic")
        if semantic == "not_scored_observability" and (policy != "not_scored" or item.get("allowed_stage1_verdicts") != []):
            errors.append("not-scored case must use not_scored policy with no allowed verdict")
        if semantic == "project_attack_positive" and family not in FAMILIES:
            errors.append("attack-positive case requires reviewed family")
        if policy == "exact" and (not isinstance(item.get("allowed_stage1_verdicts"), list) or not item["allowed_stage1_verdicts"]):
            errors.append("exact policy requires allowed verdict")
        serialized = json.dumps(item, ensure_ascii=False)
        if any(key in serialized for key in ("body_for_observability_review", "Cookie:", "Authorization:", "request_line")):
            errors.append("tracked reviewed record leaks raw source field")
    return errors


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic CSIC review sample and local worksheet")
    parser.add_argument("--index", type=Path, default=Path("/tmp/csic2010_prepare_request_index.jsonl"))
    parser.add_argument("--cache-dir", type=Path, default=Path("benchmarks/cache/csic2010"))
    parser.add_argument("--sample-output", type=Path, required=True)
    parser.add_argument("--worksheet-output", type=Path, required=True)
    args = parser.parse_args(argv)
    sample = build_sample(args.index)
    worksheet = rehydrate_worksheet(sample, args.cache_dir)
    _write(args.sample_output, sample)
    with args.worksheet_output.open("w", encoding="utf-8") as output:
        for item in worksheet:
            output.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"sample_cases={len(sample['cases'])} sample_sha256={hashlib.sha256(args.sample_output.read_bytes()).hexdigest()}")
    print(f"worksheet={args.worksheet_output} sha256={hashlib.sha256(args.worksheet_output.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
