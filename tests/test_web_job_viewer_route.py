from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import web.app as web_app_module
import web.routes.reports as report_routes
from web.services.report_loader import ReportLoader
from src import viewer_payload_builder


class FakeJobRepository:
    def __init__(self, report: Optional[dict[str, Any]]) -> None:
        self.report = report

    def get_latest_report_for_job(self, job_id: int) -> Optional[dict[str, Any]]:
        return self.report


class FakeJobDetailRepository(FakeJobRepository):
    def __init__(self, report: Optional[dict[str, Any]], *, job: Optional[dict[str, Any]] = None) -> None:
        super().__init__(report)
        self.job = job or {
            "id": 123,
            "status": "SUCCEEDED",
            "analysis_mode": "full_report",
            "time_from": "2026-05-30 00:00:00.000",
            "time_to": "2026-05-30 01:00:00.000",
            "requested_timezone": "Asia/Seoul",
            "created_at": "2026-05-30 00:00:00.000",
            "started_at": "2026-05-30 00:00:01.000",
            "finished_at": "2026-05-30 00:00:02.000",
            "heartbeat_at": "2026-05-30 00:00:02.000",
            "worker_id": "worker-01",
            "attempt_count": 1,
            "max_attempts": 1,
            "error_message": None,
            "artifact_root": "runs/jobs/123",
        }
        self.events = [{"event_type": "JOB_SUCCEEDED", "event_time": "2026-05-30 00:00:02.000", "message": "ok"}]

    def get_job(self, job_id: int) -> dict[str, Any]:
        return self.job

    def get_job_events(self, job_id: int) -> list[dict[str, Any]]:
        return self.events


def make_request(path: str = "/job/123/viewer", query_string: bytes = b"") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": query_string,
            "headers": [],
            "app": web_app_module.app,
        }
    )


def make_report(**overrides: Any) -> dict[str, Any]:
    report = {
        "artifact_root": "runs/jobs/123",
        "viewer_payload_path": "runs/jobs/123/viewer_payload.json",
    }
    report.update(overrides)
    return report


def make_viewer_payload(*, findings: Optional[list[dict[str, Any]]] = None, contexts: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    return {
        "schema_version": "viewer_payload.v1",
        "summary": {
            "report_title": "DB backed payload",
            "generated_at": "2026-05-30T00:00:00Z",
            "finding_count": len(findings) if findings is not None else 1,
            "context_count": len(contexts) if contexts is not None else 1,
            "supporting_event_count": 0,
        },
        "findings": findings
        if findings is not None
        else [
            {
                "log_time": "2026-05-30T00:00:01Z",
                "severity": "critical",
                "verdict": "needs_review",
                "category": "custom_payload_category",
                "src_ip": "203.0.113.10",
                "method": "GET",
                "uri": "/admin",
                "status_code": 403,
                "confidence": "medium",
                "reasoning_summary": "Payload value should be rendered as-is.",
            }
        ],
        "contexts": contexts
        if contexts is not None
        else [
            {
                "context_type": "scanner_baseline",
                "src_ip": "203.0.113.20",
                "request_count": 3,
                "context_only": True,
                "should_promote_to_candidate": True,
            }
        ],
        "supporting_events": [],
        "policies": {
            "guardrails": ["Viewer must not promote context-only items into findings."],
        },
    }


def make_security_standards_summary(
    *,
    total: int = 12,
    mapped: int = 9,
    unmapped: int = 3,
) -> dict[str, Any]:
    return {
        "schema_version": "security_standards_summary.v1",
        "source": "deterministic_security_standards_summary",
        "counting_unit": "deduplicated_finding",
        "scope": "all_stage2_deduplicated_incidents",
        "total_finding_count": total,
        "mapped_finding_count": mapped,
        "unmapped_finding_count": unmapped,
        "observability_counts": {
            "attempt_only": 6,
            "behavior_only": 3,
            "partial": 0,
            "not_applicable": 3,
            "future_scope": 99,
        },
        "standards": {
            "OWASP_TOP10": [
                {
                    "id": "A01:2025",
                    "name": "Broken Access Control",
                    "finding_count": 4,
                    "relationship_counts": {"direct": 3, "conditional": 0, "related": 1},
                },
                {
                    "id": "A05:2025",
                    "name": "Injection",
                    "finding_count": 7,
                    "relationship_counts": {"direct": 6, "conditional": 0, "related": 1},
                },
                {
                    "id": "A07:2025",
                    "name": "Authentication Failures",
                    "finding_count": 2,
                    "relationship_counts": {"direct": 0, "conditional": 1, "related": 1},
                },
            ],
            "CWE": [
                {
                    "id": "CWE-89",
                    "name": "SQL Injection",
                    "finding_count": 3,
                    "relationship_counts": {"direct": 3, "conditional": 0, "related": 0},
                }
            ],
            "WSTG": [
                {
                    "id": "WSTG-INPV-05",
                    "name": "Testing for SQL Injection",
                    "finding_count": 3,
                    "relationship_counts": {"direct": 3, "conditional": 0, "related": 0},
                }
            ],
            "ASVS": [
                {
                    "id": "V5.3.1",
                    "name": "Input Validation",
                    "finding_count": 1,
                    "relationship_counts": {"direct": 0, "conditional": 0, "related": 1},
                }
            ],
        },
        "diagnostics": {"invalid_finding_count": 0},
    }


def make_human_viewer_payload() -> dict[str, Any]:
    payload = make_viewer_payload()
    payload["summary"].update(
        {
            "report_title": "Canonical payload report",
            "overall_assessment": "Assessment from summary fallback.",
            "executive_summary": ["Summary fallback item"],
        }
    )
    payload["report"] = {
        "report_title": "Canonical payload report",
        "overall_assessment": "Report-level assessment text.",
        "executive_summary": ["Executive item one", "Executive item two"],
        "key_findings": [
            {
                "title": "Report key finding",
                "detail": "Key finding detail is displayed from artifact text.",
                "severity": "low",
            }
        ],
        "notable_source_ips": [
            {
                "src_ip": "203.0.113.88",
                "reason": "Same source appeared across candidate requests; this is not attribution.",
            }
        ],
        "noise_interpretation": "Candidate-excluded rows are baseline-like context for review.",
        "recommended_actions": [
            {
                "priority": "P2",
                "action": "Review matching application logs.",
                "why": "Apache logs alone do not prove exploit success.",
            }
        ],
        "confidence_and_limitations": [
            "Apache logs-only boundary applies.",
            "No browser execution result is available.",
        ],
        "presentation_takeaway": "Use the payload viewer as the primary human view.",
    }
    payload["noise"] = {
        "filtered_out_breakdown": {
            "benign_normal_search": 3,
            "known_baseline_like_legacy_alias": 2,
            "low_signal_request": 1,
        }
    }
    payload["raw_output_text"] = "must not render raw output"
    payload["raw_response"] = {"secret": "must not render raw provider response"}
    payload["prompt_text"] = "must not render prompt"
    payload["cost_estimate"] = {"usd": 1}
    return payload


def write_payload(project_root: Path, relative_path: str = "runs/jobs/123/viewer_payload.json", payload: Optional[dict[str, Any]] = None) -> Path:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload or make_viewer_payload()), encoding="utf-8")
    return path


