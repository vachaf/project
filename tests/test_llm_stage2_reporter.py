from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from llm_client import LLMResponse
import llm_stage2_reporter as stage2


def sample_standards_mapping() -> dict:
    return {
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
            },
            {
                "rule_id": "STD-MAP-SQLI-002",
                "standard": "CWE",
                "id": "CWE-89",
                "name": "SQL Injection",
                "relationship": "direct",
                "basis": ["stage1_verdict:suspicious_sqli"],
                "boundary_note": "Apache logs do not confirm DB query execution.",
            },
        ],
        "unmapped_reason": "",
    }


def empty_standards_mapping() -> dict:
    return {
        "schema_version": "security_standards_mapping.v1",
        "source": "deterministic_stage1_enrichment",
        "observability": "not_applicable",
        "items": [],
        "unmapped_reason": "non_security_verdict",
    }


def xss_standards_mapping() -> dict:
    return {
        "schema_version": "security_standards_mapping.v1",
        "source": "deterministic_stage1_enrichment",
        "observability": "attempt_only",
        "items": [
            {
                "rule_id": "STD-MAP-XSS-001",
                "standard": "OWASP_TOP10",
                "id": "A05:2025",
                "name": "Injection",
                "relationship": "direct",
                "basis": ["stage1_verdict:suspicious_xss"],
                "boundary_note": "Apache logs do not confirm browser execution.",
            },
            {
                "rule_id": "STD-MAP-XSS-002",
                "standard": "CWE",
                "id": "CWE-79",
                "name": "Cross-site Scripting",
                "relationship": "direct",
                "basis": ["stage1_verdict:suspicious_xss"],
                "boundary_note": "Apache logs do not confirm browser execution.",
            },
        ],
        "unmapped_reason": "",
    }


def write_stage1_results(tmp_path: Path) -> Path:
    payload = {
        "meta": {
            "generated_at": "2026-06-06T00:00:00+00:00",
            "mode": "routine",
            "provider": "openai",
            "selected_model": "gpt-test",
            "success_count": 1,
            "error_count": 0,
        },
        "results": [
            {
                "candidate_index": 0,
                "request_id": "req-1",
                "incident_group_key": "rid:req-1",
                "source_table": "security",
                "merged_source_tables": ["security"],
                "merged_row_count": 1,
                "merged_log_ids": [1],
                "log_id": 1,
                "src_ip": "203.0.113.10",
                "method": "GET",
                "uri": "/search",
                "query_string": "q=' OR 1=1--",
                "log_time": "2026-06-06T00:01:00+09:00",
                "status_code": 403,
                "score": 10,
                "verdict_hint": "sqli",
                "reason_hints": ["sqli:or_true(+4)"],
                "response_body_bytes": 0,
                "duration_us": 0,
                "ttfb_us": 0,
                "resp_content_type": "",
                "raw_request_target": "",
                "raw_request": "",
                "raw_log_excerpt": "",
                "user_agent": "",
                "handler": "",
                "log_schema": "",
                "path_normalized_from_raw_request": False,
                "likely_html_fallback_response": False,
                "hpp_detected": False,
                "hpp_param_names": [],
                "embedded_attack_hint": "",
                "verdict": "suspicious_sqli",
                "severity": "medium",
                "confidence": "medium",
                "false_positive_possible": True,
                "reasoning_summary": "SQLi 형태의 query string이 관찰되었다.",
                "evidence_fields": ["query_string"],
                "recommended_actions": ["review_raw_log"],
                "response_id": "resp_stage1",
                "raw_output_text": "{}",
            }
        ],
    }
    path = tmp_path / "sample_stage1_results.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def stage2_output_text() -> str:
    return json.dumps(
        {
            "report_title": "테스트 보고서",
            "overall_assessment": "관찰된 요청은 추가 확인이 필요한 시도 정황이다.",
            "executive_summary": ["요약 1", "요약 2", "요약 3"],
            "key_findings": [
                {"title": "포인트 1", "detail": "상세 1", "severity": "low"},
                {"title": "포인트 2", "detail": "상세 2", "severity": "medium"},
                {"title": "포인트 3", "detail": "상세 3", "severity": "low"},
            ],
            "notable_incidents": [
                {
                    "incident_ref": "inc-1",
                    "request_id": "req-1",
                    "src_ip": "203.0.113.10",
                    "verdict": "suspicious_sqli",
                    "severity": "medium",
                    "why_it_matters": "SQLi 형태의 요청이 관찰되었다.",
                }
            ],
            "notable_source_ips": [{"src_ip": "203.0.113.10", "reason": "후속 확인 대상"}],
            "noise_interpretation": "후보 밖 요청은 별도 확인이 필요하다.",
            "recommended_actions": [
                {"priority": "P1", "action": "원본 로그 확인", "why": "근거 확인"},
                {"priority": "P2", "action": "동일 IP 확인", "why": "반복 여부 확인"},
                {"priority": "P3", "action": "모니터링", "why": "재발 확인"},
            ],
            "confidence_and_limitations": ["Apache 로그만 사용했다.", "성공 여부는 단정하지 않는다."],
            "presentation_takeaway": "성공 단정 없이 시도 정황 중심으로 설명한다.",
        },
        ensure_ascii=False,
    )


