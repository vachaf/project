from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional

import pymysql
from pymysql.cursors import DictCursor

LIVE_LOG_TABLE = "web_logs.apache_security_logs"
CursorDirection = Literal["older", "newer"]


class LiveLogRepositoryError(RuntimeError):
    """Raised when the read-only source-log query cannot be completed."""


@dataclass(frozen=True)
class LiveLogCursor:
    log_time: datetime
    row_id: int
    direction: CursorDirection


@dataclass(frozen=True)
class LiveLogQuery:
    limit: int
    from_time: Optional[datetime] = None
    status_class: Optional[str] = None
    method: Optional[str] = None
    src_ip: Optional[str] = None
    keyword: Optional[str] = None
    cursor: Optional[LiveLogCursor] = None


@dataclass(frozen=True)
class LiveLogPage:
    latest_log_time: Optional[datetime]
    rows: List[Dict[str, Any]]
    has_older: bool
    has_newer: bool


def _timeout(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise LiveLogRepositoryError(f"{name} must be an integer") from exc
    if value < 1:
        raise LiveLogRepositoryError(f"{name} must be positive")
    return value


def get_live_log_db_config() -> Dict[str, Any]:
    """Read only LOG_DB_*; never use the analysis-job DB configuration."""

    user = str(os.getenv("LOG_DB_USER", "log_reader") or "").strip()
    host = str(os.getenv("LOG_DB_HOST", "") or "").strip()
    password = str(os.getenv("LOG_DB_PASSWORD", "") or "")
    database = str(os.getenv("LOG_DB_NAME", "web_logs") or "").strip()
    if user != "log_reader":
        raise LiveLogRepositoryError("Live Monitoring requires LOG_DB_USER=log_reader")
    if not host:
        raise LiveLogRepositoryError("LOG_DB_HOST is required for Live Monitoring")
    if not password:
        raise LiveLogRepositoryError("LOG_DB_PASSWORD is required for Live Monitoring")
    if database != "web_logs":
        raise LiveLogRepositoryError("Live Monitoring requires LOG_DB_NAME=web_logs")
    try:
        port = int(os.getenv("LOG_DB_PORT", "3306"))
    except (TypeError, ValueError) as exc:
        raise LiveLogRepositoryError("LOG_DB_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise LiveLogRepositoryError("LOG_DB_PORT must be between 1 and 65535")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "charset": "utf8mb4",
        "autocommit": True,
        "connect_timeout": _timeout("LOG_DB_CONNECT_TIMEOUT_SEC", 5),
        "read_timeout": _timeout("LOG_DB_READ_TIMEOUT_SEC", 10),
        "write_timeout": _timeout("LOG_DB_WRITE_TIMEOUT_SEC", 10),
        "cursorclass": DictCursor,
    }


@contextmanager
def live_log_db_connection() -> Iterator[pymysql.connections.Connection]:
    connection = pymysql.connect(**get_live_log_db_config())
    try:
        yield connection
    finally:
        connection.close()


def _escape_like_literal(value: str) -> str:
    return value.replace("=", "==").replace("%", "=%").replace("_", "=_")


class LiveLogRepository:
    def __init__(self, connection_factory: Callable[[], Any] = live_log_db_connection) -> None:
        self.connection_factory = connection_factory

    @staticmethod
    def _build_page_query(query: LiveLogQuery) -> tuple[str, List[Any]]:
        where: List[str] = []
        params: List[Any] = []
        if query.from_time is not None:
            where.append("log_time >= %s")
            params.append(query.from_time)
        if query.status_class is not None:
            if query.status_class == "none":
                where.append("status_code IS NULL")
            else:
                start = int(query.status_class[0]) * 100
                where.append("status_code >= %s AND status_code < %s")
                params.extend((start, start + 100))
        if query.method is not None:
            where.append("method = %s")
            params.append(query.method)
        if query.src_ip is not None:
            where.append("src_ip = %s")
            params.append(query.src_ip)
        if query.keyword is not None:
            pattern = f"%{_escape_like_literal(query.keyword)}%"
            where.append("(uri LIKE %s ESCAPE '=' OR request_target LIKE %s ESCAPE '=')")
            params.extend((pattern, pattern))

        direction: CursorDirection = "older"
        if query.cursor is not None:
            direction = query.cursor.direction
            comparator = "<" if direction == "older" else ">"
            where.append(
                f"(log_time {comparator} %s OR (log_time = %s AND id {comparator} %s))"
            )
            params.extend((query.cursor.log_time, query.cursor.log_time, query.cursor.row_id))
        order = "ASC" if direction == "newer" else "DESC"
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"""
            SELECT id, request_id, log_time, src_ip, method, uri, request_target,
                   status_code, response_body_bytes, user_agent, client_ip_source, log_schema
            FROM {LIVE_LOG_TABLE}
            {where_sql}
            ORDER BY log_time {order}, id {order}
            LIMIT %s
        """
        params.append(query.limit + 1)
        return sql, params

    def fetch_page(self, query: LiveLogQuery) -> LiveLogPage:
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    sql, params = self._build_page_query(query)
                    cursor.execute(sql, params)
                    fetched = list(cursor.fetchall())
                    cursor.execute(
                        f"SELECT log_time FROM {LIVE_LOG_TABLE} "
                        "ORDER BY log_time DESC, id DESC LIMIT 1"
                    )
                    latest = cursor.fetchone()
        except LiveLogRepositoryError:
            raise
        except Exception as exc:
            raise LiveLogRepositoryError("live log database query failed") from exc

        extra = len(fetched) > query.limit
        rows = fetched[: query.limit]
        direction = query.cursor.direction if query.cursor else "older"
        if direction == "newer":
            rows.reverse()
        return LiveLogPage(
            latest_log_time=(latest or {}).get("log_time"),
            rows=rows,
            has_older=extra if direction == "older" else bool(rows and query.cursor),
            has_newer=extra if direction == "newer" else bool(rows and query.cursor),
        )

    def fetch_raw_log(self, row_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT id, raw_log FROM {LIVE_LOG_TABLE} WHERE id = %s LIMIT 1",
                        [row_id],
                    )
                    row = cursor.fetchone()
        except LiveLogRepositoryError:
            raise
        except Exception as exc:
            raise LiveLogRepositoryError("live log database query failed") from exc
        return dict(row) if row is not None else None