def write_json_artifact(project_root: Path, relative_path: str, payload: dict[str, Any]) -> Path:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def install_repo(monkeypatch: pytest.MonkeyPatch, project_root: Path, report: Optional[dict[str, Any]]) -> None:
    monkeypatch.setattr(web_app_module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(web_app_module, "job_repository", FakeJobRepository(report))


def install_detail_repo(monkeypatch: pytest.MonkeyPatch, project_root: Path, report: Optional[dict[str, Any]]) -> None:
    monkeypatch.setattr(web_app_module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(web_app_module, "job_repository", FakeJobDetailRepository(report))


def render_response_body(response: Any) -> str:
    return response.body.decode("utf-8")


def assert_http_error(status_code: int) -> Any:
    return pytest.raises(HTTPException)


def test_job_viewer_route_renders_payload_dashboard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report())

    response = web_app_module.job_viewer_payload(make_request(), 123)
    body = render_response_body(response)

    assert response.status_code == 200
    assert "분석 보고서 보기" in body
    assert "payload-dashboard.css" in body
    assert "DB backed payload" in body
    assert "custom_payload_category" in body
    assert "scanner_baseline" in body
    assert "critical" in body
    assert "needs_review" in body


def test_job_viewer_uses_verdict_aware_finding_label_in_table_and_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command_injection_label = "명령 주입 의심 (CMDi-like request pattern)"
    payload = make_viewer_payload(
        findings=[
            {
                "request_id": "rid-cmdi",
                "category": "path_traversal_candidate",
                "verdict": "suspicious_command_injection",
            },
            {
                "request_id": "rid-traversal",
                "category": "path_traversal_candidate",
                "verdict": "suspicious_path_traversal",
            },
        ]
    )
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert f'data-finding-display-label="{command_injection_label}"' in body
    assert f'payload-category-badge">{command_injection_label}</span>' in body
    assert 'data-finding-display-label="path_traversal_candidate"' in body
    assert 'payload-category-badge">path_traversal_candidate</span>' in body
    assert "const categoryLabel = findingDisplayLabel(index, finding);" in body
    assert 'setText("pd-detail-title", categoryLabel);' in body
    assert "updateCategoryBadge(categoryLabel);" in body


def test_job_viewer_route_renders_report_level_human_sections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_payload(tmp_path, payload=make_human_viewer_payload())
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert "Report Summary" in body
    assert "Canonical payload report" in body
    assert "Report-level assessment text." in body
    assert "Executive item one" in body
    assert "Report key finding" in body
    assert "Key finding detail is displayed from artifact text." in body
    assert "Notable Source IPs" in body
    assert "203.0.113.88" in body
    assert "Candidate-Excluded / Context Notes" in body
    assert "후보 제외 행은 검토를 위한 Context이며 안전 판정이 아닙니다." in body
    assert "Baseline-like candidate-excluded context" in body
    assert "Baseline-like legacy context" in body
    assert "Low-signal request pattern" in body
    assert "Benign normal search" not in body
    assert "benign_normal_search" not in body
    assert "known_baseline_like_legacy_alias" not in body
    assert "보고서 권고 조치" in body
    assert "Review matching application logs." in body
    assert "Confidence and Limitations" in body
    assert "Apache logs-only boundary applies." in body
    assert "Presentation Takeaway" in body
    assert "Use the payload viewer as the primary human view." in body
    assert "Open Stage2 Report Viewer" not in body
    assert "stage2_report.md" not in body
    assert "raw_output_text" not in body
    assert "must not render raw output" not in body
    assert "raw_response" not in body
    assert "must not render raw provider response" not in body
    assert "prompt_text" not in body
    assert "must not render prompt" not in body
    assert "cost_estimate" not in body
    assert "benign" not in body.lower()
    assert " normal " not in body.lower()
    assert "정상" not in body
    assert "무해" not in body


@pytest.mark.parametrize(
    "summary,payload,expected_value,expected_unit,expected_source",
    [
        ({"total_request_count": 0}, {"counts": {"total_exported_rows": 9}}, 0, "requests", "summary.total_request_count"),
        ({"total_request_count": "0", "request_count": 8}, {}, 0, "requests", "summary.total_request_count"),
        ({"total_request_count": 4}, {"counts": {"total_exported_rows": 9}}, 4, "requests", "summary.total_request_count"),
        ({"total_request_count": "unknown"}, {"counts": {"total_exported_rows": 3}}, 3, "log_rows", "payload.counts.total_exported_rows"),
        ({"total_request_count": None}, {"summary": {"request_count": 2}}, 2, "requests", "payload.summary.request_count"),
        ({"total_request_count": ""}, {"meta": {"counts": {"total_rows": 5}}}, 5, "log_rows", "payload.meta.counts.total_rows"),
        ({}, {"summary": {"pipeline_counts": {"total_exported_rows": 0}}}, 0, "log_rows", "payload.summary.pipeline_counts.total_exported_rows"),
    ],
)
def test_viewer_input_count_preserves_priority_and_unit(summary, payload, expected_value, expected_unit, expected_source):
    resolved = report_routes.resolve_viewer_input_count(summary, payload)
    assert (resolved["value"], resolved["unit"], resolved["source"]) == (
        expected_value, expected_unit, expected_source
    )


@pytest.mark.parametrize(
    "summary,expected_status",
    [({}, "missing"), ({"total_request_count": None}, "null"),
     ({"total_request_count": "  "}, "empty"), ({"total_request_count": "unknown"}, "unknown")],
)
def test_viewer_input_count_distinguishes_unavailable_values(summary, expected_status):
    resolved = report_routes.resolve_viewer_input_count(summary, {})
    assert resolved["value"] is None
    assert resolved["status"] == expected_status


@pytest.mark.parametrize(
    "value,expected",
    [(0, "0"), (7, "7"), (None, "미제공"), ("", "미제공"), ("unknown", "알 수 없음")],
)
def test_job_viewer_renders_request_count_and_unavailable_values(monkeypatch, tmp_path, value, expected):
    payload = make_viewer_payload(findings=[])
    payload["summary"]["total_request_count"] = value
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())
    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))
    if expected.isdigit():
        assert "분석 입력 요청" in body
    else:
        assert "분석 입력 규모" in body
    assert f'<p class="payload-summary-value">{expected}</p>' in body