def stage2_output_text_with_filtered_wording() -> str:
    return json.dumps(
        {
            "report_title": "테스트 보고서",
            "overall_assessment": "후보 밖 요청은 benign_normal_search로 보이며 일부 정상 탐색 문맥이다.",
            "executive_summary": [
                "benign_normal_search 표현이 포함된 요약",
                "정상 검색이라는 표현이 포함된 요약",
                "normal baseline이라는 표현이 포함된 요약",
            ],
            "key_findings": [
                {"title": "benign finding", "detail": "후보 밖 row를 무해로 단정했다.", "severity": "low"},
                {"title": "포인트 2", "detail": "normalization 같은 기술 단어는 유지되어야 한다.", "severity": "low"},
                {"title": "포인트 3", "detail": "normal_search_baseline category 언급", "severity": "low"},
            ],
            "notable_incidents": [
                {
                    "incident_ref": "inc-1",
                    "request_id": "req-1",
                    "src_ip": "203.0.113.10",
                    "verdict": "suspicious_sqli",
                    "severity": "medium",
                    "why_it_matters": "SQLi 형태의 요청이 관찰되었다.",
                }
            ],
            "notable_source_ips": [{"src_ip": "203.0.113.10", "reason": "후속 확인 대상"}],
            "noise_interpretation": "filtered_out_breakdown에 benign_normal_search가 있고 정상 비교군이다.",
            "recommended_actions": [
                {"priority": "P1", "action": "원본 로그 확인", "why": "근거 확인"},
                {"priority": "P2", "action": "동일 IP 확인", "why": "반복 여부 확인"},
                {"priority": "P3", "action": "모니터링", "why": "재발 확인"},
            ],
            "confidence_and_limitations": ["Apache 로그만 사용했다.", "성공 여부는 단정하지 않는다."],
            "presentation_takeaway": "후보 제외 row를 benign으로 단정하지 않는다.",
        },
        ensure_ascii=False,
    )


def run_stage2_main(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["llm_stage2_reporter.py", *argv])
    return stage2.main()


