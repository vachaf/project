from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ALLOWED_REQUESTED_TIMEZONE = "Asia/Seoul"
ALLOWED_ANALYSIS_MODE = "full_report"
MAX_TIME_RANGE = timedelta(hours=24)
DEFAULT_ARTIFACT_ROOT_PREFIX = "runs/jobs"
TIME_RANGE_INPUT_KIND = "time_range"
LIVE_SELECTED_INPUT_KIND = "live_selected_logs"
LIVE_SELECTED_SOURCE_TABLE = "apache_security_logs"
MAX_SELECTED_LOG_IDS = 50

_SECRET_REPLACEMENT = "[REDACTED]"
_SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._\-+/=]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)['\"]?[^\s,'\"}]+"),
    re.compile(r"(?i)(x-api-key\s*[:=]\s*)['\"]?[^\s,'\"}]+"),
    re.compile(r"(?i)(token\s*[:=]\s*)['\"]?[^\s,'\"}]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)['\"]?[^\s,'\"}]+"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
]


class AnalysisJobValidationError(ValueError):
    """Raised when a DB-backed analysis job request violates MVP policy."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ValidatedAnalysisJobRequest:
    """Normalized analysis job request for DB insertion.

    Local input/display is limited to Asia/Seoul in the MVP. DB values are UTC
    naive DATETIME(3) strings so they match the Apache log storage policy.
    """

    requested_timezone: str
    analysis_mode: str
    time_from_local: datetime
    time_to_local: datetime
    time_from_utc: datetime
    time_to_utc: datetime
    time_from_db: str
    time_to_db: str

    @property
    def duration(self) -> timedelta:
        return self.time_to_utc - self.time_from_utc

    def duplicate_key(self, requested_by: Optional[int]) -> tuple[Optional[int], str, str, str, str]:
        return (
            requested_by,
            self.analysis_mode,
            self.time_from_db,
            self.time_to_db,
            self.requested_timezone,
        )

    def to_insert_params(self, requested_by: Optional[int], artifact_root: Optional[str] = None) -> Dict[str, Any]:
        return {
            "requested_by": requested_by,
            "time_from": self.time_from_db,
            "time_to": self.time_to_db,
            "requested_timezone": self.requested_timezone,
            "status": "PENDING",
            "analysis_mode": self.analysis_mode,
            "artifact_root": artifact_root,
        }


@dataclass(frozen=True)
class ValidatedSelectedLogRequest:
    """Canonical Live selection before source-row existence is checked."""

    selected_log_ids: tuple[int, ...]
    input_kind: str
    source_table: str
    input_fingerprint: str

    def duplicate_key(self, requested_by: Optional[int]) -> tuple[Optional[int], str, str, str]:
        return (
            requested_by,
            self.input_kind,
            self.source_table,
            self.input_fingerprint,
        )


def selected_log_fingerprint(selected_log_ids: Any) -> str:
    """Hash the sorted unique requested IDs using a stable JSON representation."""

    canonical = sorted(set(selected_log_ids))
    encoded = json.dumps(canonical, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def validate_selected_log_request(selected_log_ids: Any) -> ValidatedSelectedLogRequest:
    if not isinstance(selected_log_ids, list):
        raise AnalysisJobValidationError(
            "invalid_selected_log_ids",
            "selected_log_ids must be a JSON array",
        )
    if not selected_log_ids:
        raise AnalysisJobValidationError(
            "invalid_selected_log_ids",
            "selected_log_ids must contain at least one ID",
        )
    if len(selected_log_ids) > MAX_SELECTED_LOG_IDS:
        raise AnalysisJobValidationError(
            "too_many_selected_log_ids",
            f"selected_log_ids must contain at most {MAX_SELECTED_LOG_IDS} IDs",
        )

    stable_unique: list[int] = []
    seen: set[int] = set()
    for value in selected_log_ids:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise AnalysisJobValidationError(
                "invalid_selected_log_id",
                "selected_log_ids must contain positive integers only",
            )
        if value not in seen:
            seen.add(value)
            stable_unique.append(value)

    return ValidatedSelectedLogRequest(
        selected_log_ids=tuple(stable_unique),
        input_kind=LIVE_SELECTED_INPUT_KIND,
        source_table=LIVE_SELECTED_SOURCE_TABLE,
        input_fingerprint=selected_log_fingerprint(stable_unique),
    )


def _get_zoneinfo(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise AnalysisJobValidationError(
            "invalid_timezone",
            f"unsupported requested_timezone: {tz_name}",
        ) from exc


def parse_input_datetime(value: Any) -> datetime:
    """Parse a Web UI datetime value.

    Accepted examples:
      - 2026-05-28 18:30
      - 2026-05-28 18:30:00
      - 2026-05-28 18:30:00.000
      - 2026-05-28T18:30:00

    Timezone-aware input is accepted but must resolve to the same configured
    requested_timezone through validate_analysis_job_request().
    """

    if not isinstance(value, str):
        raise AnalysisJobValidationError("invalid_datetime", "datetime value must be a string")

    raw = value.strip()
    if not raw:
        raise AnalysisJobValidationError("invalid_datetime", "datetime value is empty")

    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AnalysisJobValidationError("invalid_datetime", f"invalid datetime: {raw}") from exc


def as_local_datetime(value: Any, requested_timezone: str) -> datetime:
    tz = _get_zoneinfo(requested_timezone)
    parsed = parse_input_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise AnalysisJobValidationError("invalid_datetime", "timezone-aware datetime required before UTC conversion")
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_mariadb_datetime3(dt: datetime) -> str:
    """Render a datetime as MariaDB DATETIME(3) string.

    Naive datetimes are treated as already-UTC values. Aware datetimes are first
    converted to UTC and made naive.
    """

    if dt.tzinfo is not None:
        dt = to_utc_naive(dt)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def validate_analysis_job_request(
    *,
    time_from: Any,
    time_to: Any,
    requested_timezone: str = ALLOWED_REQUESTED_TIMEZONE,
    analysis_mode: str = ALLOWED_ANALYSIS_MODE,
    max_time_range: timedelta = MAX_TIME_RANGE,
) -> ValidatedAnalysisJobRequest:
    """Validate and normalize the MVP full_report job request."""

    if requested_timezone != ALLOWED_REQUESTED_TIMEZONE:
        raise AnalysisJobValidationError(
            "unsupported_timezone",
            f"MVP only supports requested_timezone={ALLOWED_REQUESTED_TIMEZONE}",
        )
    if analysis_mode != ALLOWED_ANALYSIS_MODE:
        raise AnalysisJobValidationError(
            "unsupported_analysis_mode",
            f"MVP only supports analysis_mode={ALLOWED_ANALYSIS_MODE}",
        )

    local_from = as_local_datetime(time_from, requested_timezone)
    local_to = as_local_datetime(time_to, requested_timezone)
    utc_from = to_utc_naive(local_from)
    utc_to = to_utc_naive(local_to)

    if utc_from >= utc_to:
        raise AnalysisJobValidationError("invalid_time_range", "time_from must be earlier than time_to")

    duration = utc_to - utc_from
    if duration > max_time_range:
        raise AnalysisJobValidationError(
            "time_range_too_large",
            f"time range must be <= {max_time_range}",
        )

    return ValidatedAnalysisJobRequest(
        requested_timezone=requested_timezone,
        analysis_mode=analysis_mode,
        time_from_local=local_from,
        time_to_local=local_to,
        time_from_utc=utc_from,
        time_to_utc=utc_to,
        time_from_db=to_mariadb_datetime3(utc_from),
        time_to_db=to_mariadb_datetime3(utc_to),
    )


def redact_secret_text(value: Any, max_length: int = 2000) -> str:
    """Return an operator-safe string for error_message/job_events.

    This is intentionally conservative. It is not a full DLP engine, but it
    catches the expected provider-key/header forms before text reaches DB/UI.
    """

    text = "" if value is None else str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}{_SECRET_REPLACEMENT}" if match.groups() else _SECRET_REPLACEMENT, text)
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def build_job_artifact_root(job_id: int, prefix: str = DEFAULT_ARTIFACT_ROOT_PREFIX) -> str:
    if not isinstance(job_id, int) or job_id <= 0:
        raise AnalysisJobValidationError("invalid_job_id", "job_id must be a positive integer")
    safe_prefix = validate_relative_artifact_path(prefix)
    return f"{safe_prefix}/{job_id}"


def validate_relative_artifact_path(path_value: Any) -> str:
    """Validate a server-generated relative artifact path.

    User-provided arbitrary paths must not be accepted by the API. This helper is
    for internal/server-generated paths and guards against accidental absolute or
    traversal paths.
    """

    if not isinstance(path_value, str):
        raise AnalysisJobValidationError("invalid_artifact_path", "artifact path must be a string")
    text = path_value.strip().replace("\\", "/")
    if not text:
        raise AnalysisJobValidationError("invalid_artifact_path", "artifact path is empty")
    if text.startswith("/"):
        raise AnalysisJobValidationError("invalid_artifact_path", "absolute artifact paths are not allowed")
    parts = PurePosixPath(text).parts
    if any(part in {"..", ""} for part in parts):
        raise AnalysisJobValidationError("invalid_artifact_path", "artifact path traversal is not allowed")
    return str(PurePosixPath(*parts))
