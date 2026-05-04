from __future__ import annotations

from collections import Counter, defaultdict
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


def _extend_unique_hints(hints: List[str], extra_hints: Iterable[str]) -> None:
    for hint in extra_hints:
        _append_unique_hint(hints, hint)


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


def classify_sensitive_path_probe_category(path: str, method: str) -> str:
    normalized_method = _normalize_text(method).upper()
    normalized_path = _normalize_text(path).lower()
    if normalized_method not in {"GET", "HEAD", "OPTIONS"} or not normalized_path:
        return ""

    if normalized_path == "/wp-login.php":
        return "wp_login"
    if normalized_path == "/wp-admin/" or normalized_path.startswith("/wp-admin/"):
        return "wp_admin"
    if normalized_path == "/.env" or normalized_path.endswith("/.env"):
        return "env_file"
    if normalized_path == "/phpinfo.php":
        return "phpinfo"
    if normalized_path == "/server-status" or normalized_path.startswith("/server-status/"):
        return "server_status"
    if normalized_path == "/backup.zip":
        return "backup_artifact"
    if normalized_path == "/config.php":
        return "config_php"
    if normalized_path == "/admin/config.php":
        return "admin_config_php"
    if normalized_path == "/backup/" or normalized_path.startswith("/backup/"):
        return "backup_directory"
    if normalized_path == "/admin/" or normalized_path.startswith("/admin/"):
        return "admin_directory"
    return ""


def finalize_sensitive_path_probe_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
    *,
    sample_request_limit: int = 10,
) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    sorted_items = sorted(items, key=lambda item: item["dt"])
    status_counts = Counter(str(_safe_int(item.get("status_code"), 0)) for item in sorted_items)
    path_counts = Counter(_normalize_text(item.get("path")).lower() for item in sorted_items if _normalize_text(item.get("path")))
    path_categories_observed: List[str] = []
    sample_request_ids: List[str] = []
    reason_hints: List[str] = []
    errorish_status_observed = False

    for item in sorted_items:
        path_category = _normalize_text(item.get("path_category"))
        if path_category:
            _append_unique_hint(path_categories_observed, path_category)

        _extend_unique_hints(reason_hints, item.get("reason_hints") or [])

        status_code = _safe_int(item.get("status_code"), 0)
        if status_code in {403, 404, 500}:
            errorish_status_observed = True

        sample_request_id = _normalize_text(item.get("sample_request_id"))
        if sample_request_id and len(sample_request_ids) < sample_request_limit:
            _append_unique_hint(sample_request_ids, sample_request_id)

    repeated_path_observed = any(count >= 2 for count in path_counts.values())
    should_emit = any(
        (
            len(path_categories_observed) >= 2,
            repeated_path_observed,
            errorish_status_observed,
        )
    )
    if not should_emit:
        return None

    if repeated_path_observed or len(sorted_items) >= 3:
        _append_unique_hint(reason_hints, "sensitive_path:repeated_sensitive_path_sequence")
    _append_unique_hint(reason_hints, "sensitive_path:no_app_presence_inference")
    _append_unique_hint(reason_hints, "sensitive_path:no_admin_access_inference")
    _append_unique_hint(reason_hints, "sensitive_path:no_file_exposure_inference")
    _append_unique_hint(reason_hints, "sensitive_path:no_phpinfo_exposure_inference")
    _append_unique_hint(reason_hints, "sensitive_path:no_server_status_exposure_inference")
    _append_unique_hint(reason_hints, "sensitive_path:no_backup_exposure_inference")
    _append_unique_hint(reason_hints, "sensitive_path:no_success_inference")

    return {
        "context_role": "sensitive_path_probe_context",
        "aggregate_scope": "same_src_ip_sensitive_path_time_window",
        "should_promote_to_candidate": False,
        "src_ip": _normalize_text(sorted_items[0].get("src_ip")) or "-",
        "window_start": _normalize_text(sorted_items[0].get("log_time")),
        "window_end": _normalize_text(sorted_items[-1].get("log_time")),
        "burst_window_sec": window_sec,
        "request_count": len(sorted_items),
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (_safe_int(kv[0], 0), kv[0]))),
        "path_categories_observed": path_categories_observed,
        "path_counts": dict(sorted(path_counts.items(), key=lambda kv: (-_safe_int(kv[1]), kv[0]))),
        "sample_request_ids": sample_request_ids,
        "reason_hints": reason_hints,
        "interpretation_limit": "sensitive_path_probe_no_file_or_app_exposure_inference",
    }


