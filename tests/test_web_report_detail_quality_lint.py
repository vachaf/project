from __future__ import annotations

from pathlib import Path

from starlette.requests import Request

import web.app as web_app_module
import web.routes.reports as report_routes
from web.services.report_loader import Report


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


def make_report(tmp_path: Path) -> Report:
    report_path = tmp_path / "runs" / "lint-run" / "stage2_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("{}", encoding="utf-8")
    return Report(
        report_id="lint-report",
        file_path=report_path,
        filename="stage2_report.json",
        repo_relative_path="runs/lint-run/stage2_report.json",
        provider="openai",
        model="test-model",
        scenario="lint",
        scenario_key="lint",
        timeframe="2026-06-04",
        timeframe_key="2026-06-04",
        timeframe_label="2026-06-04",
        timeframe_id="lint-timeframe",
        generated_at="2026-06-04T00:00:00Z",
        incident_count=0,
        severity_counts={},
        verdict_counts={},
        meta={"run_id": "lint-run", "storage_type": "run_dir"},
        report={
            "overall_assessment": "안전한 요약",
            "executive_summary": [],
            "key_findings": [
                {
                    "title": "포인트 1",
                    "detail": "앞부분 맥락이 길고, 최종적으로 브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다고 단정하는 문장입니다.",
                    "severity": "low",
                }
            ],
            "notable_incidents": [],
            "notable_source_ips": [],
            "recommended_actions": [],
            "confidence_and_limitations": [],
        },
    )


class FakeReportLoader:
    def __init__(self, report: Report) -> None:
        self.report = report

    def scan_reports(self) -> list[Report]:
        return [self.report]


class FakeQARunner:
    def run_quality_lint(self, report_id: str, report_path: Path) -> dict[str, object]:
        return {
            "verdict": "FAIL",
            "checked_fields": 1,
            "blocker_count": 1,
            "warning_count": 0,
            "info_count": 0,
            "blockers": [
                {
                    "rule": "xss_execution_assertion",
                    "path": "report.key_findings[0].detail",
                    "excerpt": "...브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다고 단정하는 문장입니다.",
                    "suggestion": "Replace confirmed wording.",
                }
            ],
            "warnings": [],
            "info": [],
            "is_error": False,
            "error": None,
        }


class FakeQARunnerSummaryMismatch:
    def run_quality_lint(self, report_id: str, report_path: Path) -> dict[str, object]:
        return {
            "verdict": "WARN",
            "checked_fields": 2,
            "blocker_count": 0,
            "warning_count": 2,
            "info_count": 0,
            "blockers": [],
            "warnings": [],
            "info": [
                {
                    "rule": "auth_success_assertion",
                    "path": "report.key_findings[0].detail",
                    "excerpt": "...로그인 성공이나 계정 탈취를 말할 수는 없습니다.",
                    "source_text": "현재 로그만으로 로그인 성공이나 계정 탈취를 말할 수는 없습니다.",
                    "suggestion": "Prefer inconclusive auth wording.",
                },
                {
                    "rule": "xss_execution_assertion",
                    "path": "report.key_findings[0].detail",
                    "excerpt": "...XSS 실행이나 악성 동작은 입증되지 않았습니다.",
                    "source_text": "XSS 실행이나 악성 동작은 입증되지 않았습니다.",
                    "suggestion": "Prefer observed payload wording.",
                },
            ],
            "is_error": False,
            "error": None,
        }


class FakeQARunnerWithoutSourceText:
    def run_quality_lint(self, report_id: str, report_path: Path) -> dict[str, object]:
        return {
            "verdict": "WARN",
            "checked_fields": 1,
            "blocker_count": 0,
            "warning_count": 1,
            "info_count": 0,
            "blockers": [],
            "warnings": [
                {
                    "rule": "xss_execution_assertion",
                    "path": "report.legacy_field",
                    "excerpt": "...브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다고 단정하는 문장입니다.",
                    "source_text": "",
                    "suggestion": "Replace confirmed wording.",
                }
            ],
            "info": [],
            "is_error": False,
            "error": None,
        }


def test_report_detail_quality_lint_shows_full_source_text_and_hides_excerpt_from_default_area(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report = make_report(tmp_path)
    monkeypatch.setattr(report_routes, "loader", FakeReportLoader(report))
    monkeypatch.setattr(report_routes, "qa_runner", FakeQARunner())

    response = report_routes.report_detail(make_request("/report/lint-report"), "lint-report")
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "matched excerpt" in body
    assert "...브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다고 단정하는 문장입니다." in body
    assert "<p class=\"issue-label\">원문</p>" in body
    assert "앞부분 맥락이 길고, 최종적으로 브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다고 단정하는 문장입니다." in body
    assert '<div class="issue-source-text">앞부분 맥락이 길고, 최종적으로 브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다고 단정하는 문장입니다.</div>' in body
    assert '<p class="issue-excerpt">앞부분 맥락이 길고, 최종적으로 브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다고 단정하는 문장입니다.</p>' not in body


def test_report_detail_quality_lint_falls_back_to_excerpt_when_source_text_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report = make_report(tmp_path)
    monkeypatch.setattr(report_routes, "loader", FakeReportLoader(report))
    monkeypatch.setattr(report_routes, "qa_runner", FakeQARunnerWithoutSourceText())

    response = report_routes.report_detail(make_request("/report/lint-report"), "lint-report")
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "<p class=\"issue-label\">원문</p>" in body
    assert '<p class="issue-excerpt">...브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다고 단정하는 문장입니다.</p>' in body
    assert '<div class="issue-source-text">' not in body


def test_report_detail_quality_lint_reaggregates_counts_from_adjusted_issue_buckets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report = make_report(tmp_path)
    monkeypatch.setattr(report_routes, "loader", FakeReportLoader(report))
    monkeypatch.setattr(report_routes, "qa_runner", FakeQARunnerSummaryMismatch())

    response = report_routes.report_detail(make_request("/report/lint-report"), "lint-report")
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Reported Verdict:" in body
    assert "PASS" in body
    assert "checked_fields=2" in body
    assert "blocker=0" in body
    assert "warning=0" in body
    assert "info=2" in body
