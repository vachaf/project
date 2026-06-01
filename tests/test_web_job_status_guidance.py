from __future__ import annotations

import inspect
from typing import Any, Optional

import pytest
from starlette.requests import Request

import web.app as web_app_module
from web.services.analysis_job_repository import serialize_job_for_dashboard


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


def make_request(path: str = "/job/123") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
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