def test_legacy_viewer_uses_cached_request_count_when_payload_is_missing(monkeypatch):
    from types import SimpleNamespace

    report = SimpleNamespace(report_id="old", filename="stage2_report.json", generated_at="", meta={})
    report.to_detail = lambda: {"report_id": "old", "filename": report.filename,
                                "viewer_payload_summary": {"request_count": 6}}
    fake_loader = SimpleNamespace(scan_reports=lambda: [report], load_viewer_payload=lambda _: (None, "missing"))
    monkeypatch.setattr(report_routes, "loader", fake_loader)
    monkeypatch.setattr(report_routes, "lint_for_report", lambda _: None)
    body = render_response_body(report_routes.report_payload_detail(make_request(path="/report/old/payload"), "old"))
    assert "분석 입력 요청" in body
    assert '<p class="payload-summary-value">6</p>' in body


def test_legacy_loader_preserves_explicit_zero_when_rows_exist(tmp_path):
    payload = make_viewer_payload(findings=[{"request_id": "row-1"}])
    payload["summary"].update({"finding_count": 0, "context_count": "0", "supporting_event_count": None})
    resolved = ReportLoader(project_root=tmp_path)._build_viewer_payload_summary(payload)
    assert resolved["finding_count"] == 0
    assert resolved["context_count"] == 0
    assert resolved["supporting_event_count"] == len(payload["supporting_events"])
    assert len(resolved["findings_preview"]) == 1


@pytest.mark.parametrize("finding_count", [0, 1, 4])
def test_job_viewer_distinguishes_findings_from_report_summary_items(monkeypatch, tmp_path, finding_count):
    payload = make_viewer_payload(findings=[{"request_id": f"r-{index}"} for index in range(finding_count)])
    payload["report"] = {"key_findings": [
        {"title": "SQLi 의심", "detail": "요청 문자열 관찰", "severity": "medium"},
        {"title": "", "detail": "범위 확인", "severity": "info"},
        {"title": "판단 한계", "detail": "성공 여부 미확인", "severity": "low"},
    ]}
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())
    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))
    assert "보고서 핵심 요약 (3항목)" in body
    assert "실제 검토 대상 요청 건수와는 다릅니다" in body
    assert "제목 없는 요약 항목" in body
    assert f'<p class="payload-summary-value">{finding_count}</p>' in body
    assert body.index("요청 문자열 관찰") < body.index("Event Timeline")


def test_job_and_legacy_viewers_show_same_zero_and_scope(monkeypatch, tmp_path):
    from types import SimpleNamespace

    payload = make_viewer_payload(findings=[])
    payload["summary"]["pipeline_counts"] = {"total_exported_rows": 0}
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())
    job_body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    report = SimpleNamespace(report_id="legacy-1", filename="stage2_report.json", generated_at="", meta={})
    report.to_detail = lambda: {"report_id": "legacy-1", "filename": report.filename, "viewer_payload_summary": {}}
    fake_loader = SimpleNamespace(scan_reports=lambda: [report], load_viewer_payload=lambda _: (payload, ""))
    monkeypatch.setattr(report_routes, "loader", fake_loader)
    monkeypatch.setattr(report_routes, "lint_for_report", lambda _: None)
    legacy_body = render_response_body(report_routes.report_payload_detail(
        make_request(path="/report/legacy-1/payload"), "legacy-1"
    ))
    for body in (job_body, legacy_body):
        assert "분석 입력 로그 행" in body
        assert '<p class="payload-summary-value">0</p>' in body
        assert "서버 전체 요청 현황을 뜻하지 않습니다" in body
        assert "의심 신호의 강도와 검토 필요성을 반영한 정성 등급" in body
        assert "공격이 성공할 확률을 뜻하지 않습니다" in body


def test_sanitize_security_standards_summary_preserves_valid_known_and_unknown_groups() -> None:
    summary = make_security_standards_summary()
    summary["standards"]["A_MALFORMED"] = "not-a-list"
    summary["standards"]["CWE"].extend(
        [
            None,
            {"id": "", "finding_count": 2},
            {"id": "CWE-0", "finding_count": 0},
            {
                "id": "CWE-79",
                "name": "Cross-site Scripting",
                "finding_count": 2,
                "relationship_counts": {"direct": 1, "future": 9},
                "unknown_nested": {"drop": True},
            },
        ]
    )

    sanitized = report_routes.sanitize_security_standards_summary(summary)

    assert sanitized["schema_version"] == "security_standards_summary.v1"
    assert sanitized["total_finding_count"] == 12
    assert sanitized["mapped_finding_count"] == 9
    assert sanitized["unmapped_finding_count"] == 3
    assert [row["id"] for row in sanitized["standards"]["OWASP_TOP10"]] == [
        "A05:2025",
        "A01:2025",
        "A07:2025",
    ]
    assert [row["id"] for row in sanitized["standards"]["CWE"]] == ["CWE-89", "CWE-79"]
    assert sanitized["standards"]["CWE"][1]["relationship_counts"] == {
        "direct": 1,
        "conditional": 0,
        "related": 0,
    }
    assert "unknown_nested" not in sanitized["standards"]["CWE"][1]
    assert sanitized["standards"]["ASVS"][0]["id"] == "V5.3.1"
    assert "A_MALFORMED" not in sanitized["standards"]
    assert "future_scope" not in sanitized["observability_counts"]
    assert "diagnostics" not in sanitized


@pytest.mark.parametrize(
    "summary",
    [
        None,
        [],
        {},
        {"schema_version": "security_standards_summary.v2", "standards": {}},
        {"schema_version": "security_standards_summary.v1"},
        {"schema_version": "security_standards_summary.v1", "standards": "invalid"},
    ],
)
def test_sanitize_security_standards_summary_hides_invalid_roots(summary: Any) -> None:
    assert report_routes.sanitize_security_standards_summary(summary) == {}


