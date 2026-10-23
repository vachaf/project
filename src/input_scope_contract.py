"""Validation for the optional analysis-input scope carried between stages."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


WINDOW_ROLES = {
    "live_selected_logs": "selected_log_timestamp_envelope",
    "time_range": "query_filter",
}


def validate_input_scope(value: Any) -> dict[str, Any] | None:
    """Return a validated copy; explicit null remains distinct from absence."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("input scope: expected object or null")
    kind = value.get("kind")
    if not isinstance(kind, str) or kind not in WINDOW_ROLES:
        raise ValueError("input scope: unsupported kind")
    if value.get("window_role") != WINDOW_ROLES[kind]:
        raise ValueError("input scope: window_role conflicts with kind")
    allowed_keys = {"kind", "window_role", "window"}
    if kind == "live_selected_logs":
        count = value.get("selected_id_count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0 or count > 50:
            raise ValueError("input scope: invalid selected_id_count")
        allowed_keys.add("selected_id_count")
    if set(value) != allowed_keys:
        raise ValueError("input scope: unexpected or missing fields")

    window = value["window"]
    if window is None:
        return dict(value)
    if not isinstance(window, dict) or set(window) != {"start", "end_exclusive", "timezone"}:
        raise ValueError("input scope: invalid window shape")
    start, end, timezone_name = (window[key] for key in ("start", "end_exclusive", "timezone"))
    if not all(isinstance(item, str) and item.strip() for item in (start, end, timezone_name)):
        raise ValueError("input scope: incomplete window")
    try:
        start_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(end.replace("Z", "+00:00"))
        zone = ZoneInfo(timezone_name)
        if start_time.tzinfo is None or end_time.tzinfo is None or start_time >= end_time:
            raise ValueError
        if start_time.utcoffset() != start_time.astimezone(zone).utcoffset():
            raise ValueError
        if end_time.utcoffset() != end_time.astimezone(zone).utcoffset():
            raise ValueError
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("input scope: invalid window") from exc
    return {**value, "window": dict(window)}
