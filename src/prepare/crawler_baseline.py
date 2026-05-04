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


def classify_crawler_like_user_agent_family(user_agent: str) -> str:
    normalized = _normalize_text(user_agent).lower()
    if not normalized:
        return ""
    if "googlebot" in normalized:
        return "googlebot_like"
    if "bingbot" in normalized:
        return "bingbot_like"
    if "genericcrawler" in normalized:
        return "generic_crawler"
    if any(token in normalized for token in ("crawler", "spider", "bot")):
        return "generic_crawler"
    return ""


def classify_crawler_baseline_path_category(
    path: str,
    method: str,
    *,
    product_segments: Iterable[str],
    category_segments: Iterable[str],
    generic_segments: Iterable[str],
) -> str:
    normalized_method = _normalize_text(method).upper()
    normalized_path = _normalize_text(path).lower()
    if normalized_method not in {"GET", "HEAD"} or not normalized_path:
        return ""
    if normalized_path == "/robots.txt":
        return "robots_txt"
    if normalized_path == "/sitemap.xml":
        return "sitemap_xml"
    if normalized_method == "GET" and normalized_path == "/":
        return "normal_get"

    segments = [segment for segment in normalized_path.split("/") if segment]
    if any(segment in product_segments for segment in segments):
        return "product_browse"
    if any(segment in category_segments for segment in segments):
        return "category_browse"
    if any(segment in generic_segments for segment in segments):
        return "browse_like"
    return ""


def build_crawler_baseline_reason_hints_for_row(
    row: Dict[str, Any],
    *,
    repeated_sequence: bool = False,
    raw_text_fn: Callable[[Optional[Any]], str],
    extract_raw_request_target_fn: Callable[[str], str],
    get_uri_fn: Callable[[Dict[str, Any]], str],
    get_effective_request_path_fn: Callable[[str, str], str],
    get_method_fn: Callable[[Dict[str, Any]], str],
    get_user_agent_fn: Callable[[Dict[str, Any]], str],
    product_segments: Iterable[str],
    category_segments: Iterable[str],
    generic_segments: Iterable[str],
) -> List[str]:
    raw_request_target = extract_raw_request_target_fn(raw_text_fn(row.get("raw_request")))
    path = get_effective_request_path_fn(get_uri_fn(row), raw_request_target).lower()
    path_category = classify_crawler_baseline_path_category(
        path,
        get_method_fn(row),
        product_segments=product_segments,
        category_segments=category_segments,
        generic_segments=generic_segments,
    )
    ua_family = classify_crawler_like_user_agent_family(get_user_agent_fn(row))

    if not ua_family and not path_category:
        return []

    hints: List[str] = []
    if ua_family == "googlebot_like":
        _append_unique_hint(hints, "crawler_like:googlebot_like_ua")
    elif ua_family == "bingbot_like":
        _append_unique_hint(hints, "crawler_like:bingbot_like_ua")
    elif ua_family == "generic_crawler":
        _append_unique_hint(hints, "crawler_like:generic_crawler_ua")

    if ua_family:
        _append_unique_hint(hints, "crawler_like:ua_spoofable")
        _append_unique_hint(hints, "crawler_like:no_crawler_authenticity_inference")

    if path_category == "robots_txt":
        _append_unique_hint(hints, "crawler_like:robots_txt")
        _append_unique_hint(hints, "crawler_like:no_crawler_policy_inference")
    elif path_category == "sitemap_xml":
        _append_unique_hint(hints, "crawler_like:sitemap_xml")
        _append_unique_hint(hints, "crawler_like:no_site_structure_inference")
    elif path_category == "product_browse":
        _append_unique_hint(hints, "crawler_like:product_browse")
        _append_unique_hint(hints, "crawler_like:no_page_existence_inference")
    elif path_category == "category_browse":
        _append_unique_hint(hints, "crawler_like:category_browse")
        _append_unique_hint(hints, "crawler_like:no_page_existence_inference")
    elif path_category == "browse_like":
        _append_unique_hint(hints, "crawler_like:no_page_existence_inference")
    elif path_category == "normal_get":
        _append_unique_hint(hints, "crawler_like:normal_browse")
        _append_unique_hint(hints, "baseline:normal_get")

    if repeated_sequence and (
        ua_family or path_category in {"robots_txt", "sitemap_xml", "product_browse", "category_browse", "browse_like"}
    ):
        _append_unique_hint(hints, "crawler_like:repeated_crawl_sequence")
        _append_unique_hint(hints, "crawler_like:no_attack_inference")

    return hints


