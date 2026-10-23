from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from src import llm_stage2_reporter as stage2
from scripts import check_stage2_report_quality as quality


START = "2026-10-15T15:20:23.804+09:00"
END = "2026-10-15T15:20:23.805+09:00"


def scope(kind: str = "live_selected_logs", **changes) -> dict:
    value = {
        "kind": kind,
        "window_role": "selected_log_timestamp_envelope" if kind == "live_selected_logs" else "query_filter",
        "window": {"start": START, "end_exclusive": END, "timezone": "Asia/Seoul"},
    }
    if kind == "live_selected_logs":
        value["selected_id_count"] = 1
    value.update(changes)
    return value


def report_input(stage1_scope=..., llm_scope=..., *, llm_present=True) -> dict:
    stage1_meta = {"source_window": {"start": START, "end_exclusive": END}}
    llm_meta = {
        "analysis_window": {"start": START, "end_exclusive": END},
        "query_timezone": "Asia/Seoul",
        "counts": {"total_exported_rows": 1, "selected_source_rows": 1, "candidate_rows": 0},
    }
    if stage1_scope is not ...:
        stage1_meta["source_input_scope"] = stage1_scope
    if llm_scope is not ...:
        llm_meta["input_scope"] = llm_scope
    return stage2.build_report_input(
        {"meta": stage1_meta, "results": []},
        {"meta": llm_meta, "analysis_candidates": []} if llm_present else None,
        None, top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[],
    )


def report_text() -> dict:
    return {
        "report_title": "SQLi 분석", "overall_assessment": "요청 패턴 관찰",
        "executive_summary": [], "key_findings": [], "notable_incidents": [],
        "notable_source_ips": [], "noise_interpretation": "", "recommended_actions": [],
        "confidence_and_limitations": [], "presentation_takeaway": "",
    }


@pytest.mark.parametrize("kind", ["live_selected_logs", "time_range"])
def test_matching_scope_is_added_without_changing_existing_context_or_counts(kind):
    verified = scope(kind)
    result = report_input(verified, verified)
    assert result["analysis_context"]["input_scope"] == verified
    assert result["analysis_context"]["window"] == {"start": START, "end_exclusive": END}
    assert result["pipeline_counts"]["total_exported_rows"] == 1
    assert result["pipeline_counts"]["candidate_rows"] == 0
    assert result["pipeline_counts"]["selected_source_rows"] == 1
    assert result["top_incidents"] == []


@pytest.mark.parametrize("changed", [
    scope("time_range"),
    scope(window_role="query_filter"),
    scope(window={"start": START, "end_exclusive": "2026-10-15T15:20:23.806+09:00", "timezone": "Asia/Seoul"}),
    scope(selected_id_count=2),
])
def test_conflicting_or_invalid_scope_is_rejected(changed):
    with pytest.raises(ValueError, match="input scope"):
        report_input(scope(), changed)


@pytest.mark.parametrize("bad", [
    "live_selected_logs", {}, scope(window_role="query_filter"), scope(selected_id_count=0),
    scope(window={"start": END, "end_exclusive": START, "timezone": "Asia/Seoul"}),
    scope(window={"start": START, "end_exclusive": END, "timezone": "UTC"}),
])
def test_malformed_scope_is_rejected_before_stage2_generation(bad):
    with pytest.raises(ValueError, match="input scope"):
        report_input(bad, bad)


@pytest.mark.parametrize("stage1_meta,llm_meta", [([], {}), ({}, []), ("invalid", {}), ({}, "invalid")])
def test_malformed_metadata_containers_are_explicit_errors(stage1_meta, llm_meta):
    with pytest.raises(ValueError, match="input scope"):
        stage2.build_report_input({"meta": stage1_meta, "results": []}, {"meta": llm_meta}, None,
                                  top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[])