def test_sanitize_security_standards_summary_normalizes_negative_bool_and_garbage_counts() -> None:
    summary = make_security_standards_summary()
    summary.update(
        {
            "total_finding_count": "12",
            "mapped_finding_count": -4,
            "unmapped_finding_count": True,
            "observability_counts": {"attempt_only": "garbage", "behavior_only": -2},
        }
    )
    summary["standards"]["OWASP_TOP10"] = [
        {"id": "A01:2025", "name": "Skip negative", "finding_count": -1},
        {"id": "A05:2025", "name": "Injection", "finding_count": "2"},
    ]

    sanitized = report_routes.sanitize_security_standards_summary(summary)

    assert sanitized["total_finding_count"] == 12
    assert sanitized["mapped_finding_count"] == 0
    assert sanitized["unmapped_finding_count"] == 0
    assert sanitized["observability_counts"]["attempt_only"] == 0
    assert sanitized["observability_counts"]["behavior_only"] == 0
    assert [row["id"] for row in sanitized["standards"]["OWASP_TOP10"]] == ["A05:2025"]


def test_sanitize_security_standards_summary_bounds_display_without_changing_source() -> None:
    summary = make_security_standards_summary()
    oversized_rows = [
        {
            "id": f"CWE-{index}",
            "name": f"Weakness {index}",
            "finding_count": 1,
            "relationship_counts": {"related": 1},
        }
        for index in range(report_routes.SECURITY_STANDARDS_MAX_ROWS_PER_GROUP + 1)
    ]
    summary["standards"]["CWE"] = oversized_rows

    sanitized = report_routes.sanitize_security_standards_summary(summary)

    assert len(sanitized["standards"]["CWE"]) == report_routes.SECURITY_STANDARDS_MAX_ROWS_PER_GROUP
    assert sanitized["display_truncated"] is True
    assert len(summary["standards"]["CWE"]) == report_routes.SECURITY_STANDARDS_MAX_ROWS_PER_GROUP + 1


def test_job_viewer_renders_report_and_timeline_before_security_standards_and_uses_full_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = make_human_viewer_payload()
    payload["findings"] = payload["findings"] * 12
    payload["security_standards_summary"] = make_security_standards_summary(total=25, mapped=9, unmapped=16)
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert body.index("Report Summary") < body.index("Event Timeline")
    assert body.index("Event Timeline") < body.index("Security Standards Summary")
    assert "Mapped findings" in body
    assert "9 / 25" in body
    assert "중복 제거된 전체 Finding 25건" in body
    assert "선택된 Finding 12건" in body
    assert "OWASP-related Observed Categories" in body
    assert "A05:2025" in body
    assert "Injection" in body
    assert "직접 6" in body
    assert "Direct" in body
    assert "CWE Mapping Breakdown" in body
    assert "CWE-89" in body
    assert "Related WSTG Test Scenarios" in body
    assert "WSTG-INPV-05" in body
    assert "Other Standards Mappings" in body
    assert "V5.3.1" in body
    assert "Evidence Scope" in body
    assert "Attempt observed" in body
    assert "Relationship meanings" in body
    assert "취약점·약점·컴플라이언스 충족이나 성공적인 악용을 입증하지 않습니다" in body
    assert "Finding이나 대상이 안전하다는 뜻이 아닙니다" in body


def test_job_viewer_multi_category_summary_does_not_sum_categories_as_incidents(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = make_viewer_payload(findings=[{"request_id": "rid-1"}])
    summary = make_security_standards_summary(total=1, mapped=1, unmapped=0)
    summary["standards"]["OWASP_TOP10"] = [
        {
            "id": "A01:2025",
            "name": "Broken Access Control",
            "finding_count": 1,
            "relationship_counts": {"direct": 1},
        },
        {
            "id": "A05:2025",
            "name": "Injection",
            "finding_count": 1,
            "relationship_counts": {"related": 1},
        },
    ]
    payload["security_standards_summary"] = summary
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert "1 / 1" in body
    assert "A01:2025" in body
    assert "A05:2025" in body
    assert "분류별 건수를 전체 incident 수로 합산하지 않습니다" in body
    assert "2 incidents" not in body


def test_job_viewer_mapped_zero_uses_enrichment_empty_state_not_safety_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = make_viewer_payload(findings=[{"request_id": f"rid-{index}"} for index in range(5)])
    summary = make_security_standards_summary(total=5, mapped=0, unmapped=5)
    summary["standards"] = {"OWASP_TOP10": [], "CWE": [], "WSTG": []}
    payload["security_standards_summary"] = summary
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert "Security Standards Summary" in body
    assert "0 / 5" in body
    assert "이 보강 계층이 연결한 보안 표준 매핑이 없습니다" in body
    assert "No vulnerabilities found" not in body


def test_job_viewer_old_artifact_hides_summary_and_keeps_existing_viewer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_payload(tmp_path, payload=make_viewer_payload())
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert "Security Standards Summary" not in body
    assert "Event Timeline" in body
    assert "선택한 탐지 요청 상세" in body


def test_job_viewer_escapes_html_looking_standard_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = make_viewer_payload()
    summary = make_security_standards_summary()
    summary["standards"]["OWASP_TOP10"][0]["name"] = "<script>alert(1)</script>"
    payload["security_standards_summary"] = summary
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<strong class=\"security-standard-row-name\"><script>" not in body


def test_job_viewer_route_masks_report_level_source_ips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_payload(tmp_path, payload=make_human_viewer_payload())
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(
        web_app_module.job_viewer_payload(make_request(query_string=b"mask_src_ip=1"), 123)
    )

    assert "203.0.113.***" in body
    assert "203.0.113.88" not in body


def test_raw_viewer_payload_artifact_route_still_returns_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report())

    response = web_app_module.job_artifact(123, "viewer_payload")

    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert b"viewer_payload.v1" in response.body


