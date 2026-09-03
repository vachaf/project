from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

FILE_DISCLOSURE_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("php_filter_wrapper", re.compile(r"(?i)php\s*://\s*filter|php%3a%2f%2ffilter|php%253a%252f%252ffilter"), 5),
    ("base64_source_filter", re.compile(r"(?i)convert\.base64-encode"), 2),
    ("resource_parameter", re.compile(r"(?i)(?:^|[?&/])resource\s*=|resource%3d|resource%253d"), 2),
    ("admin_config_php", re.compile(r"(?i)(?:resource\s*=|resource%3d|resource%253d)admin/config\.php\b"), 2),
    ("config_php", re.compile(r"(?i)(?:resource\s*=|resource%3d|resource%253d)config\.php\b"), 2),
    ("index_php", re.compile(r"(?i)(?:resource\s*=|resource%3d|resource%253d)index\.php\b"), 1),
    (
        "os_file",
        re.compile(
            r"(?i)(?:/etc/passwd|(?<![\w.-])(?:windows[/\\])?win\.ini)"
            r"(?=$|%00|[\x00\s?&#/\\])"
        ),
        5,
    ),
]

PHP_FILTER_CANONICAL_PATTERN = re.compile(r"(?i)php\s*://\s*filter")


def _raw_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _append_unique_hint(hints: List[str], hint: str) -> None:
    text = _raw_text(hint)
    if text and text not in hints:
        hints.append(text)


def _unique_non_empty_texts(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        text = _raw_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def detect_file_disclosure_hints(
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    hints: List[str] = []
    score_boost = 0
    variants = query_variants + raw_request_target_variants
    samples = _unique_non_empty_texts(
        [combined_target] + [_raw_text(item.get("text")) for item in variants]
    )
    if not samples:
        return 0, []

    pattern_hits = {
        name: any(pattern.search(sample) for sample in samples)
        for name, pattern, _ in FILE_DISCLOSURE_PATTERNS
    }
    points_by_name = {name: points for name, _, points in FILE_DISCLOSURE_PATTERNS}

    canonical_in_base = bool(PHP_FILTER_CANONICAL_PATTERN.search(combined_target))
    canonical_depth1 = False
    canonical_depth2 = False
    for variant in variants:
        text = _raw_text(variant.get("text"))
        depth = _safe_int(variant.get("depth"), 0)
        if not text or not PHP_FILTER_CANONICAL_PATTERN.search(text):
            continue
        if depth >= 1:
            canonical_depth1 = True
        if depth >= 2:
            canonical_depth2 = True

    resource_context = any(
        pattern_hits.get(name, False)
        for name in ("php_filter_wrapper", "base64_source_filter", "resource_parameter")
    )

    if pattern_hits.get("php_filter_wrapper"):
        score_boost += points_by_name["php_filter_wrapper"]
        _append_unique_hint(hints, "file_disclosure:php_filter_wrapper")
    if pattern_hits.get("base64_source_filter"):
        score_boost += points_by_name["base64_source_filter"]
        _append_unique_hint(hints, "file_disclosure:base64_source_intent")
    if pattern_hits.get("resource_parameter"):
        score_boost += points_by_name["resource_parameter"]
        _append_unique_hint(hints, "file_disclosure:resource_parameter")
    if pattern_hits.get("os_file"):
        score_boost += points_by_name["os_file"]
        _append_unique_hint(hints, "file_disclosure:sensitive_resource:os_file")

    if resource_context:
        if pattern_hits.get("admin_config_php"):
            score_boost += points_by_name["admin_config_php"]
            _append_unique_hint(hints, "file_disclosure:sensitive_resource:admin_config_php")
        elif pattern_hits.get("config_php"):
            score_boost += points_by_name["config_php"]
            _append_unique_hint(hints, "file_disclosure:sensitive_resource:config_php")

        if pattern_hits.get("index_php"):
            score_boost += points_by_name["index_php"]
            _append_unique_hint(hints, "file_disclosure:sensitive_resource:index_php")

    if not canonical_in_base and canonical_depth1:
        _append_unique_hint(hints, "encoding:url_decoded_php_wrapper")
    if canonical_depth2:
        _append_unique_hint(hints, "encoding:double_decoded_php_wrapper")
        if not canonical_in_base and not canonical_depth1:
            score_boost += 1

    return score_boost, hints