def test_missing_and_explicit_null_remain_distinct():
    old = report_input()
    assert "input_scope" not in old["analysis_context"]
    explicit_unknown = report_input(None, None)
    assert "input_scope" in explicit_unknown["analysis_context"]
    assert explicit_unknown["analysis_context"]["input_scope"] is None
    assert report_input(scope(), ..., llm_present=False)["analysis_context"]["input_scope"] == scope()
    null_markdown = stage2.render_markdown(report_text(), explicit_unknown, "test", "routine")
    assert "입력 방식: 미확인" in null_markdown


@pytest.mark.parametrize("stage1_scope,llm_scope", [(scope(), ...), (..., scope()), (scope(), None)])
def test_one_sided_known_scope_with_two_artifacts_is_not_silently_trusted(stage1_scope, llm_scope):
    with pytest.raises(ValueError, match="input scope"):
        report_input(stage1_scope, llm_scope)


def test_report_input_rejects_scope_window_disagreeing_with_existing_window():
    stage1_meta = {"source_input_scope": scope(), "source_window": {"start": START, "end_exclusive": END}}
    llm_meta = {"input_scope": scope(), "analysis_window": {"start": START, "end_exclusive": "2026-10-15T15:20:23.806+09:00"}}
    with pytest.raises(ValueError, match="input scope"):
        stage2.build_report_input({"meta": stage1_meta, "results": []}, {"meta": llm_meta}, None,
                                  top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[])


def test_report_input_rejects_timezone_disagreeing_with_verified_scope():
    verified = scope()
    with pytest.raises(ValueError, match="input scope"):
        stage2.build_report_input(
            {"meta": {"source_input_scope": verified}, "results": []},
            {"meta": {"input_scope": verified, "query_timezone": "UTC"}}, None,
            top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[],
        )


def test_explicit_zero_selected_source_rows_is_kept_separate_from_missing():
    verified = scope()
    stage1_payload = {"meta": {"source_input_scope": verified}, "results": []}
    llm_payload = {"meta": {"input_scope": verified, "counts": {"selected_source_rows": 0}}}
    counted = stage2.build_report_input(stage1_payload, llm_payload, None,
                                        top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[])
    assert counted["pipeline_counts"]["selected_source_rows"] == 0
    llm_payload["meta"]["counts"] = {}
    missing = stage2.build_report_input(stage1_payload, llm_payload, None,
                                        top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[])
    assert "selected_source_rows" not in missing["pipeline_counts"]


def test_scope_timezone_is_used_when_legacy_timezone_fields_are_absent():
    utc_scope = scope("time_range", window={
        "start": "2026-10-15T06:20:23.804+00:00", "end_exclusive": "2026-10-15T06:20:23.805+00:00",
        "timezone": "UTC",
    })
    result = stage2.build_report_input(
        {"meta": {"source_input_scope": utc_scope}, "results": []},
        {"meta": {"input_scope": utc_scope}}, None,
        top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[],
    )
    assert result["analysis_context"]["query_timezone"] == "UTC"


def test_stage1_partial_failure_counts_do_not_change_input_scope():
    verified = scope(selected_id_count=3)
    stage1_payload = {"meta": {"source_input_scope": verified, "success_count": 1, "error_count": 1}, "results": []}
    prepared = {"meta": {"input_scope": verified, "counts": {
        "total_exported_rows": 2, "selected_source_rows": 2, "candidate_rows": 2,
    }}}
    result = stage2.build_report_input(stage1_payload, prepared, {"errors": [{}]},
                                       top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[])
    assert result["analysis_context"]["input_scope"]["selected_id_count"] == 3
    assert result["pipeline_counts"]["total_exported_rows"] == 2
    assert result["pipeline_counts"]["selected_source_rows"] == 2
    assert result["pipeline_counts"]["candidate_rows"] == 2
    assert result["pipeline_counts"]["stage1_success_count"] == 1
    assert result["pipeline_counts"]["stage1_error_count"] == 1