def test_stage2_normal_report_meta_includes_usage_calls_and_totals(tmp_path: Path, monkeypatch) -> None:
    stage1_path = write_stage1_results(tmp_path)
    stage1_payload = json.loads(stage1_path.read_text(encoding="utf-8"))
    input_scope = {"kind": "live_selected_logs", "window_role": "selected_log_timestamp_envelope",
                   "window": None, "selected_id_count": 1}
    stage1_payload["meta"]["source_input_scope"] = input_scope
    stage1_path.write_text(json.dumps(stage1_payload), encoding="utf-8")
    out_dir = tmp_path / "out"

    def fake_call_llm_json(**kwargs):
        return LLMResponse(
            output_text=stage2_output_text(),
            response_id="resp_stage2",
            raw_response={
                "id": "resp_stage2",
                "usage": {
                    "input_tokens": 200,
                    "input_tokens_details": {"cached_tokens": 8},
                    "output_tokens": 80,
                    "output_tokens_details": {"reasoning_tokens": 9},
                    "total_tokens": 280,
                },
            },
            provider="openai",
            model=kwargs["model"],
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(stage2, "call_llm_json", fake_call_llm_json)

    assert run_stage2_main(
        monkeypatch,
        [
            "--stage1-results",
            str(stage1_path),
            "--out-dir",
            str(out_dir),
            "--base-name",
            "sample",
            "--provider",
            "openai",
        ],
    ) == 0

    payload = json.loads((out_dir / "sample_stage2_report.json").read_text(encoding="utf-8"))
    assert payload["meta"]["input_scope"] == input_scope
    usage = payload["meta"]["llm_usage"]
    assert usage["schema_version"] == "llm_usage_stage.v1"
    assert usage["available"] is True
    assert usage["stage"] == "stage2"
    assert len(usage["calls"]) == 1
    assert usage["calls"][0]["call_role"] == "initial"
    assert usage["calls"][0]["input_tokens"] == 200
    assert usage["calls"][0]["breakdown"]["reasoning_tokens"] == 9
    assert usage["totals"]["call_count"] == 1
    assert usage["totals"]["total_tokens"] == 280
    assert "raw_response" not in json.dumps(payload)


def test_stage2_prompt_includes_candidate_excluded_wording_guardrail() -> None:
    messages = stage2.build_messages({"policy_notes": {}, "top_incidents": []})
    prompt_text = "\n".join(message["content"] for message in messages)

    assert "Do not call filtered-out or candidate-excluded rows benign or normal." in prompt_text
    assert "Candidate-excluded means not selected for candidate analysis, not safe." in prompt_text
    assert "known_baseline_like_legacy_alias" in prompt_text


def test_stage2_prompt_includes_standards_mapping_interpretation_boundary() -> None:
    messages = stage2.build_messages({"policy_notes": {}, "top_incidents": []})
    prompt_text = "\n".join(message["content"] for message in messages)

    assert "Standards mapping interpretation boundary" in prompt_text
    assert "standards_mapping is deterministic taxonomy/test-scenario enrichment" in prompt_text
    assert "not a new detection result" in prompt_text
    assert "relationship=direct" in prompt_text
    assert "not confirmed weakness, confirmed vulnerability, or successful exploitation" in prompt_text
    assert "relationship=conditional" in prompt_text
    assert "additional evidence is required" in prompt_text
    assert "relationship=related" in prompt_text
    assert "contextual category/test scenario relevance" in prompt_text
    assert "OWASP Top 10 is a high-level security risk/category mapping" in prompt_text
    assert "CWE is a software weakness taxonomy" in prompt_text
    assert "CWE-89 direct is SQL injection-like pattern correspondence" in prompt_text
    assert "WSTG is a security test scenario" in prompt_text
    assert "do not phrase WSTG IDs as vulnerability IDs" in prompt_text
    assert "Do not use standards_mapping to change Stage1 verdict, severity, confidence" in prompt_text
    assert "create incidents" in prompt_text
    assert "DB execution/results" in prompt_text
    assert "XSS execution" in prompt_text
    assert "command execution" in prompt_text
    assert "auth bypass" in prompt_text
    assert "account takeover" in prompt_text
    assert "Respect each standards_mapping.items[].boundary_note" in prompt_text
    assert "use the more conservative interpretation" in prompt_text
    assert "unmapped_reason=non_security_verdict" in prompt_text
    assert "do not use it as proof of safe, secure, benign, or no vulnerability" in prompt_text


def test_stage2_report_input_aliases_legacy_filtered_categories() -> None:
    report_input = stage2.build_report_input(
        stage1_payload={
            "meta": {"success_count": 0, "error_count": 0},
            "results": [],
        },
        llm_input_payload={
            "meta": {
                "counts": {"filtered_out_rows": 6},
                "filtered_out_breakdown": {
                    "benign_normal_search": 4,
                    "normal_search_baseline": 2,
                },
            }
        },
        stage1_errors_payload=None,
        top_incidents=3,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )

    assert report_input["distributions"]["filtered_out_breakdown"] == {
        "known_baseline_like_legacy_alias": 6
    }
    assert report_input["top_filtered_categories"] == [
        {"category": "known_baseline_like_legacy_alias", "count": 6, "share_pct": 100.0}
    ]
    assert "benign_normal_search" not in json.dumps(report_input)


def test_security_standards_summary_uses_all_deduped_incidents_not_top_n() -> None:
    base_finding = {
        "source_table": "security",
        "src_ip": "203.0.113.10",
        "method": "GET",
        "uri": "/search",
        "status_code": 403,
        "score": 10,
        "verdict": "suspicious_sqli",
        "severity": "medium",
        "confidence": "medium",
        "recommended_actions": ["review_raw_log"],
    }
    stage1_payload = {
        "meta": {"success_count": 3, "error_count": 0},
        "results": [
            {
                **base_finding,
                "candidate_index": 0,
                "request_id": "req-sqli",
                "log_id": 1,
                "log_time": "2026-06-06T00:01:00+09:00",
                "standards_mapping": sample_standards_mapping(),
            },
            {
                **base_finding,
                "candidate_index": 1,
                "request_id": "req-xss",
                "log_id": 2,
                "log_time": "2026-06-06T00:02:00+09:00",
                "verdict": "suspicious_xss",
                "standards_mapping": xss_standards_mapping(),
            },
            {
                **base_finding,
                "candidate_index": 2,
                "request_id": "req-unmapped",
                "log_id": 3,
                "log_time": "2026-06-06T00:03:00+09:00",
                "verdict": "likely_false_positive",
                "severity": "info",
                "standards_mapping": empty_standards_mapping(),
            },
        ],
    }

    report_input = stage2.build_report_input(
        stage1_payload=stage1_payload,
        llm_input_payload={"meta": {"counts": {"candidate_rows": 3}}},
        stage1_errors_payload=None,
        top_incidents=1,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )

    summary = report_input["security_standards_summary"]
    assert len(report_input["top_incidents"]) == 1
    assert report_input["pipeline_counts"]["distinct_incident_count"] == 3
    assert summary["total_finding_count"] == 3
    assert summary["mapped_finding_count"] == 2
    assert summary["unmapped_finding_count"] == 1
    assert summary["observability_counts"] == {
        "attempt_only": 2,
        "behavior_only": 0,
        "partial": 0,
        "not_applicable": 1,
    }
    assert summary["standards"]["OWASP_TOP10"][0]["id"] == "A05:2025"
    assert summary["standards"]["OWASP_TOP10"][0]["finding_count"] == 2
    assert {row["id"]: row["finding_count"] for row in summary["standards"]["CWE"]} == {
        "CWE-79": 1,
        "CWE-89": 1,
    }
    assert (
        report_input["pipeline_counts"]["distinct_incident_count"]
        == summary["total_finding_count"]
    )


def test_stage2_llm_projection_excludes_aggregate_but_preserves_finding_mapping() -> None:
    original_mapping = sample_standards_mapping()
    report_input = stage2.build_report_input(
        stage1_payload={
            "meta": {"success_count": 1, "error_count": 0},
            "results": [
                {
                    "candidate_index": 0,
                    "request_id": "req-projection",
                    "source_table": "security",
                    "log_id": 1,
                    "src_ip": "203.0.113.10",
                    "method": "GET",
                    "uri": "/search",
                    "log_time": "2026-06-06T00:01:00+09:00",
                    "status_code": 403,
                    "score": 10,
                    "verdict": "suspicious_sqli",
                    "severity": "medium",
                    "confidence": "medium",
                    "standards_mapping": original_mapping,
                }
            ],
        },
        llm_input_payload={"meta": {"counts": {"candidate_rows": 1}}},
        stage1_errors_payload=None,
        top_incidents=1,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )
    original_report_input = json.loads(json.dumps(report_input))

    messages = stage2.build_messages(report_input)
    llm_payload = json.loads(messages[1]["content"])

    assert "security_standards_summary" in report_input
    assert "security_standards_summary" not in llm_payload["report_input"]
    assert llm_payload["report_input"]["top_incidents"][0]["standards_mapping"] == original_mapping
    assert report_input == original_report_input


def test_stage2_wording_sanitizer_replaces_forbidden_report_text_and_keeps_normalization() -> None:
    sanitized, warnings = stage2.sanitize_report_text(
        "benign_normal_search 정상 무해 normal baseline, but path normalization stays."
    )

    assert sanitized == "benign_normal_search 정상 무해 normal baseline, but path normalization stays."
    assert len(warnings) == 1
    detail = json.loads(warnings[0].split(":", 1)[1])
    assert detail["source_text"] == sanitized
    assert detail["reason"] == "mixed_or_unsupported_safety_judgment"


def test_postprocessing_preserves_technical_strings_and_separators() -> None:
    text = (
        "URL https://example.com/a.php?file=php://filter/convert.base64-encode/resource=index.php&x=1. "
        "IP 192.168.56.1 및 2001:db8::1.\n"
        "wrapper php://filter/convert.base64-encode/resource=config.php 관찰."
    )
    report, warnings = stage2.postprocess_report_json({"overall_assessment": text}, {})
    assert report["overall_assessment"] == text
    assert warnings == []

    report, warnings = stage2.postprocess_report_json(
        {"overall_assessment": text + "\n403으로 차단되었습니다."}, {}
    )
    assert report["overall_assessment"].startswith(text + "\nHTTP 403")
    assert warnings == [stage2.HTTP_STATUS_OUTCOME_WARNING]


def test_sanitizer_handles_korean_inflections_without_broken_wording() -> None:
    cases = {
        "입력값을 무해화하세요.": "입력값을 안전하게 처리하세요.",
        "입력값의 무해화를 권고합니다.": "입력값의 안전한 처리를 권고합니다.",
        "무해화 조치를 검토하세요.": "안전한 처리 조치를 검토하세요.",
        "이 요청은 무해합니다.": "이 요청은 안전하다고 확정할 수 없습니다.",
        "무해한 요청입니다.": "안전 여부가 확인되지 않은 요청입니다.",
    }
    for text, expected in cases.items():
        report, warnings = stage2.postprocess_report_json(
            {"recommended_actions": [{"action": text}]}, {}
        )
        assert report["recommended_actions"][0]["action"] == expected
        assert warnings == ["forbidden_phrase:무해"]


def test_http_status_semantic_validator_replaces_unsupported_outcome_assertions() -> None:
    unsafe_cases = {
        "403으로 차단되었습니다.": "HTTP 403 응답이 관찰되어 접근 제한 가능성이 있습니다.",
        "이 요청은 애플리케이션에 의해 차단된 것으로 추정됩니다.": "HTTP 응답 metadata만으로 실제 차단 여부나 접근 제어 동작은 Apache 로그만으로 판단할 수 없습니다.",
        "경로 탐색 시도가 차단된 정황입니다.": "접근 제한 가능성은 있으나, 실제 차단 여부나 공격 성공·실패는 Apache 로그만으로 판단할 수 없습니다.",
        "요청이 차단된 것으로 보입니다.": "접근 제한 가능성은 있으나, 실제 차단 여부나 공격 성공·실패는 Apache 로그만으로 판단할 수 없습니다.",
        "차단이 정상 동작했습니다.": "HTTP 응답 metadata만으로 실제 차단 여부나 접근 제어 동작은 Apache 로그만으로 판단할 수 없습니다.",
        "차단은 동작한 것으로 보입니다.": "HTTP 응답 metadata만으로 실제 차단 여부나 접근 제어 동작은 Apache 로그만으로 판단할 수 없습니다.",
        "접근 제어가 정상 동작했습니다.": "HTTP 응답 metadata만으로 실제 차단 여부나 접근 제어 동작은 Apache 로그만으로 판단할 수 없습니다.",
        "공격은 실패했습니다.": "공격 성공·실패 여부는 Apache 로그만으로 판단할 수 없습니다.",
        "파일 접근에 실패했습니다.": "실제 파일 접근 성공·실패 여부는 Apache 로그만으로 판단할 수 없습니다.",
    }
    for unsafe, expected_correction in unsafe_cases.items():
        report, warnings = stage2.postprocess_report_json({"overall_assessment": unsafe}, {})
        assert expected_correction in report["overall_assessment"]
        assert unsafe not in report["overall_assessment"]
        # The context identifies the affected system/request and remains evidence.
        for context in ("애플리케이션에 의해", "경로 탐색 시도가", "요청이"):
            if context in unsafe:
                assert context in report["overall_assessment"]
        assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings


def test_http_status_semantic_validator_preserves_safe_actions_and_negations() -> None:
    safe_cases = [
        "403 응답이 관찰되었습니다.",
        "403 응답이 관찰되어 접근 제한 가능성이 있습니다.",
        "공격 성공·실패 여부는 Apache 로그만으로 판단할 수 없습니다.",
        "파일 접근 성공 여부는 확인되지 않았습니다.",
        "차단 여부는 확인되지 않았습니다.",
        "403만으로 차단되었다고 단정할 수 없습니다.",
        "공격이 실패했다고 볼 수 없습니다.",
        "파일 접근 실패 여부는 확인되지 않았습니다.",
    ]
    for safe in safe_cases:
        report, warnings = stage2.postprocess_report_json({"overall_assessment": safe}, {})
        assert report["overall_assessment"] == safe
        assert stage2.HTTP_STATUS_OUTCOME_WARNING not in warnings

    path_text = "`../../../etc/passwd` 요청이 관찰되었습니다. 실제 파일 읽기 성공은 확인되지 않았습니다."
    report, warnings = stage2.postprocess_report_json({"overall_assessment": path_text}, {})
    assert report["overall_assessment"] == path_text
    assert stage2.HTTP_STATUS_OUTCOME_WARNING not in warnings

    actions = ["WAF 차단 정책을 점검하세요.", "차단 여부를 추가 로그에서 확인하세요.", "접근 제어 설정을 검토하세요."]
    report, warnings = stage2.postprocess_report_json(
        {"recommended_actions": [{"action": action, "why": action} for action in actions]}, {}
    )
    assert [item["action"] for item in report["recommended_actions"]] == actions
    assert [item["why"] for item in report["recommended_actions"]] == actions
    assert stage2.HTTP_STATUS_OUTCOME_WARNING not in warnings


TECHNICAL_IDENTIFIERS = [
    "192.168.56.121",
    "api.example.test",
    "https://api.example.test/search?q=a&next=/a.b#part",
    "/search?q=a",
    "15:20:23.804",
    "2026-10-23T15:20:23.804+09:00",
    "2026-10-23T06:20:23.804Z",
    "./logs/access.log",
    "../../../etc/passwd",
    "req.ab?cd!ef-123",
    "/search?q=%252e%252e%252f&value=a%20b%3Fc",
]


@pytest.mark.parametrize("text", [
    "관찰된 요청은 추가 확인이 필요합니다.",
    "  요청을 관찰했습니다.  추가 확인이 필요합니까?\n\n근거를 검토합니다!\t끝.  ",
    *[f"관찰 자료: {identifier} 요청을 확인했습니다." for identifier in TECHNICAL_IDENTIFIERS],
    "관찰 자료: " + " | ".join(TECHNICAL_IDENTIFIERS),
    "DB 실행, 데이터 유출 및 실제 침해 성공 여부는 Apache 로그만으로 판단할 수 없습니다.",
])
def test_stage2_postprocess_preserves_unmodified_text_exactly(text: str) -> None:
    original = {"overall_assessment": text}
    validated, warnings = stage2.validate_http_status_report_semantics(original, {})
    assert validated == original
    assert warnings == []
    processed, warnings = stage2.postprocess_report_json(original, {})
    assert processed == original
    assert warnings == []
    assert stage2.postprocess_report_json(processed, {}) == (processed, [])


@pytest.mark.parametrize("assertion", [
    "403으로 차단되었습니다.",
    "HTTP 401 응답으로 차단되었습니다.",
    "HTTP 404 응답으로 공격은 실패했습니다.",
    "HTTP 404 응답으로 파일 접근에 실패했습니다.",
    "WAF에 의해 차단된 것으로 추정됩니다.",
    # Identifiers can occur inside the context matched by the block rule.
    "403 /search?q=a 차단되었습니다.",
    "403 /search?q=a 차단되었습니다, 공격은 실패했습니다.",
    "403 https://api.example.test/" + "long-path/" * 20 + " 차단되었습니다.",
])
def test_stage2_correction_preserves_surrounding_evidence(assertion: str) -> None:
    evidence = " | ".join(TECHNICAL_IDENTIFIERS)
    prefix = f"자료 {evidence} 요청에서 "
    suffix = "\n\n추가 근거를 확인합니다.  원본을 검토합니다!"
    report, warnings = stage2.postprocess_report_json(
        {"overall_assessment": prefix + assertion + suffix}, {}
    )
    text = report["overall_assessment"]
    assert text.startswith(prefix)
    assert text.endswith(suffix)
    for identifier in TECHNICAL_IDENTIFIERS:
        assert identifier in text
    if "/search?q=a" in assertion:
        assert text.count("/search?q=a") == (prefix + assertion + suffix).count("/search?q=a")
    assert "Apache 로그만으로 판단할 수 없습니다." in text
    for unsupported in ["차단되었습니다", "공격은 실패했습니다", "파일 접근에 실패했습니다", "차단된 것으로 추정됩니다"]:
        assert unsupported not in text
    assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings
    reprocessed, repeated_warnings = stage2.postprocess_report_json(report, {})
    assert reprocessed == report
    assert stage2.HTTP_STATUS_OUTCOME_WARNING not in repeated_warnings


def test_stage2_sentence_boundaries_keep_independent_assertion_correction() -> None:
    safe = "공격이 실패했다고 볼 수 없습니다."
    for separator in ["  ", "\n", "\r\n\r\n", "\t"]:
        original = safe + separator + "HTTP 404 응답에서 공격은 실패했습니다."
        report, warnings = stage2.postprocess_report_json({"detail": original}, {})
        assert report["detail"].startswith(safe + separator)
        assert "공격은 실패했습니다" not in report["detail"]
        assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings


def test_stage2_json_and_markdown_preserve_technical_identifiers() -> None:
    original = json.loads(stage2_output_text())
    evidence = "관찰 자료: " + " | ".join(TECHNICAL_IDENTIFIERS)
    original["overall_assessment"] = evidence
    original["key_findings"][0]["detail"] = evidence + " HTTP 404 응답에서 공격은 실패했습니다."
    report, warnings = stage2.postprocess_report_json(original, {})
    serialized = json.dumps(report, ensure_ascii=False)
    markdown = stage2.render_markdown(report, {}, "fixture-model", "routine")
    assert report["overall_assessment"] == evidence
    for identifier in TECHNICAL_IDENTIFIERS:
        assert identifier in serialized
        assert identifier in markdown
    assert "공격은 실패했습니다" not in serialized
    assert "공격은 실패했습니다" not in markdown
    assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings


@pytest.mark.parametrize("repair", [False, True], ids=["direct_parse", "repair_parse"])
def test_stage2_main_saves_preserved_identifiers_in_json_and_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repair: bool
) -> None:
    report = json.loads(stage2_output_text())
    evidence = "관찰 자료: " + " | ".join(TECHNICAL_IDENTIFIERS)
    report["overall_assessment"] = evidence
    report["key_findings"][0]["detail"] = evidence + " HTTP 404 응답에서 공격은 실패했습니다."
    responses = iter((["invalid json"] if repair else []) + [json.dumps(report, ensure_ascii=False)])
    calls = []

    def fake_call_llm_json(**kwargs):
        calls.append(kwargs)
        return LLMResponse(
            output_text=next(responses), response_id="fixture", raw_response={},
            provider=kwargs["config"].provider, model=kwargs["model"],
        )

    stage1_path = write_stage1_results(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(stage2, "call_llm_json", fake_call_llm_json)
    assert run_stage2_main(monkeypatch, [
        "--stage1-results", str(stage1_path), "--out-dir", str(out_dir),
        "--base-name", "fixture", "--provider", "anthropic" if repair else "openai", "--model", "fixture-model",
    ]) == 0
    assert len(calls) == (2 if repair else 1)
    payload = json.loads((out_dir / "fixture_stage2_report.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "fixture_stage2_report.md").read_text(encoding="utf-8")
    assert payload["report"]["overall_assessment"] == evidence
    for identifier in TECHNICAL_IDENTIFIERS:
        assert identifier in payload["report"]["key_findings"][0]["detail"]
        assert identifier in markdown
    assert "공격은 실패했습니다" not in markdown
    assert stage2.HTTP_STATUS_OUTCOME_WARNING in payload["meta"]["guardrail_warnings"]


def test_http_status_semantic_validator_is_not_limited_to_low_signal_reports() -> None:
    candidate_report_input = {
        "pipeline_counts": {"candidate_rows": 1, "distinct_incident_count": 1, "stage1_success_count": 1},
        "top_incidents": [{"status_code": 403}],
        "ip_behavior_aggregates": [{"request_count": 1}],
    }
    report, warnings = stage2.postprocess_report_json(
        {"overall_assessment": "403으로 차단되었습니다."}, candidate_report_input
    )
    assert report["overall_assessment"].startswith("HTTP 403 응답이 관찰되어 접근 제한 가능성이 있습니다.")
    assert warnings == [stage2.HTTP_STATUS_OUTCOME_WARNING]


def test_stage2_prompt_and_dry_run_keep_http_status_boundary() -> None:
    prompt = stage2.build_messages({})[0]["content"]
    assert "401/403은 접근 거부·인증 필요 또는 접근 제한 가능성을 보여주는 HTTP 응답으로만 설명하라." in prompt
    assert "403/401은 access control이 동작한 정황" not in prompt

    dry_run = stage2.build_dry_run_markdown({}, selected_model="test", mode="routine")
    assert "401/403은 접근 거부·인증 필요 또는 접근 제한 가능성을 보여주는 HTTP 응답으로만 설명" in dry_run


def test_stage2_output_forbidden_wording_gets_replaced_and_warned(tmp_path: Path, monkeypatch) -> None:
    stage1_path = write_stage1_results(tmp_path)
    out_dir = tmp_path / "out"

    def fake_call_llm_json(**kwargs):
        return LLMResponse(
            output_text=stage2_output_text_with_filtered_wording(),
            response_id="resp_stage2",
            raw_response={
                "id": "resp_stage2",
                "usage": {
                    "input_tokens": 200,
                    "output_tokens": 80,
                    "total_tokens": 280,
                },
            },
            provider="openai",
            model=kwargs["model"],
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(stage2, "call_llm_json", fake_call_llm_json)

    assert run_stage2_main(
        monkeypatch,
        [
            "--stage1-results",
            str(stage1_path),
            "--out-dir",
            str(out_dir),
            "--base-name",
            "sample",
            "--provider",
            "openai",
        ],
    ) == 0

    payload = json.loads((out_dir / "sample_stage2_report.json").read_text(encoding="utf-8"))
    report_text = json.dumps(payload["report"], ensure_ascii=False)
    assert payload["report"] == json.loads(stage2_output_text_with_filtered_wording())
    assert "normalization 같은" in report_text
    assert "benign_normal_search" in report_text
    warnings = payload["meta"]["guardrail_warnings"]
    reviews = [json.loads(note.split(":", 1)[1]) for note in warnings if note.startswith("safety_review:")]
    assert any(row["path"] == "report.overall_assessment" for row in reviews)
    assert any(row["source_text"] == payload["report"]["key_findings"][0]["detail"] for row in reviews)
    assert all(row["reason"] for row in reviews)


def test_stage2_anthropic_repair_success_preserves_initial_and_repair_usage(tmp_path: Path, monkeypatch) -> None:
    stage1_path = write_stage1_results(tmp_path)
    out_dir = tmp_path / "out"
    calls = []

    def fake_call_llm_json(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return LLMResponse(
                output_text="not-json",
                response_id="msg_initial",
                raw_response={
                    "id": "msg_initial",
                    "usage": {
                        "input_tokens": 100,
                        "cache_creation_input_tokens": 2,
                        "cache_read_input_tokens": 3,
                        "output_tokens": 40,
                        "service_tier": "standard",
                    },
                },
                provider="anthropic",
                model=kwargs["model"],
            )
        return LLMResponse(
            output_text=stage2_output_text(),
            response_id="msg_repair",
            raw_response={
                "id": "msg_repair",
                "usage": {
                    "input_tokens": 20,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 1,
                    "output_tokens": 10,
                    "service_tier": "standard",
                },
            },
            provider="anthropic",
            model=kwargs["model"],
        )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")
    monkeypatch.setattr(stage2, "call_llm_json", fake_call_llm_json)

    assert run_stage2_main(
        monkeypatch,
        [
            "--stage1-results",
            str(stage1_path),
            "--out-dir",
            str(out_dir),
            "--base-name",
            "sample",
            "--provider",
            "anthropic",
        ],
    ) == 0

    payload = json.loads((out_dir / "sample_stage2_report.json").read_text(encoding="utf-8"))
    usage = payload["meta"]["llm_usage"]
    assert [call["call_role"] for call in usage["calls"]] == ["initial", "repair"]
    assert usage["calls"][0]["response_id"] == "msg_initial"
    assert usage["calls"][0]["total_input_tokens"] == 105
    assert usage["calls"][1]["response_id"] == "msg_repair"
    assert usage["calls"][1]["total_input_tokens"] == 21
    assert usage["totals"]["call_count"] == 2
    assert usage["totals"]["input_tokens"] == 120
    assert usage["totals"]["output_tokens"] == 50
    assert usage["totals"]["total_tokens"] == 176


def test_stage2_dry_run_marks_usage_unavailable(tmp_path: Path, monkeypatch) -> None:
    stage1_path = write_stage1_results(tmp_path)
    out_dir = tmp_path / "out"

    assert run_stage2_main(
        monkeypatch,
        [
            "--stage1-results",
            str(stage1_path),
            "--out-dir",
            str(out_dir),
            "--base-name",
            "sample",
            "--dry-run",
        ],
    ) == 0

    payload = json.loads((out_dir / "sample_stage2_report.json").read_text(encoding="utf-8"))
    assert payload["meta"]["dry_run"] is True
    assert payload["meta"]["llm_usage"] == {
        "schema_version": "llm_usage_stage.v1",
        "available": False,
        "stage": "stage2",
        "estimated": False,
        "calls": [],
        "totals": {
            "call_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated": False,
        },
        "unavailable_reason": "dry_run_no_provider_call",
    }
    report_input = json.loads(
        (out_dir / "sample_stage2_report_input.json").read_text(encoding="utf-8")
    )
    assert report_input["security_standards_summary"]["total_finding_count"] == 1
    assert report_input["security_standards_summary"]["unmapped_finding_count"] == 1


def test_stage2_report_input_preserves_standards_mapping_exactly() -> None:
    original_mapping = sample_standards_mapping()
    stage1_payload = {
        "meta": {"success_count": 1, "error_count": 0},
        "results": [
            {
                "candidate_index": 0,
                "request_id": "req-1",
                "incident_group_key": "rid:req-1",
                "source_table": "security",
                "log_id": 1,
                "src_ip": "203.0.113.10",
                "method": "GET",
                "uri": "/search",
                "query_string": "q=' OR 1=1--",
                "log_time": "2026-06-06T00:01:00+09:00",
                "status_code": 403,
                "score": 10,
                "verdict": "suspicious_sqli",
                "severity": "medium",
                "confidence": "medium",
                "reason_hints": ["sqli:boolean_true_condition"],
                "evidence_fields": ["query_string"],
                "recommended_actions": ["review_raw_log"],
                "standards_mapping": original_mapping,
            }
        ],
    }

    report_input = stage2.build_report_input(
        stage1_payload=stage1_payload,
        llm_input_payload={"meta": {"counts": {"candidate_rows": 1}}},
        stage1_errors_payload=None,
        top_incidents=3,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )

    actual_mapping = report_input["top_incidents"][0]["standards_mapping"]
    assert actual_mapping == original_mapping
    assert actual_mapping["items"][0]["relationship"] == "direct"
    assert actual_mapping["items"][1]["id"] == "CWE-89"
    assert actual_mapping["items"][0]["boundary_note"] == "Apache logs do not confirm DB query execution."
    assert "standards_mapping" in stage2.build_messages(report_input)[1]["content"]


def test_stage2_old_artifact_without_standards_mapping_uses_empty_fallback(tmp_path: Path) -> None:
    stage1_payload = json.loads(write_stage1_results(tmp_path).read_text(encoding="utf-8"))

    report_input = stage2.build_report_input(
        stage1_payload=stage1_payload,
        llm_input_payload={"meta": {"counts": {"candidate_rows": 1}}},
        stage1_errors_payload=None,
        top_incidents=3,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )

    assert report_input["top_incidents"][0]["request_id"] == "req-1"
    assert report_input["top_incidents"][0]["standards_mapping"] == {}


def test_stage2_report_input_preserves_empty_standards_mapping() -> None:
    original_mapping = empty_standards_mapping()
    stage1_payload = {
        "meta": {"success_count": 1, "error_count": 0},
        "results": [
            {
                "candidate_index": 0,
                "request_id": "req-fp",
                "incident_group_key": "rid:req-fp",
                "source_table": "security",
                "log_id": 3,
                "src_ip": "203.0.113.12",
                "method": "GET",
                "uri": "/search",
                "query_string": "q=select training material",
                "log_time": "2026-06-06T00:02:00+09:00",
                "status_code": 200,
                "score": 2,
                "verdict": "likely_false_positive",
                "severity": "info",
                "confidence": "medium",
                "reason_hints": ["fp_hint:sql_keyword_without_attack_structure"],
                "evidence_fields": ["query_string"],
                "recommended_actions": ["watch"],
                "standards_mapping": original_mapping,
            }
        ],
    }

    report_input = stage2.build_report_input(
        stage1_payload=stage1_payload,
        llm_input_payload={"meta": {"counts": {"candidate_rows": 1}}},
        stage1_errors_payload=None,
        top_incidents=3,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )

    assert report_input["top_incidents"][0]["standards_mapping"] == original_mapping
    assert report_input["top_incidents"][0]["standards_mapping"]["items"] == []


def test_stage2_uses_representative_row_standards_mapping_without_union() -> None:
    lower_priority_mapping = empty_standards_mapping()
    representative_mapping = sample_standards_mapping()
    stage1_payload = {
        "meta": {"success_count": 2, "error_count": 0},
        "results": [
            {
                "candidate_index": 0,
                "request_id": "req-dup",
                "source_table": "access",
                "log_id": 1,
                "src_ip": "203.0.113.10",
                "method": "GET",
                "uri": "/search",
                "query_string": "q=test",
                "log_time": "2026-06-06T00:01:00+09:00",
                "status_code": 200,
                "score": 2,
                "verdict": "likely_false_positive",
                "severity": "info",
                "confidence": "medium",
                "recommended_actions": ["watch"],
                "standards_mapping": lower_priority_mapping,
            },
            {
                "candidate_index": 1,
                "request_id": "req-dup",
                "source_table": "security",
                "log_id": 2,
                "src_ip": "203.0.113.10",
                "method": "GET",
                "uri": "/search",
                "query_string": "q=' OR 1=1--",
                "log_time": "2026-06-06T00:01:00+09:00",
                "status_code": 403,
                "score": 10,
                "verdict": "suspicious_sqli",
                "severity": "medium",
                "confidence": "medium",
                "recommended_actions": ["review_raw_log"],
                "standards_mapping": representative_mapping,
            },
        ],
    }

    briefs = stage2.build_incident_briefs(
        stage1_payload["results"],
        top_n=3,
        known_asset_ips=[],
    )

    assert len(briefs) == 1
    assert briefs[0].duplicate_count == 2
    assert briefs[0].source_table == "security"
    assert briefs[0].standards_mapping == representative_mapping
    assert briefs[0].standards_mapping != lower_priority_mapping

    report_input = stage2.build_report_input(
        stage1_payload=stage1_payload,
        llm_input_payload={"meta": {"counts": {"candidate_rows": 2}}},
        stage1_errors_payload=None,
        top_incidents=3,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )
    summary = report_input["security_standards_summary"]
    assert report_input["pipeline_counts"]["distinct_incident_count"] == 1
    assert summary["total_finding_count"] == 1
    assert summary["mapped_finding_count"] == 1
    assert summary["unmapped_finding_count"] == 0
    assert summary["standards"]["OWASP_TOP10"][0]["id"] == "A05:2025"
    assert summary["standards"]["OWASP_TOP10"][0]["finding_count"] == 1


def test_safety_negations_preserve_original_wording_without_warnings() -> None:
    for text in (
        "무해함을 의미하지는 않습니다.",
        "무해하다고 단정할 수는 없습니다.",
        "무해한 요청이라고 판단할 근거가 부족합니다.",
        "무해하지 않습니다.",
        "무해하다는 증거가 없습니다.",
    ):
        report, warnings = stage2.postprocess_report_json({"overall_assessment": text}, {})
        assert report["overall_assessment"] == text
        assert warnings == []


def test_safety_negation_scope_does_not_exempt_other_claims() -> None:
    for separator in (". ", ", ", "; ", "\n", " 하지만 "):
        text = "무해함을 의미하지는 않습니다" + separator + "다른 요청은 무해합니다."
        expected = "무해함을 의미하지는 않습니다" + separator + "다른 요청은 안전하다고 확정할 수 없습니다."
        assert stage2.sanitize_report_text(text) == (expected, ["forbidden_phrase:무해"])
    text = "이 요청은 무해합니다. 다른 요청은 무해하다고 단정할 수는 없습니다."
    expected = "이 요청은 안전하다고 확정할 수 없습니다. 다른 요청은 무해하다고 단정할 수는 없습니다."
    assert stage2.sanitize_report_text(text) == (expected, ["forbidden_phrase:무해"])


def test_neutralization_action_is_distinct_from_negated_safety_claim() -> None:
    text = "무해하다고 단정할 수는 없습니다. 입력값을 무해화하세요."
    report, warnings = stage2.postprocess_report_json(
        {"recommended_actions": [{"action": text}]}, {}
    )
    assert report["recommended_actions"][0]["action"] == (
        "무해하다고 단정할 수는 없습니다. 입력값을 안전하게 처리하세요."
    )
    assert warnings == ["forbidden_phrase:무해"]


def test_direct_safety_judgment_negation_and_uncertain_scope() -> None:
    for text in (
        "무해한 것으로 볼 수 없습니다.",
        "무해함을 의미하지는 않습니다.",
    ):
        assert stage2.sanitize_report_text(text) == (text, [])
    for text in (
        "무해한 요청이지만 공격 성공을 확인할 수는 없습니다.",
        "이 요청은 무해합니다만 공격 성공을 확인할 수는 없습니다.",
        "무해한 요청이며 공격 성공을 입증할 수는 없습니다.",
        "무해한 요청을 확인하지는 않았습니다.",
        "무해하지 않은 것은 아닙니다.",
        '분석가는 "이 요청은 무해합니다"라고 말했습니다.',
        '"무해함을 의미하지는 않습니다."라는 표현을 인용합니다.',
    ):
        report, warnings = stage2.postprocess_report_json(
            {"key_findings": [{"detail": text}]}, {}
        )
        assert report["key_findings"][0]["detail"] == text
        assert len(warnings) == 1
        assert warnings[0].startswith("safety_review:")
        detail = json.loads(warnings[0].split(":", 1)[1])
        assert detail["source_text"] == text
        assert detail["path"] == "report.key_findings[0].detail"
        assert detail["reason"]


@pytest.mark.parametrize("evidence", [
    '192.168.56.121', 'api.example.test', 'req.ab?cd!ef-123',
    'https://api.example.test/공격은실패했습니다?q=403',
    '/403/차단되었습니다', 'request_id=공격은실패했습니다',
    '`403으로 차단되었습니다.`', '"403으로 차단되었습니다."',
])
def test_http_correction_masks_evidence_but_corrects_adjacent_assertion(evidence):
    original = f"  {evidence} HTTP 401 응답에서 차단되었습니다.\r\n\t다음 자료.  "
    report, warnings = stage2.postprocess_report_json({"detail": original}, {})
    assert report["detail"] == (
        f"  {evidence} HTTP 401 응답에서 "
        + stage2.shared_http_status_outcome_fallback("401으로 차단되었습니다.")
        + "\r\n\t다음 자료.  "
    )
    assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings


def test_http_correction_preserves_all_separators_and_evidence_fields():
    original = {
        "detail": "  403 /x?q=a 차단되었습니다,  공격은 실패했습니다;\t파일 접근에 실패했습니다.\r\n끝.  ",
        "src_ip": "192.168.56.121",
        "raw_request": "  GET /403/차단되었습니다?q=공격은실패했습니다 HTTP/1.1  ",
        "request_id": "req.ab?cd!ef-123",
        "generated_at": "2026-10-23T15:20:23.804+09:00",
    }
    result, warnings = stage2.postprocess_report_json(original, {})
    block = stage2.shared_http_status_outcome_fallback("403으로 차단되었습니다.")
    attack = stage2.shared_http_status_outcome_fallback("공격은 실패했습니다.")
    file_access = stage2.shared_http_status_outcome_fallback("파일 접근에 실패했습니다.")
    assert result == {**original, "detail": f"  403 /x?q=a {block},  {attack};\t{file_access}\r\n끝.  "}
    assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings


@pytest.mark.parametrize("prefix,suffix", [("  ", "  "), ("\t", "\r\n"), ("\r\n  ", "\n\n")])
def test_safety_sanitizer_keeps_whitespace_around_corrected_claim(prefix, suffix):
    original = prefix + "이 요청은 무해합니다." + suffix
    result, warnings = stage2.postprocess_report_json({"detail": original}, {})
    assert result["detail"] == prefix + "이 요청은 안전하다고 확정할 수 없습니다." + suffix
    assert warnings == ["forbidden_phrase:무해"]
