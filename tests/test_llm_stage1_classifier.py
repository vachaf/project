from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from llm_client import LLMResponse
import llm_stage1_classifier as stage1


def write_llm_input(tmp_path: Path) -> Path:
    payload = {
        "meta": {
            "analysis_window": {"start": "2026-06-06T00:00:00+09:00", "end_exclusive": "2026-06-06T01:00:00+09:00"},
            "query_timezone": "Asia/Seoul",
            "counts": {"candidate_rows": 1},
        },
        "candidate_group_summary": [],
        "analysis_candidates": [
            {
                "source_table": "security",
                "log_id": 1,
                "request_id": "req-1",
                "incident_group_key": "rid:req-1",
                "src_ip": "203.0.113.10",
                "method": "GET",
                "uri": "/search",
                "query_string": "q=' OR 1=1--",
                "status_code": 403,
                "score": 10,
                "verdict_hint": "sqli",
                "reason_hints": ["sqli:or_true(+4)"],
                "merged_source_tables": ["security"],
                "merged_row_count": 1,
                "merged_log_ids": [1],
            }
        ],
    }
    path = tmp_path / "sample_llm_input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def stage1_output_text() -> str:
    return json.dumps(
        {
            "verdict": "suspicious_sqli",
            "severity": "medium",
            "confidence": "medium",
            "false_positive_possible": True,
            "reasoning_summary": "SQLi 형태의 query string이 관찰되었다.",
            "evidence_fields": ["query_string", "sqli:or_true(+4)"],
            "recommended_actions": ["review_raw_log"],
        },
        ensure_ascii=False,
    )


def stage1_output_text_for(verdict: str, severity: str = "medium") -> str:
    return json.dumps(
        {
            "verdict": verdict,
            "severity": severity,
            "confidence": "medium",
            "false_positive_possible": verdict in {"likely_false_positive", "inconclusive"},
            "reasoning_summary": f"{verdict} 분류 결과.",
            "evidence_fields": ["query_string"],
            "recommended_actions": ["review_raw_log"],
        },
        ensure_ascii=False,
    )