@pytest.mark.parametrize("kind,required", [
    ("live_selected_logs", "선택되지 않은 주변 요청"),
    ("time_range", "종료 시각은 포함되지"),
])
def test_scope_specific_prompt_preserves_existing_security_instructions(kind, required):
    text = "\n".join(part["content"] for part in stage2.build_messages(report_input(scope(kind), scope(kind))))
    assert required in text
    assert "OR 1=1" in text or "SQLi" in text
    assert "CWE" in text and "WSTG" in text
    assert "403" in text and "404" in text
    assert "성공" in text
    unknown = "\n".join(part["content"] for part in stage2.build_messages(report_input()))
    assert "입력 방식" in unknown and "추정" in unknown


def test_prompt_does_not_treat_missing_scope_window_as_verified_time_boundary():
    for kind in ("live_selected_logs", "time_range"):
        unverified = scope(kind, window=None)
        text = stage2.build_messages(report_input(unverified, unverified))[0]["content"]
        assert "검증된 시각 경계가 없으므로" in text
        markdown = stage2.render_markdown(report_text(), report_input(unverified, unverified), "test", "routine")
        assert "범위: 미제공" in markdown


def test_selected_scope_guard_corrects_only_unsupported_absence_and_keeps_identifiers():
    original = report_text()
    original["overall_assessment"] = "해당 시간대에 추가 요청은 관찰되지 않았습니다. /search?q=%2527 OR 1=1은 SQLi 의심입니다."
    original["executive_summary"] = [
        "선택되지 않은 주변 요청은 없었습니다.",
        "제공된 로그에서는 추가 관련 요청이 확인되지 않았습니다.",
        "두 선택 로그에서 연속된 SQLi 의심 패턴이 관찰되었습니다.",
        "해당 시간대에 /search?q=%2527 OR 1=1 관련 추가 요청은 없었습니다.",
    ]
    before = deepcopy(original)
    processed, warnings = stage2.postprocess_report_json(original, report_input(scope(), scope()))
    assert processed["overall_assessment"].startswith("이번 분석에 제공된 로그")
    assert "/search?q=%2527 OR 1=1" in processed["overall_assessment"]
    assert "선택되지 않은 주변 요청의 존재 여부는 이번 입력으로 확인할 수 없습니다" in processed["executive_summary"][0]
    assert processed["executive_summary"][1:3] == before["executive_summary"][1:3]
    assert "/search?q=%2527 OR 1=1" in processed["executive_summary"][3]
    assert "해당 시간대" not in processed["executive_summary"][3]
    assert warnings
    assert original == before
    assert stage2.postprocess_report_json(processed, report_input(scope(), scope())) == (processed, [])


def test_time_range_outside_claim_is_flagged_without_overwriting_report():
    report = {"overall_assessment": "조회 범위 밖에는 공격 요청이 없었습니다."}
    processed, warnings = stage2.postprocess_report_json(report, report_input(scope("time_range"), scope("time_range")))
    assert processed == report
    assert any("scope" in warning for warning in warnings)
    checked = quality.analyze_stage2_report_data({"report": processed, "meta": {"guardrail_warnings": warnings}})
    assert checked["verdict"] in {"WARN", "FAIL"}
    assert any(row["rule"] == "safety_judgment_review" for row in checked["warnings"])


def test_selected_window_wide_claim_is_reviewed_when_no_requests_were_claimed():
    input_data = report_input(scope(), scope())
    report = {"overall_assessment": "해당 시간대 전체에 요청은 없었습니다.",
              "noise_interpretation": "해당 시간대에 추가 요청은 없었지만, /search?q=%2527을 재검토하세요."}
    processed, warnings = stage2.postprocess_report_json(report, input_data)
    assert processed["overall_assessment"] == report["overall_assessment"]
    assert processed["noise_interpretation"] == report["noise_interpretation"]
    reviews = [warning for warning in warnings if "input_scope_review_required" in warning]
    assert len(reviews) == 2
    checked = quality.analyze_stage2_report_data({"report": processed, "meta": {"guardrail_warnings": warnings}})
    assert checked["verdict"] == "WARN"
    assert len([row for row in checked["warnings"] if row["rule"] == "safety_judgment_review"]) == 2
    assert stage2.postprocess_report_json(processed, input_data) == (processed, warnings)


