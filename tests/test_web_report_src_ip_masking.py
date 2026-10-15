from __future__ import annotations

import copy
import html
import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request

import web.app as web_app
import web.routes.reports as report_routes
from web.services.report_loader import Report


SOURCE_IP = "192.168.56.121"
MASKED_IP = "192.168.56.***"
REFERENCE_IP = "192.168.56.119"
TECHNICAL_TEXT = "/download.php?file=normal/%2527&ref=192.168.56.119 V1.2.3.4"


def make_payload():
    sentence = f"출발지 {SOURCE_IP}에서 요청 · 참고 서버 {REFERENCE_IP} · {TECHNICAL_TEXT}"
    return {
        "schema_version": "viewer_payload.v1",
        "meta": {"generated_at": "2026-10-14T15:55:01+09:00"},
        "summary": {
            "report_title": sentence,
            "overall_assessment": sentence,
            "executive_summary": [sentence],
            "finding_count": 1,
        },
        "report": {
            "report_title": sentence,
            "overall_assessment": sentence,
            "executive_summary": [sentence],
            "presentation_takeaway": sentence,
            "key_findings": [{"title": sentence, "detail": sentence, "severity": "medium"}],
            "notable_incidents": [{"src_ip": SOURCE_IP, "why_it_matters": sentence}],
            "notable_source_ips": [{"src_ip": SOURCE_IP, "reason": sentence}],
            "noise_interpretation": sentence,
            "recommended_actions": [{"priority": "P1", "action": sentence, "why": sentence}],
            "confidence_and_limitations": [sentence],
        },
        "findings": [{
            "request_id": "r-1", "src_ip": SOURCE_IP, "method": "GET", "uri": "/search",
            "status_code": 404, "verdict": "suspicious_sqli", "severity": "medium",
            "confidence": "high", "reasoning_summary": sentence, "evidence_fields": [sentence],
            "raw_request_target": "/search?q=%2527", "raw_request": "GET /search?q=%2527 HTTP/1.1",
            "query_string": "?q=%2527",
        }],
        "contexts": [{"src_ip": SOURCE_IP, "context_type": "probing_sequence", "description": sentence}],
        "supporting_events": [{"src_ip": SOURCE_IP, "description": sentence}],
    }


def request(path, masked):
    return Request({"type": "http", "method": "GET", "path": path,
                    "query_string": b"mask_src_ip=1" if masked else b"mask_src_ip=0",
                    "headers": [], "app": web_app.app})


@pytest.mark.parametrize("route", ["job", "legacy"])
@pytest.mark.parametrize("report_present", [True, False])
def test_viewer_masks_report_and_restores_original_without_changing_artifact(monkeypatch, tmp_path, route, report_present):
    payload = make_payload()
    if not report_present:
        payload["report"] = {}
    path = tmp_path / "runs/jobs/123/viewer_payload.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)

    if route == "job":
        monkeypatch.setattr(web_app, "job_repository", SimpleNamespace(
            get_latest_report_for_job=lambda _: {"artifact_root": "runs/jobs/123",
                "viewer_payload_path": "runs/jobs/123/viewer_payload.json"}))
        render = lambda masked: web_app.job_viewer_payload(request("/job/123/viewer", masked), 123)
    else:
        report = Report(report_id="fixture", file_path=tmp_path / "stage2_report.json",
            filename="stage2_report.json", repo_relative_path="stage2_report.json",
            provider="openai", model="fixture", scenario="fixture", scenario_key="fixture",
            timeframe="fixture", timeframe_key="fixture", timeframe_label="fixture", timeframe_id="fixture",
            generated_at="2026-10-14T15:55:01+09:00", incident_count=1,
            severity_counts={"medium": 1}, verdict_counts={"suspicious_sqli": 1},
            report=payload["report"], viewer_payload_available=True,
            viewer_payload_summary=payload["summary"])
        monkeypatch.setattr(report_routes, "loader", SimpleNamespace(
            scan_reports=lambda: [report],
            load_viewer_payload=lambda _: (json.loads(path.read_text(encoding="utf-8")), None)))
        monkeypatch.setattr(report_routes, "lint_for_report", lambda _: None)
        render = lambda masked: report_routes.report_payload_detail(request("/report/fixture/payload", masked), "fixture")

    raw_response = render(False)
    raw_before = raw_response.body
    masked_response = render(True)
    body = masked_response.body.decode("utf-8")
    assert SOURCE_IP not in body
    assert MASKED_IP in body
    assert REFERENCE_IP in body
    assert TECHNICAL_TEXT in html.unescape(body)
    displayed = masked_response.context["payload"]
    if report_present:
        expected_report = copy.deepcopy(payload["report"])
        for key in ("report_title", "overall_assessment", "presentation_takeaway", "noise_interpretation"):
            assert displayed["report"][key] == expected_report[key].replace(SOURCE_IP, MASKED_IP)
        assert displayed["report"]["executive_summary"][0] == expected_report["executive_summary"][0].replace(SOURCE_IP, MASKED_IP)
        assert displayed["report"]["key_findings"][0]["detail"] == expected_report["key_findings"][0]["detail"].replace(SOURCE_IP, MASKED_IP)
        assert displayed["report"]["recommended_actions"][0]["why"] == expected_report["recommended_actions"][0]["why"].replace(SOURCE_IP, MASKED_IP)
        assert displayed["report"]["confidence_and_limitations"][0] == expected_report["confidence_and_limitations"][0].replace(SOURCE_IP, MASKED_IP)
    else:
        for key in ("report_title", "overall_assessment"):
            assert masked_response.context["payload_summary"][key] == payload["summary"][key].replace(SOURCE_IP, MASKED_IP)
            assert raw_response.context["payload_summary"][key] == payload["summary"][key]
    assert render(False).body == raw_before
    assert path.read_bytes() == original
    assert json.loads(original) == payload


