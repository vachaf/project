#!/usr/bin/env python3
"""Isolated CSIC 2010 Apache-observable projection and Prepare baseline.

This benchmark intentionally does not create Apache rows from POST bodies or
unlogged header values, and does not call any LLM or Stage1 classifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from src.external_benchmark_csic2010 import (
    DATASET_NAME,
    FILE_SPECS,
    RawHttpRequest,
    build_inventory,
    parse_raw_http_stream,
    scan_source_file,
)
from src.external_benchmark_prepare import (
    PREPARE_MIN_REPEAT_AGGREGATE,
    PREPARE_MIN_SCORE,
    SOURCE_TABLE,
    _matching_filtered_reasons,
    build_prepare_export_payload,
)
from src.prepare_llm_input import build_outputs


RESULT_SCHEMA_VERSION = "external_security_benchmark_csic2010_prepare_result.v1"
PROJECTION_SCHEMA_VERSION = "csic2010_apache_observable_projection.v1"
FIXED_LOG_TIME = "2026-01-01T00:00:00+09:00"
DOCUMENTATION_IP = "192.0.2.60"
LOGGED_HEADERS = {b"host", b"user-agent", b"referer", b"content-type", b"content-length", b"cookie", b"authorization"}
SHA256_RE = __import__("re").compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class ProjectionLoss:
    body_omitted: bool
    cookie_value_omitted: bool
    authorization_value_omitted: bool
    unlogged_header_present: bool


def _header_value(request: RawHttpRequest, name: bytes) -> str:
    for header in request.headers:
        if header.name.lower() == name:
            return header.value.decode("latin-1")
    return ""


def _header_present(request: RawHttpRequest, name: bytes) -> bool:
    return any(header.name.lower() == name for header in request.headers)


def _split_target(raw_target: bytes) -> tuple[str, str]:
    """Derive Apache URI/query fields without altering the raw request target."""

    target = raw_target.decode("latin-1")
    if target.startswith(("http://", "https://")):
        parts = urlsplit(target)
        uri = parts.path or "/"
        return uri, f"?{parts.query}" if parts.query else ""
    if "?" in target:
        uri, query = target.split("?", 1)
        return uri, f"?{query}"
    return target, ""


def project_request(request: RawHttpRequest) -> tuple[dict[str, Any], ProjectionLoss]:
    """Project a full raw request onto current Apache security-row observability."""

    uri, query_string = _split_target(request.raw_target)
    raw_target = request.raw_target.decode("latin-1")
    protocol = request.http_version.decode("ascii")
    loss = ProjectionLoss(
        body_omitted=bool(request.body_bytes),
        cookie_value_omitted=_header_present(request, b"cookie"),
        authorization_value_omitted=_header_present(request, b"authorization"),
        unlogged_header_present=any(header.name.lower() not in LOGGED_HEADERS for header in request.headers),
    )
    request_id = f"csic2010-row-{request.raw_request_sha256[:24]}"
    row = {
        "id": request.request_index,
        "request_id": request_id,
        "log_time": FIXED_LOG_TIME,
        "src_ip": DOCUMENTATION_IP,
        "method": request.method,
        "uri": uri,
        "query_string": query_string,
        "protocol": protocol,
        "raw_request": f"{request.method} {raw_target} {protocol}",
        "raw_request_target": raw_target,
        "raw_log": "",
        "status_code": 200,
        "original_status_code": 200,
        "response_body_bytes": 0,
        "duration_us": 0,
        "ttfb_us": 0,
        "referer": _header_value(request, b"referer"),
        "user_agent": _header_value(request, b"user-agent"),
        "req_host": _header_value(request, b"host"),
        "req_content_type": _header_value(request, b"content-type"),
        "req_content_length": _header_value(request, b"content-length"),
        "has_cookie": _header_present(request, b"cookie"),
        "has_authorization": _header_present(request, b"authorization"),
        "resp_content_type": "",
        "error_link_id": "",
    }
    serialized = json.dumps(row, ensure_ascii=False, sort_keys=True)
    if any(marker in serialized for marker in ("source_normal", "source_anomalous", "CSIC", "benchmark")):
        raise ValueError("benchmark/source label leaked into projected row")
    return row, loss


def _filtered_reason_hints(filtered_rows: Sequence[Mapping[str, Any]], request_id: str) -> list[str]:
    return sorted({hint for item in filtered_rows if item.get("request_id") == request_id for hint in item.get("reason_hints", []) if isinstance(hint, str)})


def evaluate_isolated_request(request: RawHttpRequest, *, prepare_builder=build_outputs) -> dict[str, Any]:
    """Run exactly one production Prepare invocation for one parsed request."""

    row, loss = project_request(request)
    payload = build_prepare_export_payload(row)
    try:
        _llm_input, candidates, _noise, filtered_reasons_payload, filtered_rows = prepare_builder(
            payload,
            min_score=PREPARE_MIN_SCORE,
            min_repeat_aggregate=PREPARE_MIN_REPEAT_AGGREGATE,
            source_tables=[SOURCE_TABLE],
        )
    except ValueError as error:
        return _base_index_record(request, loss, error_type=type(error).__name__)
    request_id = row["request_id"]
    matches = [item for item in candidates if item.get("request_id") == request_id]
    filtered = [item for item in filtered_rows if item.get("request_id") == request_id]
    if len(matches) > 1 or (matches and filtered):
        return _base_index_record(request, loss, error_type="ambiguous_prepare_output")
    candidate = matches[0] if matches else None
    return _base_index_record(
        request,
        loss,
        selected=candidate is not None,
        score=candidate.get("score") if candidate else None,
        verdict_hint=candidate.get("verdict_hint") if candidate else None,
        reason_hints=list(candidate.get("reason_hints", [])) if candidate else [],
        filtered_reasons=_matching_filtered_reasons(filtered_reasons_payload, request_id),
        filtered_reason_hints=_filtered_reason_hints(filtered_rows, request_id),
    )


def _base_index_record(
    request: RawHttpRequest,
    loss: ProjectionLoss,
    *,
    selected: bool = False,
    score: int | None = None,
    verdict_hint: str | None = None,
    reason_hints: list[str] | None = None,
    filtered_reasons: list[str] | None = None,
    filtered_reason_hints: list[str] | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    return {
        "source_file": request.source_file,
        "request_index": request.request_index,
        "raw_request_sha256": request.raw_request_sha256,
        "source_label": request.source_label,
        "method": request.method,
        "has_body": bool(request.body_bytes),
        "projection_loss": asdict(loss),
        "selected": selected,
        "score": score,
        "verdict_hint": verdict_hint,
        "reason_hints": sorted(reason_hints or []),
        "filtered_reasons": sorted(filtered_reasons or []),
        "filtered_reason_hints": sorted(filtered_reason_hints or []),
        "error_type": error_type,
    }


def _increment(bucket: dict[str, Counter[str]], record: Mapping[str, Any]) -> None:
    group = f"{record['source_label']}:{record['source_file']}"
    combined = str(record["source_label"])
    for key in (group, combined, "overall"):
        values = bucket.setdefault(key, Counter())
        values["total"] += 1
        values["selected"] += int(bool(record["selected"]))
        values["suppressed"] += int(not record["selected"])
        values["failures"] += int(record["error_type"] is not None)


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _metric_group(counter: Mapping[str, int]) -> dict[str, Any]:
    total = int(counter.get("total", 0))
    selected = int(counter.get("selected", 0))
    return {"total": total, "selected": selected, "suppressed": int(counter.get("suppressed", 0)), "candidate_rate": _rate(selected, total), "suppression_rate": _rate(int(counter.get("suppressed", 0)), total), "failures": int(counter.get("failures", 0))}


def _distribution(records: Iterable[Mapping[str, Any]], *, key: str, selected_only: bool = False) -> dict[str, dict[str, int]]:
    result: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        if selected_only and not record["selected"]:
            continue
        values = record.get(key)
        if isinstance(values, list):
            labels = values or ["<none>"]
        else:
            labels = [values if values is not None else "<none>"]
        for label in labels:
            result[str(record["source_label"])][str(label)] += 1
    return {label: dict(sorted(counter.items())) for label, counter in sorted(result.items())}


def _method_body_breakdown(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    method: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    body: dict[tuple[str, bool], Counter[str]] = defaultdict(Counter)
    for record in records:
        for bucket in (method[(str(record["source_label"]), str(record["method"]))], body[(str(record["source_label"]), bool(record["has_body"]))]):
            bucket["total"] += 1
            bucket["selected"] += int(bool(record["selected"]))
    return {
        "method": [{"source_label": label, "method": name, "total": values["total"], "selected": values["selected"], "candidate_rate": _rate(values["selected"], values["total"])} for (label, name), values in sorted(method.items())],
        "body": [{"source_label": label, "has_body": present, "total": values["total"], "selected": values["selected"], "candidate_rate": _rate(values["selected"], values["total"])} for (label, present), values in sorted(body.items())],
    }


def run_prepare_pass(cache_dir: Path, index_path: Path) -> dict[str, Any]:
    """Validate frozen source, then stream one isolated Prepare call per request."""

    manifest_path = Path("benchmarks/manifests/csic2010_source.v1.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {item["filename"]: item for item in manifest["canonical_acquisition"]["files"]}
    preflight: list[dict[str, Any]] = []
    for spec in FILE_SPECS:
        filename = str(spec["filename"])
        path = cache_dir / "primary" / filename
        facts = scan_source_file(path, source_label=str(spec["source_label"]))
        locked = expected.get(filename, {})
        if facts["byte_size"] != locked.get("byte_size") or facts["sha256"] != locked.get("sha256") or facts["parsed_requests"] != locked.get("parsed_request_count") or facts["parse_error_count"] != 0 or facts["byte_consumption"]["unaccounted_bytes"] != 0:
            raise ValueError(f"frozen source gate failed for {filename}")
        preflight.append({"filename": filename, "byte_size": facts["byte_size"], "sha256": facts["sha256"], "parsed_requests": facts["parsed_requests"]})

    counters: dict[str, Counter[str]] = {}
    records_for_distributions: list[dict[str, Any]] = []
    projection_loss = Counter()
    errors: list[dict[str, Any]] = []
    with index_path.open("w", encoding="utf-8") as output:
        for spec in FILE_SPECS:
            filename = str(spec["filename"])
            source_label = str(spec["source_label"])
            source_path = cache_dir / "primary" / filename
            with source_path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
                def evaluate(request: RawHttpRequest) -> None:
                    record = evaluate_isolated_request(request)
                    _increment(counters, record)
                    records_for_distributions.append(record)
                    for key, value in record["projection_loss"].items():
                        projection_loss[key] += int(bool(value))
                    if record["error_type"]:
                        errors.append({key: record[key] for key in ("source_file", "request_index", "raw_request_sha256", "error_type")})
                    output.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                parse_raw_http_stream(data, source_file=filename, source_label=source_label, on_request=evaluate)

    normal = _metric_group(counters["source_normal"])
    anomalous = _metric_group(counters["source_anomalous"])
    selected_total = normal["selected"] + anomalous["selected"]
    metrics = {
        "source_normal_candidate_rate": normal["candidate_rate"],
        "source_normal_suppression_rate": normal["suppression_rate"],
        "source_anomalous_candidate_rate": anomalous["candidate_rate"],
        "source_anomalous_suppression_rate": anomalous["suppression_rate"],
        "candidate_anomaly_proportion": _rate(anomalous["selected"], selected_total),
        "selection_rate_ratio": (anomalous["candidate_rate"] / normal["candidate_rate"] if normal["candidate_rate"] else None),
    }
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "complete": not errors,
        "dataset": DATASET_NAME,
        "source_manifest": {"path": str(manifest_path), "schema_version": manifest["schema_version"], "files": preflight},
        "production_revision": _git_head(),
        "evaluation_mode": "production_prepare_only",
        "isolation_policy": "one parsed request -> one projected security row -> one build_outputs invocation; no corpus order semantics",
        "projection_policy": {"schema_version": PROJECTION_SCHEMA_VERSION, "raw_request_is_request_line_only": True, "body_omitted": True, "cookie_values_omitted": True, "authorization_values_omitted": True, "arbitrary_unlogged_headers_omitted": True, "neutral_response_metadata": {"status_code": 200, "response_body_bytes": 0, "resp_content_type": "", "duration_us": 0, "ttfb_us": 0}},
        "accounting": {"parsed": sum(item["parsed_requests"] for item in preflight), "projected": len(records_for_distributions), "prepare_evaluated": len(records_for_distributions), "evaluation_failures": len(errors), "errors": errors, "projection_loss": dict(sorted(projection_loss.items()))},
        "groups": {key: _metric_group(value) for key, value in sorted(counters.items())},
        "metrics": metrics,
        "breakdowns": _method_body_breakdown(records_for_distributions),
        "distributions": {"selected_verdict_hints": _distribution(records_for_distributions, key="verdict_hint", selected_only=True), "selected_reason_hints": _distribution(records_for_distributions, key="reason_hints", selected_only=True), "scores": _distribution(records_for_distributions, key="score"), "filtered_reasons": _distribution(records_for_distributions, key="filtered_reasons")},
        "review_pools": {"selected_source_normal": normal["selected"], "selected_source_anomalous": anomalous["selected"], "suppressed_source_anomalous": anomalous["suppressed"]},
        "artifacts": {"request_index": str(index_path)},
    }


def _git_head() -> str:
    head = Path(".git/HEAD")
    if not head.is_file():
        return "unknown"
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        return Path(".git", value[5:]).read_text(encoding="utf-8").strip()
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_result_contract(result: Mapping[str, Any]) -> list[str]:
    required = {"schema_version", "complete", "dataset", "source_manifest", "production_revision", "evaluation_mode", "isolation_policy", "projection_policy", "accounting", "groups", "metrics", "breakdowns", "distributions", "review_pools", "artifacts"}
    errors: list[str] = []
    if set(result) != required or result.get("schema_version") != RESULT_SCHEMA_VERSION or result.get("dataset") != DATASET_NAME:
        errors.append("invalid result root")
    accounting = result.get("accounting", {})
    if not isinstance(accounting, Mapping) or not all(isinstance(accounting.get(key), int) for key in ("parsed", "projected", "prepare_evaluated", "evaluation_failures")):
        errors.append("invalid accounting")
    if result.get("complete") and accounting.get("parsed") != 97065:
        errors.append("complete result must account for the frozen corpus")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run isolated production Prepare over local CSIC source bytes")
    parser.add_argument("--cache-dir", type=Path, default=Path("benchmarks/cache/csic2010"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-index", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_prepare_pass(args.cache_dir, args.output_index)
        result["artifacts"]["request_index_sha256"] = hashlib.sha256(args.output_index.read_bytes()).hexdigest()
        errors = validate_result_contract(result)
        if errors:
            raise ValueError("; ".join(errors))
        _write_json(args.output, result)
        print(f"complete={str(result['complete']).lower()} parsed={result['accounting']['parsed']} evaluated={result['accounting']['prepare_evaluated']} failures={result['accounting']['evaluation_failures']}")
        print(f"index={args.output_index} sha256={result['artifacts']['request_index_sha256']}")
        print(f"output={args.output} sha256={hashlib.sha256(args.output.read_bytes()).hexdigest()}")
        return 0 if result["complete"] else 1
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