@pytest.mark.parametrize("claim", [
    "후속 공격은 없었습니다.",
    "제공된 로그를 확인했으며 해당 시간대 전체에 다른 요청은 없었습니다.",
])
def test_selected_unscoped_or_compound_absence_is_reviewed_without_rewriting(claim):
    input_data = report_input(scope(), scope())
    report = {"overall_assessment": claim}
    processed, warnings = stage2.postprocess_report_json(report, input_data)
    assert processed == report
    assert any("input_scope_review_required" in warning for warning in warnings)
    checked = quality.analyze_stage2_report_data({"report": processed, "meta": {"guardrail_warnings": warnings}})
    assert checked["verdict"] == "WARN"
    assert any(row["rule"] == "safety_judgment_review" for row in checked["warnings"])
    assert stage2.postprocess_report_json(processed, input_data) == (processed, warnings)


def test_selected_followup_uncertainty_is_not_flagged():
    report = {"overall_assessment": "후속 공격 여부는 확인할 수 없습니다."}
    assert stage2.postprocess_report_json(report, report_input(scope(), scope())) == (report, [])


def test_scope_review_keeps_prior_http_status_correction():
    report = {"overall_assessment": "403으로 차단되었습니다. 해당 시간대 전체에 요청은 없었습니다."}
    processed, warnings = stage2.postprocess_report_json(report, report_input(scope(), scope()))
    assert processed["overall_assessment"].startswith("HTTP 403 응답이 관찰되어 접근 제한 가능성이 있습니다.")
    assert processed["overall_assessment"].endswith("해당 시간대 전체에 요청은 없었습니다.")
    assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings
    assert any("input_scope_review_required" in warning for warning in warnings)


def test_selected_one_incident_window_phrase_is_scoped_to_supplied_logs():
    report = {"overall_assessment": "분석 창에는 단일 SQLi 요청 1건만 확인됩니다."}
    processed, warnings = stage2.postprocess_report_json(report, report_input(scope(), scope()))
    assert processed["overall_assessment"] == "이번 분석에 제공된 로그에는 단일 SQLi 요청 1건만 확인됩니다."
    assert warnings


def test_scope_correction_does_not_change_quoted_phrase_or_compound_unselected_claim():
    report = {
        "overall_assessment": '"해당 시간대" 표현과 별개로 해당 시간대에 추가 요청은 없었습니다.',
        "noise_interpretation": "선택되지 않은 주변 요청은 없었고 다른 자료도 확인했습니다.",
    }
    processed, warnings = stage2.postprocess_report_json(report, report_input(scope(), scope()))
    assert processed["overall_assessment"].startswith('"해당 시간대"')
    assert "이번 분석에 제공된 로그에 추가 요청" in processed["overall_assessment"]
    assert processed["noise_interpretation"] == report["noise_interpretation"]
    assert any("review_required" in warning for warning in warnings)


def test_scope_correction_preserves_ip_uri_sqli_status_and_standard_identifiers():
    identifiers = "192.168.56.121 /search?q=%2527 OR 1=1 HTTP 404 CWE-89 WSTG-INPV-05"
    report = {"overall_assessment": f"해당 시간대에 {identifiers} 관련 추가 요청은 없었습니다."}
    processed, warnings = stage2.postprocess_report_json(report, report_input(scope(), scope()))
    assert identifiers in processed["overall_assessment"]
    assert processed["overall_assessment"].startswith("이번 분석에 제공된 로그")
    assert warnings