def finalize_crawler_baseline_bucket(
    items: List[Dict[str, Any]],
    window_sec: int,
    *,
    sample_request_limit: int = 10,
) -> Optional[Dict[str, Any]]:
    if len(items) < 2:
        return None

    sorted_items = sorted(items, key=lambda item: item["dt"])
    status_counts = Counter(str(_safe_int(item.get("status_code"), 0)) for item in sorted_items)
    path_counts = Counter(_normalize_text(item.get("path")).lower() for item in sorted_items if _normalize_text(item.get("path")))
    crawler_like_user_agent_families: List[str] = []
    path_categories_observed: List[str] = []
    sample_request_ids: List[str] = []
    reason_hints: List[str] = []

    crawler_like_request_count = 0
    normal_get_count = 0
    has_robots_or_sitemap_with_crawler_ua = False
    has_browse_like_with_crawler_ua = False

    for item in sorted_items:
        ua_family = _normalize_text(item.get("crawler_like_user_agent_family"))
        path_category = _normalize_text(item.get("path_category"))
        if ua_family:
            crawler_like_request_count += 1
            _append_unique_hint(crawler_like_user_agent_families, ua_family)
        if path_category:
            _append_unique_hint(path_categories_observed, path_category)
        if path_category == "normal_get":
            normal_get_count += 1
        if ua_family and path_category in {"robots_txt", "sitemap_xml"}:
            has_robots_or_sitemap_with_crawler_ua = True
        if ua_family and path_category in {"product_browse", "category_browse", "browse_like"}:
            has_browse_like_with_crawler_ua = True

        _extend_unique_hints(reason_hints, item.get("reason_hints") or [])

        sample_request_id = _normalize_text(item.get("sample_request_id"))
        if sample_request_id and len(sample_request_ids) < sample_request_limit:
            _append_unique_hint(sample_request_ids, sample_request_id)

    should_emit = any(
        (
            crawler_like_request_count >= 2,
            has_robots_or_sitemap_with_crawler_ua,
            has_browse_like_with_crawler_ua,
            crawler_like_request_count >= 1 and normal_get_count >= 1,
        )
    )
    if not should_emit:
        return None

    if crawler_like_request_count >= 2 or len(sorted_items) >= 3:
        _append_unique_hint(reason_hints, "crawler_like:repeated_crawl_sequence")
    _append_unique_hint(reason_hints, "crawler_like:ua_spoofable")
    _append_unique_hint(reason_hints, "crawler_like:no_crawler_authenticity_inference")
    if "robots_txt" in path_categories_observed:
        _append_unique_hint(reason_hints, "crawler_like:robots_txt")
        _append_unique_hint(reason_hints, "crawler_like:no_crawler_policy_inference")
    if "sitemap_xml" in path_categories_observed:
        _append_unique_hint(reason_hints, "crawler_like:sitemap_xml")
        _append_unique_hint(reason_hints, "crawler_like:no_site_structure_inference")
    if any(category in {"product_browse", "category_browse", "browse_like"} for category in path_categories_observed):
        _append_unique_hint(reason_hints, "crawler_like:no_page_existence_inference")
    _append_unique_hint(reason_hints, "crawler_like:no_attack_inference")

    return {
        "context_role": "crawler_baseline_context",
        "aggregate_scope": "same_src_ip_crawler_like_time_window",
        "should_promote_to_candidate": False,
        "src_ip": _normalize_text(sorted_items[0].get("src_ip")) or "-",
        "window_start": _normalize_text(sorted_items[0].get("log_time")),
        "window_end": _normalize_text(sorted_items[-1].get("log_time")),
        "burst_window_sec": window_sec,
        "request_count": len(sorted_items),
        "status_counts": dict(sorted(status_counts.items(), key=lambda kv: (_safe_int(kv[0], 0), kv[0]))),
        "crawler_like_user_agent_families": crawler_like_user_agent_families,
        "path_categories_observed": path_categories_observed,
        "path_counts": dict(sorted(path_counts.items(), key=lambda kv: (-_safe_int(kv[1]), kv[0]))),
        "sample_request_ids": sample_request_ids,
        "reason_hints": reason_hints,
        "interpretation_limit": "crawler_ua_spoofable_no_content_or_page_existence_inference",
    }


