from __future__ import annotations

import base64
import binascii
import ipaddress
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, cast
from zoneinfo import ZoneInfo

from web.services.live_log_repository import (
    CursorDirection,
    LiveLogCursor,
    LiveLogPage,
    LiveLogQuery,
    LiveLogRepository,
)
from web.services.live_security_observation import observe_live_security_signals

UTC = timezone.utc
KST = ZoneInfo("Asia/Seoul")
PERIOD_MINUTES = {"5m": 5, "30m": 30, "1h": 60}
PERIOD_OPTIONS = {"all", *PERIOD_MINUTES}
STATUS_OPTIONS = {"2xx", "3xx", "4xx", "5xx", "none"}
METHOD_OPTIONS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT", "TRACE"}
MAX_PAGE_SIZE = 50
MAX_KEYWORD_LENGTH = 256
MAX_CURSOR_LENGTH = 512


class LiveSnapshotValidationError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class LiveSnapshotRequest:
    period: str = "all"
    status_class: Optional[str] = None
    method: Optional[str] = None
    src_ip: Optional[str] = None
    keyword: Optional[str] = None
    limit: int = MAX_PAGE_SIZE
    cursor: Optional[str] = None


class LiveCursorCodec:
    @staticmethod
    def encode(cursor: LiveLogCursor) -> str:
        payload = {"v": 1, "t": cursor.log_time.isoformat(timespec="microseconds"), "i": cursor.row_id, "d": cursor.direction}
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def decode(value: str) -> LiveLogCursor:
        if not value or len(value) > MAX_CURSOR_LENGTH:
            raise LiveSnapshotValidationError("페이지 커서가 올바르지 않습니다.", code="invalid_cursor")
        try:
            raw = base64.b64decode((value + "=" * (-len(value) % 4)).encode("ascii"), altchars=b"-_", validate=True)
            payload = json.loads(raw.decode())
            direction = payload.get("d")
            row_id = payload.get("i")
            if payload.get("v") != 1 or direction not in {"older", "newer"} or isinstance(row_id, bool) or not isinstance(row_id, int) or row_id < 1:
                raise ValueError
            log_time = datetime.fromisoformat(str(payload.get("t") or ""))
            if log_time.tzinfo is not None:
                log_time = log_time.astimezone(UTC).replace(tzinfo=None)
            return LiveLogCursor(log_time, row_id, direction)
        except (UnicodeError, binascii.Error, json.JSONDecodeError, TypeError, ValueError, AttributeError) as exc:
            raise LiveSnapshotValidationError("페이지 커서가 올바르지 않습니다.", code="invalid_cursor") from exc


def _text(value: Optional[str]) -> Optional[str]:
    value = str(value or "").strip()
    return value or None


def _db_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _kst(value: Any) -> Optional[str]:
    parsed = _db_utc(value)
    return parsed.astimezone(KST).isoformat(timespec="milliseconds") if parsed else None


class LiveLogService:
    def __init__(self, repository: LiveLogRepository, *, now_factory: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.repository = repository
        self.now_factory = now_factory

    def _now(self) -> datetime:
        value = self.now_factory()
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def _validate(self, request: LiveSnapshotRequest) -> LiveLogQuery:
        period = str(request.period or "all").strip().lower()
        if period not in PERIOD_OPTIONS:
            raise LiveSnapshotValidationError("기간은 all, 5m, 30m, 1h 중에서 선택해주세요.", code="invalid_period")
        status = _text(request.status_class)
        status = status.lower() if status else None
        if status and status not in STATUS_OPTIONS:
            raise LiveSnapshotValidationError("응답 상태 필터가 올바르지 않습니다.", code="invalid_status")
        method = _text(request.method)
        method = method.upper() if method else None
        if method and method not in METHOD_OPTIONS:
            raise LiveSnapshotValidationError("HTTP 요청 방식이 올바르지 않습니다.", code="invalid_method")
        src_ip = _text(request.src_ip)
        if src_ip:
            try:
                ipaddress.ip_address(src_ip)
            except ValueError as exc:
                raise LiveSnapshotValidationError("IP 주소 전체를 정확히 입력해주세요.", code="invalid_src_ip") from exc
        keyword = _text(request.keyword)
        if keyword and len(keyword) > MAX_KEYWORD_LENGTH:
            raise LiveSnapshotValidationError(f"검색어는 {MAX_KEYWORD_LENGTH}자 이하여야 합니다.", code="keyword_too_long")
        try:
            limit = int(request.limit)
        except (TypeError, ValueError) as exc:
            raise LiveSnapshotValidationError("표시 건수는 숫자여야 합니다.", code="invalid_limit") from exc
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise LiveSnapshotValidationError("표시 건수는 1~50 사이여야 합니다.", code="invalid_limit")
        from_time = None
        if period in PERIOD_MINUTES:
            from_time = (self._now() - timedelta(minutes=PERIOD_MINUTES[period])).replace(tzinfo=None)
        cursor = LiveCursorCodec.decode(_text(request.cursor)) if _text(request.cursor) else None
        return LiveLogQuery(limit, from_time, status, method, src_ip, keyword, cursor)

    @staticmethod
    def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
        serialized = {
            "row_id": int(row["id"]), "request_id": row.get("request_id"),
            "log_time": _kst(row.get("log_time")), "src_ip": row.get("src_ip"),
            "method": row.get("method"), "uri": row.get("uri"),
            "request_target": row.get("request_target"),
            "status_code": int(row["status_code"]) if row.get("status_code") is not None else None,
            "response_body_bytes": int(row["response_body_bytes"]) if row.get("response_body_bytes") is not None else None,
            "user_agent": row.get("user_agent"), "client_ip_source": row.get("client_ip_source"),
            "log_schema": row.get("log_schema"),
        }
        serialized["observation"] = observe_live_security_signals(row)
        return serialized

    @staticmethod
    def _cursor(row: Dict[str, Any], direction: CursorDirection) -> Optional[str]:
        log_time = _db_utc(row.get("log_time"))
        if log_time is None or row.get("id") is None:
            return None
        return LiveCursorCodec.encode(LiveLogCursor(log_time.replace(tzinfo=None), int(row["id"]), cast(CursorDirection, direction)))

    def snapshot(self, request: LiveSnapshotRequest) -> Dict[str, Any]:
        page: LiveLogPage = self.repository.fetch_page(self._validate(request))
        older = self._cursor(page.rows[-1], "older") if page.rows and page.has_older else None
        newer = self._cursor(page.rows[0], "newer") if page.rows and page.has_newer else None
        return {
            "fetched_at": self._now().astimezone(KST).isoformat(timespec="seconds"),
            "latest_log_time": _kst(page.latest_log_time),
            "items": [self._serialize(row) for row in page.rows],
            "older_cursor": older, "newer_cursor": newer,
            "has_older": bool(older), "has_newer": bool(newer), "page_size": len(page.rows),
        }

    def raw_log(self, row_id: int) -> Dict[str, Any]:
        if isinstance(row_id, bool) or row_id < 1:
            raise LiveSnapshotValidationError("DB 행 번호가 올바르지 않습니다.", code="invalid_row_id")
        row = self.repository.fetch_raw_log(row_id)
        if row is None:
            raise LiveSnapshotValidationError("해당 원천 로그를 찾을 수 없습니다.", code="live_log_not_found")
        return {"row_id": int(row["id"]), "raw_log": row.get("raw_log")}