def test_job_detail_renders_artifact_usage_and_filtered_reason_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_json_artifact(
        tmp_path,
        "runs/jobs/123/stage1_results.json",
        {
            "meta": {
                "llm_usage_totals": {
                    "available": True,
                    "call_count": 5,
                    "input_tokens": 13463,
                    "output_tokens": 956,
                    "total_tokens": 14419,
                    "provider": "openai",
                    "selected_model": "gpt-5.4-mini",
                    "unavailable_count": 0,
                }
            },
            "results": [{"request_id": "req-1", "raw_output_text": "must not render"}],
        },
    )
    write_json_artifact(
        tmp_path,
        "runs/jobs/123/stage2_report.json",
        {
            "meta": {
                "provider": "openai",
                "selected_model": "gpt-5.4-mini",
                "llm_usage": {
                    "available": True,
                    "calls": [{"provider": "openai", "model": "gpt-5.4-mini"}],
                    "totals": {
                        "call_count": 1,
                        "input_tokens": 15674,
                        "output_tokens": 2172,
                        "total_tokens": 17846,
                        "unavailable_count": 0,
                    },
                },
            }
        },
    )
    write_json_artifact(
        tmp_path,
        "runs/jobs/123/filtered_reasons.json",
        {
            "schema_version": "filtered_reasons.v1",
            "total_rows": 14,
            "candidate_count": 5,
            "excluded_count": 9,
            "excluded_summary": {"low_signal_request": 4, "static_asset_like": 3},
            "guardrails": [
                "candidate_excluded_does_not_mean_benign",
                "apache_logs_only_no_success_inference",
                "status_code_response_size_route_or_user_agent_do_not_prove_success_or_benign",
            ],
            "excluded": [{"request_id": "excluded-1", "reason": "low_signal_request"}],
        },
    )
    install_detail_repo(
        monkeypatch,
        tmp_path,
        make_report(
            stage1_result_path="runs/jobs/123/stage1_results.json",
            stage2_report_path="runs/jobs/123/stage2_report.json",
        ),
    )

    response = web_app_module.job_detail(make_request(path="/job/123"), 123)
    body = render_response_body(response)

    assert response.status_code == 200
    assert "아티팩트 요약" in body
    assert "Artifact Summary" in body
    assert "Stage1 LLM 사용량" in body
    assert "Stage1 LLM Usage" in body
    assert "Stage2 LLM 사용량" in body
    assert "Stage2 LLM Usage" in body
    assert "13,463" in body
    assert "15,674" in body
    assert "17,846" in body
    assert "32,265" in body
    assert "14,419" in body
    assert ">6<" in body
    assert "gpt-5.4-mini" in body
    assert "후보 제외 행" in body
    assert "Candidate-excluded rows" in body
    assert "low_signal_request" in body
    assert "후보 제외 행은 안전 판정이 아닙니다." in body
    assert "Apache logs alone do not prove exploit success." in body
    assert "Status, size, route, or user-agent alone are not proof." in body
    assert "해석 가드레일" in body
    assert "Guardrails" in body
    assert "(3)" in body
    assert "candidate_excluded_does_not_mean_benign" not in body
    assert "apache_logs_only_no_success_inference" not in body
    assert "status_code_response_size_route_or_user_agent_do_not_prove_success_or_benign" not in body
    assert "사용량 확인 불가 호출" not in body
    assert "Unavailable calls" not in body
    assert 'href="/job/123/artifact/filtered_reasons"' in body
    assert "raw_output_text" not in body
    assert "must not render" not in body
    assert "cost_estimate" not in body
    assert "benign" not in body.lower()
    assert "normal" not in body.lower()
    assert "정상" not in body
    assert "무해" not in body


def test_job_detail_renders_positive_unavailable_usage_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_json_artifact(
        tmp_path,
        "runs/jobs/123/stage1_results.json",
        {
            "meta": {
                "llm_usage_totals": {
                    "available": True,
                    "call_count": 3,
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "provider": "openai",
                    "selected_model": "gpt-5.4-mini",
                    "unavailable_count": 2,
                }
            }
        },
    )
    install_detail_repo(
        monkeypatch,
        tmp_path,
        make_report(stage1_result_path="runs/jobs/123/stage1_results.json"),
    )

    body = render_response_body(web_app_module.job_detail(make_request(path="/job/123"), 123))

    assert "사용량 확인 불가 호출" in body
    assert "Unavailable calls" in body
    assert "3,000" in body


def test_job_detail_filtered_reasons_missing_is_graceful(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_json_artifact(
        tmp_path,
        "runs/jobs/123/stage1_results.json",
        {"meta": {"llm_usage_totals": {"available": False, "unavailable_reason": "dry_run_no_provider_call"}}},
    )
    install_detail_repo(
        monkeypatch,
        tmp_path,
        make_report(stage1_result_path="runs/jobs/123/stage1_results.json"),
    )

    body = render_response_body(web_app_module.job_detail(make_request(path="/job/123"), 123))

    assert "Usage unavailable" in body
    assert "Dry-run에서는 provider 호출이 없습니다." in body
    assert "필터링 사유 아티팩트를 찾지 못했습니다" in body


def test_raw_filtered_reasons_artifact_route_is_job_root_scoped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_json_artifact(
        tmp_path,
        "runs/jobs/123/filtered_reasons.json",
        {"schema_version": "filtered_reasons.v1"},
    )
    install_repo(monkeypatch, tmp_path, make_report())

    response = web_app_module.job_artifact(123, "filtered_reasons")

    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert b"filtered_reasons.v1" in response.body


def test_filtered_reasons_artifact_root_traversal_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_json_artifact(
        tmp_path,
        "runs/jobs/secret/filtered_reasons.json",
        {"schema_version": "filtered_reasons.v1"},
    )
    install_repo(monkeypatch, tmp_path, make_report(artifact_root="runs/jobs/123/../secret"))

    with assert_http_error(404) as exc_info:
        web_app_module.job_artifact(123, "filtered_reasons")

    assert exc_info.value.status_code == 404


def test_job_viewer_route_uses_job_back_link(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert 'href="/job/123"' in body
    assert "분석 작업 상세로 돌아가기" in body
    assert 'href="/report/job-123"' not in body


def test_job_viewer_route_mask_link_stays_on_job_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert 'href="/job/123/viewer?mask_src_ip=1"' in body
    assert 'href="/report/job-123/payload' not in body


def test_null_viewer_payload_path_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install_repo(monkeypatch, tmp_path, make_report(viewer_payload_path=None))

    with assert_http_error(404) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 404


def test_missing_report_row_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install_repo(monkeypatch, tmp_path, None)

    with assert_http_error(404) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 404


def test_missing_viewer_payload_file_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install_repo(monkeypatch, tmp_path, make_report())

    with assert_http_error(404) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 404


def test_missing_artifact_root_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report(artifact_root=None))

    with assert_http_error(404) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 404


def test_absolute_viewer_payload_path_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report(viewer_payload_path=str(path)))

    with assert_http_error(404) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 404


def test_viewer_payload_path_traversal_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path, "runs/jobs/secret.json")
    install_repo(monkeypatch, tmp_path, make_report(viewer_payload_path="runs/jobs/123/../secret.json"))

    with assert_http_error(404) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 404


def test_viewer_payload_symlink_outside_project_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    outside_root = tmp_path.parent / "outside-job-viewer-route-test"
    outside_root.mkdir(exist_ok=True)
    outside_file = outside_root / "viewer_payload.json"
    outside_file.write_text(json.dumps(make_viewer_payload()), encoding="utf-8")
    link_path = tmp_path / "runs" / "jobs" / "123" / "viewer_payload.json"
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(outside_file)
    install_repo(monkeypatch, tmp_path, make_report())

    with assert_http_error(404) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 404


