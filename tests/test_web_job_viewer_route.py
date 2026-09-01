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
    assert "Viewer Payload Dashboard" in body
    assert "payload-dashboard.css" in body
    assert "DB backed payload" in body
    assert "custom_payload_category" in body
    assert "scanner_baseline" in body
    assert "critical" in body
    assert "needs_review" in body


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
    assert "Candidate-excluded rows are context for review, not safety verdicts." in body
    assert "Baseline-like candidate-excluded context" in body
    assert "Baseline-like legacy context" in body
    assert "Low-signal request pattern" in body
    assert "Benign normal search" not in body
    assert "benign_normal_search" not in body
    assert "known_baseline_like_legacy_alias" not in body
    assert "Report-Level Recommended Actions" in body
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


def test_job_viewer_renders_security_standards_summary_before_report_and_uses_full_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = make_human_viewer_payload()
    payload["findings"] = payload["findings"] * 12
    payload["security_standards_summary"] = make_security_standards_summary(total=25, mapped=9, unmapped=16)
    write_payload(tmp_path, payload=payload)
    install_repo(monkeypatch, tmp_path, make_report())

    body = render_response_body(web_app_module.job_viewer_payload(make_request(), 123))

    assert body.index("Security Standards Summary") < body.index("Report Summary")
    assert "Mapped findings" in body
    assert "9 / 25" in body
    assert "Summary covers all 25 deduplicated findings" in body
    assert "timeline currently contains 12 selected findings" in body
    assert "OWASP-related Observed Categories" in body
    assert "A05:2025" in body
    assert "Injection" in body
    assert "Direct 6" in body
    assert "CWE Mapping Breakdown" in body
    assert "CWE-89" in body
    assert "Related WSTG Test Scenarios" in body
    assert "WSTG-INPV-05" in body
    assert "Other Standards Mappings" in body
    assert "V5.3.1" in body
    assert "Evidence Scope" in body
    assert "Attempt observed" in body
    assert "Relationship meanings" in body
    assert "do not confirm vulnerabilities, weaknesses, compliance, or successful exploitation" in body
    assert "does not mean the finding or target is safe" in body


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
    assert "Category counts should not be summed as a total incident count" in body
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
    assert "No standards mappings were assigned by this enrichment layer" in body
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
    assert "Selected Event Detail" in body


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
    assert "Artifact Summary" in body
    assert "Stage1 LLM Usage" in body
    assert "Stage2 LLM Usage" in body
    assert "13,463" in body
    assert "15,674" in body
    assert "17,846" in body
    assert "32,265" in body
    assert "14,419" in body
    assert ">6<" in body
    assert "gpt-5.4-mini" in body
    assert "Candidate-excluded rows" in body
    assert "low_signal_request" in body
    assert "Candidate-excluded rows are not safety verdicts." in body
    assert "Apache logs alone do not prove exploit success." in body
    assert "Status, size, route, or user-agent alone are not proof." in body
    assert "Guardrails (3)" in body
    assert "candidate_excluded_does_not_mean_benign" not in body
    assert "apache_logs_only_no_success_inference" not in body
    assert "status_code_response_size_route_or_user_agent_do_not_prove_success_or_benign" not in body
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
    assert "Dry-run: no provider call." in body
    assert "Filtered reasons artifact not found" in body


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
    assert "No explicit related contexts in this viewer payload." in body
    assert "No explicit related supporting events in this viewer payload." in body


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
    assert "Observed attack patterns and standards mappings do not confirm" in body
    assert "A05:2025" in body
    assert "Injection" in body
    assert "CWE-89" in body
    assert "SQL Injection" in body
    assert "WSTG-INPV-05" in body
    assert "Testing for SQL Injection" in body
    assert "Direct" in body
    assert "standards_mapping" in body
