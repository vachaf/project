from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from llm_client import LLMResponse
import llm_stage2_reporter as stage2


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