def write_stage1_mapping_input(tmp_path: Path) -> Path:
    candidates = [
        {
            "source_table": "security",
            "log_id": 1,
            "request_id": "req-sqli",
            "incident_group_key": "rid:req-sqli",
            "src_ip": "203.0.113.10",
            "method": "GET",
            "uri": "/search",
            "query_string": "q=' OR 1=1--",
            "status_code": 403,
            "score": 10,
            "verdict_hint": "sqli",
            "reason_hints": ["sqli:boolean_true_condition"],
            "merged_source_tables": ["security"],
            "merged_row_count": 1,
            "merged_log_ids": [1],
        },
        {
            "source_table": "security",
            "log_id": 2,
            "request_id": "req-traversal",
            "incident_group_key": "rid:req-traversal",
            "src_ip": "203.0.113.11",
            "method": "GET",
            "uri": "/download",
            "query_string": "file=../../etc/passwd",
            "status_code": 400,
            "score": 12,
            "verdict_hint": "traversal",
            "reason_hints": ["traversal:dotdot_slash(+4)"],
            "merged_source_tables": ["security"],
            "merged_row_count": 1,
            "merged_log_ids": [2],
        },
        {
            "source_table": "security",
            "log_id": 3,
            "request_id": "req-fp",
            "incident_group_key": "rid:req-fp",
            "src_ip": "203.0.113.12",
            "method": "GET",
            "uri": "/search",
            "query_string": "q=select training material",
            "status_code": 200,
            "score": 2,
            "verdict_hint": "sqli",
            "reason_hints": ["fp_hint:sql_keyword_without_attack_structure"],
            "merged_source_tables": ["security"],
            "merged_row_count": 1,
            "merged_log_ids": [3],
        },
        {
            "source_table": "security",
            "log_id": 4,
            "request_id": "req-php-wrapper",
            "incident_group_key": "rid:req-php-wrapper",
            "src_ip": "203.0.113.13",
            "method": "GET",
            "uri": "/index.php",
            "query_string": "page=php://filter/convert.base64-encode/resource=config.php",
            "status_code": 200,
            "score": 14,
            "verdict_hint": "file_disclosure",
            "reason_hints": [
                "file_disclosure:php_filter_wrapper",
                "file_disclosure:base64_source_intent",
                "file_disclosure:resource_parameter",
            ],
            "merged_source_tables": ["security"],
            "merged_row_count": 1,
            "merged_log_ids": [4],
        },
        {
            "source_table": "security",
            "log_id": 5,
            "request_id": "req-xss-admin-raw",
            "incident_group_key": "rid:req-xss-admin-raw",
            "src_ip": "203.0.113.14",
            "method": "GET",
            "uri": "/redirect",
            "query_string": "next=/admin&q=<script>alert(1)</script>",
            "status_code": 200,
            "score": 11,
            "verdict_hint": "xss",
            "reason_hints": ["xss:script_tag"],
            "merged_source_tables": ["security"],
            "merged_row_count": 1,
            "merged_log_ids": [5],
        },
        {
            "source_table": "security",
            "log_id": 6,
            "request_id": "req-sqli-admin-hint",
            "incident_group_key": "rid:req-sqli-admin-hint",
            "src_ip": "203.0.113.15",
            "method": "GET",
            "uri": "/admin/search",
            "query_string": "q=1' union select 1--",
            "status_code": 403,
            "score": 13,
            "verdict_hint": "sqli",
            "reason_hints": ["sqli:union_select", "sensitive_path:admin", "dir_probe:admin_sequence"],
            "merged_source_tables": ["security"],
            "merged_row_count": 1,
            "merged_log_ids": [6],
        },
    ]
    payload = {
        "meta": {
            "analysis_window": {"start": "2026-06-06T00:00:00+09:00", "end_exclusive": "2026-06-06T01:00:00+09:00"},
            "query_timezone": "Asia/Seoul",
            "counts": {"candidate_rows": len(candidates)},
        },
        "candidate_group_summary": [],
        "analysis_candidates": candidates,
    }
    path = tmp_path / "mapping_llm_input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def mapping_keys(mapping: dict) -> set[tuple[str, str, str]]:
    return {
        (item["standard"], item["id"], item["relationship"])
        for item in mapping["items"]
    }


def mapping_ids(mapping: dict) -> set[str]:
    return {item["id"] for item in mapping["items"]}


def private_secret_candidate() -> dict:
    return {
        "source_table": "security",
        "log_id": 51,
        "request_id": "req-private-secret",
        "incident_group_key": "rid:req-private-secret",
        "src_ip": "192.168.56.120",
        "method": "GET",
        "uri": "/private/secret.txt",
        "query_string": "",
        "status_code": 403,
        "score": 5,
        "verdict_hint": "suspicious",
        "reason_hints": [
            "error_status:403(+2)",
            "error_linked(+2)",
            "no_referer_non_browser_error(+1)",
        ],
        "raw_request": "GET /private/secret.txt HTTP/1.1",
        "raw_request_target": "/private/secret.txt",
        "user_agent": "demo-path-traversal/1.0",
        "referer": "",
        "response_body_bytes": 285,
        "resp_content_type": "text/html",
        "merged_source_tables": ["security"],
        "merged_row_count": 1,
        "merged_log_ids": [51],
    }


def test_stage1_prompt_requires_explicit_traversal_evidence_for_path_traversal() -> None:
    messages = stage1.build_messages(
        {"analysis_window": {"start": "2026-06-24T15:37:00+09:00", "end_exclusive": "2026-06-24T15:40:00+09:00"}},
        private_secret_candidate(),
        max_evidence_items=8,
    )

    system_prompt = messages[0]["content"]
    user_payload = json.loads(messages[1]["content"])
    traversal_guidance = user_payload["label_guidance"]["suspicious_path_traversal"]
    instructions = "\n".join(user_payload["instructions"])

    assert "explicit directory-escape evidence" in system_prompt
    assert "../" in system_prompt
    assert "encoded equivalent" in system_prompt
    assert "traversal reason hint" in system_prompt
    assert "directory escape" in traversal_guidance
    assert "traversal:* reason hint" in traversal_guidance
    assert "민감해 보이는 경로에 직접 요청했다는 사실만으로는 suspicious_path_traversal 을 선택하지 마라" in system_prompt
    assert "/private/secret.txt, /.env, /admin, /config.php" in instructions


