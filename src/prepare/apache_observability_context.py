from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, unquote_plus

PLACEHOLDER_STRINGS = {"", "-", "none", "null"}
PROBE_LIKE_NEEDLES = (
    "/.env",
    "/server-status",
    "/wp-login.php",
    "/admin",
    "/private/",
    "/download.php",
    "/does-not-exist",
    "../",
    "%2e%2e",
    "etc/passwd",
    "file=",
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in PLACEHOLDER_STRINGS:
        return ""
    return text


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _append_unique(hints: List[str], hint: str) -> None:
    text = _normalize_text(hint)
    if text and text not in hints:
        hints.append(text)


def _query_string_variants(query_string: str) -> List[str]:
    raw = query_string.lstrip("?")
    if not raw:
        return []
    decoded = unquote_plus(raw)
    if decoded == raw:
        return [raw]
    return [raw, decoded]


def _extract_route_param(query_string: str) -> Optional[str]:
    for variant in _query_string_variants(query_string):
        pairs = parse_qsl(variant, keep_blank_values=True)
        for key, value in pairs:
            if _normalize_text(key).lower() != "_route_":
                continue
            route = _normalize_text(value)
            if route:
                return route
    return None


def _has_route_param(query_string: str) -> bool:
    for variant in _query_string_variants(query_string):
        pairs = parse_qsl(variant, keep_blank_values=True)
        for key, _ in pairs:
            if _normalize_text(key).lower() == "_route_":
                return True
    return False


def _looks_probe_like(uri: str, query_string: str, raw_request_target: str) -> bool:
    samples = [
        uri.lower(),
        query_string.lower(),
        raw_request_target.lower(),
    ]
    combined = " ".join(sample for sample in samples if sample)
    if not combined:
        return False
    return any(needle in combined for needle in PROBE_LIKE_NEEDLES)


def _has_location_header(row: Dict[str, Any]) -> bool:
    for key in ("location", "resp_location", "response_location", "location_header"):
        if _normalize_text(row.get(key)):
            return True
    return False


def build_apache_observability_reason_hints_for_row(row: Dict[str, Any]) -> List[str]:
    uri = _normalize_text(row.get("uri"))
    query_string = _normalize_text(row.get("query_string"))
    raw_request_target = _normalize_text(row.get("raw_request_target"))
    handler = _normalize_text(row.get("handler")).lower()
    status_code = _safe_int(row.get("status_code"), 0)
    has_location = _has_location_header(row)

    route_param_present = _has_route_param(query_string)
    route_param_value = _extract_route_param(query_string)
    probe_like = _looks_probe_like(uri, query_string, raw_request_target)

    hints: List[str] = []

    if route_param_present or handler == "redirect-handler":
        _append_unique(hints, "observability:front_controller_candidate")
    if route_param_present:
        _append_unique(hints, "observability:route_param_present")
    if route_param_value:
        _append_unique(hints, f"observability:route_param={route_param_value}")

    if handler == "proxy-server":
        _append_unique(hints, "observability:reverse_proxy_candidate")
        _append_unique(hints, "observability:backend_response_candidate")

    if handler == "server-status" or uri == "/server-status":
        _append_unique(hints, "observability:server_status_handler_observed")

    if handler == "httpd/unix-directory" or (300 <= status_code <= 399 and has_location):
        _append_unique(hints, "observability:directory_redirect_candidate")

    if 300 <= status_code <= 399 or has_location:
        _append_unique(hints, "observability:redirect_candidate")

    if (
        status_code == 200
        and probe_like
        and (
            handler == "redirect-handler"
            or route_param_present
            or handler == "proxy-server"
        )
    ):
        _append_unique(hints, "observability:fallback_200_candidate")

    if status_code == 200 and handler == "proxy-server" and probe_like:
        _append_unique(hints, "observability:backend_fallback_200_candidate")

    return hints
