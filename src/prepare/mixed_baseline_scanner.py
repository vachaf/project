from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


def build_mixed_baseline_scanner_row_context(
    row: Dict[str, Any],
    *,
    extract_raw_request_target: Callable[[str], str],
    raw_text: Callable[[Any], str],
    get_effective_request_path: Callable[[str, str], str],
    get_uri: Callable[[Dict[str, Any]], str],
    get_method: Callable[[Dict[str, Any]], str],
    get_user_agent: Callable[[Dict[str, Any]], str],
    classify_static_baseline_asset_category: Callable[[str, str], str],
    classify_crawler_baseline_path_category: Callable[[str, str], str],
    classify_crawler_like_user_agent_family: Callable[[str], str],
    classify_sensitive_path_probe_category: Callable[[str, str], str],
    map_mixed_static_path_category: Callable[[str], str],
    map_mixed_crawler_path_category: Callable[[str], str],
    map_mixed_sensitive_path_category: Callable[[str], str],
    append_unique_hint: Callable[[List[str], str], None],
    get_src_ip: Callable[[Dict[str, Any]], str],
    choose_best_time: Callable[[Dict[str, Any]], Optional[str]],
    parse_flexible_iso_dt: Callable[[str], Optional[datetime]],
    get_status_code: Callable[[Dict[str, Any]], int],
    get_sample_request_id: Callable[[Dict[str, Any]], str],
) -> Optional[Dict[str, Any]]:
    raw_request_target = extract_raw_request_target(raw_text(row.get("raw_request")))
    path = get_effective_request_path(get_uri(row), raw_request_target).lower()
    method = get_method(row)
    user_agent = get_user_agent(row)

    static_category = classify_static_baseline_asset_category(path, method)
    crawler_path_category = classify_crawler_baseline_path_category(path, method)
    crawler_ua_family = classify_crawler_like_user_agent_family(user_agent)
    sensitive_path_category = classify_sensitive_path_probe_category(path, method)

    baseline_contexts: List[str] = []
    scanner_contexts: List[str] = []
    path_categories_observed: List[str] = []

    if static_category:
        mapped_static_category = map_mixed_static_path_category(static_category)
        if mapped_static_category:
            append_unique_hint(path_categories_observed, mapped_static_category)
        if static_category == "normal_get":
            append_unique_hint(baseline_contexts, "normal_get")
        else:
            append_unique_hint(baseline_contexts, "static_baseline")

    crawler_context_detected = False
    if crawler_ua_family:
        if crawler_path_category in {
            "robots_txt",
            "sitemap_xml",
            "product_browse",
            "category_browse",
            "browse_like",
            "normal_get",
        }:
            crawler_context_detected = True
        elif not static_category and not sensitive_path_category:
            crawler_context_detected = True
    if crawler_context_detected:
        append_unique_hint(baseline_contexts, "crawler_baseline")
        mapped_crawler_category = map_mixed_crawler_path_category(crawler_path_category)
        if mapped_crawler_category:
            append_unique_hint(path_categories_observed, mapped_crawler_category)

    if sensitive_path_category:
        append_unique_hint(scanner_contexts, "sensitive_path_probe")
        mapped_sensitive_category = map_mixed_sensitive_path_category(sensitive_path_category)
        if mapped_sensitive_category:
            append_unique_hint(path_categories_observed, mapped_sensitive_category)

    if not baseline_contexts and not scanner_contexts:
        return None

    return {
        "src_ip": get_src_ip(row),
        "log_time": choose_best_time(row),
        "dt": parse_flexible_iso_dt(choose_best_time(row) or ""),
        "path": path,
        "status_code": get_status_code(row),
        "baseline_contexts": baseline_contexts,
        "scanner_contexts": scanner_contexts,
        "path_categories_observed": path_categories_observed,
        "sample_request_id": get_sample_request_id(row),
    }


