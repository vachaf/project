from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import unquote_plus


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


def _safe_int(value: Optional[Any], default: int = 0) -> int:
    if value is None:
        return default
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
    return _normalize_text(row.get("src_ip")) or _normalize_text(row.get("client_ip")) or "-"


def _get_status_code(row: Dict[str, Any]) -> int:
    return _safe_int(row.get("status_code") or row.get("status") or row.get("response_status"), 0)


def _get_method(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("method")) or "-"


def _get_user_agent(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("user_agent")) or _normalize_text(row.get("http_user_agent"))


def _get_sample_request_id(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("request_id")) or _normalize_text(row.get("error_link_id"))


def _choose_best_time(row: Dict[str, Any]) -> Optional[str]:
    return _normalize_text(row.get("log_time")) or _normalize_text(row.get("created_at")) or None


def _get_uri(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("uri")) or _normalize_text(row.get("request_uri"))


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


def is_sensitive_ip_behavior_path(
    path: str,
    *,
    get_probe_sequence_reason_hints_fn: Optional[Callable[[str], List[str]]] = None,
) -> bool:
    if get_probe_sequence_reason_hints_fn is None:
        return False

    hints = get_probe_sequence_reason_hints_fn(path)
    return any(
        hint in {"dir_probe:sensitive_path", "dir_probe:sensitive_config_path", "dir_probe:admin_path"}
        or hint.startswith("file_probe:")
        for hint in hints
    )


def finalize_ip_behavior_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
    *,
    sample_request_limit: int = 10,
    sensitive_path_limit: int = 10,
    normalize_text_fn: Callable[[Optional[Any]], str] = _normalize_text,
    safe_int_fn: Callable[[Optional[Any], int], int] = _safe_int,
    append_unique_hint_fn: Callable[[List[str], str], None] = _append_unique_hint,
    get_attack_categories_from_reason_hints_fn: Optional[Callable[[Iterable[str]], List[str]]] = None,
) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    request_count = len(items)

    distinct_paths: List[str] = []
    seen_paths = set()
    distinct_methods: List[str] = []
    seen_methods = set()
    distinct_user_agents = set()
    attack_categories_attempted: List[str] = []
    sensitive_path_hits: List[str] = []
    sample_request_ids: List[str] = []

    status_4xx_count = 0
    status_5xx_count = 0

    for item in items:
        path = normalize_text_fn(item.get("path")).lower()
        if path and path not in seen_paths:
            seen_paths.add(path)
            distinct_paths.append(path)

        method = normalize_text_fn(item.get("method")).upper()
        if method and method not in seen_methods:
            seen_methods.add(method)
            distinct_methods.append(method)

        user_agent = normalize_text_fn(item.get("user_agent"))
        if user_agent:
            distinct_user_agents.add(user_agent)

        status_code = safe_int_fn(item.get("status_code"), 0)
        if 400 <= status_code < 500:
            status_4xx_count += 1
        if 500 <= status_code < 600:
            status_5xx_count += 1

        if get_attack_categories_from_reason_hints_fn is not None:
            for category in get_attack_categories_from_reason_hints_fn(item.get("reason_hints") or []):
                append_unique_hint_fn(attack_categories_attempted, category)

        if path and bool(item.get("is_sensitive_path")) and len(sensitive_path_hits) < sensitive_path_limit:
            append_unique_hint_fn(sensitive_path_hits, path)

        sample_request_id = normalize_text_fn(item.get("sample_request_id"))
        if sample_request_id and len(sample_request_ids) < sample_request_limit:
            append_unique_hint_fn(sample_request_ids, sample_request_id)

    status_4xx_ratio = round(status_4xx_count / request_count, 4) if request_count else 0.0
    reason_hints: List[str] = []
    if request_count >= 5 and len(distinct_paths) >= 4:
        append_unique_hint_fn(reason_hints, "ip_behavior:multi_path_burst")
    if request_count >= 4 and status_4xx_ratio >= 0.5:
        append_unique_hint_fn(reason_hints, "ip_behavior:high_4xx_ratio")
    if len(attack_categories_attempted) >= 2:
        append_unique_hint_fn(reason_hints, "ip_behavior:multiple_attack_categories")
    if len(sensitive_path_hits) >= 2:
        append_unique_hint_fn(reason_hints, "ip_behavior:sensitive_path_focus")
    if status_5xx_count >= 2:
        append_unique_hint_fn(reason_hints, "ip_behavior:server_error_cluster")

    if not reason_hints:
        return None

    sorted_items = sorted(items, key=lambda item: item["dt"])
    return {
        "context_role": "ip_behavior_context",
        "aggregate_scope": "same_src_ip_time_window",
        "should_promote_to_candidate": False,
        "src_ip": normalize_text_fn(sorted_items[0].get("src_ip")) or "-",
        "window_start": normalize_text_fn(sorted_items[0].get("log_time")),
        "window_end": normalize_text_fn(sorted_items[-1].get("log_time")),
        "burst_window_sec": window_sec,
        "request_count": request_count,
        "distinct_paths": len(distinct_paths),
        "distinct_methods": len(distinct_methods),
        "status_4xx_count": status_4xx_count,
        "status_4xx_ratio": status_4xx_ratio,
        "status_5xx_count": status_5xx_count,
        "distinct_user_agents": len(distinct_user_agents),
        "attack_categories_attempted": attack_categories_attempted,
        "sensitive_path_hits": sensitive_path_hits,
        "sample_request_ids": sample_request_ids,
        "reason_hints": reason_hints,
        "interpretation_limit": "context_only_no_success_inference",
    }


