from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any

import pytest

from web.services.live_log_repository import (
    LiveLogCursor, LiveLogQuery, LiveLogRepository, LiveLogRepositoryError,
    get_live_log_db_config,
)


class Cursor:
    def __init__(self, all_rows=None, one_rows=None):
        self.all_rows = list(all_rows or [])
        self.one_rows = list(one_rows or [])
        self.executions: list[tuple[str, Any]] = []
    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def execute(self, sql, params=None): self.executions.append((sql, params))
    def fetchall(self): return self.all_rows
    def fetchone(self): return self.one_rows.pop(0) if self.one_rows else None


def factory(cursor):
    class Connection:
        def cursor(self): return cursor
    @contextmanager
    def connection(): yield Connection()
    return connection


def item(row_id, second=0): return {"id": row_id, "log_time": datetime(2026, 9, 1, 1, 1, second)}


def test_config_uses_only_log_db_and_requires_reader(monkeypatch):
    monkeypatch.setenv("APP_DB_USER", "analysis_app")
    monkeypatch.setenv("APP_DB_PASSWORD", "must-not-be-used")
    monkeypatch.setenv("DB_HOST", "wrong-host")
    monkeypatch.setenv("LOG_DB_HOST", "log-host")
    monkeypatch.setenv("LOG_DB_USER", "log_reader")
    monkeypatch.setenv("LOG_DB_PASSWORD", "reader-secret")
    monkeypatch.setenv("LOG_DB_NAME", "web_logs")
    config = get_live_log_db_config()
    assert (config["host"], config["user"], config["password"]) == ("log-host", "log_reader", "reader-secret")
    assert config["autocommit"] is True
    monkeypatch.setenv("LOG_DB_USER", "log_writer")
    with pytest.raises(LiveLogRepositoryError, match="log_reader"):
        get_live_log_db_config()


def test_page_query_is_parameterized_select_only_and_uses_51_lookahead():
    rows = [item(number, number % 60) for number in range(100, 49, -1)]
    cursor = Cursor(rows, [{"log_time": datetime(2026, 9, 1, 2)}])
    page = LiveLogRepository(factory(cursor)).fetch_page(LiveLogQuery(
        50, status_class="4xx", method="GET", src_ip="192.0.2.1", keyword="100%_ok"
    ))
    assert len(page.rows) == 50 and page.has_older is True
    sql, params = cursor.executions[0]
    assert sql.lstrip().upper().startswith("SELECT")
    assert "ORDER BY log_time DESC, id DESC" in sql
    assert "src_ip = %s" in sql and "request_target LIKE %s" in sql
    assert params[-1] == 51
    assert all(word not in sql.upper() for word in ("INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "CREATE", "COMMIT"))
    assert all(execution[0].lstrip().upper().startswith("SELECT") for execution in cursor.executions)


def test_same_time_tie_break_and_newer_page_restore_descending_order():
    boundary = datetime(2026, 9, 1, 1)
    sql, params = LiveLogRepository._build_page_query(LiveLogQuery(50, cursor=LiveLogCursor(boundary, 50, "older")))
    assert "id < %s" in sql and "ORDER BY log_time DESC, id DESC" in sql and params[-1] == 51
    cursor = Cursor([item(51), item(52), item(53)], [{"log_time": boundary}])
    page = LiveLogRepository(factory(cursor)).fetch_page(LiveLogQuery(2, cursor=LiveLogCursor(boundary, 50, "newer")))
    assert [row["id"] for row in page.rows] == [52, 51]
    assert "ORDER BY log_time ASC, id ASC" in cursor.executions[0][0]
    assert page.has_newer is True and page.has_older is True


def test_older_newer_round_trip_has_no_gap_or_duplicate_at_same_time():
    timestamp = datetime(2026, 9, 1, 1)
    all_ids = list(range(120, 0, -1))
    latest = all_ids[:50]
    older_boundary = latest[-1]
    older_candidates = [row_id for row_id in all_ids if row_id < older_boundary]
    older = older_candidates[:50]
    newer_boundary = older[0]
    newer_candidates_asc = sorted(row_id for row_id in all_ids if row_id > newer_boundary)
    newer = list(reversed(newer_candidates_asc[:50]))

    assert latest == list(range(120, 70, -1))
    assert older == list(range(70, 20, -1))
    assert set(latest).isdisjoint(older)
    assert newer == latest

    older_sql, _ = LiveLogRepository._build_page_query(
        LiveLogQuery(50, cursor=LiveLogCursor(timestamp, older_boundary, "older"))
    )
    newer_sql, _ = LiveLogRepository._build_page_query(
        LiveLogQuery(50, cursor=LiveLogCursor(timestamp, newer_boundary, "newer"))
    )
    assert "id < %s" in older_sql and "ORDER BY log_time DESC, id DESC" in older_sql
    assert "id > %s" in newer_sql and "ORDER BY log_time ASC, id ASC" in newer_sql


def test_raw_log_is_separate_exact_select_and_is_not_in_page_select():
    raw = '<script>alert("x")</script> & 한글\nnext'
    cursor = Cursor(one_rows=[{"id": 7, "raw_log": raw}])
    repository = LiveLogRepository(factory(cursor))
    assert repository.fetch_raw_log(7) == {"id": 7, "raw_log": raw}
    sql, params = cursor.executions[0]
    assert "SELECT id, raw_log" in sql and "WHERE id = %s LIMIT 1" in sql
    assert params == [7]
    page_sql, _ = repository._build_page_query(LiveLogQuery(50))
    assert "raw_log" not in page_sql


def test_repository_wraps_secret_database_errors():
    @contextmanager
    def broken():
        raise RuntimeError("password=secret")
        yield
    with pytest.raises(LiveLogRepositoryError) as error:
        LiveLogRepository(broken).fetch_page(LiveLogQuery(50))
    assert str(error.value) == "live log database query failed"
    assert "secret" not in str(error.value)