@pytest.mark.parametrize(("text", "expected"), [
    (f"{SOURCE_IP}에서 요청", f"{MASKED_IP}에서 요청"),
    (f"({SOURCE_IP}).", f"({MASKED_IP})."),
    (f"IP:{SOURCE_IP}:8080", f"IP:{MASKED_IP}:8080"),
    (f"http://{SOURCE_IP}/search?q=%2527", f"http://{MASKED_IP}/search?q=%2527"),
    (f"{SOURCE_IP} / {REFERENCE_IP}", f"{MASKED_IP} / {REFERENCE_IP}"),
    ("1192.168.56.121", "1192.168.56.121"),
    ("192.168.56.1210", "192.168.56.1210"),
    ("192.168.56.121.9", "192.168.56.121.9"),
    ("v192.168.56.121", "v192.168.56.121"),
    ("192.168.56.121abc", "192.168.56.121abc"),
    ("file_192.168.56.121.log", "file_192.168.56.121.log"),
    ("192.168.56.12", "192.168.56.12"),
])
def test_display_mask_matches_exact_source_ip_tokens(text, expected):
    payload = {"findings": [{"src_ip": SOURCE_IP}], "report": {"overall_assessment": text}}
    displayed, _ = report_routes._apply_payload_src_ip_display_mode(payload, {}, True)
    assert displayed["report"]["overall_assessment"] == expected
    assert payload["report"]["overall_assessment"] == text


@pytest.mark.parametrize("container", ["findings", "contexts", "supporting_events",
    "payload_preview", "summary_preview", "notable_incidents", "notable_source_ips"])
def test_display_mask_uses_structured_source_fields(container):
    payload = {"report": {"overall_assessment": SOURCE_IP}}
    summary = {}
    if container == "payload_preview":
        payload["summary"] = {"findings_preview": [{"src_ip": SOURCE_IP}]}
    elif container == "summary_preview":
        summary["contexts_preview"] = [{"src_ip": SOURCE_IP}]
    elif container.startswith("notable_"):
        payload["report"][container] = [{"source_ip": SOURCE_IP}]
    else:
        payload[container] = [{"src_ip": SOURCE_IP}]
    displayed, _ = report_routes._apply_payload_src_ip_display_mode(payload, summary, True)
    assert displayed["report"]["overall_assessment"] == MASKED_IP


def test_display_mask_preserves_types_and_ignores_reference_only_addresses():
    payload = make_payload()
    payload["meta"]["known_asset_ips"] = [REFERENCE_IP]
    payload["meta"]["typed_values"] = [False, 1, None]
    payload["report"]["overall_assessment"] += " <script>설명</script>"
    before = copy.deepcopy(payload)
    summary = {"overall_assessment": f"{SOURCE_IP}에서 요청", "count": 1}
    displayed, display_summary = report_routes._apply_payload_src_ip_display_mode(payload, summary, True)
    assert displayed["meta"]["known_asset_ips"] == [REFERENCE_IP]
    assert displayed["meta"]["typed_values"] == [False, 1, None]
    assert display_summary == {"overall_assessment": f"{MASKED_IP}에서 요청", "count": 1}
    assert payload == before
    assert summary["overall_assessment"] == f"{SOURCE_IP}에서 요청"
    restored, restored_summary = report_routes._apply_payload_src_ip_display_mode(payload, summary, False)
    assert restored == before
    assert restored_summary == summary


def test_display_mask_does_not_guess_source_ips_from_report_prose():
    payload = {"report": {"overall_assessment": f"참고 서버 {REFERENCE_IP}"},
               "meta": {"known_asset_ips": [REFERENCE_IP]}}
    displayed, summary = report_routes._apply_payload_src_ip_display_mode(payload, {}, True)
    assert displayed == payload
    assert summary == {}