def build_sensitive_path_probe_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = 300,
    *,
    sample_request_limit: int = 10,
    get_src_ip_fn: Callable[[Dict[str, Any]], str] = _get_src_ip,
    choose_best_time_fn: Callable[[Dict[str, Any]], Optional[str]] = _choose_best_time,
    parse_flexible_iso_dt_fn: Callable[[str], Optional[datetime]] = _parse_flexible_iso_dt,
    raw_text_fn: Callable[[Optional[Any]], str] = _raw_text,
    extract_raw_request_target_fn: Callable[[str], str] = _extract_raw_request_target,
    get_uri_fn: Callable[[Dict[str, Any]], str] = _get_uri,
    get_effective_request_path_fn: Callable[[str, str], str] = _get_effective_request_path,
    get_method_fn: Callable[[Dict[str, Any]], str] = _get_method,
    classify_sensitive_path_probe_category_fn: Callable[[str, str], str] = classify_sensitive_path_probe_category,
    get_status_code_fn: Callable[[Dict[str, Any]], int] = _get_status_code,
    build_sensitive_path_reason_hints_for_row_fn: Optional[Callable[[Dict[str, Any]], List[str]]] = None,
    get_sample_request_id_fn: Callable[[Dict[str, Any]], str] = _get_sample_request_id,
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

        raw_request_target = extract_raw_request_target_fn(raw_text_fn(row.get("raw_request")))
        path = get_effective_request_path_fn(get_uri_fn(row), raw_request_target).lower()
        path_category = classify_sensitive_path_probe_category_fn(path, get_method_fn(row))
        if not path_category:
            continue

        reason_hints = []
        if build_sensitive_path_reason_hints_for_row_fn is not None:
            reason_hints = build_sensitive_path_reason_hints_for_row_fn(row)

        rows_by_ip[src_ip].append(
            {
                "src_ip": src_ip,
                "log_time": log_time,
                "dt": dt,
                "path": path,
                "path_category": path_category,
                "status_code": get_status_code_fn(row),
                "reason_hints": reason_hints,
                "sample_request_id": get_sample_request_id_fn(row),
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

            summary = finalize_sensitive_path_probe_bucket(
                bucket,
                window_sec=window_sec,
                sample_request_limit=sample_request_limit,
            )
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = finalize_sensitive_path_probe_bucket(
            bucket,
            window_sec=window_sec,
            sample_request_limit=sample_request_limit,
        )
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            _safe_int(item.get("request_count"), 0),
            len(item.get("path_categories_observed") or []),
            _normalize_text(item.get("window_start")),
        ),
        reverse=True,
    )
    return summaries


def build_sensitive_path_probe_summary_contexts(
    sensitive_path_probe_summaries: List[Dict[str, Any]],
    *,
    parse_flexible_iso_dt_fn: Callable[[str], Optional[datetime]] = _parse_flexible_iso_dt,
) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    for summary in sensitive_path_probe_summaries:
        src_ip = _normalize_text(summary.get("src_ip"))
        window_start = _normalize_text(summary.get("window_start"))
        window_end = _normalize_text(summary.get("window_end"))
        start_dt = parse_flexible_iso_dt_fn(window_start)
        end_dt = parse_flexible_iso_dt_fn(window_end)
        if not src_ip or start_dt is None or end_dt is None:
            continue
        contexts.append(
            {
                "summary": summary,
                "src_ip": src_ip,
                "start_dt": start_dt,
                "end_dt": end_dt,
            }
        )
    return contexts

