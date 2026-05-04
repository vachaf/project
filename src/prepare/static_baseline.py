from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
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


def _extend_unique_hints(hints: List[str], extra_hints: List[str]) -> None:
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


def finalize_static_baseline_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
    *,
    min_static_paths: int = 3,
    sample_request_limit: int = 10,
) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    sorted_items = sorted(items, key=lambda item: item["dt"])
    status_counts = Counter(str(_safe_int(item.get("status_code"), 0)) for item in sorted_items)
    path_counts = Counter(_normalize_text(item.get("path")).lower() for item in sorted_items if _normalize_text(item.get("path")))
    asset_categories_observed: List[str] = []
    sample_request_ids: List[str] = []
    reason_hints: List[str] = []

    static_like_count = 0
    health_like_count = 0
    normal_get_count = 0

    for item in sorted_items:
        category = _normalize_text(item.get("asset_category"))
        if category:
            _append_unique_hint(asset_categories_observed, category)

        if bool(item.get("is_static_like")):
            static_like_count += 1
        if category == "health_check":
            health_like_count += 1
        if category == "normal_get":
            normal_get_count += 1

        _extend_unique_hints(reason_hints, item.get("reason_hints") or [])

        sample_request_id = _normalize_text(item.get("sample_request_id"))
        if sample_request_id and len(sample_request_ids) < sample_request_limit:
            _append_unique_hint(sample_request_ids, sample_request_id)

    should_emit = any(
        (
            static_like_count >= min_static_paths,
            health_like_count >= 1,
            normal_get_count >= 1 and (static_like_count >= 1 or health_like_count >= 1),
            len(asset_categories_observed) >= 3,
        )
    )
    if not should_emit:
        return None

    if static_like_count >= 1:
        _append_unique_hint(reason_hints, "baseline:no_static_content_inference")
    if "robots_txt" in asset_categories_observed:
        _append_unique_hint(reason_hints, "baseline:no_crawler_policy_inference")
    if "sitemap_xml" in asset_categories_observed:
        _append_unique_hint(reason_hints, "baseline:no_site_structure_inference")
    if "javascript_asset" in asset_categories_observed:
        _append_unique_hint(reason_hints, "baseline:no_js_execution_inference")
    if "image_asset" in asset_categories_observed:
        _append_unique_hint(reason_hints, "baseline:no_file_exposure_inference")
    if "health_check" in asset_categories_observed:
        _append_unique_hint(reason_hints, "baseline:no_health_status_inference")

    return {
        "context_role": "static_baseline_context",
        "aggregate_scope": "same_src_ip_static_baseline_time_window",
        "should_promote_to_candidate": False,
        "src_ip": _normalize_text(sorted_items[0].get("src_ip")) or "-",
        "window_start": _normalize_text(sorted_items[0].get("log_time")),
        "window_end": _normalize_text(sorted_items[-1].get("log_time")),
        "burst_window_sec": window_sec,
        "request_count": len(sorted_items),
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (_safe_int(kv[0], 0), kv[0]))),
        "asset_categories_observed": asset_categories_observed,
        "path_counts": dict(sorted(path_counts.items(), key=lambda kv: (-_safe_int(kv[1]), kv[0]))),
        "sample_request_ids": sample_request_ids,
        "reason_hints": reason_hints,
        "interpretation_limit": "static_content_not_visible_no_attack_inference",
    }


