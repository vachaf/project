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
