from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import web.app as web_app_module
import web.routes.reports as report_routes


class FakeJobRepository:
    def __init__(self, report: Optional[dict[str, Any]]) -> None:
        self.report = report

    def get_latest_report_for_job(self, job_id: int) -> Optional[dict[str, Any]]:
        return self.report


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
            "finding_count": len(findings or []),
            "context_count": len(contexts or []),
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


def write_payload(project_root: Path, relative_path: str = "runs/jobs/123/viewer_payload.json", payload: Optional[dict[str, Any]] = None) -> Path:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload or make_viewer_payload()), encoding="utf-8")
    return path


def install_repo(monkeypatch: pytest.MonkeyPatch, project_root: Path, report: Optional[dict[str, Any]]) -> None:
    monkeypatch.setattr(web_app_module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(web_app_module, "job_repository", FakeJobRepository(report))


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
    assert "Viewer Payload Dashboard" in body
    assert "payload-dashboard.css" in body
    assert "DB backed payload" in body
    assert "custom_payload_category" in body
    assert "scanner_baseline" in body
    assert "critical" in body
    assert "needs_review" in body


def test_raw_viewer_payload_artifact_route_still_returns_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report())

    response = web_app_module.job_artifact(123, "viewer_payload")

    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert b"viewer_payload.v1" in response.body


def test_job_viewer_route_uses_job_back_link(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_payload(tmp_path)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert 'href="/job/123"' in body
    assert "Back To Job Detail" in body
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

    assert "No findings in viewer payload." in body
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
    assert "No explicit related contexts in this viewer payload." in body
    assert "No explicit related supporting events in this viewer payload." in body
