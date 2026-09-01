from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pytest
from starlette.requests import Request

import web.app as web_app_module
import web.routes.reports as report_routes
from web.services.report_loader import Report


LEGACY_NOTICE = "Legacy run-dir report viewer. For DB-backed analysis jobs, use Job Dashboard and /job/{id}/viewer."


def make_request(path: str) -> Request:
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


def render_template(name: str, **context: Any) -> str:
    template = web_app_module.templates.get_template(name)
    return template.render(**context)


def test_job_dashboard_nav_labels_legacy_reports_without_relabeling_primary_title() -> None:
    body = render_template(
        "job_dashboard.html",
        jobs=[],
        status_counts={"PENDING": 0, "RUNNING": 0, "SUCCEEDED": 0, "FAILED": 0},
        error="",
    )

    assert "Job Dashboard" in body
    assert "Legacy Stage2 Reports" in body
    assert '<h1 class="job-page-title">분석 작업 대시보드</h1>' in body
    assert "Legacy 분석 작업 대시보드" not in body


def test_reports_index_title_and_notice_are_marked_legacy() -> None:
    body = render_template(
        "index.html",
        summary={
            "total_count": 0,
            "timeframe_count": 0,
            "groups": {},
            "lint_aggregate": {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0},
        },
        filters={"q": None, "lint": None, "pair": None, "provider": None, "sort": "time_desc"},
        filter_options={
            "lint": ["pass", "warn", "fail", "error"],
            "pair": ["both", "partial"],
            "provider": ["openai", "anthropic", "unknown"],
            "sort": ["time_desc", "time_asc", "severity_desc"],
        },
        reports_index_url="/reports",
        result_count=0,
        unfiltered_count=0,
    )

    assert "Legacy Stage2 Report Overview" in body
    assert "Run directory / manifest based legacy reports." in body
    assert "Legacy Report Viewer" in body


def make_legacy_report(tmp_path: Path) -> Report:
    report_path = tmp_path / "runs" / "legacy-run" / "stage2_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("{}", encoding="utf-8")
    return Report(
        report_id="legacy-report",
        file_path=report_path,
        filename="stage2_report.json",
        repo_relative_path="runs/legacy-run/stage2_report.json",
        provider="openai",
        model="test-model",
        scenario="legacy",
        scenario_key="legacy",
        timeframe="2026-05-30",
        timeframe_key="2026-05-30",
        timeframe_label="2026-05-30",
        timeframe_id="legacy-timeframe",
        generated_at="2026-05-30T00:00:00Z",
        incident_count=0,
        severity_counts={},
        verdict_counts={},
        meta={"run_id": "legacy-run", "storage_type": "run_dir"},
        report={},
        viewer_payload_available=True,
        viewer_payload_path="runs/legacy-run/viewer_payload.json",
        viewer_payload_summary={"schema_version": "viewer_payload.v1"},
    )


class FakeReportLoader:
    def __init__(self, report: Report) -> None:
        self.report = report

    def scan_reports(self) -> list[Report]:
        return [self.report]

    def load_viewer_payload(self, report: Report) -> tuple[dict[str, Any], None]:
        return {
            "schema_version": "viewer_payload.v1",
            "summary": {"schema_version": "viewer_payload.v1", "finding_count": 0, "context_count": 0},
            "findings": [],
            "contexts": [],
            "supporting_events": [],
        }, None


class FakeSummaryReportLoader(FakeReportLoader):
    def load_viewer_payload(self, report: Report) -> tuple[dict[str, Any], None]:
        payload, error = super().load_viewer_payload(report)
        payload["security_standards_summary"] = {
            "schema_version": "security_standards_summary.v1",
            "source": "deterministic_security_standards_summary",
            "counting_unit": "deduplicated_finding",
            "scope": "all_stage2_deduplicated_incidents",
            "total_finding_count": 1,
            "mapped_finding_count": 1,
            "unmapped_finding_count": 0,
            "observability_counts": {"attempt_only": 1},
            "standards": {
                "OWASP_TOP10": [
                    {
                        "id": "A05:2025",
                        "name": "Injection",
                        "finding_count": 1,
                        "relationship_counts": {"direct": 1},
                    }
                ],
                "CWE": [],
                "WSTG": [],
            },
        }
        return payload, error


def test_legacy_report_payload_route_shows_legacy_notice_and_stage2_back_link(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = make_legacy_report(tmp_path)
    monkeypatch.setattr(report_routes, "loader", FakeReportLoader(report))
    monkeypatch.setattr(report_routes, "lint_for_report", lambda report: None)

    response = report_routes.report_payload_detail(make_request("/report/legacy-report/payload"), "legacy-report")
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert LEGACY_NOTICE in body
    assert "Back To Stage2 Detail" in body
    assert 'href="/report/legacy-report"' in body


def test_legacy_report_payload_route_renders_sanitized_security_standards_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = make_legacy_report(tmp_path)
    monkeypatch.setattr(report_routes, "loader", FakeSummaryReportLoader(report))
    monkeypatch.setattr(report_routes, "lint_for_report", lambda report: None)

    response = report_routes.report_payload_detail(make_request("/report/legacy-report/payload"), "legacy-report")
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Security Standards Summary" in body
    assert "1 / 1" in body
    assert "A05:2025" in body


class FakeJobRepository:
    def __init__(self, report: Optional[dict[str, Any]]) -> None:
        self.report = report

    def get_latest_report_for_job(self, job_id: int) -> Optional[dict[str, Any]]:
        return self.report


def write_job_payload(project_root: Path) -> None:
    payload_path = project_root / "runs" / "jobs" / "123" / "viewer_payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(
        json.dumps(
            {
                "schema_version": "viewer_payload.v1",
                "summary": {"schema_version": "viewer_payload.v1", "finding_count": 0, "context_count": 0},
                "findings": [],
                "contexts": [],
                "supporting_events": [],
            }
        ),
        encoding="utf-8",
    )


def test_job_viewer_route_does_not_show_legacy_notice_and_keeps_job_back_link(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_job_payload(tmp_path)
    monkeypatch.setattr(web_app_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        web_app_module,
        "job_repository",
        FakeJobRepository(
            {
                "artifact_root": "runs/jobs/123",
                "viewer_payload_path": "runs/jobs/123/viewer_payload.json",
            }
        ),
    )

    response = web_app_module.job_viewer_payload(make_request("/job/123/viewer"), 123)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert LEGACY_NOTICE not in body
    assert "Back To Job Detail" in body
    assert 'href="/job/123"' in body