def build_ip_behavior_aggregates(
    rows: List[Dict[str, Any]],
    window_sec: int = 300,
    *,
    sample_request_limit: int = 10,
    sensitive_path_limit: int = 10,
    get_src_ip_fn: Callable[[Dict[str, Any]], str] = _get_src_ip,
    choose_best_time_fn: Callable[[Dict[str, Any]], Optional[str]] = _choose_best_time,
    parse_flexible_iso_dt_fn: Callable[[str], Optional[datetime]] = _parse_flexible_iso_dt,
    get_uri_fn: Callable[[Dict[str, Any]], str] = _get_uri,
    raw_text_fn: Callable[[Optional[Any]], str] = _raw_text,
    extract_raw_request_target_fn: Callable[[str], str] = _extract_raw_request_target,
    get_effective_request_path_fn: Callable[[str, str], str] = _get_effective_request_path,
    get_method_fn: Callable[[Dict[str, Any]], str] = _get_method,
    get_status_code_fn: Callable[[Dict[str, Any]], int] = _get_status_code,
    get_user_agent_fn: Callable[[Dict[str, Any]], str] = _get_user_agent,
    get_sample_request_id_fn: Callable[[Dict[str, Any]], str] = _get_sample_request_id,
    build_row_context_reason_hints_fn: Optional[Callable[[Dict[str, Any]], List[str]]] = None,
    is_sensitive_ip_behavior_path_fn: Callable[..., bool] = is_sensitive_ip_behavior_path,
    finalize_ip_behavior_bucket_fn: Callable[..., Optional[Dict[str, Any]]] = finalize_ip_behavior_bucket,
    normalize_text_fn: Callable[[Optional[Any]], str] = _normalize_text,
    get_probe_sequence_reason_hints_fn: Optional[Callable[[str], List[str]]] = None,
    get_attack_categories_from_reason_hints_fn: Optional[Callable[[Iterable[str]], List[str]]] = None,
    append_unique_hint_fn: Callable[[List[str], str], None] = _append_unique_hint,
    safe_int_fn: Callable[[Optional[Any], int], int] = _safe_int,
) -> List[Dict[str, Any]]:
    rows_by_ip: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        src_ip = get_src_ip_fn(row)
        if not src_ip or src_ip == "-":
            continue

        log_time = choose_best_time_fn(row)
        dt = parse_flexible_iso_dt_fn(log_time or "")
        if dt is None:
            continue

        uri = get_uri_fn(row)
        raw_request_target = extract_raw_request_target_fn(raw_text_fn(row.get("raw_request")))
        path = get_effective_request_path_fn(uri, raw_request_target).lower()
        rows_by_ip[src_ip].append(
            {
                "src_ip": src_ip,
                "log_time": log_time,
                "dt": dt,
                "path": path,
                "method": get_method_fn(row),
                "status_code": get_status_code_fn(row),
                "user_agent": get_user_agent_fn(row),
                "sample_request_id": get_sample_request_id_fn(row),
                "reason_hints": build_row_context_reason_hints_fn(row) if build_row_context_reason_hints_fn is not None else [],
                "is_sensitive_path": is_sensitive_ip_behavior_path_fn(
                    path,
                    get_probe_sequence_reason_hints_fn=get_probe_sequence_reason_hints_fn,
                ),
            }
        )

    aggregates: List[Dict[str, Any]] = []
    for _src_ip, items in rows_by_ip.items():
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

            aggregate = finalize_ip_behavior_bucket_fn(
                bucket,
                window_sec=window_sec,
                sample_request_limit=sample_request_limit,
                sensitive_path_limit=sensitive_path_limit,
                normalize_text_fn=normalize_text_fn,
                safe_int_fn=safe_int_fn,
                append_unique_hint_fn=append_unique_hint_fn,
                get_attack_categories_from_reason_hints_fn=get_attack_categories_from_reason_hints_fn,
            )
            if aggregate:
                aggregates.append(aggregate)
            bucket = [item]
            bucket_start = item["dt"]

        aggregate = finalize_ip_behavior_bucket_fn(
            bucket,
            window_sec=window_sec,
            sample_request_limit=sample_request_limit,
            sensitive_path_limit=sensitive_path_limit,
            normalize_text_fn=normalize_text_fn,
            safe_int_fn=safe_int_fn,
            append_unique_hint_fn=append_unique_hint_fn,
            get_attack_categories_from_reason_hints_fn=get_attack_categories_from_reason_hints_fn,
        )
        if aggregate:
            aggregates.append(aggregate)

    aggregates.sort(
        key=lambda item: (
            safe_int_fn(item.get("request_count"), 0),
            len(item.get("attack_categories_attempted") or []),
            safe_int_fn(item.get("distinct_paths"), 0),
            normalize_text_fn(item.get("window_start")),
        ),
        reverse=True,
    )
    return aggregates