def test_viewer_payload_outside_artifact_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path, "runs/jobs/999/viewer_payload.json")
    install_repo(monkeypatch, tmp_path, make_report(viewer_payload_path="runs/jobs/999/viewer_payload.json"))

    with assert_http_error(404) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 404


def test_invalid_viewer_payload_json_is_400(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "runs" / "jobs" / "123" / "viewer_payload.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")
    install_repo(monkeypatch, tmp_path, make_report())

    with assert_http_error(400) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 400


def test_viewer_payload_non_object_json_is_400(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "runs" / "jobs" / "123" / "viewer_payload.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    install_repo(monkeypatch, tmp_path, make_report())

    with assert_http_error(400) as exc_info:
        web_app_module.job_viewer_payload(make_request(), 123)

    assert exc_info.value.status_code == 400


def test_job_viewer_route_does_not_call_lint_for_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail_lint(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("lint_for_report must not be called by DB-backed job viewer")

    write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report())
    monkeypatch.setattr(report_routes, "lint_for_report", fail_lint)

    response = web_app_module.job_viewer_payload(make_request(), 123)

    assert response.status_code == 200


def test_context_only_items_are_not_promoted_to_findings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = make_viewer_payload(
        findings=[],
        contexts=[
            {
                "context_type": "context_should_remain_context",
                "src_ip": "203.0.113.77",
                "request_count": 5,
                "context_only": True,
                "should_promote_to_candidate": True,
            }
        ],
    )
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert "Viewer payload에 주요 탐지 요청이 없습니다." in body
    assert "context_should_remain_context" in body
    assert 'class="payload-finding-row' not in body


def test_sanitize_payload_findings_preserves_relation_id_lists_only() -> None:
    rows = [
        {
            "request_id": "rid-1",
            "related_context_ids": ["ctx_1", 2, "", {"raw": "object"}],
            "supporting_event_ids": ["sev_1", None, "sev_2"],
        },
        {
            "request_id": "rid-2",
            "related_context_ids": {"ctx": "not-list"},
            "supporting_event_ids": "sev_not_list",
        },
    ]

    findings = report_routes.sanitize_payload_findings(rows)

    assert findings[0]["related_context_ids"] == ["ctx_1", "2"]
    assert findings[0]["supporting_event_ids"] == ["sev_1", "sev_2"]
    assert findings[1]["related_context_ids"] == []
    assert findings[1]["supporting_event_ids"] == []


def test_sanitize_payload_findings_preserves_standards_mapping() -> None:
    mapping = {
        "schema_version": "security_standards_mapping.v1",
        "source": "deterministic_stage1_enrichment",
        "observability": "attempt_only",
        "items": [
            {
                "rule_id": "STD-MAP-SQLI-001",
                "standard": "OWASP_TOP10",
                "id": "A05:2025",
                "name": "Injection",
                "relationship": "direct",
                "basis": ["stage1_verdict:suspicious_sqli"],
                "boundary_note": "Apache logs do not confirm DB query execution.",
            }
        ],
        "unmapped_reason": "",
    }

    findings = report_routes.sanitize_payload_findings(
        [
            {
                "request_id": "rid-1",
                "standards_mapping": mapping,
            },
            {
                "request_id": "rid-2",
                "standards_mapping": {"items": "invalid"},
            },
        ]
    )

    assert findings[0]["standards_mapping"] == mapping
    assert "standards_mapping" not in findings[1]


def test_job_viewer_route_renders_explicit_relation_contract_without_heuristic_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = make_viewer_payload(
        findings=[
            {
                "log_time": "2026-05-30T00:00:01Z",
                "severity": "low",
                "verdict": "needs_review",
                "category": "auth_behavior_candidate",
                "src_ip": "203.0.113.10",
                "method": "POST",
                "uri": "/login",
                "status_code": 401,
                "request_id": "rid-1",
                "related_context_ids": ["ctx_auth"],
                "supporting_event_ids": ["sev_auth"],
            }
        ],
        contexts=[
            {
                "context_id": "ctx_auth",
                "context_type": "auth_behavior",
                "src_ip": "203.0.113.10",
                "request_count": 3,
                "context_only": True,
                "should_promote_to_candidate": False,
            }
        ],
    )
    payload["supporting_events"] = [
        {
            "event_id": "sev_auth",
            "request_id": "rid-1",
            "supporting_role": "auth_behavior_support",
            "context_only": True,
        }
    ]
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert "related_context_ids" in body
    assert "supporting_event_ids" in body
    assert "이 Viewer payload에 명시적으로 연결된 해석 정보가 없습니다." in body
    assert "이 Viewer payload에 명시적으로 연결된 주변 참고 요청이 없습니다." in body


def test_job_viewer_route_preserves_security_standards_mapping_in_payload_script(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = make_viewer_payload(
        findings=[
            {
                "log_time": "2026-05-30T00:00:01Z",
                "severity": "medium",
                "confidence": "medium",
                "verdict": "suspicious_sqli",
                "category": "sqli_candidate",
                "src_ip": "203.0.113.10",
                "method": "GET",
                "uri": "/search",
                "status_code": 403,
                "request_id": "rid-sqli",
                "standards_mapping": {
                    "schema_version": "security_standards_mapping.v1",
                    "source": "deterministic_stage1_enrichment",
                    "observability": "attempt_only",
                    "items": [
                        {
                            "standard": "OWASP_TOP10",
                            "id": "A05:2025",
                            "name": "Injection",
                            "relationship": "direct",
                            "boundary_note": "Apache logs do not confirm DB query execution.",
                        },
                        {
                            "standard": "CWE",
                            "id": "CWE-89",
                            "name": "SQL Injection",
                            "relationship": "direct",
                            "boundary_note": "Apache logs do not confirm DB query execution.",
                        },
                        {
                            "standard": "WSTG",
                            "id": "WSTG-INPV-05",
                            "name": "Testing for SQL Injection",
                            "relationship": "direct",
                            "boundary_note": "Apache logs do not confirm DB query execution.",
                        },
                    ],
                    "unmapped_reason": "",
                },
            }
        ]
    )
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert "Security Standards" in body
    assert "Evidence Scope" in body
    assert "관찰된 패턴과 보안 표준 매핑은 취약점이나 성공적인 악용을 입증하지 않습니다" in body
    assert "A05:2025" in body
    assert "Injection" in body
    assert "CWE-89" in body
    assert "SQL Injection" in body
    assert "WSTG-INPV-05" in body
    assert "Testing for SQL Injection" in body
    assert "Direct" in body
    assert "standards_mapping" in body


@pytest.mark.parametrize('summary_time,meta_time,expected,source', [
    ('legacy-time', 'viewer-time', 'viewer-time', 'payload.meta.generated_at'),
    (None, 'viewer-time', 'viewer-time', 'payload.meta.generated_at'),
    ('', 'viewer-time', 'viewer-time', 'payload.meta.generated_at'),
    ('unknown', 'viewer-time', 'viewer-time', 'payload.meta.generated_at'),
    ('  ', 'viewer-time', 'viewer-time', 'payload.meta.generated_at'),
    ('unknown', 'N/A', None, '미제공'),
    (None, None, None, '미제공'),
])
def test_viewer_timestamp_precedence_and_provenance(summary_time, meta_time, expected, source):
    payload = {'summary': {'generated_at': summary_time}, 'meta': {'generated_at': meta_time},
               'report': {'generated_at': 'stage2-time'}}
    before = json.dumps(payload)
    result = web_app_module._build_job_viewer_payload_summary(payload)
    assert result.get('generated_at') == expected
    assert source in result['generated_at_source']
    assert result['stage2_generated_at'] == 'stage2-time'
    assert json.dumps(payload) == before


def finding_script(body):
    import re
    match = re.search(r'<script type="application/json" id="payload-findings-data">(.*?)</script>', body, re.S)
    assert match is not None
    return json.loads(match.group(1))


@pytest.mark.parametrize('mask', [False, True])
def test_job_viewer_original_fields_safe_serialization_and_mask(monkeypatch, tmp_path, mask):
    raw = '  GET /x?q=%2527%2520%253Cscript%253E&ip=203%2e0%2e113%2e10  HTTP/1.1\n</script><img src=x onerror=alert(1)>  '
    rows = [dict(src_ip='203.0.113.10', request_id='r-1', uri='/display',
                 raw_request_target=raw, raw_request=raw, query_string=raw),
            dict(src_ip='203.0.113.20', request_id='r-2', uri='/display?composed=true')]
    payload = make_viewer_payload(findings=rows)
    payload['summary'].pop('generated_at')
    payload['meta'] = {'generated_at': 'actual-viewer-time'}
    payload['report'] = {'generated_at': 'actual-stage2-time'}
    artifact = write_payload(tmp_path, payload=payload)
    original_bytes = artifact.read_bytes()
    install_repo(monkeypatch, tmp_path, make_report())
    response = web_app_module.job_viewer_payload(make_request(query_string=b'mask_src_ip=1' if mask else b''), 123)
    body = render_response_body(response)
    findings = {row['request_id']: row for row in finding_script(body)}
    for key in ('raw_request_target', 'raw_request', 'query_string'):
        assert findings['r-1'][key] == (None if mask else raw)
        assert findings['r-2'][key] is None
    if mask:
        assert findings['r-1']['raw_request_hidden'] is True
        assert '203%2e0%2e113%2e10' not in body
        assert 'onerror=alert(1)' not in body
    else:
        assert '</script><img src=x onerror=alert(1)>' not in body
        assert '203%2e0%2e113%2e10' in body
    assert 'actual-viewer-time' in body and 'payload.meta.generated_at' in body
    assert 'actual-stage2-time' in body and 'Stage2 보고서 시각' in body
    assert artifact.read_bytes() == original_bytes


def test_original_fields_preserve_empty_whitespace_and_do_not_synthesize():
    rows = [dict(raw_request_target='', raw_request=' \t\n ', query_string='  x=%2520+%2B  '),
            dict(method='GET', uri='/x?q=1', request={'raw_request': 'not-an-explicit-original'})]
    before = json.dumps(rows)
    result = report_routes.sanitize_payload_findings(rows)
    assert result[0]['raw_request_target'] == ''
    assert result[0]['raw_request'] == ' \t\n '
    assert result[0]['query_string'] == '  x=%2520+%2B  '
    assert all(result[1][key] is None for key in ('raw_request_target', 'raw_request', 'query_string'))
    assert json.dumps(rows) == before


def test_job_viewer_missing_timestamp_renders_unprovided(monkeypatch, tmp_path):
    payload = make_viewer_payload()
    payload['summary'].pop('generated_at')
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())
    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))
    assert '생성 시각 미제공' in body
    assert '실제 생성 시각 미제공' in body


