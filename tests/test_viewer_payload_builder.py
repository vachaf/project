from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER = REPO_ROOT / "src" / "viewer_payload_builder.py"


def write_json(tmp_path: Path, name: str, payload: Any) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_builder(
    tmp_path: Path,
    *,
    stage2_report_input: Dict[str, Any],
    stage2_report: Dict[str, Any] | None = None,
    stage1_results: Dict[str, Any] | None = None,
    llm_input: Dict[str, Any] | None = None,
    raw_export: Dict[str, Any] | None = None,
    noise_summary: Any = None,
    include_raw_log: bool = False,
) -> Dict[str, Any]:
    report_input_path = write_json(tmp_path, "stage2_report_input.json", stage2_report_input)
    out_path = tmp_path / "viewer_payload.json"

    cmd: List[str] = [
        sys.executable,
        str(BUILDER),
        "--stage2-report-input",
        str(report_input_path),
        "--out",
        str(out_path),
    ]

    if stage2_report is not None:
        cmd.extend(["--stage2-report", str(write_json(tmp_path, "stage2_report.json", stage2_report))])
    if stage1_results is not None:
        cmd.extend(["--stage1-results", str(write_json(tmp_path, "stage1_results.json", stage1_results))])
    if llm_input is not None:
        cmd.extend(["--llm-input", str(write_json(tmp_path, "llm_input.json", llm_input))])
    if raw_export is not None:
        cmd.extend(["--raw-export", str(write_json(tmp_path, "raw_export.json", raw_export))])
    if noise_summary is not None:
        cmd.extend(["--noise-summary", str(write_json(tmp_path, "noise_summary.json", noise_summary))])
    if include_raw_log:
        cmd.append("--include-raw-log")

    completed = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return load_json(out_path)


