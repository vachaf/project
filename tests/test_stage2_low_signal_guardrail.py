from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_client import LLMResponse
import llm_stage2_reporter as stage2


def neutral_input(count: int = 1) -> dict:
    return {
        "pipeline_counts": {"candidate_rows": 0},
        "distributions": {"filtered_out_breakdown": {"low_signal_request": count}},
        "top_incidents": [],
        "top_out_of_candidate_recon": [],
        "probing_sequence_summaries": [],
        "sensitive_path_probe_summaries": [],
        "mixed_baseline_scanner_summaries": [],
        "method_behavior_summaries": [],
        "ip_behavior_aggregates": [],
    }


def model_report() -> dict:
    return {
        "report_title": "저신호 보고서",
        "overall_assessment": "후보 밖 탐색성 요청 1건",
        "executive_summary": ["경미한 탐색성 트래픽", "저신호 요청이 제외되었습니다.", "의도 미확인"],
        "key_findings": [
            {"title": "향후 탐색·스캔의 전조", "detail": "추가 확인 필요", "severity": "low"},
            {"title": "후보 현황", "detail": "분석 후보 없음", "severity": "info"},
            {"title": "해석 한계", "detail": "정보 부족", "severity": "info"},
        ],
        "notable_incidents": [
            {"incident_ref": "none", "request_id": "", "src_ip": "", "verdict": "inconclusive", "severity": "info", "why_it_matters": "의도 미확인"}
        ],
        "notable_source_ips": [{"src_ip": "", "reason": "추가 정보 필요"}],
        "noise_interpretation": "저신호 탐색성 요청",
        "recommended_actions": [
            {"priority": "P1", "action": "향후 scanning 감시", "why": "예방 목적"},
            {"priority": "P2", "action": "추가 로그 검토", "why": "정보 부족"},
            {"priority": "P3", "action": "분류 기준 확인", "why": "후보 제외"},
        ],
        "confidence_and_limitations": ["정보가 부족합니다.", "의도 미확인"],
        "presentation_takeaway": "판단 유보",
    }


def test_low_signal_neutral_replaces_offending_sections_and_warns() -> None:
    report_input = neutral_input()
    assert stage2.is_low_signal_only_neutral_mode(report_input)
    report, warnings = stage2.postprocess_report_json(model_report(), report_input)

    assert warnings == [stage2.LOW_SIGNAL_RECON_WARNING]
    assert report["overall_assessment"].startswith("분석 후보로 승격된 요청은 확인되지 않았으며")
    assert report["executive_summary"] != model_report()["executive_summary"]
    assert len(report["key_findings"]) == 3
    assert all(row["severity"] == "info" for row in report["key_findings"])
    assert len(report["recommended_actions"]) == 3
    assert not stage2.LOW_SIGNAL_RECON_TERMS.search(json.dumps(report, ensure_ascii=False))
    assert "정상" not in json.dumps(report, ensure_ascii=False)
    assert "benign" not in json.dumps(report, ensure_ascii=False)


def test_low_signal_neutral_uses_actual_count() -> None:
    report, warnings = stage2.postprocess_report_json(model_report(), neutral_input(3))
    assert stage2.LOW_SIGNAL_RECON_WARNING in warnings
    assert "3건" in report["overall_assessment"]
    assert "3건" in report["noise_interpretation"]
    assert "3건" in json.dumps(report["key_findings"], ensure_ascii=False)
    assert "1건" not in json.dumps(report, ensure_ascii=False)


@pytest.mark.parametrize(
    ("category", "wording"),
    [("low_signal_fuzzing", "후보 밖 탐색성 fuzzing 요청"), ("low_signal_dir_probe", "후보 밖 탐색 probing 요청")],
)
def test_actual_out_of_candidate_recon_keeps_language(category: str, wording: str) -> None:
    report_input = neutral_input()
    report_input["distributions"]["filtered_out_breakdown"][category] = 1
    report_input["top_out_of_candidate_recon"] = [{"category": category, "count": 1}]
    report = model_report()
    report["noise_interpretation"] = wording

    assert not stage2.is_low_signal_only_neutral_mode(report_input)
    accepted, warnings = stage2.postprocess_report_json(report, report_input)
    assert accepted["noise_interpretation"] == wording
    assert stage2.LOW_SIGNAL_RECON_WARNING not in warnings


def test_candidate_mixed_report_does_not_trigger_neutral_fallback() -> None:
    report_input = neutral_input()
    report_input["pipeline_counts"]["candidate_rows"] = 1
    report_input["top_incidents"] = [{"incident_ref": "inc-1"}]
    report = model_report()
    accepted, warnings = stage2.postprocess_report_json(report, report_input)
    assert accepted["overall_assessment"] == report["overall_assessment"]
    assert stage2.LOW_SIGNAL_RECON_WARNING not in warnings


def test_attack_filtered_category_blocks_neutral_mode_even_without_recon_rows() -> None:
    report_input = neutral_input()
    report_input["distributions"]["filtered_out_breakdown"]["low_signal_fuzzing"] = 1
    assert report_input["top_out_of_candidate_recon"] == []
    assert not stage2.is_low_signal_only_neutral_mode(report_input)


@pytest.mark.parametrize(
    "evidence_key",
    ["probing_sequence_summaries", "sensitive_path_probe_summaries", "mixed_baseline_scanner_summaries", "method_behavior_summaries", "ip_behavior_aggregates"],
)
def test_real_probing_or_ip_context_disables_neutral_mode(evidence_key: str) -> None:
    report_input = neutral_input()
    report_input[evidence_key] = [{"request_count": 1}]
    assert not stage2.is_low_signal_only_neutral_mode(report_input)
    report = model_report()
    accepted, warnings = stage2.postprocess_report_json(report, report_input)
    assert accepted["overall_assessment"] == report["overall_assessment"]
    assert stage2.LOW_SIGNAL_RECON_WARNING not in warnings


