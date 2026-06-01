from __future__ import annotations

from typing import Any, Optional

import web.app as web_app_module


def make_job() -> dict[str, Any]:
    return {
        "id": 123,
        "status": "SUCCEEDED",
        "analysis_mode": "full_report",
        "time_from": "2026-05-30 09:00",
        "time_to": "2026-05-30 10:00",
        "created_at": "05-30 09:00",
        "started_at": "05-30 09:01",
        "finished_at": "05-30 09:02",
        "heartbeat_at": "05-30 09:02",
        "worker_id": "test-worker",
        "attempt_count": 1,
        "artifact_root": "runs/jobs/123",
        "error_message": "",
    }


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


def render_job_detail(report: Optional[dict[str, Any]]) -> str:
    template = web_app_module.templates.get_template("job_detail.html")
    return template.render(job=make_job(), events=[], report=report)


def test_job_detail_shows_persisted_full_report_artifact_paths() -> None:
    body = render_job_detail(make_report())

    assert "Analysis Report Artifacts" in body
    assert "runs/jobs/123/export.json" in body
    assert "runs/jobs/123/analysis_candidates.json" in body
    assert "runs/jobs/123/noise_summary.json" in body
    assert "runs/jobs/123/stage2_report.json" in body
    assert "runs/jobs/123/stage2_report.md" in body
    assert "runs/jobs/123/viewer_payload.json" in body
    assert 'href="/job/123/artifact/export"' in body
    assert 'href="/job/123/artifact/stage2_report"' in body
    assert 'href="/job/123/artifact/stage2_report_md"' in body
    assert 'href="/job/123/artifact/viewer_payload"' in body
    assert 'href="/job/123/viewer"' in body
    assert "/report/job-123/payload" not in body
    assert "severity" not in body.lower()


def test_job_detail_shows_no_data_report_without_error_state() -> None:
    body = render_job_detail(
        make_report(
            summary="No logs found in requested time range.",
            llm_input_path=None,
            analysis_candidates_path=None,
            noise_summary_path=None,
            stage1_result_path=None,
            stage2_report_path=None,
            stage2_report_md_path=None,
            viewer_payload_path=None,
        )
    )

    assert "No logs found in requested time range." in body
    assert "runs/jobs/123/export.json" in body
    assert 'href="/job/123/artifact/export"' in body
    assert 'href="/job/123/artifact/stage2_report"' not in body
    assert 'href="/job/123/artifact/viewer_payload"' not in body
    assert 'href="/job/123/viewer"' not in body
    assert body.count("not generated") >= 6
    assert "FAILED" not in body


def test_job_detail_without_analysis_report_still_renders() -> None:
    body = render_job_detail(None)

    assert "아직 analysis_reports row가 없습니다" in body
