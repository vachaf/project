from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Pattern, Tuple
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
    return _normalize_text(row.get("method")).upper()


def _get_sample_request_id(row: Dict[str, Any]) -> str:
    return _normalize_text(row.get("request_id")) or _normalize_text(row.get("error_link_id"))


def _choose_best_time(row: Dict[str, Any]) -> Optional[str]:
    return _normalize_text(row.get("log_time")) or _normalize_text(row.get("created_at")) or None


def _get_user_agent(row: Dict[str, Any]) -> str:
    return (
        _normalize_text(row.get("user_agent"))
        or _normalize_text(row.get("ua"))
        or _normalize_text(row.get("request_user_agent"))
    )


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


def _get_auth_endpoint_family(
    method: str,
    uri: str,
    *,
    raw_request_target: str = "",
    auth_endpoint_family_patterns: Iterable[Tuple[str, Pattern[str]]],
) -> str:
    if _normalize_text(method).upper() != "POST":
        return ""

    path = _get_effective_request_path(uri, raw_request_target).lower()
    if not path:
        return ""

    for family, pattern in auth_endpoint_family_patterns:
        if pattern.search(path):
            return family
    return ""


def _max_bucket_size_within_window(
    items: List[Dict[str, Any]],
    window_sec: int,
    *,
    status_predicate: Optional[Callable[[int], bool]] = None,
) -> int:
    if not items:
        return 0

    filtered = items
    if status_predicate is not None:
        filtered = [item for item in items if status_predicate(_safe_int(item.get("status_code"), 0))]
        if not filtered:
            return 0

    max_count = 0
    left = 0
    for right, item in enumerate(filtered):
        current_dt = item["dt"]
        while left <= right and (current_dt - filtered[left]["dt"]).total_seconds() > window_sec:
            left += 1
        max_count = max(max_count, right - left + 1)
    return max_count


def finalize_auth_behavior_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
    rapid_window_sec: int,
    *,
    sample_request_limit: int,
) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    sorted_items = sorted(items, key=lambda item: item["dt"])
    request_count = len(sorted_items)
    status_counts = Counter(str(_safe_int(item.get("status_code"), 0)) for item in sorted_items)
    status_401_count = _safe_int(status_counts.get("401"), 0)
    status_4xx_count = sum(count for code, count in status_counts.items() if 400 <= _safe_int(code, 0) < 500)
    status_2xx_count = sum(count for code, count in status_counts.items() if 200 <= _safe_int(code, 0) < 300)
    max_requests_rapid = _max_bucket_size_within_window(sorted_items, rapid_window_sec)
    max_401_rapid = _max_bucket_size_within_window(
        sorted_items,
        rapid_window_sec,
        status_predicate=lambda status_code: status_code == 401,
    )

    has_repeated_401 = status_401_count >= 3
    has_rapid_burst = max_requests_rapid >= 10
    has_mixed_401_200 = status_401_count > 0 and status_2xx_count > 0
    has_single_200_only = request_count == 1 and status_2xx_count == 1 and status_4xx_count == 0
    has_normal_session_like_baseline = (
        request_count <= 2 and status_2xx_count >= 1 and status_4xx_count == 0 and not has_mixed_401_200
    )

    should_emit = any(
        (
            request_count >= 3,
            has_repeated_401,
            has_mixed_401_200,
            has_rapid_burst,
            has_single_200_only,
        )
    )
    if not should_emit:
        return None

    distinct_user_agents = {
        _normalize_text(item.get("user_agent"))
        for item in sorted_items
        if _normalize_text(item.get("user_agent"))
    }
    sample_request_ids: List[str] = []
    for item in sorted_items:
        request_id = _normalize_text(item.get("sample_request_id"))
        if request_id and request_id not in sample_request_ids:
            sample_request_ids.append(request_id)
        if len(sample_request_ids) >= sample_request_limit:
            break

    reason_hints: List[str] = []
    if request_count >= 3:
        _append_unique_hint(reason_hints, "auth_abuse:repeated_auth_endpoint")
    if has_repeated_401:
        _append_unique_hint(reason_hints, "auth_abuse:repeated_401")
    if has_rapid_burst and (max_401_rapid >= 3 or status_4xx_count >= status_2xx_count):
        _append_unique_hint(reason_hints, "auth_abuse:rapid_fail_burst")
    if has_mixed_401_200:
        _append_unique_hint(reason_hints, "auth_abuse:mixed_401_200_sequence")
    if has_single_200_only:
        _append_unique_hint(reason_hints, "auth_abuse:single_200_baseline")
    elif has_normal_session_like_baseline:
        _append_unique_hint(reason_hints, "auth_abuse:normal_session_like_baseline")
    _append_unique_hint(reason_hints, "auth_abuse:post_body_not_visible")
    _append_unique_hint(reason_hints, "auth_abuse:no_auth_success_inference")

    return {
        "context_role": "auth_behavior_context",
        "aggregate_scope": "same_src_ip_auth_endpoint_time_window",
        "should_promote_to_candidate": False,
        "src_ip": _normalize_text(sorted_items[0].get("src_ip")) or "-",
        "window_start": _normalize_text(sorted_items[0].get("log_time")),
        "window_end": _normalize_text(sorted_items[-1].get("log_time")),
        "burst_window_sec": window_sec,
        "endpoint_family": _normalize_text(sorted_items[0].get("endpoint_family")) or "auth_endpoint",
        "request_count": request_count,
        "auth_request_count": request_count,
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (_safe_int(kv[0], 0), kv[0]))),
        "status_4xx_count": status_4xx_count,
        "status_2xx_count": status_2xx_count,
        "has_repeated_401": has_repeated_401,
        "has_rapid_burst": has_rapid_burst,
        "has_mixed_401_200": has_mixed_401_200,
        "has_single_200_only": has_single_200_only,
        "distinct_user_agents": len(distinct_user_agents),
        "sample_request_ids": sample_request_ids,
        "reason_hints": reason_hints,
        "interpretation_limit": "post_body_not_visible_no_auth_success_inference",
    }


