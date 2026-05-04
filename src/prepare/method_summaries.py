from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

METHOD_BEHAVIOR_WINDOW_SEC = 300
METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
METHOD_RISKY_FAMILIES = ("OPTIONS", "TRACE", "PUT", "DELETE", "PATCH")
METHOD_BASELINE_FAMILIES = ("GET", "HEAD")
METHOD_DESTRUCTIVE_FAMILIES = {"PUT", "DELETE", "PATCH"}


def _normalize_text(value: Optional[Any]) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _raw_text(value: Optional[Any]) -> str:
    return "" if value is None else str(value)


def _append_unique_hint(hints: List[str], hint: str) -> None:
    if hint and hint not in hints:
        hints.append(hint)


def _extend_unique_hints(hints: List[str], extra_hints: Iterable[str]) -> None:
    for hint in extra_hints:
        _append_unique_hint(hints, hint)


def _safe_int(value: Optional[Any], default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_flexible_iso_dt(text: str) -> Optional[datetime]:
    value = _normalize_text(text)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _classify_method_behavior_family(
    method: str,
    *,
    method_risky_families: Iterable[str],
    method_baseline_families: Iterable[str],
    standard_http_methods: Iterable[str],
) -> str:
    normalized = _normalize_text(method).upper()
    if not normalized or normalized == "-":
        return "unknown"
    if normalized in method_risky_families:
        return "risky"
    if normalized in method_baseline_families:
        return "baseline"
    if normalized not in standard_http_methods:
        return "unknown"
    return "other"


def _has_method_protocol_anomaly(
    row: Dict[str, Any],
    method: str,
) -> bool:
    normalized_method = _normalize_text(method).upper()
    if not normalized_method or normalized_method == "-":
        return True
    if not re.fullmatch(r"[A-Z!#$%&'*+.^_`|~-]{1,32}", normalized_method):
        return True

    protocol = _normalize_text(row.get("protocol"))
    if protocol and not re.fullmatch(r"HTTP/\d(?:\.\d)?", protocol, re.IGNORECASE):
        return True
    return False


def _get_src_ip(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("src_ip")) or _normalize_text(row.get("peer_ip")) or "-"


def _get_status_code(row: Dict[str, Any]) -> int:
    return _safe_int(row.get("status_code"), 0)


def _get_method(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("method")).upper()


def _get_sample_request_id(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("request_id")) or _normalize_text(row.get("error_link_id"))


def _choose_best_time(row: Dict[str, Any]) -> Optional[str]:
    for key in ("log_time", "created_at"):
        text = _normalize_text(row.get(key))
        if text:
            return text
    return None


def build_method_behavior_reason_hints_for_row(
    row: Dict[str, Any],
    *,
    include_inference_limit: bool = False,
    method_destructive_families: Iterable[str],
    method_risky_families: Iterable[str],
    method_baseline_families: Iterable[str],
    standard_http_methods: Iterable[str],
) -> List[str]:
    method = _get_method(row)
    family = _classify_method_behavior_family(
        method,
        method_risky_families=method_risky_families,
        method_baseline_families=method_baseline_families,
        standard_http_methods=standard_http_methods,
    )
    hints: List[str] = []
    normalized_method = _normalize_text(method).upper()

    if family == "risky":
        method_hint = {
            "OPTIONS": "method_probe:options",
            "TRACE": "method_probe:trace",
            "PUT": "method_probe:put",
            "DELETE": "method_probe:delete",
            "PATCH": "method_probe:patch",
        }.get(normalized_method)
        if method_hint:
            _append_unique_hint(hints, method_hint)
        if normalized_method in method_destructive_families:
            _append_unique_hint(hints, "method_probe:destructive_method")
    elif family == "baseline":
        baseline_hint = {
            "HEAD": "baseline:normal_head",
            "GET": "baseline:normal_get",
        }.get(normalized_method)
        if baseline_hint:
            _append_unique_hint(hints, baseline_hint)
    elif family == "unknown" or _has_method_protocol_anomaly(row, normalized_method):
        _append_unique_hint(hints, "method_probe:unsupported_method")

    if include_inference_limit and hints:
        _append_unique_hint(hints, "method_probe:no_method_success_inference")
    return hints


def _finalize_method_behavior_bucket(
    items: List[Dict[str, Any]],
    *,
    window_sec: int,
    sample_request_limit: int,
    method_destructive_families: Iterable[str],
    method_risky_families: Iterable[str],
    method_baseline_families: Iterable[str],
    standard_http_methods: Iterable[str],
) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    sorted_items = sorted(items, key=lambda item: item["dt"])
    method_counts = Counter(_normalize_text(item.get("method")).upper() or "-" for item in sorted_items)
    status_counts = Counter(str(_safe_int(item.get("status_code"), 0)) for item in sorted_items)

    risky_methods_observed: List[str] = []
    baseline_methods_observed: List[str] = []
    sample_request_ids: List[str] = []
    unsupported_method_observed = False
    protocol_anomaly_observed = False

    for item in sorted_items:
        method = _normalize_text(item.get("method")).upper() or "-"
        family = _raw_text(item.get("method_family"))
        if family == "risky":
            _append_unique_hint(risky_methods_observed, method)
        elif family == "baseline":
            _append_unique_hint(baseline_methods_observed, method)
        elif family == "unknown":
            unsupported_method_observed = True

        if bool(item.get("protocol_anomaly")):
            protocol_anomaly_observed = True

        sample_request_id = _normalize_text(item.get("sample_request_id"))
        if sample_request_id and len(sample_request_ids) < sample_request_limit:
            _append_unique_hint(sample_request_ids, sample_request_id)

    should_emit = any(
        (
            len(risky_methods_observed) >= 2,
            bool(risky_methods_observed) and bool(baseline_methods_observed),
            unsupported_method_observed,
            protocol_anomaly_observed,
        )
    )
    if not should_emit:
        return None

    reason_hints: List[str] = []
    for item in sorted_items:
        _extend_unique_hints(
            reason_hints,
            build_method_behavior_reason_hints_for_row(
                item,
                include_inference_limit=False,
                method_destructive_families=method_destructive_families,
                method_risky_families=method_risky_families,
                method_baseline_families=method_baseline_families,
                standard_http_methods=standard_http_methods,
            ),
        )
    if len(method_counts) >= 2:
        _append_unique_hint(reason_hints, "method_probe:mixed_method_sequence")
    _append_unique_hint(reason_hints, "method_probe:no_method_success_inference")

    return {
        "context_role": "method_behavior_context",
        "aggregate_scope": "same_src_ip_method_time_window",
        "should_promote_to_candidate": False,
        "src_ip": _normalize_text(sorted_items[0].get("src_ip")) or "-",
        "window_start": _normalize_text(sorted_items[0].get("log_time")),
        "window_end": _normalize_text(sorted_items[-1].get("log_time")),
        "burst_window_sec": window_sec,
        "request_count": len(sorted_items),
        "method_counts": dict(sorted(method_counts.items(), key=lambda kv: (-_safe_int(kv[1]), kv[0]))),
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (-_safe_int(kv[1]), kv[0]))),
        "risky_methods_observed": risky_methods_observed,
        "baseline_methods_observed": baseline_methods_observed,
        "sample_request_ids": sample_request_ids,
        "reason_hints": reason_hints,
        "interpretation_limit": "no_method_success_inference_from_apache_logs",
    }