def test_stage1_prompt_does_not_allow_weak_context_alone_as_traversal_evidence() -> None:
    messages = stage1.build_messages({}, private_secret_candidate(), max_evidence_items=8)

    prompt_text = messages[0]["content"] + "\n" + messages[1]["content"]

    assert "403 응답" in prompt_text
    assert "error linkage" in prompt_text
    assert "Referer 부재" in prompt_text
    assert "non-browser User-Agent" in prompt_text
    assert "directory escape 증거를 대체하지 못한다" in prompt_text
    assert "likely_false_positive 같은 보수적 verdict 를 우선 검토하라" in prompt_text


def test_stage1_does_not_add_code_based_path_traversal_fallback() -> None:
    parsed = {
        "verdict": "suspicious_path_traversal",
        "severity": "low",
        "confidence": "medium",
        "false_positive_possible": True,
        "reasoning_summary": "모델이 path traversal로 반환했다.",
        "evidence_fields": ["uri"],
        "recommended_actions": ["watch"],
    }

    normalized = stage1.maybe_normalize_file_disclosure_verdict(parsed, private_secret_candidate())

    assert normalized["verdict"] == "suspicious_path_traversal"


def test_stage1_success_artifact_includes_per_candidate_usage_and_totals(tmp_path: Path, monkeypatch) -> None:
    input_path = write_llm_input(tmp_path)
    out_dir = tmp_path / "out"

    def fake_call_llm_json(**kwargs):
        return LLMResponse(
            output_text=stage1_output_text(),
            response_id="resp_stage1",
            raw_response={
                "id": "resp_stage1",
                "usage": {
                    "input_tokens": 100,
                    "input_tokens_details": {"cached_tokens": 4},
                    "output_tokens": 25,
                    "output_tokens_details": {"reasoning_tokens": 3},
                    "total_tokens": 125,
                },
            },
            provider="openai",
            model=kwargs["model"],
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(stage1, "call_llm_json", fake_call_llm_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm_stage1_classifier.py",
            "--input",
            str(input_path),
            "--out-dir",
            str(out_dir),
            "--base-name",
            "sample",
            "--provider",
            "openai",
        ],
    )

    assert stage1.main() == 0

    payload = json.loads((out_dir / "sample_stage1_results.json").read_text(encoding="utf-8"))
    result = payload["results"][0]
    assert result["request_id"] == "req-1"
    assert result["response_id"] == "resp_stage1"
    assert result["llm_usage"]["schema_version"] == "llm_usage.v1"
    assert result["llm_usage"]["available"] is True
    assert result["llm_usage"]["call_role"] == "stage1_candidate"
    assert result["llm_usage"]["input_tokens"] == 100
    assert result["llm_usage"]["breakdown"]["cached_input_tokens"] == 4
    assert result["llm_usage"]["breakdown"]["reasoning_tokens"] == 3

    totals = payload["meta"]["llm_usage_totals"]
    assert totals["schema_version"] == "llm_usage_totals.v1"
    assert totals["available"] is True
    assert totals["call_count"] == 1
    assert totals["input_tokens"] == 100
    assert totals["output_tokens"] == 25
    assert totals["total_tokens"] == 125
    assert totals["by_provider"]["openai"]["call_count"] == 1
    assert "raw_response" not in json.dumps(payload)


def test_stage1_dry_run_marks_usage_unavailable_without_per_candidate_usage(tmp_path: Path, monkeypatch) -> None:
    input_path = write_llm_input(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm_stage1_classifier.py",
            "--input",
            str(input_path),
            "--out-dir",
            str(out_dir),
            "--base-name",
            "sample",
            "--dry-run",
        ],
    )

    assert stage1.main() == 0

    payload = json.loads((out_dir / "sample_stage1_results.json").read_text(encoding="utf-8"))
    assert "llm_usage" not in payload["candidates_preview"][0]
    assert payload["meta"]["llm_usage_totals"] == {
        "schema_version": "llm_usage_totals.v1",
        "available": False,
        "estimated": False,
        "call_count": 0,
        "unavailable_reason": "dry_run_no_provider_call",
    }


