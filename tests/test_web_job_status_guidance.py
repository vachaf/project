from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest
from starlette.requests import Request

import web.app as web_app_module
from web.services.analysis_job_repository import serialize_job_for_dashboard


def utc_text(minutes_delta: int) -> str:
    return (
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=minutes_delta)
    ).strftime("%Y-%m-%d %H:%M:%S.%f")


def make_job(**overrides: Any) -> dict[str, Any]:
    job = {
        "id": 123,
        "status": "PENDING",
        "analysis_mode": "full_report",
        "time_from": "2026-05-30 00:00:00.000",
        "time_to": "2026-05-30 01:00:00.000",
        "requested_timezone": "Asia/Seoul",
        "created_at": "2026-05-30 00:00:00.000",
        "started_at": None,
        "finished_at": None,
        "heartbeat_at": None,
        "worker_id": None,
        "attempt_count": 0,
        "max_attempts": 1,
        "error_message": None,
        "artifact_root": "runs/jobs/123",
    }
    job.update(overrides)
    return serialize_job_for_dashboard(job)


def make_report(**overrides: Any) -> dict[str, Any]:
    report = {
        "summary": None,
        "artifact_root": "runs/jobs/123",
        "export_path": "runs/jobs/123/export.json",
        "llm_input_path": "runs/jobs/123/llm_input.json",
        "analysis_candidates_path": "runs/jobs/123/analysis_candidates.json",
        "noise_summary_path": "runs/jobs/123/noise_summary.json",
        "stage1_result_path": "runs/jobs/123/stage1_results.json",
        "stage2_report_path": "runs/jobs/123/stage2_report.json",
        "stage2_report_md_path": "runs/jobs/123/stage2_report.md",
        "viewer_payload_path": "runs/jobs/123/viewer_payload.json",
        "lint_result_path": None,
    }
    report.update(overrides)
    return report


def make_event(event_type: str, *, message: str = "ok", detail_json: str = "{}") -> dict[str, Any]:
    return {
        "event_time": "2026-05-30 00:02:00.000",
        "event_type": event_type,
        "message": message,
        "detail_json": detail_json,
    }


def render_job_detail(
    *,
    job: dict[str, Any],
    events: Optional[list[dict[str, Any]]] = None,
    report: Optional[dict[str, Any]] = None,
    is_no_data_job: bool = False,
) -> str:
    template = web_app_module.templates.get_template("job_detail.html")
    return template.render(
        job=job,
        events=events or [],
        report=report,
        is_no_data_job=is_no_data_job,
    )


def render_dashboard(jobs: list[dict[str, Any]]) -> str:
    template = web_app_module.templates.get_template("job_dashboard.html")
    return template.render(
        jobs=jobs,
        status_counts={"PENDING": 1, "RUNNING": 1, "SUCCEEDED": 0, "FAILED": 0},
        error="",
        status_options=("PENDING", "RUNNING", "SUCCEEDED", "FAILED"),
        filter_state={"status": "", "from": "", "to": "", "stale": False},
        filter_warnings=[],
        active_filter_chips=[],
        has_active_filters=False,
        result_count=len(jobs),
    )


class FakeJobRepository:
    def __init__(
        self,
        *,
        job: dict[str, Any],
        events: list[dict[str, Any]],
        report: Optional[dict[str, Any]],
    ) -> None:
        self.job = job
        self.events = events
        self.report = report

    def get_job(self, job_id: int) -> dict[str, Any]:
        return self.job

    def get_job_events(self, job_id: int) -> list[dict[str, Any]]:
        return self.events

    def get_latest_report_for_job(self, job_id: int) -> Optional[dict[str, Any]]:
        return self.report


class FakeDashboardRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.list_jobs_calls: list[dict[str, Any]] = []
        self.mutation_calls: list[str] = []

    def count_by_status(self) -> dict[str, int]:
        counts = {"PENDING": 0, "RUNNING": 0, "SUCCEEDED": 0, "FAILED": 0}
        for row in self.rows:
            status = str(row.get("status") or "").upper()
            if status in counts:
                counts[status] += 1
        return counts

    def list_jobs(
        self,
        *,
        status: Optional[str] = None,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None,
        stale_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.list_jobs_calls.append(
            {
                "status": status,
                "time_from": time_from,
                "time_to": time_to,
                "stale_only": stale_only,
                "limit": limit,
            }
        )
        rows = list(self.rows)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if stale_only:
            rows = [
                row
                for row in rows
                if row.get("is_potentially_stale") or serialize_job_for_dashboard(row)["is_potentially_stale"]
            ]
        return rows[:limit]


def make_request(path: str = "/job/123") -> Request:
    raw_path, _, raw_query = path.partition("?")
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": raw_path,
            "query_string": raw_query.encode("utf-8"),
            "headers": [],
            "app": web_app_module.app,
        }
    )


