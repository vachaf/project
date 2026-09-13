from __future__ import annotations

import json
import asyncio
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest

import analysis_job_worker
import web.routes.live as live_routes
from export_db_logs_cli import (
    DBConfig,
    LogExporter,
    RangeConfig,
    build_export_payload,
)
from full_report_job_runner import FullReportJobRunner, FullReportRunnerError
from web.services.analysis_job_policy import (
    AnalysisJobValidationError,
    selected_log_fingerprint,
    validate_selected_log_request,
)
from web.services.analysis_job_repository import (
    AnalysisJobRepository,
    AnalysisJobRepositoryError,
    CreatedSelectedAnalysisJob,
)


def test_selected_policy_stable_dedupes_and_fingerprints_sorted_unique_ids() -> None:
    request = validate_selected_log_request([9, 2, 9, 7, 2])

    assert request.selected_log_ids == (9, 2, 7)
    assert request.input_kind == "live_selected_logs"
    assert request.source_table == "apache_security_logs"
    assert request.input_fingerprint == selected_log_fingerprint([2, 7, 9])
    assert request.input_fingerprint == validate_selected_log_request([7, 9, 2]).input_fingerprint


@pytest.mark.parametrize("value", [True, False, 0, -1, "1", 1.5, None])
def test_selected_policy_requires_positive_json_integers(value: Any) -> None:
    with pytest.raises(AnalysisJobValidationError, match="positive integers"):
        validate_selected_log_request([value])


def test_selected_policy_caps_raw_selection_at_50() -> None:
    assert len(validate_selected_log_request(list(range(1, 51))).selected_log_ids) == 50
    with pytest.raises(AnalysisJobValidationError) as exc:
        validate_selected_log_request(list(range(1, 52)))
    assert exc.value.code == "too_many_selected_log_ids"


def _json_request(payload: Any):
    from starlette.requests import Request

    body = json.dumps(payload).encode("utf-8")
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({"type": "http", "method": "POST", "path": "/api/live/jobs/create", "headers": []}, receive)


def test_live_selected_creation_endpoint_returns_partial_missing_details(monkeypatch) -> None:
    class Repository:
        def create_live_selected_logs_job(self, **kwargs):
            assert kwargs["requested_by"] is None
            assert kwargs["validated_request"].selected_log_ids == (5, 99, 1)
            return CreatedSelectedAnalysisJob(
                job_id=42,
                artifact_root="runs/jobs/42",
                selected_log_ids=(5, 99, 1),
                missing_log_ids=(99,),
            )

    monkeypatch.setattr(live_routes, "selected_job_repository", Repository())
    response = asyncio.run(
        live_routes.create_live_selected_logs_job(_json_request({"selected_log_ids": [5, 99, 1, 5]}))
    )
    payload = json.loads(response.body)
    assert response.status_code == 200
    assert payload["status"] == "PENDING" and payload["job_id"] == 42
    assert payload["selected_log_ids"] == [5, 99, 1]
    assert payload["missing_log_ids"] == [99]


def test_live_selected_creation_endpoint_returns_no_data_without_job(monkeypatch) -> None:
    class Repository:
        def create_live_selected_logs_job(self, **_kwargs):
            return CreatedSelectedAnalysisJob(job_id=None, selected_log_ids=(4,), missing_log_ids=(4,))

    monkeypatch.setattr(live_routes, "selected_job_repository", Repository())
    response = asyncio.run(
        live_routes.create_live_selected_logs_job(_json_request({"selected_log_ids": [4]}))
    )
    payload = json.loads(response.body)
    assert response.status_code == 200
    assert payload["status"] == payload["code"] == "NO_DATA"
    assert payload["job_id"] is None


class _ExactCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.sql = ""
        self.params: list[int] = []

    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def execute(self, sql: str, params: list[int]) -> None:
        self.sql = " ".join(sql.split())
        self.params = params
    def fetchall(self) -> list[dict[str, Any]]: return self.rows


class _ExactConnection:
    def __init__(self, cursor: _ExactCursor) -> None: self._cursor = cursor
    def ping(self, reconnect: bool = True) -> None: return None
    def cursor(self) -> _ExactCursor: return self._cursor


