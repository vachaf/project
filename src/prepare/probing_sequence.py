from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


def finalize_probing_sequence_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
    *,
    min_requests: int,
    min_distinct_paths: int,
    sample_path_limit: int,
    normalize_text: Callable[[Any], str],
    safe_int: Callable[[Any, int], int],
    normalize_content_type_bucket: Callable[[Any], str],
    extend_unique_hints: Callable[[List[str], List[str]], None],
    get_probe_sequence_reason_hints: Callable[[Any], List[str]],
    append_unique_hint: Callable[[List[str], str], None],
) -> Optional[Dict[str, Any]]:
    if len(items) < min_requests:
        return None

    distinct_paths: List[str] = []
    seen_paths = set()
    for item in items:
        path = normalize_text(item.get("path")).lower()
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        distinct_paths.append(path)

    if len(distinct_paths) < min_distinct_paths:
        return None

    status_counts = Counter(str(safe_int(item.get("status_code"), 0)) for item in items)
    content_type_counts = Counter(normalize_content_type_bucket(item.get("resp_content_type")) or "-" for item in items)

    html_200_rows = [
        item
        for item in items
        if safe_int(item.get("status_code"), 0) == 200
        and normalize_content_type_bucket(item.get("resp_content_type")) == "text/html"
        and safe_int(item.get("response_body_bytes"), 0) > 0
    ]
    response_size_repetition: Dict[str, Any] = {}
    if html_200_rows:
        size_counter = Counter(safe_int(item.get("response_body_bytes"), 0) for item in html_200_rows)
        dominant_size, dominant_count = size_counter.most_common(1)[0]
        if dominant_size > 0 and dominant_count >= 2 and dominant_count * 2 >= len(html_200_rows):
            response_size_repetition = {
                "dominant_response_body_bytes": dominant_size,
                "dominant_count": dominant_count,
            }

    reason_hints: List[str] = []
    for item in items:
        extend_unique_hints(reason_hints, get_probe_sequence_reason_hints(item.get("path")))
    if response_size_repetition:
        append_unique_hint(reason_hints, "dir_probe:repeated_fallback_like_html")

    sorted_items = sorted(items, key=lambda item: normalize_text(item.get("log_time")))
    return {
        "category": "low_signal_dir_probe_burst",
        "policy": "context_only",
        "src_ip": normalize_text(sorted_items[0].get("src_ip")) or "-",
        "start": normalize_text(sorted_items[0].get("log_time")),
        "end": normalize_text(sorted_items[-1].get("log_time")),
        "window_sec": window_sec,
        "request_count": len(items),
        "distinct_path_count": len(distinct_paths),
        "sample_paths": distinct_paths[:sample_path_limit],
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (-safe_int(kv[1]), kv[0]))),
        "content_type_counts": dict(sorted(content_type_counts.items(), key=lambda kv: (-safe_int(kv[1]), kv[0]))),
        "response_size_repetition": response_size_repetition,
        "reason_hints": reason_hints,
        "interpretation_hint": (
            "Multiple low-signal directory probing paths from the same source in a short window. "
            "Context only; do not treat as confirmed compromise."
        ),
    }


def build_probing_sequence_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int,
    *,
    finalize_bucket: Callable[..., Optional[Dict[str, Any]]],
    get_method: Callable[[Dict[str, Any]], str],
    get_probe_sequence_path: Callable[..., str],
    get_uri: Callable[[Dict[str, Any]], str],
    extract_raw_request_target: Callable[[str], str],
    raw_text: Callable[[Any], str],
    is_likely_probe_sequence_path: Callable[..., bool],
    normalize_text: Callable[[Any], str],
    parse_flexible_iso_dt: Callable[[str], Optional[datetime]],
    choose_best_time: Callable[[Dict[str, Any]], str],
    get_src_ip: Callable[[Dict[str, Any]], str],
    get_status_code: Callable[[Dict[str, Any]], int],
    get_resp_content_type: Callable[[Dict[str, Any]], str],
    get_response_body_bytes: Callable[[Dict[str, Any]], int],
    safe_int: Callable[[Any, int], int],
) -> List[Dict[str, Any]]:
    probe_rows_by_ip: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        method = get_method(row)
        if method not in {"GET", "HEAD", "OPTIONS"}:
            continue
        path = get_probe_sequence_path(
            uri=get_uri(row),
            raw_request_target=extract_raw_request_target(raw_text(row.get("raw_request"))),
        )
        if not is_likely_probe_sequence_path(path, query_string=normalize_text(row.get("query_string"))):
            continue

        dt = parse_flexible_iso_dt(choose_best_time(row) or "")
        if dt is None:
            continue

        probe_rows_by_ip[get_src_ip(row)].append(
            {
                "src_ip": get_src_ip(row),
                "log_time": choose_best_time(row),
                "dt": dt,
                "path": path,
                "status_code": get_status_code(row),
                "resp_content_type": get_resp_content_type(row),
                "response_body_bytes": get_response_body_bytes(row),
            }
        )

    summaries: List[Dict[str, Any]] = []
    for _src_ip, items in probe_rows_by_ip.items():
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

            summary = finalize_bucket(bucket, window_sec=window_sec)
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = finalize_bucket(bucket, window_sec=window_sec)
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            safe_int(item.get("request_count"), 0),
            safe_int(item.get("distinct_path_count"), 0),
            normalize_text(item.get("start")),
        ),
        reverse=True,
    )
    return summaries
