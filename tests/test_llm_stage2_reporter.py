from __future__ import annotations

import json
from pathlib import Path
import sys


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

    assert "benign_normal_search" not in sanitized
    assert "정상" not in sanitized
    assert "무해" not in sanitized
    assert " normal " not in sanitized
    assert "path normalization stays" in sanitized
    assert "forbidden_phrase:benign_normal_search" in warnings
    assert "forbidden_phrase:정상" in warnings
    assert "forbidden_phrase:무해" in warnings
    assert "forbidden_phrase:normal" in warnings


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
    assert "benign_normal_search" not in report_text
    assert "normal_search_baseline" not in report_text
    assert "정상" not in report_text
    assert "무해" not in report_text
    assert "normalization 같은" in report_text
    assert "known_baseline_like_legacy_alias" in report_text
    warnings = payload["meta"]["guardrail_warnings"]
    assert "forbidden_phrase:benign_normal_search" in warnings
    assert "forbidden_phrase:normal_search_baseline" in warnings
    assert "forbidden_phrase:정상" in warnings


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