def build_crawler_baseline_summaries(
    rows: List[Dict[str, Any]],
    window_sec: int = 300,
    *,
    sample_request_limit: int = 10,
    get_src_ip_fn: Callable[[Dict[str, Any]], str],
    choose_best_time_fn: Callable[[Dict[str, Any]], Optional[str]],
    raw_text_fn: Callable[[Optional[Any]], str],
    extract_raw_request_target_fn: Callable[[str], str],
    get_uri_fn: Callable[[Dict[str, Any]], str],
    get_effective_request_path_fn: Callable[[str, str], str],
    get_method_fn: Callable[[Dict[str, Any]], str],
    get_user_agent_fn: Callable[[Dict[str, Any]], str],
    get_status_code_fn: Callable[[Dict[str, Any]], int],
    get_sample_request_id_fn: Callable[[Dict[str, Any]], str],
    product_segments: Iterable[str],
    category_segments: Iterable[str],
    generic_segments: Iterable[str],
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
        path_category = classify_crawler_baseline_path_category(
            path,
            get_method_fn(row),
            product_segments=product_segments,
            category_segments=category_segments,
            generic_segments=generic_segments,
        )
        crawler_like_user_agent_family = classify_crawler_like_user_agent_family(get_user_agent_fn(row))
        if not crawler_like_user_agent_family and not path_category:
            continue

        rows_by_ip[src_ip].append(
            {
                "src_ip": src_ip,
                "log_time": log_time,
                "dt": dt,
                "path": path,
                "status_code": get_status_code_fn(row),
                "path_category": path_category,
                "crawler_like_user_agent_family": crawler_like_user_agent_family,
                "reason_hints": build_crawler_baseline_reason_hints_for_row(
                    row,
                    raw_text_fn=raw_text_fn,
                    extract_raw_request_target_fn=extract_raw_request_target_fn,
                    get_uri_fn=get_uri_fn,
                    get_effective_request_path_fn=get_effective_request_path_fn,
                    get_method_fn=get_method_fn,
                    get_user_agent_fn=get_user_agent_fn,
                    product_segments=product_segments,
                    category_segments=category_segments,
                    generic_segments=generic_segments,
                ),
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

            summary = finalize_crawler_baseline_bucket(
                bucket,
                window_sec=window_sec,
                sample_request_limit=sample_request_limit,
            )
            if summary:
                summaries.append(summary)
            bucket = [item]
            bucket_start = item["dt"]

        summary = finalize_crawler_baseline_bucket(
            bucket,
            window_sec=window_sec,
            sample_request_limit=sample_request_limit,
        )
        if summary:
            summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            _safe_int(item.get("request_count"), 0),
            len(item.get("crawler_like_user_agent_families") or []),
            len(item.get("path_categories_observed") or []),
            _normalize_text(item.get("window_start")),
        ),
        reverse=True,
    )
    return summaries


def build_crawler_baseline_summary_contexts(
    crawler_baseline_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    for summary in crawler_baseline_summaries:
        src_ip = _normalize_text(summary.get("src_ip"))
        window_start = _normalize_text(summary.get("window_start"))
        window_end = _normalize_text(summary.get("window_end"))
        start_dt = _parse_flexible_iso_dt(window_start)
        end_dt = _parse_flexible_iso_dt(window_end)
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