def build_static_baseline_reason_hints_for_row(
    row: Dict[str, Any],
    *,
    raw_text_fn: Callable[[Optional[Any]], str],
    extract_raw_request_target_fn: Callable[[str], str],
    get_uri_fn: Callable[[Dict[str, Any]], str],
    get_effective_request_path_fn: Callable[[str, str], str],
    get_method_fn: Callable[[Dict[str, Any]], str],
    classify_static_baseline_asset_category_fn: Callable[[str, str], str],
) -> List[str]:
    raw_request_target = extract_raw_request_target_fn(raw_text_fn(row.get("raw_request")))
    path = get_effective_request_path_fn(get_uri_fn(row), raw_request_target).lower()
    category = classify_static_baseline_asset_category_fn(path, get_method_fn(row))
    if not category:
        return []

    hints: List[str] = []
    if category == "favicon":
        _append_unique_hint(hints, "baseline:favicon")
        _append_unique_hint(hints, "baseline:static_asset")
    elif category == "robots_txt":
        _append_unique_hint(hints, "baseline:robots_txt")
        _append_unique_hint(hints, "baseline:no_crawler_policy_inference")
    elif category == "sitemap_xml":
        _append_unique_hint(hints, "baseline:sitemap_xml")
        _append_unique_hint(hints, "baseline:no_site_structure_inference")
    elif category == "javascript_asset":
        _append_unique_hint(hints, "baseline:static_asset")
        _append_unique_hint(hints, "baseline:static_js")
        _append_unique_hint(hints, "baseline:no_js_execution_inference")
    elif category == "css_asset":
        _append_unique_hint(hints, "baseline:static_asset")
        _append_unique_hint(hints, "baseline:static_css")
    elif category == "image_asset":
        _append_unique_hint(hints, "baseline:static_asset")
        _append_unique_hint(hints, "baseline:static_image")
        _append_unique_hint(hints, "baseline:no_file_exposure_inference")
    elif category == "static_asset":
        _append_unique_hint(hints, "baseline:static_asset")
    elif category == "health_check":
        _append_unique_hint(hints, "baseline:health_check")
        _append_unique_hint(hints, "baseline:no_health_status_inference")
    elif category == "normal_get":
        _append_unique_hint(hints, "baseline:normal_get")
    return hints


def build_static_baseline_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = 300,
    *,
    min_static_paths: int = 3,
    sample_request_limit: int = 10,
    get_src_ip_fn: Callable[[Dict[str, Any]], str],
    choose_best_time_fn: Callable[[Dict[str, Any]], Optional[str]],
    raw_text_fn: Callable[[Optional[Any]], str],
    extract_raw_request_target_fn: Callable[[str], str],
    get_uri_fn: Callable[[Dict[str, Any]], str],
    get_effective_request_path_fn: Callable[[str, str], str],
    get_method_fn: Callable[[Dict[str, Any]], str],
    classify_static_baseline_asset_category_fn: Callable[[str, str], str],
    get_status_code_fn: Callable[[Dict[str, Any]], int],
    get_sample_request_id_fn: Callable[[Dict[str, Any]], str],
) -> List[Dict[str, Any]]:
    rows_by_ip: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        src_ip = get_src_ip_fn(row)
        if not src_ip or src_ip == "-":
            continue

        log_time = choose_best_time_fn(row)
        dt = _parse_flexible_iso_dt(log_time or "")
        if dt is None:
            continue

        raw_request_target = extract_raw_request_target_fn(raw_text_fn(row.get("raw_request")))
        path = get_effective_request_path_fn(get_uri_fn(row), raw_request_target).lower()
        asset_category = classify_static_baseline_asset_category_fn(path, get_method_fn(row))
        if not asset_category:
            continue

        rows_by_ip[src_ip].append(
            {
                "src_ip": src_ip,
                "log_time": log_time,
                "dt": dt,
                "path": path,
                "status_code": get_status_code_fn(row),
                "asset_category": asset_category,
                "reason_hints": build_static_baseline_reason_hints_for_row(
                    row,
                    raw_text_fn=raw_text_fn,
                    extract_raw_request_target_fn=extract_raw_request_target_fn,
                    get_uri_fn=get_uri_fn,
                    get_effective_request_path_fn=get_effective_request_path_fn,
                    get_method_fn=get_method_fn,
                    classify_static_baseline_asset_category_fn=classify_static_baseline_asset_category_fn,
                ),
                "sample_request_id": get_sample_request_id_fn(row),
                "is_static_like": asset_category in {
                    "favicon",
                    "robots_txt",
                    "sitemap_xml",
                    "javascript_asset",
                    "css_asset",
                    "image_asset",
                    "static_asset",
                },
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

            summary = finalize_static_baseline_bucket(
                bucket,
                window_sec=window_sec,
                min_static_paths=min_static_paths,
                sample_request_limit=sample_request_limit,
            )
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = finalize_static_baseline_bucket(
            bucket,
            window_sec=window_sec,
            min_static_paths=min_static_paths,
            sample_request_limit=sample_request_limit,
        )
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            _safe_int(item.get("request_count"), 0),
            len(item.get("asset_categories_observed") or []),
            _normalize_text(item.get("window_start")),
        ),
        reverse=True,
    )
    return summaries


def build_static_baseline_summary_contexts(
    static_baseline_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    for summary in static_baseline_summaries:
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