def build_method_behavior_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = 300,
    *,
    sample_request_limit: int = 10,
    method_risky_families: Iterable[str],
    method_baseline_families: Iterable[str],
    method_destructive_families: Iterable[str],
    standard_http_methods: Iterable[str],
) -> List[Dict[str, Any]]:
    rows_by_ip: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        src_ip = _get_src_ip(row)
        if not src_ip or src_ip == "-":
            continue

        log_time = _choose_best_time(row)
        dt = _parse_flexible_iso_dt(log_time or "")
        if dt is None:
            continue

        method = _get_method(row)
        method_family = _classify_method_behavior_family(
            method,
            method_risky_families=method_risky_families,
            method_baseline_families=method_baseline_families,
            standard_http_methods=standard_http_methods,
        )
        protocol_anomaly = _has_method_protocol_anomaly(row, method)
        if method_family == "other" and not protocol_anomaly:
            continue

        rows_by_ip[src_ip].append(
            {
                "src_ip": src_ip,
                "log_time": log_time,
                "dt": dt,
                "method": method,
                "method_family": method_family,
                "status_code": _get_status_code(row),
                "sample_request_id": _get_sample_request_id(row),
                "protocol_anomaly": protocol_anomaly,
            }
        )

    summaries: List[Dict[str, Any]] = []
    for items in rows_by_ip.values():
        sorted_items = sorted(items, key=lambda item: item["dt"])
        bucket: List[Dict[str, Any]] = []
        bucket_start: Optional[datetime] = None
        for item in sorted_items:
            if not bucket:
                bucket = [item]
                bucket_start = item["dt"]
                continue

            if bucket_start is not None and (item["dt"] - bucket_start).total_seconds() <= window_sec:
                bucket.append(item)
                continue

            summary = _finalize_method_behavior_bucket(
                bucket,
                window_sec=window_sec,
                sample_request_limit=sample_request_limit,
                method_destructive_families=method_destructive_families,
                method_risky_families=method_risky_families,
                method_baseline_families=method_baseline_families,
                standard_http_methods=standard_http_methods,
            )
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = _finalize_method_behavior_bucket(
            bucket,
            window_sec=window_sec,
            sample_request_limit=sample_request_limit,
            method_destructive_families=method_destructive_families,
            method_risky_families=method_risky_families,
            method_baseline_families=method_baseline_families,
            standard_http_methods=standard_http_methods,
        )
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            _safe_int(item.get("request_count"), 0),
            len(item.get("risky_methods_observed") or []),
            len(item.get("baseline_methods_observed") or []),
            _normalize_text(item.get("window_start")),
        ),
        reverse=True,
    )
    return summaries


def build_method_behavior_summary_contexts(
    method_behavior_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    for summary in method_behavior_summaries:
        src_ip = _normalize_text(summary.get("src_ip"))
        window_start = _normalize_text(summary.get("window_start"))
        window_end = _normalize_text(summary.get("window_end"))
        start_dt = _parse_flexible_iso_dt(window_start)
        end_dt = _parse_flexible_iso_dt(window_end)
        if not src_ip or start_dt is None or end_dt is None:
            continue
        contexts.append(
            {
                "src_ip": src_ip,
                "start_dt": start_dt,
                "end_dt": end_dt,
            }
        )
    return contexts