def test_exact_export_query_excludes_unselected_middle_row_and_orders_canonically() -> None:
    rows = [
        {"id": 30, "log_time": datetime(2026, 1, 1, 1)},
        {"id": 10, "log_time": datetime(2026, 1, 1, 2)},
    ]
    cursor = _ExactCursor(rows)
    exporter = LogExporter(DBConfig("h", 3306, "u", "p", "web_logs"))
    exporter.conn = _ExactConnection(cursor)

    assert exporter.fetch_rows_by_ids("apache_security_logs", [10, 30]) == rows
    assert "WHERE id IN (%s, %s)" in cursor.sql
    assert "log_time >=" not in cursor.sql and "log_time <" not in cursor.sql
    assert "ORDER BY log_time ASC, id ASC" in cursor.sql
    assert cursor.params == [10, 30]


def _range() -> RangeConfig:
    from datetime import timezone
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 3, tzinfo=timezone.utc)
    return RangeConfig("custom", "Asia/Seoul", "UTC", start, end, start, end)


def test_exact_id_empty_export_preserves_existing_json_schema() -> None:
    payload = build_export_payload(
        "web_logs",
        "security",
        _range(),
        None,
        {"access": [], "security": [], "error": []},
        selected_log_ids=[10, 30],
    )

    assert set(payload) == {"meta", "counts", "data"}
    assert payload["meta"]["total_count"] == 0
    assert payload["counts"] == {"access": 0, "security": 0, "error": 0}
    assert payload["data"] == {"access": [], "security": [], "error": []}


def _selected_job(**overrides: Any) -> dict[str, Any]:
    ids = [30, 10]
    selected_input_rows = [
        {
            "job_id": 8,
            "source_id": 30,
            "selection_index": 0,
            "found_at_submission": 1,
            "log_time_at_submission": datetime(2026, 1, 1),
            "created_at": datetime(2026, 1, 1, 0, 0, 1),
        },
        {
            "job_id": 8,
            "source_id": 10,
            "selection_index": 1,
            "found_at_submission": 0,
            "log_time_at_submission": None,
            "created_at": datetime(2026, 1, 1, 0, 0, 1),
        },
    ]
    job = {
        "id": 8,
        "time_from": datetime(2026, 1, 1),
        "time_to": datetime(2026, 1, 3),
        "requested_timezone": "Asia/Seoul",
        "artifact_root": "runs/jobs/8",
        "analysis_mode": "full_report",
        "input_kind": "live_selected_logs",
        "input_source_table": "apache_security_logs",
        "input_fingerprint": selected_log_fingerprint(ids),
        "selected_input_rows": selected_input_rows,
    }
    job.update(overrides)
    return job


class _EmptyExactSubprocess:
    def __init__(self) -> None: self.calls: list[list[str]] = []
    def __call__(self, cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "meta": {"total_count": 0},
                    "counts": {"access": 0, "security": 0, "error": 0},
                    "data": {"access": [], "security": [], "error": []},
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def test_selected_runner_accepts_over_24h_metadata_and_passes_exact_ids(tmp_path: Path) -> None:
    fake = _EmptyExactSubprocess()
    result = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake).run(_selected_job())

    assert result.no_data is True
    cmd = fake.calls[0]
    assert [cmd[index + 1] for index, value in enumerate(cmd) if value == "--selected-log-id"] == ["30", "10"]
    assert "--start" in cmd and "--end" in cmd


@pytest.mark.parametrize(
    "override",
    [
        {"input_kind": "corrupt"},
        {"input_source_table": "apache_access_logs"},
        {"input_fingerprint": "0" * 64},
        {"selected_input_rows": []},
        {
            "selected_input_rows": [
                {
                    "job_id": 8, "source_id": 30, "selection_index": 0,
                    "found_at_submission": 0, "log_time_at_submission": datetime(2026, 1, 1),
                    "created_at": datetime(2026, 1, 1),
                }
            ]
        },
    ],
)
def test_corrupt_selected_metadata_fails_without_time_range_fallback(
    tmp_path: Path, override: dict[str, Any]
) -> None:
    fake = _EmptyExactSubprocess()
    with pytest.raises(FullReportRunnerError) as exc:
        FullReportJobRunner(project_root=tmp_path, subprocess_run=fake).run(_selected_job(**override))
    assert exc.value.failed_at_stage == "export"
    assert fake.calls == []


def test_corrupt_selected_row_identity_and_found_flag_never_fall_back(tmp_path: Path) -> None:
    for mutation in (
        {"job_id": 99},
        {"selection_index": 4},
        {"source_id": "30"},
        {"found_at_submission": 1.0},
        {"created_at": None},
    ):
        rows = [dict(row) for row in _selected_job()["selected_input_rows"]]
        rows[0].update(mutation)
        fake = _EmptyExactSubprocess()
        with pytest.raises(FullReportRunnerError) as exc:
            FullReportJobRunner(project_root=tmp_path, subprocess_run=fake).run(
                _selected_job(selected_input_rows=rows)
            )
        assert exc.value.failed_at_stage == "export"
        assert fake.calls == []