def finalize_mixed_baseline_scanner_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
    *,
    min_request_count: int,
    sample_request_limit: int,
    safe_int: Callable[[Any, int], int],
    extend_unique_hints: Callable[[List[str], List[str]], None],
    normalize_text: Callable[[Any], str],
    append_unique_hint: Callable[[List[str], str], None],
) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    sorted_items = sorted(items, key=lambda item: item["dt"])
    if len(sorted_items) < min_request_count:
        return None

    status_counts = Counter(str(safe_int(item.get("status_code"), 0)) for item in sorted_items)
    baseline_contexts_observed: List[str] = []
    scanner_contexts_observed: List[str] = []
    path_categories_observed: List[str] = []
    sample_request_ids: List[str] = []

    for item in sorted_items:
        extend_unique_hints(baseline_contexts_observed, item.get("baseline_contexts") or [])
        extend_unique_hints(scanner_contexts_observed, item.get("scanner_contexts") or [])
        extend_unique_hints(path_categories_observed, item.get("path_categories_observed") or [])

        sample_request_id = normalize_text(item.get("sample_request_id"))
        if sample_request_id and len(sample_request_ids) < sample_request_limit:
            append_unique_hint(sample_request_ids, sample_request_id)

    has_baseline_context = any(
        context in {"static_baseline", "crawler_baseline", "normal_get"}
        for context in baseline_contexts_observed
    )
    has_scanner_context = "sensitive_path_probe" in scanner_contexts_observed
    if not (has_baseline_context and has_scanner_context):
        return None

    reason_hints: List[str] = [
        "mixed_context:benign_and_scanner_like",
        "mixed_context:keep_baseline_and_scanner_separate",
        "mixed_context:no_single_attack_inference",
        "mixed_context:no_success_inference",
        "mixed_context:no_file_exposure_inference",
        "mixed_context:no_crawler_authenticity_inference",
        "mixed_context:no_page_existence_inference",
    ]
    if "static_baseline" in baseline_contexts_observed:
        append_unique_hint(reason_hints, "mixed_context:static_baseline_present")
    if "crawler_baseline" in baseline_contexts_observed:
        append_unique_hint(reason_hints, "mixed_context:crawler_baseline_present")
    if "normal_get" in baseline_contexts_observed:
        append_unique_hint(reason_hints, "mixed_context:normal_browse_present")
    if "sensitive_path_probe" in scanner_contexts_observed:
        append_unique_hint(reason_hints, "mixed_context:sensitive_path_probe_present")

    return {
        "context_role": "mixed_baseline_scanner_context",
        "aggregate_scope": "same_src_ip_mixed_baseline_scanner_time_window",
        "should_promote_to_candidate": False,
        "src_ip": normalize_text(sorted_items[0].get("src_ip")) or "-",
        "window_start": normalize_text(sorted_items[0].get("log_time")),
        "window_end": normalize_text(sorted_items[-1].get("log_time")),
        "burst_window_sec": window_sec,
        "request_count": len(sorted_items),
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (safe_int(kv[0], 0), kv[0]))),
        "baseline_contexts_observed": baseline_contexts_observed,
        "scanner_contexts_observed": scanner_contexts_observed,
        "path_categories_observed": path_categories_observed,
        "sample_request_ids": sample_request_ids,
        "reason_hints": reason_hints,
        "interpretation_limit": "mixed_context_no_success_or_single_attack_inference",
    }


def build_mixed_baseline_scanner_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int,
    *,
    get_src_ip: Callable[[Dict[str, Any]], str],
    build_mixed_baseline_scanner_row_context: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
    finalize_mixed_baseline_scanner_bucket: Callable[[List[Dict[str, Any]], int], Optional[Dict[str, Any]]],
    safe_int: Callable[[Any, int], int],
    normalize_text: Callable[[Any], str],
) -> List[Dict[str, Any]]:
    rows_by_ip: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        src_ip = get_src_ip(row)
        if not src_ip or src_ip == "-":
            continue

        row_context = build_mixed_baseline_scanner_row_context(row)
        if not row_context:
            continue

        row_dt = row_context.get("dt")
        if row_dt is None:
            continue

        rows_by_ip[src_ip].append(row_context)

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

            summary = finalize_mixed_baseline_scanner_bucket(bucket, window_sec)
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = finalize_mixed_baseline_scanner_bucket(bucket, window_sec)
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            safe_int(item.get("request_count"), 0),
            len(item.get("baseline_contexts_observed") or []),
            len(item.get("scanner_contexts_observed") or []),
            normalize_text(item.get("window_start")),
        ),
        reverse=True,
    )
    return summaries