def test_negated_scan_sentence_is_replaced_as_a_whole() -> None:
    report = model_report()
    report["overall_assessment"] = "스캔 근거가 확인되지 않았습니다."
    accepted, _ = stage2.postprocess_report_json(report, neutral_input())
    assert accepted["overall_assessment"] != "근거가 확인되지 않았습니다."
    assert "의도나 공격성을 판단할 수 없습니다" in accepted["overall_assessment"]
    assert "근거가 확인되었습니다" not in accepted["overall_assessment"]


def test_existing_benign_sanitizer_warning_survives_semantic_fallback() -> None:
    report = model_report()
    report["overall_assessment"] = "정상 탐색성 트래픽"
    report["presentation_takeaway"] = "normalization 용어는 유지합니다."
    accepted, warnings = stage2.postprocess_report_json(report, neutral_input())
    assert "forbidden_phrase:정상" in warnings
    assert stage2.LOW_SIGNAL_RECON_WARNING in warnings
    assert "정상" not in json.dumps(accepted, ensure_ascii=False)
    assert "normalization 용어는 유지합니다." == accepted["presentation_takeaway"]


@pytest.mark.parametrize(
    "field",
    ["report_title", "confidence_and_limitations", "presentation_takeaway", "notable_incidents", "notable_source_ips"],
)
def test_remaining_markdown_free_text_fields_receive_neutral_fallback(field: str) -> None:
    report = model_report()
    if field == "notable_incidents":
        report[field][0]["why_it_matters"] = "reconnaissance context"
    elif field == "notable_source_ips":
        report[field][0]["reason"] = "probe context"
    elif field == "confidence_and_limitations":
        report[field][0] = "scanner-like request"
    else:
        report[field] = "scanning context"
    accepted, warnings = stage2.postprocess_report_json(report, neutral_input())
    assert stage2.LOW_SIGNAL_RECON_WARNING in warnings
    assert not stage2.LOW_SIGNAL_RECON_TERMS.search(json.dumps(accepted, ensure_ascii=False))


def test_english_detection_uses_word_boundaries() -> None:
    report, _ = stage2.postprocess_report_json(model_report(), neutral_input())
    report["presentation_takeaway"] = "scannable이라는 일반 단어만 있습니다."
    accepted, warnings = stage2.postprocess_report_json(report, neutral_input())
    assert accepted["presentation_takeaway"] == report["presentation_takeaway"]
    assert stage2.LOW_SIGNAL_RECON_WARNING not in warnings


def test_neutral_markdown_policy_does_not_claim_out_of_candidate_recon() -> None:
    report_input = neutral_input()
    report, _ = stage2.postprocess_report_json(model_report(), report_input)
    markdown = stage2.render_markdown(report, report_input, selected_model="test", mode="routine")
    assert "후보 밖 탐색성 요청" not in markdown
    assert "low_signal_request 는 후보 기준을 넘지 않은 저신호 요청" in markdown


def test_low_signal_prompt_guardrail_only_applies_to_neutral_mode() -> None:
    report_input = neutral_input()
    system, user = (message["content"] for message in stage2.build_messages(report_input))
    assert "low_signal_request != reconnaissance" in system
    assert "low_signal_request != reconnaissance" in user
    assert "top_out_of_candidate_recon에 실제 항목이 있을 때만" in system
    report_input["top_out_of_candidate_recon"] = [{"category": "low_signal_fuzzing", "count": 1}]
    system = stage2.build_messages(report_input)[0]["content"]
    assert "K. Low-signal-only neutral mode" not in system


@pytest.mark.parametrize("repair", [False, True], ids=["direct_parse", "repair_parse"])
def test_main_accepted_json_paths_share_semantic_postprocessing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repair: bool
) -> None:
    stage1_path = tmp_path / "sample_stage1_results.json"
    llm_input_path = tmp_path / "sample_llm_input.json"
    out_dir = tmp_path / "out"
    stage1_path.write_text(json.dumps({"meta": {"success_count": 0, "error_count": 0}, "results": []}), encoding="utf-8")
    llm_input_path.write_text(
        json.dumps({"meta": {"counts": {"candidate_rows": 0, "filtered_out_rows": 1}, "filtered_out_breakdown": {"low_signal_request": 1}}}),
        encoding="utf-8",
    )
    calls = []

    def fake_call_llm_json(**kwargs):
        calls.append(kwargs)
        output = "invalid json" if repair and len(calls) == 1 else json.dumps(model_report(), ensure_ascii=False)
        return LLMResponse(output_text=output, response_id=f"mock-{len(calls)}", raw_response={}, provider=kwargs["config"].provider, model=kwargs["model"])

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(stage2, "call_llm_json", fake_call_llm_json)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llm_stage2_reporter.py", "--stage1-results", str(stage1_path), "--llm-input", str(llm_input_path), "--out-dir", str(out_dir), "--base-name", "sample", "--provider", "anthropic" if repair else "openai"],
    )
    assert stage2.main() == 0
    assert len(calls) == (2 if repair else 1)
    payload = json.loads((out_dir / "sample_stage2_report.json").read_text(encoding="utf-8"))
    assert stage2.LOW_SIGNAL_RECON_WARNING in payload["meta"]["guardrail_warnings"]
    assert not stage2.LOW_SIGNAL_RECON_TERMS.search(json.dumps(payload["report"], ensure_ascii=False))