def test_stage1_artifact_rows_include_deterministic_standards_mapping(tmp_path: Path, monkeypatch) -> None:
    input_path = write_stage1_mapping_input(tmp_path)
    out_dir = tmp_path / "out"
    outputs = [
        stage1_output_text_for("suspicious_sqli"),
        stage1_output_text_for("suspicious_path_traversal"),
        stage1_output_text_for("likely_false_positive", severity="info"),
        stage1_output_text_for("suspicious_file_disclosure"),
        stage1_output_text_for("suspicious_xss"),
        stage1_output_text_for("suspicious_sqli"),
    ]
    call_index = 0
    mapping_candidates = []
    real_mapping_builder = stage1.build_security_standards_mapping

    def fake_call_llm_json(**kwargs):
        nonlocal call_index
        output_text = outputs[call_index]
        call_index += 1
        return LLMResponse(
            output_text=output_text,
            response_id=f"resp-{call_index}",
            raw_response={"id": f"resp-{call_index}", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}},
            provider="openai",
            model=kwargs["model"],
        )

    def spy_mapping_builder(stage1_result, candidate=None):
        mapping_candidates.append(candidate)
        return real_mapping_builder(stage1_result, candidate)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(stage1, "call_llm_json", fake_call_llm_json)
    monkeypatch.setattr(stage1, "build_security_standards_mapping", spy_mapping_builder)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm_stage1_classifier.py",
            "--input",
            str(input_path),
            "--out-dir",
            str(out_dir),
            "--base-name",
            "mapping",
            "--provider",
            "openai",
        ],
    )

    assert stage1.main() == 0

    payload = json.loads((out_dir / "mapping_stage1_results.json").read_text(encoding="utf-8"))
    rows = {row["request_id"]: row for row in payload["results"]}
    assert call_index == 6
    assert [candidate["request_id"] for candidate in mapping_candidates] == [
        "req-sqli",
        "req-traversal",
        "req-fp",
        "req-php-wrapper",
        "req-xss-admin-raw",
        "req-sqli-admin-hint",
    ]

    sqli_mapping = rows["req-sqli"]["standards_mapping"]
    assert ("OWASP_TOP10", "A05:2025", "direct") in mapping_keys(sqli_mapping)
    assert ("CWE", "CWE-89", "direct") in mapping_keys(sqli_mapping)
    assert ("WSTG", "WSTG-INPV-05", "direct") in mapping_keys(sqli_mapping)

    traversal_mapping = rows["req-traversal"]["standards_mapping"]
    assert ("CWE", "CWE-22", "direct") in mapping_keys(traversal_mapping)

    fp_mapping = rows["req-fp"]["standards_mapping"]
    assert fp_mapping["observability"] == "not_applicable"
    assert fp_mapping["items"] == []
    assert fp_mapping["unmapped_reason"] == "non_security_verdict"

    php_wrapper_mapping = rows["req-php-wrapper"]["standards_mapping"]
    assert ("CWE", "CWE-98", "conditional") in mapping_keys(php_wrapper_mapping)

    raw_admin_mapping = rows["req-xss-admin-raw"]["standards_mapping"]
    assert "CWE-425" not in mapping_ids(raw_admin_mapping)
    assert "WSTG-CONF-05" not in mapping_ids(raw_admin_mapping)
    assert "A01:2025" not in mapping_ids(raw_admin_mapping)

    admin_hint_mapping = rows["req-sqli-admin-hint"]["standards_mapping"]
    assert ("OWASP_TOP10", "A01:2025", "related") in mapping_keys(admin_hint_mapping)
    assert ("CWE", "CWE-425", "conditional") in mapping_keys(admin_hint_mapping)
    assert ("WSTG", "WSTG-CONF-05", "related") in mapping_keys(admin_hint_mapping)

    assert rows["req-sqli"]["verdict"] == "suspicious_sqli"
    assert rows["req-sqli"]["severity"] == "medium"
    assert rows["req-sqli"]["confidence"] == "medium"