@pytest.mark.parametrize('mask', [False, True])
def test_legacy_report_viewer_uses_same_original_and_timestamp_contract(monkeypatch, tmp_path, mask):
    from types import SimpleNamespace
    raw = '  /q?x=%2527&h=<script>  '
    payload = make_viewer_payload(findings=[{'src_ip': '203.0.113.10', 'request_id': 'legacy-r', 'raw_request_target': raw}])
    payload['summary'].pop('generated_at')
    payload['meta'] = {'generated_at': 'legacy-payload-time'}
    report = SimpleNamespace(report_id='legacy-1', filename='stage2_report.json', generated_at='stage2-only-time', meta={'generated_at': 'legacy-stage2-time'})
    report.to_detail = lambda: {'report_id': report.report_id, 'filename': report.filename, 'viewer_payload_summary': {}}
    loader = SimpleNamespace(scan_reports=lambda: [report], load_viewer_payload=lambda r: (payload, ''))
    monkeypatch.setattr(report_routes, 'loader', loader)
    monkeypatch.setattr(report_routes, 'lint_for_report', lambda r: None)
    response = report_routes.report_payload_detail(make_request(path='/report/legacy-1/payload', query_string=b'mask_src_ip=1' if mask else b''), 'legacy-1')
    body = render_response_body(response)
    parsed = finding_script(body)[0]
    assert parsed['raw_request_target'] == (None if mask else raw)
    assert 'legacy-payload-time' in body and 'payload.meta.generated_at' in body
    assert 'stage2-only-time' not in body
    assert 'legacy-stage2-time' in body and 'stage2_report.meta.generated_at (기존 보고서 로더)' in body