def test_unknown_scope_flags_broad_time_claim_without_guessing_or_rewriting():
    report = {"overall_assessment": "해당 시간대 전체에 요청은 없었습니다."}
    processed, warnings = stage2.postprocess_report_json(report, report_input())
    assert processed == report
    assert any("review_required" in warning for warning in warnings)


def test_time_range_window_wide_claim_is_reviewed_without_auto_rewriting():
    report = {"overall_assessment": "해당 시간대 전체에 요청은 없었습니다."}
    processed, warnings = stage2.postprocess_report_json(report, report_input(scope("time_range"), scope("time_range")))
    assert processed == report
    assert any("review_required" in warning for warning in warnings)


@pytest.mark.parametrize("kind,label", [
    ("live_selected_logs", "선택 로그의 시각 범위"),
    ("time_range", "로그 조회 시간 범위"),
])
def test_markdown_labels_verified_time_role_and_keeps_sections(kind, label):
    markdown = stage2.render_markdown(report_text(), report_input(scope(kind), scope(kind)), "test", "routine")
    assert label in markdown and START in markdown and END in markdown
    assert "## 1. 전체 평가" in markdown and "권고 조치" in markdown
    assert "입력 방식:" in markdown
    unknown = stage2.render_markdown(report_text(), report_input(), "test", "routine")
    assert "입력 방식: 미확인" in unknown
    assert "제공된 분석 입력의 시간 정보" in unknown


def test_legacy_markdown_handles_malformed_unverified_window_without_inference():
    markdown = stage2.render_markdown(report_text(), {"analysis_context": {"window": "invalid"}}, "test", "routine")
    assert "입력 방식: 미확인" in markdown
    assert "제공된 분석 입력의 시간 정보: 미제공" in markdown


def test_stage2_dry_run_artifacts_carry_verified_scope_outside_report_schema(tmp_path: Path, monkeypatch):
    selected = scope()
    stage1_path = tmp_path / "sample_stage1_results.json"
    llm_path = tmp_path / "sample_llm_input.json"
    stage1_path.write_text(json.dumps({"meta": {"source_input_scope": selected}, "results": []}), encoding="utf-8")
    llm_path.write_text(json.dumps({"meta": {"input_scope": selected, "counts": {"candidate_rows": 0}}}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["llm_stage2_reporter.py", "--stage1-results", str(stage1_path),
                                  "--llm-input", str(llm_path), "--out-dir", str(tmp_path / "out"), "--dry-run"])
    assert stage2.main() == 0
    report_input_payload = json.loads((tmp_path / "out/sample_stage2_report_input.json").read_text(encoding="utf-8"))
    report_payload = json.loads((tmp_path / "out/sample_stage2_report.json").read_text(encoding="utf-8"))
    assert report_input_payload["analysis_context"]["input_scope"] == selected
    assert report_payload["meta"]["input_scope"] == selected
    assert report_payload["report"] is None
    assert "input_scope" not in stage2.build_schema()["properties"]
    assert stage2.build_schema()["properties"]["key_findings"]["minItems"] == 3
    assert stage2.build_schema()["additionalProperties"] is False


def test_stage2_resume_rejects_different_scope_before_writing_report_input(tmp_path: Path, monkeypatch, capsys):
    stage1_path = tmp_path / "sample_stage1_results.json"
    llm_path = tmp_path / "sample_llm_input.json"
    stage1_path.write_text(json.dumps({"meta": {"source_input_scope": scope()}, "results": []}), encoding="utf-8")
    llm_path.write_text(json.dumps({"meta": {"input_scope": scope("time_range")}}), encoding="utf-8")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["llm_stage2_reporter.py", "--stage1-results", str(stage1_path),
                                  "--llm-input", str(llm_path), "--out-dir", str(out_dir), "--dry-run"])
    assert stage2.main() == 2
    assert "input scope" in capsys.readouterr().err
    assert not (out_dir / "sample_stage2_report_input.json").exists()