def test_pending_job_detail_shows_worker_wait_guidance() -> None:
    body = render_job_detail(job=make_job(status="PENDING"))

    assert "대기 중입니다. Analysis Job Worker가 작업을 처리할 때까지 기다립니다." in body
    assert "worker service가 꺼져 있거나 다른 작업을 처리 중일 수 있습니다." in body


def test_pending_job_dashboard_shows_waiting_hint() -> None:
    body = render_dashboard([make_job(status="PENDING")])

    assert "PENDING" in body
    assert "Waiting for worker" in body


def test_running_job_detail_shows_worker_and_heartbeat() -> None:
    body = render_job_detail(
        job=make_job(
            status="RUNNING",
            worker_id="worker-01",
            started_at="2026-05-30 00:01:00.000",
            heartbeat_at="2026-05-30 00:02:00.000",
            attempt_count=1,
        )
    )

    assert "Analysis Job Worker가 작업을 실행 중입니다." in body
    assert "worker-01" in body
    assert "Last heartbeat:" in body
    assert "최근 worker heartbeat 기준으로 실행 중입니다." in body


def test_running_job_dashboard_shows_running_hint_and_heartbeat() -> None:
    body = render_dashboard(
        [
            make_job(
                status="RUNNING",
                worker_id="worker-01",
                heartbeat_at="2026-05-30 00:02:00.000",
            )
        ]
    )

    assert "Running by worker-01" in body
    assert "Last heartbeat:" in body


def test_job_dashboard_default_route_keeps_recent_full_report_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeDashboardRepository([make_job(id=1, status="PENDING")])
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_dashboard(make_request("/"))
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert 'name="status"' in body
    assert 'name="from"' in body
    assert 'name="to"' in body
    assert 'name="stale"' in body
    assert 'class="job-filter-form"' in body
    assert 'class="job-filter-checkbox job-filter-check"' in body
    assert ">Apply</button>" in body
    assert 'href="/" class="job-btn">Clear</a>' in body
    assert "#1" in body
    assert repo.list_jobs_calls == [
        {
            "status": None,
            "time_from": None,
            "time_to": None,
            "stale_only": False,
            "limit": 100,
        }
    ]
    assert repo.mutation_calls == []


def test_job_dashboard_status_filter_returns_matching_status_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeDashboardRepository(
        [
            make_job(id=1, status="FAILED", error_message="failed"),
            make_job(id=2, status="RUNNING", started_at=utc_text(-1), heartbeat_at=utc_text(-1)),
        ]
    )
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_dashboard(make_request("/?status=FAILED"))
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "#1" in body
    assert "#2" not in body
    assert "Status: FAILED" in body
    assert repo.list_jobs_calls[-1]["status"] == "FAILED"


def test_job_dashboard_invalid_status_warns_and_ignores_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeDashboardRepository(
        [
            make_job(id=1, status="FAILED", error_message="failed"),
            make_job(id=2, status="RUNNING", started_at=utc_text(-1), heartbeat_at=utc_text(-1)),
        ]
    )
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_dashboard(make_request("/?status=FAILED%27%20OR%201=1--"))
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Invalid status filter ignored." in body
    assert "#1" in body
    assert "#2" in body
    assert repo.list_jobs_calls[-1]["status"] is None
    assert repo.mutation_calls == []


def test_job_dashboard_date_filters_are_kst_dates_converted_to_utc_naive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeDashboardRepository([make_job(id=1, status="SUCCEEDED")])
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_dashboard(make_request("/?from=2026-06-01&to=2026-06-02"))

    assert response.status_code == 200
    call = repo.list_jobs_calls[-1]
    assert call["time_from"] == datetime(2026, 5, 31, 15, 0, 0)
    assert call["time_to"] == datetime(2026, 6, 2, 15, 0, 0)


def test_job_dashboard_invalid_date_warns_and_ignores_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeDashboardRepository([make_job(id=1, status="FAILED")])
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_dashboard(make_request("/?from=2026-99-99"))
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Invalid from date filter ignored: use YYYY-MM-DD." in body
    assert repo.list_jobs_calls[-1]["time_from"] is None


def test_job_dashboard_stale_filter_returns_potentially_stale_running_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeDashboardRepository(
        [
            make_job(id=1, status="RUNNING", started_at=utc_text(-90), heartbeat_at=utc_text(-45)),
            make_job(id=2, status="RUNNING", started_at=utc_text(-2), heartbeat_at=utc_text(-1)),
            make_job(id=3, status="FAILED", started_at=utc_text(-90), heartbeat_at=utc_text(-45)),
        ]
    )
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_dashboard(make_request("/?stale=1"))
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "#1" in body
    assert "#2" not in body
    assert "#3" not in body
    assert "Potentially stale" in body
    assert repo.list_jobs_calls[-1]["stale_only"] is True