def build_auth_behavior_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = 300,
    rapid_window_sec: int = 60,
    *,
    sample_request_limit: int = 10,
    auth_endpoint_family_patterns: Iterable[Tuple[str, Pattern[str]]],
) -> List[Dict[str, Any]]:
    rows_by_group: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        src_ip = _get_src_ip(row)
        if not src_ip or src_ip == "-":
            continue

        log_time = _choose_best_time(row)
        dt = _parse_flexible_iso_dt(log_time or "")
        if dt is None:
            continue

        method = _get_method(row)
        uri = _get_uri(row)
        raw_request_target = _extract_raw_request_target(_raw_text(row.get("raw_request")))
        endpoint_family = _get_auth_endpoint_family(
            method,
            uri,
            raw_request_target=raw_request_target,
            auth_endpoint_family_patterns=auth_endpoint_family_patterns,
        )
        if not endpoint_family:
            continue

        rows_by_group[(src_ip, endpoint_family)].append(
            {
                "src_ip": src_ip,
                "log_time": log_time,
                "dt": dt,
                "status_code": _get_status_code(row),
                "user_agent": _get_user_agent(row),
                "sample_request_id": _get_sample_request_id(row),
                "endpoint_family": endpoint_family,
            }
        )

    summaries: List[Dict[str, Any]] = []
    for _, items in rows_by_group.items():
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

            summary = finalize_auth_behavior_bucket(
                bucket,
                window_sec=window_sec,
                rapid_window_sec=rapid_window_sec,
                sample_request_limit=sample_request_limit,
            )
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = finalize_auth_behavior_bucket(
            bucket,
            window_sec=window_sec,
            rapid_window_sec=rapid_window_sec,
            sample_request_limit=sample_request_limit,
        )
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            _safe_int(item.get("request_count"), 0),
            _safe_int(item.get("status_4xx_count"), 0),
            _safe_int(item.get("status_2xx_count"), 0),
            _normalize_text(item.get("window_start")),
        ),
        reverse=True,
    )
    return summaries


def build_auth_behavior_summary_contexts(
    auth_behavior_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    for summary in auth_behavior_summaries:
        if not bool(summary.get("has_repeated_401")):
            continue
        src_ip = _normalize_text(summary.get("src_ip"))
        endpoint_family = _normalize_text(summary.get("endpoint_family"))
        window_start = _normalize_text(summary.get("window_start"))
        window_end = _normalize_text(summary.get("window_end"))
        start_dt = _parse_flexible_iso_dt(window_start)
        end_dt = _parse_flexible_iso_dt(window_end)
        if not src_ip or not endpoint_family or start_dt is None or end_dt is None:
            continue
        contexts.append(
            {
                "summary": summary,
                "src_ip": src_ip,
                "endpoint_family": endpoint_family,
                "window_start": window_start,
                "window_end": window_end,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "summary_key": "|".join([src_ip, endpoint_family, window_start, window_end]),
            }
        )
    return contexts