def test_selected_child_projection_returns_full_authoritative_rows() -> None:
    expected = {
        "job_id": 8,
        "source_id": 30,
        "selection_index": 0,
        "found_at_submission": 1,
        "log_time_at_submission": datetime(2026, 1, 1),
        "created_at": datetime(2026, 1, 1, 0, 0, 1),
    }

    class Cursor:
        sql = ""
        params = ()
        def execute(self, sql, params):
            self.sql = " ".join(sql.split())
            self.params = params
        def fetchall(self): return [expected]

    cursor = Cursor()
    rows = AnalysisJobRepository._select_selected_input_rows(cursor, 8)
    assert rows == [expected]
    assert cursor.params == (8,)
    assert "FROM analysis_job_selected_input_rows" in cursor.sql
    for column in (
        "job_id", "source_id", "selection_index", "found_at_submission",
        "log_time_at_submission", "created_at",
    ):
        assert column in cursor.sql


class _CreationState:
    def __init__(self, source_times: Optional[dict[int, datetime]] = None) -> None:
        self.source_times = source_times or {}
        self.jobs: list[dict[str, Any]] = []
        self.children: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.connections: list[_CreationConnection] = []
        self.lock = threading.Lock()
        self.next_id = 1
        self.fail_child_index: Optional[int] = None

    def factory(self) -> "_CreationConnection":
        connection = _CreationConnection(self)
        self.connections.append(connection)
        return connection


class _CreationConnection:
    def __init__(self, state: _CreationState) -> None:
        self.state = state
        self.pending_jobs: list[dict[str, Any]] = []
        self.pending_children: list[dict[str, Any]] = []
        self.pending_events: list[dict[str, Any]] = []
        self.commits = 0
        self.rollbacks = 0
        self.lock_held = False

    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def cursor(self): return _CreationCursor(self)
    def commit(self) -> None:
        self.state.jobs.extend(self.pending_jobs)
        self.state.children.extend(self.pending_children)
        self.state.events.extend(self.pending_events)
        self.pending_jobs = []
        self.pending_children = []
        self.pending_events = []
        self.commits += 1
    def rollback(self) -> None:
        self.pending_jobs = []
        self.pending_children = []
        self.pending_events = []
        self.rollbacks += 1


class _CreationCursor:
    def __init__(self, connection: _CreationConnection) -> None:
        self.connection = connection
        self.state = connection.state
        self.result: list[dict[str, Any]] = []
        self.rowcount = 0
        self.lastrowid = 0

    def __enter__(self): return self
    def __exit__(self, *_args): return None

    def execute(self, sql: str, params: Any = ()) -> None:
        normalized = " ".join(sql.lower().split())
        self.result = []
        self.rowcount = 0
        if "get_lock(" in normalized:
            acquired = self.state.lock.acquire(timeout=float(params[1]))
            self.connection.lock_held = acquired
            self.result = [{"acquired": 1 if acquired else 0}]
        elif "release_lock(" in normalized:
            assert self.connection.lock_held
            self.connection.lock_held = False
            self.state.lock.release()
            self.result = [{"released": 1}]
        elif normalized == "start transaction":
            return
        elif "from apache_security_logs" in normalized:
            self.result = [
                {"id": log_id, "log_time": self.state.source_times[log_id]}
                for log_id in params
                if log_id in self.state.source_times
            ]
        elif "select id, artifact_root from analysis_jobs" in normalized:
            requested_by, input_kind, source, fingerprint = params
            self.result = [
                {"id": job["id"], "artifact_root": job.get("artifact_root")}
                for job in reversed(self.state.jobs)
                if job["requested_by"] == requested_by
                and job["input_kind"] == input_kind
                and job["input_source_table"] == source
                and job["input_fingerprint"] == fingerprint
                and job["status"] in {"PENDING", "RUNNING"}
            ][:1]
        elif normalized.startswith("insert into analysis_jobs"):
            job_id = self.state.next_id
            self.state.next_id += 1
            self.lastrowid = job_id
            self.connection.pending_jobs.append(
                {
                    "id": job_id,
                    "requested_by": params[0],
                    "time_from": params[1],
                    "time_to": params[2],
                    "status": "PENDING",
                    "input_kind": params[3],
                    "input_source_table": params[4],
                    "input_fingerprint": params[5],
                    "artifact_root": None,
                }
            )
            self.rowcount = 1
        elif normalized.startswith("update analysis_jobs set artifact_root"):
            self.connection.pending_jobs[-1]["artifact_root"] = params[0]
            self.rowcount = 1
        elif normalized.startswith("insert into analysis_job_selected_input_rows"):
            if self.state.fail_child_index == params[2]:
                raise RuntimeError("injected child insert failure")
            self.connection.pending_children.append(
                {
                    "job_id": params[0],
                    "source_id": params[1],
                    "selection_index": params[2],
                    "found_at_submission": params[3],
                    "log_time_at_submission": params[4],
                    "created_at": datetime(2026, 1, 3),
                }
            )
            self.rowcount = 1
        elif normalized.startswith("insert into job_events"):
            self.connection.pending_events.append(
                {"job_id": params[0], "event_type": "JOB_CREATED", "detail_json": params[2]}
            )
            self.rowcount = 1
        else:
            raise AssertionError(normalized)

    def fetchone(self) -> Optional[dict[str, Any]]:
        return self.result[0] if self.result else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.result)