def test_job_dashboard_empty_filter_result_uses_no_match_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeDashboardRepository([])
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_dashboard(make_request("/?status=FAILED"))
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "No jobs match the current filters." in body


def test_fresh_running_job_does_not_show_potentially_stale_guidance() -> None:
    job = make_job(
        status="RUNNING",
        worker_id="worker-01",
        started_at=utc_text(-3),
        heartbeat_at=utc_text(-1),
        attempt_count=1,
    )
    detail_body = render_job_detail(job=job)
    dashboard_body = render_dashboard([job])

    assert job["is_potentially_stale"] is False
    assert "Potentially stale" not in detail_body
    assert "Heartbeat is older than the stale threshold." not in dashboard_body
    assert 'class="job-stale-badge">Potentially stale</span>' not in dashboard_body


def test_old_heartbeat_running_job_shows_potentially_stale_guidance() -> None:
    job = make_job(
        status="RUNNING",
        worker_id="worker-01",
        started_at=utc_text(-90),
        heartbeat_at=utc_text(-45),
        attempt_count=1,
    )
    detail_body = render_job_detail(job=job)
    dashboard_body = render_dashboard([job])

    assert job["is_potentially_stale"] is True
    assert job["stale_reason"] == "stale_heartbeat"
    assert job["stale_threshold_minutes"] == 30
    assert "Potentially stale" in detail_body
    assert "Potentially stale" in dashboard_body
    assert "Heartbeat is older than the stale threshold. Verify worker status before marking failed." in detail_body
    assert "Heartbeat is older than the stale threshold. Verify worker status before marking failed." in dashboard_body
    assert "python3 src/analysis_job_worker.py --recover-stale --dry-run" in detail_body
    assert "--mark-failed" not in detail_body


def test_non_running_job_with_old_heartbeat_does_not_show_potentially_stale_guidance() -> None:
    job = make_job(
        status="FAILED",
        started_at=utc_text(-90),
        heartbeat_at=utc_text(-45),
        error_message="failed",
    )
    body = render_job_detail(job=job)

    assert job["is_potentially_stale"] is False
    assert "Potentially stale" not in body


def test_missing_heartbeat_running_job_after_startup_grace_shows_potentially_stale_guidance() -> None:
    job = make_job(
        status="RUNNING",
        worker_id="worker-01",
        started_at=utc_text(-10),
        heartbeat_at=None,
        attempt_count=1,
    )
    body = render_job_detail(job=job)

    assert job["is_potentially_stale"] is True
    assert job["stale_reason"] == "missing_heartbeat_startup_grace"
    assert job["stale_threshold_minutes"] == 5
    assert "Potentially stale" in body
    assert "Reason: missing_heartbeat_startup_grace." in body


def test_job_detail_route_potentially_stale_guidance_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [make_event("JOB_CLAIMED")]
    repo = FakeJobRepository(
        job={
            "id": 123,
            "status": "RUNNING",
            "analysis_mode": "full_report",
            "time_from": utc_text(-120),
            "time_to": utc_text(-60),
            "requested_timezone": "Asia/Seoul",
            "created_at": utc_text(-120),
            "started_at": utc_text(-90),
            "finished_at": None,
            "heartbeat_at": utc_text(-45),
            "worker_id": "worker-01",
            "attempt_count": 1,
            "max_attempts": 1,
            "error_message": None,
            "artifact_root": "runs/jobs/123",
        },
        events=events,
        report=None,
    )
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_detail(make_request(), 123)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Potentially stale" in body
    assert events == [make_event("JOB_CLAIMED")]
    assert "JOB_MARKED_FAILED_STALE" not in body
    assert 'type="submit"' not in body
    assert "--mark-failed" not in body


def test_succeeded_job_with_no_data_event_shows_neutral_no_data_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_job = {
        **make_job(status="SUCCEEDED", finished_at="2026-05-30 00:02:00.000"),
        "id": 123,
    }
    repo = FakeJobRepository(
        job={
            **raw_job,
            "time_from": "2026-05-30 00:00:00.000",
            "time_to": "2026-05-30 01:00:00.000",
            "created_at": "2026-05-30 00:00:00.000",
            "finished_at": "2026-05-30 00:02:00.000",
        },
        events=[{"event_type": "JOB_NO_DATA", "event_time": "2026-05-30 00:02:00.000", "message": "no data"}],
        report=make_report(
            summary="No logs found in requested time range.",
            llm_input_path=None,
            analysis_candidates_path=None,
            noise_summary_path=None,
            stage1_result_path=None,
            stage2_report_path=None,
            stage2_report_md_path=None,
            viewer_payload_path=None,
        ),
    )
    monkeypatch.setattr(web_app_module, "job_repository", repo)

    response = web_app_module.job_detail(make_request(), 123)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "No logs found in requested time range." in body
    assert "선택한 구간에 분석할 로그가 없습니다." in body
    assert "Analysis failed." not in body
    assert "not generated for no-data job" in body