def contains_key_recursive(obj: Any, key: str) -> bool:
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(contains_key_recursive(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_key_recursive(v, key) for v in obj)
    return False


def base_stage2_report_input() -> Dict[str, Any]:
    return {
        "analysis_context": {
            "window": {"start": "2026-05-08T10:00:00+09:00", "end": "2026-05-08T10:05:00+09:00"},
            "mode": "routine",
            "selected_model": "gpt-5.4-mini",
        },
        "pipeline_counts": {"total_exported_rows": 3, "candidate_rows": 1},
        "distributions": {"filtered_out_breakdown": {"low_signal_fuzzing": 2}},
        "top_filtered_categories": [{"category": "benign_normal_search", "count": 1}],
        "top_out_of_candidate_recon": [{"src_ip": "192.0.2.10", "count": 1}],
        "policy_notes": {"apache_logs_only": True},
    }


def auth_finding(reason_hints: Any) -> Dict[str, Any]:
    return {
        "incident_ref": "inc-1",
        "request_id": "rid-1",
        "src_ip": "192.0.2.10",
        "method": "POST",
        "uri": "/rest/user/login",
        "status_code": 401,
        "severity": "low",
        "confidence": "low",
        "verdict": "suspicious_auth_abuse",
        "reason_hints": reason_hints,
        "reasoning_summary": "auth endpoint 401 반복 관찰",
        "evidence_fields": ["status_code", "uri", "reason_hints"],
        "recommended_actions": ["watch"],
    }


def traversal_finding_with_xss_context() -> Dict[str, Any]:
    return {
        "incident_ref": "inc-trv-1",
        "request_id": "rid-trv-1",
        "src_ip": "192.0.2.11",
        "method": "GET",
        "uri": "/download.php",
        "status_code": 200,
        "severity": "low",
        "confidence": "low",
        "verdict": "inconclusive",
        "verdict_hint": "path_traversal",
        "reason_hints": [
            "traversal:dotdot_slash(+4)",
            "traversal:etc_passwd(+5)",
            "xss:external_navigation",
        ],
        "reasoning_summary": "traversal-like request observed",
        "evidence_fields": ["reason_hints", "raw_request_target"],
        "recommended_actions": ["review"],
        "handler": "proxy-server",
        "log_schema": "apache_security_io_v1",
    }


def test_minimal_payload_has_required_top_level_keys(tmp_path: Path) -> None:
    payload = run_builder(tmp_path, stage2_report_input=base_stage2_report_input())
    required_keys = {
        "schema_version",
        "meta",
        "summary",
        "report",
        "findings",
        "contexts",
        "supporting_events",
        "noise",
        "policies",
        "source_files",
        "integrity",
    }
    assert required_keys.issubset(payload.keys())
    assert payload["schema_version"] == "viewer_payload.v1"


def test_works_without_stage2_report(tmp_path: Path) -> None:
    payload = run_builder(tmp_path, stage2_report_input=base_stage2_report_input())
    assert payload["report"] == {
        "report_title": None,
        "overall_assessment": None,
        "executive_summary": [],
        "key_findings": [],
        "notable_incidents": [],
        "notable_source_ips": [],
        "noise_interpretation": None,
        "recommended_actions": [],
        "confidence_and_limitations": None,
        "presentation_takeaway": None,
    }


def test_reason_hints_type_defense_list_string_none(tmp_path: Path) -> None:
    stage2_report_input = base_stage2_report_input()
    stage2_report_input["top_incidents"] = [
        auth_finding(["error_status:401(+2)", "login_endpoint(+1)"]),
        auth_finding("auth_payload_content_type(+1)"),
        auth_finding(None),
    ]

    payload = run_builder(tmp_path, stage2_report_input=stage2_report_input)
    findings = payload["findings"]
    assert len(findings) == 3
    assert findings[0]["reason_hints"] == ["error_status:401(+2)", "login_endpoint(+1)"]
    assert findings[1]["reason_hints"] == ["auth_payload_content_type(+1)"]
    assert findings[2]["reason_hints"] == []
    assert all(f["category"] == "auth_behavior_candidate" for f in findings)


def test_noise_summary_type_defense_list_and_dict(tmp_path: Path) -> None:
    payload_list = run_builder(
        tmp_path / "list_case",
        stage2_report_input=base_stage2_report_input(),
        noise_summary=[{"noise_category": "low_signal_fuzzing", "count": 2}],
    )
    assert isinstance(payload_list["noise"]["noise_summary_file"], list)

    payload_dict = run_builder(
        tmp_path / "dict_case",
        stage2_report_input=base_stage2_report_input(),
        noise_summary={"groups": [{"noise_category": "low_signal_fuzzing", "count": 2}]},
    )
    assert isinstance(payload_dict["noise"]["noise_summary_file"], dict)


def test_raw_log_excluded_by_default(tmp_path: Path) -> None:
    stage2_report_input = base_stage2_report_input()
    stage2_report_input["top_incidents"] = [auth_finding(["error_status:401(+2)"])]
    stage2_report_input["supporting_events"] = [
        {"request_id": "rid-1", "context_role": "auth_behavior_context", "supporting_role": "auth_behavior_support"}
    ]
    raw_export = {
        "data": {
            "security": [
                {
                    "request_id": "rid-1",
                    "id": 101,
                    "src_ip": "192.0.2.10",
                    "method": "POST",
                    "uri": "/rest/user/login",
                    "status_code": 401,
                    "log_time": "2026-05-08T10:00:01+09:00",
                    "user_agent": "test-agent",
                    "raw_log": "very-sensitive-line",
                }
            ]
        }
    }

    payload = run_builder(tmp_path, stage2_report_input=stage2_report_input, raw_export=raw_export)
    assert not contains_key_recursive(payload, "raw_log")


def test_raw_log_included_with_opt_in(tmp_path: Path) -> None:
    stage2_report_input = base_stage2_report_input()
    stage2_report_input["top_incidents"] = [auth_finding(["error_status:401(+2)"])]
    raw_export = {
        "data": {
            "security": [
                {
                    "request_id": "rid-1",
                    "id": 101,
                    "src_ip": "192.0.2.10",
                    "method": "POST",
                    "uri": "/rest/user/login",
                    "status_code": 401,
                    "log_time": "2026-05-08T10:00:01+09:00",
                    "raw_log": "very-sensitive-line",
                }
            ]
        }
    }

    payload = run_builder(
        tmp_path,
        stage2_report_input=stage2_report_input,
        raw_export=raw_export,
        include_raw_log=True,
    )
    assert contains_key_recursive(payload, "raw_log")


def test_context_only_summaries_stay_in_contexts_not_findings(tmp_path: Path) -> None:
    stage2_report_input = base_stage2_report_input()
    stage2_report_input["top_incidents"] = [auth_finding(["error_status:401(+2)"])]
    stage2_report_input["auth_behavior_summaries"] = [
        {"src_ip": "192.0.2.10", "should_promote_to_candidate": False, "request_count": 5}
    ]
    stage2_report_input["ip_behavior_aggregates"] = [
        {"src_ip": "192.0.2.10", "should_promote_to_candidate": False, "request_count": 9}
    ]

    payload = run_builder(tmp_path, stage2_report_input=stage2_report_input)
    contexts = payload["contexts"]
    assert len(contexts) == 2
    assert all(item["context_only"] is True for item in contexts)
    assert {item["context_type"] for item in contexts} == {"auth_behavior", "ip_behavior"}
    assert all(item.get("should_promote_to_candidate") is False for item in contexts)
    assert all("should_promote_to_candidate" not in f for f in payload["findings"])


def test_supporting_events_stay_top_level_and_context_only(tmp_path: Path) -> None:
    stage2_report_input = base_stage2_report_input()
    stage2_report_input["top_incidents"] = [auth_finding(["error_status:401(+2)"])]
    stage2_report_input["supporting_events"] = [
        {
            "request_id": "rid-1",
            "context_role": "auth_behavior_context",
            "supporting_role": "auth_behavior_support",
            "interpretation_limit": "post_body_not_visible_no_auth_success_inference",
            "reason_hints": ["login_endpoint(+1)"],
        }
    ]

    payload = run_builder(tmp_path, stage2_report_input=stage2_report_input)
    assert len(payload["supporting_events"]) == 1
    assert payload["supporting_events"][0]["context_only"] is True
    assert payload["supporting_events"][0]["supporting_role"] == "auth_behavior_support"
    assert all("supporting_role" not in f for f in payload["findings"])


def test_findings_priority_top_incidents_then_stage1_then_llm_input(tmp_path: Path) -> None:
    stage2_report_input_a = base_stage2_report_input()
    stage2_report_input_a["top_incidents"] = [auth_finding(["error_status:401(+2)"])]
    payload_a = run_builder(tmp_path / "case_a", stage2_report_input=stage2_report_input_a)
    assert payload_a["meta"]["source_of_truth"]["findings"] == "stage2_report_input.top_incidents"
    assert payload_a["findings"][0]["verdict"] == "suspicious_auth_abuse"

    stage2_report_input_b = base_stage2_report_input()
    stage1_results = {"results": [auth_finding("login_endpoint(+1)")]}
    payload_b = run_builder(
        tmp_path / "case_b",
        stage2_report_input=stage2_report_input_b,
        stage1_results=stage1_results,
    )
    assert payload_b["meta"]["source_of_truth"]["findings"] == "stage1_results.results"
    assert payload_b["findings"][0]["verdict"] == "suspicious_auth_abuse"

    stage2_report_input_c = base_stage2_report_input()
    llm_input = {"analysis_candidates": [auth_finding(None)]}
    payload_c = run_builder(
        tmp_path / "case_c",
        stage2_report_input=stage2_report_input_c,
        llm_input=llm_input,
    )
    assert payload_c["meta"]["source_of_truth"]["findings"] == "llm_input.analysis_candidates"
    assert payload_c["findings"][0]["verdict"] == "suspicious_auth_abuse"


def test_traversal_category_takes_priority_over_xss_context_hint(tmp_path: Path) -> None:
    stage2_report_input = base_stage2_report_input()
    stage2_report_input["top_incidents"] = [traversal_finding_with_xss_context()]

    payload = run_builder(tmp_path, stage2_report_input=stage2_report_input)
    finding = payload["findings"][0]
    assert finding["category"] == "path_traversal_candidate"


def test_handler_and_log_schema_are_preserved_in_findings(tmp_path: Path) -> None:
    stage2_report_input = base_stage2_report_input()
    stage2_report_input["top_incidents"] = [traversal_finding_with_xss_context()]

    payload = run_builder(tmp_path, stage2_report_input=stage2_report_input)
    finding = payload["findings"][0]
    assert finding["handler"] == "proxy-server"
    assert finding["log_schema"] == "apache_security_io_v1"


def test_apache_logs_only_guardrail_present(tmp_path: Path) -> None:
    payload = run_builder(tmp_path, stage2_report_input=base_stage2_report_input())
    guardrails = payload["policies"]["guardrails"]
    assert isinstance(guardrails, list)
    joined = " ".join(guardrails).lower()
    assert "apache logs alone do not prove exploit success" in joined
    assert "not success proof" in joined