def _creation_request(ids: list[int]):
    return validate_selected_log_request(ids)


def test_selected_creation_is_atomic_and_partial_missing_preserves_child_order() -> None:
    state = _CreationState(
        {5: datetime(2026, 1, 3), 1: datetime(2026, 1, 1)}
    )
    result = AnalysisJobRepository(state.factory).create_live_selected_logs_job(
        requested_by=7,
        validated_request=_creation_request([5, 99, 1, 5]),
    )

    assert result.job_id == 1 and result.missing_log_ids == (99,)
    assert [
        (
            row["selection_index"], row["source_id"], row["found_at_submission"],
            row["log_time_at_submission"],
        )
        for row in state.children
    ] == [
        (0, 5, 1, "2026-01-03 00:00:00.000"),
        (1, 99, 0, None),
        (2, 1, 1, "2026-01-01 00:00:00.000"),
    ]
    assert len(state.jobs) == 1 and len(state.events) == 1
    assert datetime.fromisoformat(state.jobs[0]["time_to"]) - datetime.fromisoformat(state.jobs[0]["time_from"]) > timedelta(hours=24)
    assert state.connections[0].commits == 1


def test_all_missing_returns_no_data_without_job() -> None:
    state = _CreationState()
    result = AnalysisJobRepository(state.factory).create_live_selected_logs_job(
        requested_by=None,
        validated_request=_creation_request([4, 8]),
    )
    assert result.no_data and result.missing_log_ids == (4, 8)
    assert state.jobs == state.children == state.events == []
    assert state.connections[0].commits == 0


def test_selected_creation_rolls_back_parent_children_and_event_on_failure() -> None:
    state = _CreationState({1: datetime(2026, 1, 1), 2: datetime(2026, 1, 2)})
    state.fail_child_index = 1
    with pytest.raises(AnalysisJobRepositoryError):
        AnalysisJobRepository(state.factory).create_live_selected_logs_job(
            requested_by=3,
            validated_request=_creation_request([1, 2]),
        )
    assert state.jobs == state.children == state.events == []
    assert state.connections[0].rollbacks >= 1


def test_null_requested_by_duplicate_is_null_safe_and_lock_uses_same_connection() -> None:
    state = _CreationState({1: datetime(2026, 1, 1)})
    repo = AnalysisJobRepository(state.factory)
    first = repo.create_live_selected_logs_job(requested_by=None, validated_request=_creation_request([1]))
    second = repo.create_live_selected_logs_job(requested_by=None, validated_request=_creation_request([1]))
    assert first.created and second.duplicate_existing_job_id == first.job_id
    assert len(state.jobs) == 1
    assert all(not connection.lock_held for connection in state.connections)


def test_concurrent_duplicate_submission_creates_one_active_job() -> None:
    state = _CreationState({1: datetime(2026, 1, 1)})
    repo = AnalysisJobRepository(state.factory)
    barrier = threading.Barrier(3)
    results = []

    def submit() -> None:
        barrier.wait()
        results.append(
            repo.create_live_selected_logs_job(
                requested_by=11,
                validated_request=_creation_request([1]),
            )
        )

    threads = [threading.Thread(target=submit) for _ in range(2)]
    for thread in threads: thread.start()
    barrier.wait()
    for thread in threads: thread.join(timeout=2)
    assert len(results) == 2 and len(state.jobs) == 1
    assert sum(result.created for result in results) == 1
    assert sum(result.duplicate_existing_job_id is not None for result in results) == 1


