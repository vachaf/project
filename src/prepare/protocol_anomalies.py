from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import unquote_plus

PROTOCOL_ANOMALY_WINDOW_SEC = 300
PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT = 10
PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN = 512


def _normalize_text(value: Optional[Any]) -> str:
    if value is None:
        return ""
    return unquote_plus(str(value)).strip()


def _raw_text(value: Optional[Any]) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _append_unique_hint(hints: List[str], hint: str) -> None:
    text = _raw_text(hint)
    if text and text not in hints:
        hints.append(text)


def _extend_unique_hints(hints: List[str], extra_hints: Iterable[str]) -> None:
    for hint in extra_hints:
        _append_unique_hint(hints, hint)


def _safe_int(value: Optional[Any], default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_flexible_iso_dt(text: str) -> Optional[datetime]:
    raw = _normalize_text(text)
    if not raw:
        return None
    candidates = [raw]
    if raw.endswith(" 09:00") or raw.endswith(" 00:00"):
        candidates.append(raw[:-6] + "+" + raw[-5:])
    if " " in raw and raw.count(":") >= 3 and "+" not in raw and raw[-6:-5] == " ":
        candidates.append(raw[:-6] + "+" + raw[-5:])
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


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


def _get_uri(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("uri"))


def _extract_raw_request_target(raw_request: str) -> str:
    raw = "" if raw_request is None else str(raw_request).strip()
    if not raw:
        return ""

    first_space = raw.find(" ")
    if first_space == -1:
        return ""

    http_marker = raw.rfind(" HTTP/")
    if http_marker == -1:
        target = raw[first_space + 1 :]
    else:
        target = raw[first_space + 1 : http_marker]

    return target.strip()


def _path_from_target(target: str) -> str:
    value = _normalize_text(target)
    if not value:
        return ""
    return value.split("?", 1)[0]


def _get_effective_request_path(uri: str, raw_request_target: str) -> str:
    normalized_raw_path = _path_from_target(raw_request_target)
    return normalized_raw_path or _normalize_text(uri)


def _get_row_protocol_value(row: Dict[str, Any]) -> str:
    protocol = _normalize_text(row.get("protocol"))
    if protocol:
        return protocol.upper()

    raw_request = _raw_text(row.get("raw_request"))
    parts = raw_request.split()
    if len(parts) >= 3 and parts[-1].upper().startswith("HTTP/"):
        return parts[-1].upper()
    return ""


def _get_row_host_value(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("host")) or _normalize_text(row.get("request_host"))


def _is_valid_host_header_value(host: str) -> bool:
    normalized = _normalize_text(host).strip("[]")
    if not normalized:
        return False
    if normalized.lower() == "localhost":
        return True
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", normalized):
        octets = normalized.split(".")
        return all(0 <= _safe_int(octet, -1) <= 255 for octet in octets)
    if ":" in normalized and normalized.count(":") >= 2:
        return bool(re.fullmatch(r"[0-9a-fA-F:]+", normalized))
    if ".." in normalized:
        return False
    return bool(
        re.fullmatch(
            r"(?i)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*",
            normalized,
        )
    )


def _get_protocol_anomaly_types_for_row(
    row: Dict[str, Any],
    *,
    long_path_min_len: int,
    standard_http_methods: Iterable[str],
) -> List[str]:
    method = _normalize_text(_get_method(row)).upper()
    protocol = _get_row_protocol_value(row)
    host = _get_row_host_value(row)
    status_code = _get_status_code(row)
    raw_request_target = _extract_raw_request_target(_raw_text(row.get("raw_request")))
    request_path = _get_effective_request_path(_get_uri(row), raw_request_target)

    anomaly_types: List[str] = []

    if (
        not method
        or method == "-"
        or method not in standard_http_methods
        or not re.fullmatch(r"[A-Z!#$%&'*+.^_`|~-]{1,32}", method)
    ):
        _append_unique_hint(anomaly_types, "unsupported_method")

    if protocol == "HTTP/1.0":
        _append_unique_hint(anomaly_types, "http10_request")

    if protocol:
        normalized_protocol = protocol.upper()
        if normalized_protocol.startswith("HTTP/") and normalized_protocol not in {
            "HTTP/1.0",
            "HTTP/1.1",
            "HTTP/2",
            "HTTP/2.0",
            "HTTP/3",
            "HTTP/3.0",
        }:
            _append_unique_hint(anomaly_types, "bad_protocol_version")
        elif not re.fullmatch(r"HTTP/\d(?:\.\d)?", normalized_protocol):
            _append_unique_hint(anomaly_types, "bad_protocol_version")

    if protocol == "HTTP/1.1" and not host and status_code in {400, 408, 414, 421, 431}:
        _append_unique_hint(anomaly_types, "missing_host")

    if host and not _is_valid_host_header_value(host):
        _append_unique_hint(anomaly_types, "odd_host")

    if len(request_path) >= long_path_min_len:
        _append_unique_hint(anomaly_types, "long_path")

    return anomaly_types


def build_protocol_anomaly_reason_hints_for_row(
    row: Dict[str, Any],
    *,
    include_inference_limit: bool = False,
    long_path_min_len: int,
    standard_http_methods: Iterable[str],
) -> List[str]:
    anomaly_types = _get_protocol_anomaly_types_for_row(
        row,
        long_path_min_len=long_path_min_len,
        standard_http_methods=standard_http_methods,
    )
    if not anomaly_types:
        return []

    hints: List[str] = []
    status_code = _get_status_code(row)

    for anomaly_type in anomaly_types:
        if anomaly_type == "unsupported_method":
            _append_unique_hint(hints, "method_probe:unsupported_method")
            _append_unique_hint(hints, "protocol_anomaly:unsupported_method")
        elif anomaly_type == "http10_request":
            _append_unique_hint(hints, "protocol_anomaly:http10_request")
            _append_unique_hint(hints, "protocol_anomaly:legacy_protocol_observation")
        elif anomaly_type == "bad_protocol_version":
            _append_unique_hint(hints, "protocol_anomaly:bad_protocol_version")
        elif anomaly_type == "missing_host":
            _append_unique_hint(hints, "protocol_anomaly:missing_host")
        elif anomaly_type == "odd_host":
            _append_unique_hint(hints, "protocol_anomaly:odd_host")
        elif anomaly_type == "long_path":
            _append_unique_hint(hints, "protocol_anomaly:long_path")

    if (
        status_code in {400, 408, 414, 501, 505}
        and any(anomaly in {"missing_host", "bad_protocol_version", "unsupported_method", "long_path"} for anomaly in anomaly_types)
    ):
        _append_unique_hint(hints, "protocol_anomaly:malformed_request")

    if include_inference_limit:
        _append_unique_hint(hints, "protocol_anomaly:no_success_inference")
    return hints


def finalize_protocol_anomaly_bucket(
    items: List[Dict[str, Any]],
    *,
    window_sec: int,
    sample_request_limit: int,
    long_path_min_len: int,
    standard_http_methods: Iterable[str],
) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    sorted_items = sorted(items, key=lambda item: item["dt"])
    method_counts = Counter(_normalize_text(item.get("method")).upper() or "-" for item in sorted_items)
    status_counts = Counter(str(_safe_int(item.get("status_code"), 0)) for item in sorted_items)
    anomaly_types_observed: List[str] = []
    sample_request_ids: List[str] = []
    reason_hints: List[str] = []

    for item in sorted_items:
        _extend_unique_hints(anomaly_types_observed, item.get("anomaly_types") or [])
        _extend_unique_hints(
            reason_hints,
            build_protocol_anomaly_reason_hints_for_row(
                item,
                include_inference_limit=False,
                long_path_min_len=long_path_min_len,
                standard_http_methods=standard_http_methods,
            ),
        )
        sample_request_id = _normalize_text(item.get("sample_request_id"))
        if sample_request_id and len(sample_request_ids) < sample_request_limit:
            _append_unique_hint(sample_request_ids, sample_request_id)

    if not anomaly_types_observed:
        return None

    _append_unique_hint(reason_hints, "protocol_anomaly:no_success_inference")
    return {
        "context_role": "protocol_anomaly_context",
        "aggregate_scope": "same_src_ip_protocol_anomaly_time_window",
        "should_promote_to_candidate": False,
        "src_ip": _normalize_text(sorted_items[0].get("src_ip")) or "-",
        "window_start": _normalize_text(sorted_items[0].get("log_time")),
        "window_end": _normalize_text(sorted_items[-1].get("log_time")),
        "burst_window_sec": window_sec,
        "request_count": len(sorted_items),
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (_safe_int(kv[0], 0), kv[0]))),
        "method_counts": dict(sorted(method_counts.items(), key=lambda kv: (-_safe_int(kv[1]), kv[0]))),
        "anomaly_types_observed": anomaly_types_observed,
        "sample_request_ids": sample_request_ids,
        "reason_hints": reason_hints,
        "interpretation_limit": "protocol_anomaly_context_only_no_success_inference",
    }


