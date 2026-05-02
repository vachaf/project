from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import unquote_plus

DECODE_VARIANT_MAX_CHARS = 4096
HTML_ENTITY_RE = re.compile(r"&#x?[0-9a-fA-F]+;", re.IGNORECASE)


def _raw_text(value: Optional[Any]) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Optional[Any], default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_decoded_variants(value: str, max_depth: int = 2) -> List[Dict[str, Any]]:
    current = _raw_text(value)
    if not current:
        return []

    if len(current) > DECODE_VARIANT_MAX_CHARS:
        current = current[:DECODE_VARIANT_MAX_CHARS]

    variants: List[Dict[str, Any]] = [{"depth": 0, "text": current}]
    for depth in range(1, max(0, max_depth) + 1):
        try:
            decoded = unquote_plus(current)
        except Exception:
            break
        if len(decoded) > DECODE_VARIANT_MAX_CHARS:
            decoded = decoded[:DECODE_VARIANT_MAX_CHARS]
        if decoded == current:
            break
        variants.append({"depth": depth, "text": decoded})
        current = decoded
    return variants


def build_html_entity_decoded_variant(value: str) -> str:
    current = _raw_text(value)
    if not current:
        return ""
    if len(current) > DECODE_VARIANT_MAX_CHARS:
        current = current[:DECODE_VARIANT_MAX_CHARS]
    try:
        decoded = html.unescape(current)
    except Exception:
        return current
    if len(decoded) > DECODE_VARIANT_MAX_CHARS:
        decoded = decoded[:DECODE_VARIANT_MAX_CHARS]
    return decoded


def build_html_entity_variants(value: str, source: str) -> List[Dict[str, Any]]:
    raw_value = _raw_text(value)
    if not raw_value or not HTML_ENTITY_RE.search(raw_value):
        return []
    decoded = build_html_entity_decoded_variant(raw_value)
    if not decoded or decoded == raw_value:
        return []
    return [{
        "depth": 0,
        "text": decoded,
        "variant_type": "html_entity",
        "source": source,
        "source_text": raw_value,
    }]


def append_html_entity_variants(variants: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    html_variants: List[Dict[str, Any]] = []
    seen_texts = {_raw_text(item.get("text")) for item in variants if _raw_text(item.get("text"))}
    for item in list(variants):
        for extra_variant in build_html_entity_variants(_raw_text(item.get("text")), source=source):
            text = _raw_text(extra_variant.get("text"))
            if not text or text in seen_texts:
                continue
            extra_variant["source_variant_depth"] = _safe_int(item.get("depth"), 0)
            html_variants.append(extra_variant)
            seen_texts.add(text)
    variants.extend(html_variants)
    return variants
