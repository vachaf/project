from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

from web.services.analysis_job_repository import ANALYSIS_REPORT_UPSERT_COLUMNS, AnalysisJobRepository


class FakeDb:
    def __init__(self, jobs: Optional[List[Dict[str, Any]]] = None) -> None:
        self.jobs = jobs or []
        self.events: List[Dict[str, Any]] = []
        self.reports: List[Dict[str, Any]] = []
        self.sql_statements: List[str] = []
        self.commits = 0
        self.rollbacks = 0
        self._tick = 0

    def now(self) -> str:
        self._tick += 1
        return f"2026-05-31 00:00:00.{self._tick:03d}"


class FakeConnection:
    def __init__(self, db: FakeDb) -> None:
        self.db = db

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def cursor(self) -> "FakeCursor":
        return FakeCursor(self.db)

    def commit(self) -> None:
        self.db.commits += 1

    def rollback(self) -> None:
        self.db.rollbacks += 1


class FakeCursor:
    def __init__(self, db: FakeDb) -> None:
        self.db = db
        self.rowcount = 0
        self._rows: List[Dict[str, Any]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        normalized = " ".join(sql.lower().split())
        self.db.sql_statements.append(normalized)
        self.rowcount = 0
        self._rows = []

        if normalized == "start transaction":
            return

        if "select * from analysis_jobs" in normalized and "for update" in normalized:
            candidates = [
                row
                for row in self.db.jobs
                if row["status"] == "PENDING"
                and row["analysis_mode"] == "full_report"
                and row["attempt_count"] < row["max_attempts"]
            ]
            candidates.sort(key=lambda row: (row["created_at"], row["id"]))
            self._rows = [deepcopy(candidates[0])] if candidates else []
            return

        if "select id, requested_by" in normalized and "from analysis_jobs" in normalized:
            job_id = int(params[0])
            job = self._job(job_id)
            self._rows = [deepcopy(job)] if job else []
            return

        if "update analysis_jobs set status = 'running'" in normalized:
            worker_id, job_id = params
            job = self._job(int(job_id))
            if job and job["status"] == "PENDING":
                job["status"] = "RUNNING"
                job["started_at"] = job["started_at"] or self.db.now()
                job["worker_id"] = worker_id
                job["heartbeat_at"] = self.db.now()
                job["attempt_count"] += 1
                job["error_message"] = None
                self.rowcount = 1
            return

        if "update analysis_jobs set status = 'failed'" in normalized:
            error_message, job_id, worker_id = params
            job = self._job(int(job_id))
            if job and job["status"] == "RUNNING" and job["worker_id"] == worker_id:
                job["status"] = "FAILED"
                job["finished_at"] = self.db.now()
                job["heartbeat_at"] = self.db.now()
                job["error_message"] = error_message
                self.rowcount = 1
            return

        if "update analysis_jobs set status = 'succeeded'" in normalized:
            job_id, worker_id = params
            job = self._job(int(job_id))
            if job and job["status"] == "RUNNING" and job["worker_id"] == worker_id:
                job["status"] = "SUCCEEDED"
                job["finished_at"] = self.db.now()
                job["heartbeat_at"] = self.db.now()
                job["error_message"] = None
                self.rowcount = 1
            return

        if "update analysis_jobs set heartbeat_at = utc_timestamp(3)" in normalized:
            job_id, worker_id = params
            job = self._job(int(job_id))
            if job and job["status"] == "RUNNING" and job["worker_id"] == worker_id:
                job["heartbeat_at"] = self.db.now()
                self.rowcount = 1
            return

        if "insert into job_events" in normalized:
            job_id, event_type, message, detail_json = params
            self.db.events.append(
                {
                    "id": len(self.db.events) + 1,
                    "job_id": int(job_id),
                    "event_time": self.db.now(),
                    "event_type": event_type,
                    "message": message,
                    "detail_json": detail_json,
                }
            )
            self.rowcount = 1
            return

        if "insert into analysis_reports" in normalized and "on duplicate key update" in normalized:
            if "manifest_path" in normalized or "updated_at" in normalized:
                raise AssertionError(f"DDL-mismatched column in SQL: {sql}")

            values = dict(zip(ANALYSIS_REPORT_UPSERT_COLUMNS, params))
            existing = self._report(int(values["job_id"]))
            if existing:
                existing.update(values)
                self.rowcount = 2
                return

            row = {
                "id": len(self.db.reports) + 1,
                **values,
                "created_at": self.db.now(),
            }
            self.db.reports.append(row)
            self.rowcount = 1
            return

        raise AssertionError(f"Unhandled SQL: {sql}")

    def fetchone(self) -> Optional[Dict[str, Any]]:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> List[Dict[str, Any]]:
        return self._rows

    def _job(self, job_id: int) -> Optional[Dict[str, Any]]:
        for job in self.db.jobs:
            if int(job["id"]) == job_id:
                return job
        return None

    def _report(self, job_id: int) -> Optional[Dict[str, Any]]:
        for report in self.db.reports:
            if int(report["job_id"]) == job_id:
                return report
        return None


def make_job(**overrides: Any) -> Dict[str, Any]:
    job = {
        "id": 1,
        "requested_by": 7,
        "time_from": "2026-05-30 00:00:00.000",
        "time_to": "2026-05-30 01:00:00.000",
        "requested_timezone": "Asia/Seoul",
        "status": "PENDING",
        "analysis_mode": "full_report",
        "created_at": "2026-05-31 00:00:00.000",
        "started_at": None,
        "finished_at": None,
        "worker_id": None,
        "heartbeat_at": None,
        "attempt_count": 0,
        "max_attempts": 1,
        "error_message": "old error",
        "artifact_root": "runs/jobs/1",
    }
    job.update(overrides)
    return job


def make_repo(db: FakeDb) -> AnalysisJobRepository:
    return AnalysisJobRepository(connection_factory=lambda: FakeConnection(db))


def test_claim_next_pending_full_report_job_moves_job_to_running_and_returns_row() -> None:
    db = FakeDb([make_job()])
    repo = make_repo(db)

    claimed = repo.claim_next_pending_full_report_job(worker_id="worker-1")

    assert claimed is not None
    assert claimed["id"] == 1
    assert claimed["status"] == "RUNNING"
    assert claimed["worker_id"] == "worker-1"
    assert claimed["attempt_count"] == 1
    assert claimed["started_at"] is not None
    assert claimed["heartbeat_at"] is not None
    assert claimed["error_message"] is None
    assert db.jobs[0]["status"] == "RUNNING"
    assert db.jobs[0]["worker_id"] == "worker-1"
    assert db.jobs[0]["attempt_count"] == 1
    assert db.jobs[0]["started_at"] is not None
    assert db.jobs[0]["heartbeat_at"] is not None
    assert db.jobs[0]["error_message"] is None
    assert db.events[0]["event_type"] == "JOB_CLAIMED"
    assert json.loads(db.events[0]["detail_json"]) == {"worker_id": "worker-1"}
    assert db.commits == 1


def test_claim_next_pending_full_report_job_returns_none_when_no_pending_job() -> None:
    db = FakeDb([make_job(status="RUNNING", worker_id="worker-1")])
    repo = make_repo(db)

    assert repo.claim_next_pending_full_report_job(worker_id="worker-2") is None
    assert db.events == []
    assert db.rollbacks == 1


def test_claim_next_pending_full_report_job_skips_wrong_mode_status_and_exhausted_attempts() -> None:
    db = FakeDb(
        [
            make_job(id=1, analysis_mode="windowed_triage"),
            make_job(id=2, status="FAILED"),
            make_job(id=3, attempt_count=1, max_attempts=1),
        ]
    )
    repo = make_repo(db)

    assert repo.claim_next_pending_full_report_job(worker_id="worker-1") is None
    assert all(job["status"] != "RUNNING" for job in db.jobs)
    assert db.events == []


def test_append_job_event_uses_detail_json_column_and_serializes_structured_values() -> None:
    db = FakeDb()
    repo = make_repo(db)

    repo.append_job_event(
        job_id=42,
        event_type="CUSTOM",
        message="custom event",
        detail_json={"b": 2, "a": 1},
    )

    assert db.events == [
        {
            "id": 1,
            "job_id": 42,
            "event_time": "2026-05-31 00:00:00.001",
            "event_type": "CUSTOM",
            "message": "custom event",
            "detail_json": '{"a": 1, "b": 2}',
        }
    ]


def test_mark_job_failed_sets_failed_state_and_appends_event() -> None:
    db = FakeDb([make_job(status="RUNNING", worker_id="worker-1", error_message=None)])
    repo = make_repo(db)

    changed = repo.mark_job_failed(
        job_id=1,
        worker_id="worker-1",
        error_message="pipeline failed",
        detail_json={"step": "stage2"},
    )

    assert changed is True
    assert db.jobs[0]["status"] == "FAILED"
    assert db.jobs[0]["finished_at"] is not None
    assert db.jobs[0]["heartbeat_at"] is not None
    assert db.jobs[0]["error_message"] == "pipeline failed"
    assert db.events[0]["event_type"] == "JOB_FAILED"
    assert json.loads(db.events[0]["detail_json"]) == {"step": "stage2"}


def test_mark_job_failed_returns_false_for_worker_mismatch() -> None:
    db = FakeDb([make_job(status="RUNNING", worker_id="worker-1", error_message=None)])
    repo = make_repo(db)

    changed = repo.mark_job_failed(
        job_id=1,
        worker_id="worker-2",
        error_message="should not apply",
    )

    assert changed is False
    assert db.jobs[0]["status"] == "RUNNING"
    assert db.jobs[0]["error_message"] is None
    assert db.events == []


def test_update_job_heartbeat_only_updates_running_job_for_same_worker() -> None:
    db = FakeDb([make_job(status="RUNNING", worker_id="worker-1", heartbeat_at=None)])
    repo = make_repo(db)

    assert repo.update_job_heartbeat(job_id=1, worker_id="worker-1") is True
    first_heartbeat = db.jobs[0]["heartbeat_at"]
    assert first_heartbeat is not None

    assert repo.update_job_heartbeat(job_id=1, worker_id="worker-2") is False
    assert db.jobs[0]["heartbeat_at"] == first_heartbeat


def test_mark_job_succeeded_sets_succeeded_state_and_appends_event() -> None:
    db = FakeDb([make_job(status="RUNNING", worker_id="worker-1", error_message="old")])
    repo = make_repo(db)

    changed = repo.mark_job_succeeded(
        job_id=1,
        worker_id="worker-1",
        detail_json={"artifact_root": "runs/jobs/1"},
    )

    assert changed is True
    assert db.jobs[0]["status"] == "SUCCEEDED"
    assert db.jobs[0]["finished_at"] is not None
    assert db.jobs[0]["error_message"] is None
    assert db.events[0]["event_type"] == "JOB_SUCCEEDED"
    assert json.loads(db.events[0]["detail_json"]) == {"artifact_root": "runs/jobs/1"}


def test_mark_job_succeeded_returns_false_for_worker_mismatch() -> None:
    db = FakeDb([make_job(status="RUNNING", worker_id="worker-1")])
    repo = make_repo(db)

    assert repo.mark_job_succeeded(job_id=1, worker_id="worker-2") is False
    assert db.jobs[0]["status"] == "RUNNING"
    assert db.events == []


def test_upsert_analysis_report_inserts_direct_full_report_paths() -> None:
    db = FakeDb()
    repo = make_repo(db)

    repo.upsert_analysis_report(
        job_id=1,
        artifact_root="runs/jobs/1",
        summary="direct report",
        export_path="runs/jobs/1/export/security.json",
        llm_input_path="runs/jobs/1/llm_input.json",
        analysis_candidates_path="runs/jobs/1/analysis_candidates.json",
        noise_summary_path="runs/jobs/1/noise_summary.json",
        stage1_result_path="runs/jobs/1/stage1_result.json",
        stage2_report_path="runs/jobs/1/stage2_report.json",
        stage2_report_md_path="runs/jobs/1/stage2_report.md",
        viewer_payload_path="runs/jobs/1/viewer_payload.json",
        lint_result_path="runs/jobs/1/lint_result.json",
    )

    assert len(db.reports) == 1
    report = db.reports[0]
    assert report["job_id"] == 1
    assert report["artifact_root"] == "runs/jobs/1"
    assert report["summary"] == "direct report"
    assert report["export_path"] == "runs/jobs/1/export/security.json"
    assert report["llm_input_path"] == "runs/jobs/1/llm_input.json"
    assert report["analysis_candidates_path"] == "runs/jobs/1/analysis_candidates.json"
    assert report["noise_summary_path"] == "runs/jobs/1/noise_summary.json"
    assert report["stage1_result_path"] == "runs/jobs/1/stage1_result.json"
    assert report["stage2_report_path"] == "runs/jobs/1/stage2_report.json"
    assert report["stage2_report_md_path"] == "runs/jobs/1/stage2_report.md"
    assert report["viewer_payload_path"] == "runs/jobs/1/viewer_payload.json"
    assert report["lint_result_path"] == "runs/jobs/1/lint_result.json"
    assert report["window_summary_path"] is None
    assert report["rollup_input_path"] is None
    assert report["rollup_summary_path"] is None
    assert report["operator_queue_items_path"] is None
    assert report["operator_queue_summary_path"] is None
    assert db.commits == 1


def test_upsert_analysis_report_updates_existing_row_by_unique_job_id() -> None:
    db = FakeDb()
    repo = make_repo(db)

    repo.upsert_analysis_report(
        job_id=1,
        artifact_root="runs/jobs/1",
        summary="first",
        stage2_report_path="runs/jobs/1/old_stage2_report.json",
    )
    first_created_at = db.reports[0]["created_at"]
    repo.upsert_analysis_report(
        job_id=1,
        artifact_root="runs/jobs/1",
        summary="second",
        stage2_report_path="runs/jobs/1/stage2_report.json",
        stage2_report_md_path="runs/jobs/1/stage2_report.md",
        viewer_payload_path="runs/jobs/1/viewer_payload.json",
    )

    assert len(db.reports) == 1
    assert db.reports[0]["summary"] == "second"
    assert db.reports[0]["stage2_report_path"] == "runs/jobs/1/stage2_report.json"
    assert db.reports[0]["stage2_report_md_path"] == "runs/jobs/1/stage2_report.md"
    assert db.reports[0]["viewer_payload_path"] == "runs/jobs/1/viewer_payload.json"
    assert db.reports[0]["created_at"] == first_created_at


def test_upsert_analysis_report_sql_does_not_use_manifest_path_or_updated_at() -> None:
    db = FakeDb()
    repo = make_repo(db)

    repo.upsert_analysis_report(job_id=1, artifact_root="runs/jobs/1")

    sql = "\n".join(db.sql_statements)
    assert "manifest_path" not in sql
    assert "updated_at" not in sql


def test_upsert_analysis_report_can_store_windowed_followup_paths_when_explicit() -> None:
    db = FakeDb()
    repo = make_repo(db)

    repo.upsert_analysis_report(
        job_id=2,
        artifact_root="runs/jobs/2",
        window_summary_path="runs/jobs/2/window_summary.json",
        rollup_input_path="runs/jobs/2/rollup_input.json",
        rollup_summary_path="runs/jobs/2/rollup_summary.json",
        operator_queue_items_path="runs/jobs/2/queue_items.json",
        operator_queue_summary_path="runs/jobs/2/queue_summary.json",
    )

    report = db.reports[0]
    assert report["window_summary_path"] == "runs/jobs/2/window_summary.json"
    assert report["rollup_input_path"] == "runs/jobs/2/rollup_input.json"
    assert report["rollup_summary_path"] == "runs/jobs/2/rollup_summary.json"
    assert report["operator_queue_items_path"] == "runs/jobs/2/queue_items.json"
    assert report["operator_queue_summary_path"] == "runs/jobs/2/queue_summary.json"