def build_protocol_anomaly_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int,
    *,
    sample_request_limit: int,
    long_path_min_len: int,
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

        anomaly_types = _get_protocol_anomaly_types_for_row(
            row,
            long_path_min_len=long_path_min_len,
            standard_http_methods=standard_http_methods,
        )
        if not anomaly_types:
            continue

        rows_by_ip[src_ip].append(
            {
                "src_ip": src_ip,
                "log_time": log_time,
                "dt": dt,
                "method": _get_method(row),
                "status_code": _get_status_code(row),
                "sample_request_id": _get_sample_request_id(row),
                "anomaly_types": anomaly_types,
                "protocol": _get_row_protocol_value(row),
                "host": _get_row_host_value(row),
                "uri": _get_uri(row),
                "raw_request": _raw_text(row.get("raw_request")),
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

            summary = finalize_protocol_anomaly_bucket(
                bucket,
                window_sec=window_sec,
                sample_request_limit=sample_request_limit,
                long_path_min_len=long_path_min_len,
                standard_http_methods=standard_http_methods,
            )
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = finalize_protocol_anomaly_bucket(
            bucket,
            window_sec=window_sec,
            sample_request_limit=sample_request_limit,
            long_path_min_len=long_path_min_len,
            standard_http_methods=standard_http_methods,
        )
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            _safe_int(item.get("request_count"), 0),
            len(item.get("anomaly_types_observed") or []),
            _normalize_text(item.get("window_start")),
        ),
        reverse=True,
    )
    return summaries


def build_protocol_anomaly_summary_contexts(
    protocol_anomaly_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    for summary in protocol_anomaly_summaries:
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