def test_optional_asset_input_invalidates_web_quality_cache(tmp_path, monkeypatch):
    import os
    from web.services import qa_runner
    paths = {name: tmp_path / name for name in ('script.py', 'semantics.py', 'report.json', 'cache.json', 'stage2_report_input.json')}
    for name in ('script.py', 'semantics.py', 'report.json'):
        paths[name].write_text('{}')
        os.utime(paths[name], (100, 100))
    paths['cache.json'].write_text(json.dumps({'scope': 'all', 'coverage': {'stage1': {'status': 'missing'}, 'viewer': {'status': 'missing'}}, 'asset_review': {'status': 'not_evaluable'}}))
    os.utime(paths['cache.json'], (200, 200))
    monkeypatch.setattr(qa_runner, 'SEMANTICS_PATH', paths['semantics.py'])
    runner = qa_runner.QARunner(script_path=paths['script.py'])
    assert runner._read_cached_if_fresh(paths['cache.json'], paths['report.json']) is not None
    paths['stage2_report_input.json'].write_text('{}')
    os.utime(paths['stage2_report_input.json'], (150, 150))
    assert runner._read_cached_if_fresh(paths['cache.json'], paths['report.json']) is None


def test_stage2_and_viewer_metadata_times_remain_distinct():
    payload = {'summary': {'generated_at': 'legacy-time'},
               'meta': {'generated_at': 'viewer-time', 'stage2_generated_at': 'actual-stage2-time'},
               'report': {'generated_at': 'report-fallback-time'}}
    summary = web_app_module._build_job_viewer_payload_summary(payload)
    assert summary['generated_at'] == 'viewer-time'
    assert summary['viewer_generated_at'] == 'viewer-time'
    assert summary['stage2_generated_at'] == 'actual-stage2-time'
    assert 'stage2_report.meta.generated_at' in summary['stage2_generated_at_source']


PAYLOAD_TIME = "2026-10-23T15:20:23.804+09:00"
LEGACY_TIME = "2026-10-22T06:00:00.123Z"


def assert_viewer_times_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, payload: dict[str, Any], expected: Optional[str]
) -> None:
    original = json.dumps(payload, sort_keys=True)
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())
    job_response = web_app_module.job_viewer_payload(make_request(), 123)

    # Load the same payload through the existing report Viewer, with a deliberately
    # different Stage2 timestamp to catch accidental substitution of report time.
    stage2_time = "2000-01-01T00:00:00Z"
    write_json_artifact(tmp_path, "fixture_stage2_report.json", {
        "meta": {"generated_at": stage2_time}, "report": {"report_title": "Fixture report"},
    })
    write_json_artifact(tmp_path, "fixture_viewer_payload.json", payload)
    loader = ReportLoader(project_root=tmp_path, report_globs=["fixture_stage2_report.json"])
    reports = loader.scan_reports()
    assert len(reports) == 1
    report = reports[0]
    assert report.generated_at == stage2_time
    assert report.viewer_payload_summary["generated_at"] == (expected or "unknown")
    timestamps = web_app_module._build_job_viewer_payload_summary(payload)
    for key in ("generated_at_source", "viewer_generated_at", "stage2_generated_at", "stage2_generated_at_source"):
        assert report.viewer_payload_summary[key] == timestamps[key]
    monkeypatch.setattr(report_routes, "loader", loader)
    monkeypatch.setattr(report_routes, "lint_for_report", lambda report: None)
    legacy_response = report_routes.report_payload_detail(
        make_request(f"/report/{report.report_id}/payload"), report.report_id
    )

    for response in [job_response, legacy_response]:
        assert response.status_code == 200
        assert response.context["payload_summary"]["generated_at"] == expected
        for key in ("generated_at_source", "viewer_generated_at"):
            assert response.context["payload_summary"][key] == timestamps[key]
        if timestamps["stage2_generated_at"]:
            for key in ("stage2_generated_at", "stage2_generated_at_source"):
                assert response.context["payload_summary"][key] == timestamps[key]
        assert re.search(
            r'payload-summary-time">\s*' + re.escape(expected or "생성 시각 미제공") + r"\s*</p>",
            render_response_body(response),
        )
    assert json.dumps(payload, sort_keys=True) == original


@pytest.mark.parametrize("meta,summary,expected", [
    ({"generated_at": PAYLOAD_TIME}, {}, PAYLOAD_TIME),
    ({}, {"generated_at": LEGACY_TIME}, LEGACY_TIME),
    ({"generated_at": PAYLOAD_TIME}, {"generated_at": LEGACY_TIME}, PAYLOAD_TIME),
    ({}, {}, None),
    (None, None, None),
    ("invalid-meta", [], None),
    ({"generated_at": LEGACY_TIME}, {"generated_at": PAYLOAD_TIME}, LEGACY_TIME),
    *[({"generated_at": invalid}, {"generated_at": LEGACY_TIME}, LEGACY_TIME)
      for invalid in [None, "", "  \t", "unknown", " UnKnOwN ", "N/A", "-", 0, False, [], {}]],
    *[({"generated_at": invalid}, {"generated_at": invalid}, None)
      for invalid in [None, "", "  ", "unknown", " UNKNOWN ", "n/a", "-", 0, False, [], {}]],
])
def test_viewer_generated_at_priority_and_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, meta: Any, summary: Any, expected: Optional[str]
) -> None:
    payload = make_viewer_payload()
    payload["meta"] = meta
    payload["summary"] = summary
    assert_viewer_times_match(monkeypatch, tmp_path, payload, expected)


def test_viewers_keep_unknown_when_timestamp_fields_are_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = make_viewer_payload()
    payload.pop("meta", None)
    payload["summary"].pop("generated_at", None)
    assert_viewer_times_match(monkeypatch, tmp_path, payload, None)


def test_actual_builder_payload_timestamp_renders_in_both_viewers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report_input_path = write_json_artifact(tmp_path, "builder_input.json", {
        "pipeline_counts": {"total_exported_rows": 0}
    })
    stage2_path = write_json_artifact(tmp_path, "builder_stage2.json", {
        "meta": {"generated_at": "2000-01-01T00:00:00Z"},
        "report": {"report_title": "Actual builder fixture"},
    })
    out_path = tmp_path / "builder_viewer.json"
    monkeypatch.setattr(viewer_payload_builder, "iso_now", lambda: PAYLOAD_TIME)
    monkeypatch.setattr(sys, "argv", [
        "viewer_payload_builder.py", "--stage2-report-input", str(report_input_path),
        "--stage2-report", str(stage2_path), "--out", str(out_path),
    ])
    assert viewer_payload_builder.main() == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["meta"]["generated_at"] == PAYLOAD_TIME
    assert "generated_at" not in payload["summary"]
    assert payload["meta"]["stage2_generated_at"] == "2000-01-01T00:00:00Z"
    assert payload["summary"]["finding_count"] == len(payload["findings"]) == 0
    assert report_routes.resolve_viewer_input_count(payload["summary"], payload)["value"] == 0
    assert_viewer_times_match(monkeypatch, tmp_path, payload, PAYLOAD_TIME)