class _WorkerRepository:
    def __init__(self, claimed: dict[str, Any]) -> None:
        self.claimed = claimed
        self.events: list[dict[str, Any]] = []
        self.failed: list[dict[str, Any]] = []
        self.succeeded: list[dict[str, Any]] = []
        self.upserts: list[dict[str, Any]] = []
    def claim_next_pending_full_report_job(self, **_kwargs):
        claimed, self.claimed = self.claimed, None
        return claimed
    def append_job_event(self, **kwargs): self.events.append(kwargs)
    def update_job_heartbeat(self, **_kwargs): return True
    def upsert_analysis_report(self, **kwargs): self.upserts.append(kwargs)
    def mark_job_succeeded(self, **kwargs): self.succeeded.append(kwargs); return True
    def mark_job_failed(self, **kwargs): self.failed.append(kwargs); return True


def test_worker_passes_selected_metadata_to_runner_and_keeps_job_no_data_lifecycle() -> None:
    repo = _WorkerRepository(_selected_job(status="RUNNING", worker_id="w"))

    class Runner:
        received = None
        def run(self, claimed, event_sink=None):
            self.received = dict(claimed)
            return {
                "artifact_root": "runs/jobs/8", "summary": "No logs found", "no_data": True,
                "export_path": "runs/jobs/8/export.json",
            }

    runner = Runner()
    assert analysis_job_worker.run_once(
        repo, worker_id="w", run_pipeline=True, runner=runner, heartbeat_interval=0.01
    ) == 0
    assert runner.received["input_kind"] == "live_selected_logs"
    assert [row["source_id"] for row in runner.received["selected_input_rows"]] == [30, 10]
    assert runner.received["selected_input_rows"][1]["found_at_submission"] == 0
    assert "JOB_NO_DATA" in [event["event_type"] for event in repo.events]
    assert repo.succeeded and not repo.failed


def test_worker_marks_corrupt_selected_input_failed_without_fallback(tmp_path: Path) -> None:
    repo = _WorkerRepository(_selected_job(status="RUNNING", worker_id="w", input_fingerprint="bad"))
    fake = _EmptyExactSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)
    assert analysis_job_worker.run_once(
        repo, worker_id="w", run_pipeline=True, runner=runner, heartbeat_interval=0.01
    ) == 1
    assert repo.failed and not repo.succeeded and not repo.upserts
    assert fake.calls == []


def test_ddl_contains_selected_input_columns_child_constraints_and_read_only_source_grant() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = (root / "docs/operations/sql/01_analysis_job_tables.sql").read_text(encoding="utf-8")
    migration = (root / "docs/operations/sql/02_live_selected_input_v1.sql").read_text(encoding="utf-8")
    grants = (root / "docs/operations/sql/11_analysis_app_grants.sql").read_text(encoding="utf-8")
    verification = (root / "docs/operations/sql/90_verify_mariadb_setup.sql").read_text(encoding="utf-8")
    for text in (schema, migration):
        assert "input_kind" in text and "input_source_table" in text and "input_fingerprint" in text
        assert "analysis_job_selected_input_rows" in text
        assert "analysis_job_selected_logs" not in text
        for column in (
            "job_id", "source_id", "selection_index", "found_at_submission",
            "log_time_at_submission", "created_at",
        ):
            assert column in text
        assert "PRIMARY KEY (job_id, selection_index)" in text
        assert "UNIQUE KEY uk_analysis_job_selected_input_source (job_id, source_id)" in text
        assert "found_at_submission = 1 AND log_time_at_submission IS NOT NULL" in text
        assert "found_at_submission = 0 AND log_time_at_submission IS NULL" in text
        table_ddl = text.split(
            "CREATE TABLE IF NOT EXISTS analysis_job_selected_input_rows", 1
        )[1].split(") ENGINE=InnoDB", 1)[0]
        for column in (
            "job_id", "source_id", "selection_index", "found_at_submission",
            "log_time_at_submission", "created_at",
        ):
            assert column in table_ddl
        assert "selected_log_id" not in table_ddl
    assert "GRANT SELECT ON web_logs.apache_security_logs" in grants
    assert "GRANT SELECT, INSERT ON web_logs.analysis_job_selected_input_rows" in grants
    assert "DESCRIBE analysis_job_selected_input_rows" in verification
    assert "SHOW INDEX FROM analysis_job_selected_input_rows" in verification