def test_job_detail_renders_phase1_stage_event_timeline_read_only() -> None:
    event_types = [
        "JOB_CREATED",
        "JOB_CLAIMED",
        "JOB_STARTED",
        "EXPORT_STARTED",
        "EXPORT_COMPLETED",
        "PIPELINE_STARTED",
        "PIPELINE_COMPLETED",
        "REPORT_SAVE_STARTED",
        "REPORT_SAVE_COMPLETED",
        "JOB_SUCCEEDED",
    ]
    body = render_job_detail(
        job=make_job(status="SUCCEEDED", worker_id="worker-01"),
        events=[make_event(event_type, detail_json='{"worker_id":"worker-01"}') for event_type in event_types],
        report=make_report(),
    )

    positions = [body.index(event_type) for event_type in event_types]
    assert positions == sorted(positions)
    assert "job_events 테이블에 저장된 실제 이벤트만 표시합니다." in body
    assert 'class="job-timeline-dot is-success"' in body
    assert 'class="job-timeline-dot is-error"' not in body
    assert "worker-01" in body
    assert "run_analysis_pipeline" not in body
    assert "mark_job_succeeded" not in body


def test_job_detail_renders_no_data_phase1_timeline_read_only() -> None:
    event_types = [
        "EXPORT_STARTED",
        "EXPORT_COMPLETED",
        "EXPORT_NO_DATA",
        "JOB_NO_DATA",
        "REPORT_SAVE_STARTED",
        "REPORT_SAVE_COMPLETED",
        "JOB_SUCCEEDED",
    ]
    body = render_job_detail(
        job=make_job(status="SUCCEEDED", worker_id="worker-01"),
        events=[make_event(event_type) for event_type in event_types],
        report=make_report(
            summary="No logs found in requested time range.",
            llm_input_path=None,
            analysis_candidates_path=None,
            noise_summary_path=None,
            stage1_result_path=None,
            stage2_report_path=None,
            stage2_report_md_path=None,
            viewer_payload_path=None,
        ),
        is_no_data_job=True,
    )

    positions = [body.index(event_type) for event_type in event_types]
    assert positions == sorted(positions)
    assert "EXPORT_NO_DATA" in body
    assert "JOB_NO_DATA" in body
    assert "Analysis failed." not in body


def test_job_detail_renders_failed_phase1_timeline_read_only() -> None:
    event_types = [
        "EXPORT_STARTED",
        "EXPORT_COMPLETED",
        "PIPELINE_STARTED",
        "PIPELINE_FAILED",
        "JOB_FAILED",
    ]
    body = render_job_detail(
        job=make_job(status="FAILED", error_message="pipeline failed", worker_id="worker-01"),
        events=[make_event(event_type, detail_json='{"failed_at_stage":"pipeline"}') for event_type in event_types],
        report=make_report(viewer_payload_path=None),
    )

    positions = [body.index(event_type) for event_type in event_types]
    assert positions == sorted(positions)
    assert 'class="job-timeline-dot is-error"' in body
    assert "failed_at_stage" in body
    assert "pipeline" in body
    assert 'href="/job/123/viewer"' not in body


def test_job_detail_renders_failed_subprocess_diagnostics_in_timeline() -> None:
    body = render_job_detail(
        job=make_job(status="FAILED", error_message="full_report pipeline failed at pipeline: returncode=8"),
        events=[
            make_event(
                "JOB_FAILED",
                message="full_report pipeline failed at pipeline: returncode=8",
                detail_json='{"failed_at_stage":"pipeline","returncode":8,"stdout_tail":"short out","stderr_tail":"short err"}',
            )
        ],
        report=None,
    )

    assert "failed_at_stage" in body
    assert "pipeline" in body
    assert "returncode" in body
    assert "stdout_tail" in body
    assert "stderr_tail" in body
    assert "short err" in body
    assert 'type="submit"' not in body


def test_failed_job_detail_shows_failure_guidance_error_and_missing_viewer() -> None:
    body = render_job_detail(
        job=make_job(status="FAILED", error_message="pipeline failed"),
        report=make_report(viewer_payload_path=None),
    )

    assert "Analysis failed." in body
    assert "Artifacts may not have been generated." in body
    assert "pipeline failed" in body
    assert "not generated due to failure" in body
    assert 'href="/job/123/viewer"' not in body


def test_web_app_routes_do_not_execute_worker_or_pipeline() -> None:
    source = inspect.getsource(web_app_module)

    assert "subprocess" not in source
    assert "analysis_job_worker" not in source
    assert "run_analysis_pipeline" not in source
    assert "mark_job_succeeded" not in source
    assert "mark_job_failed" not in source
