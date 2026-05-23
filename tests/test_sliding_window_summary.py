from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "src" / "sliding_window_summary.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sliding_window_summary", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["sliding_window_summary"] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def make_window_dir(tmp_path: Path) -> Path:
    window_dir = tmp_path / "data/windowed/2026-05-24/sw_0200_0300"
    export_payload = {
        "meta": {
            "database": "web_logs",
            "query_timezone": "Asia/Seoul",
            "start": "2026-05-24T02:00:00.000+09:00",
            "end_exclusive": "2026-05-24T03:00:00.000+09:00",
            "table_option": "security",
            "total_count": 14,
        },
        "counts": {"access": 0, "security": 14, "error": 0},
        "data": {"security": []},
    }
    llm_input_payload = {
        "meta": {
            "query_timezone": "Asia/Seoul",
            "analysis_window": {
                "start": "2026-05-24T02:00:00.000+09:00",
                "end_exclusive": "2026-05-24T03:00:00.000+09:00",
            },
            "source_database": "web_logs",
            "source_table_option": "security",
            "selected_source_tables": ["security"],
            "analysis_primary_table": "security",
            "counts": {
                "total_exported_rows": 14,
                "selected_source_rows": 14,
                "filtered_out_rows": 9,
                "filtered_out_non_aggregated_rows": 9,
                "noise_group_count": 0,
                "candidate_rows_before_dedup": 5,
                "candidate_rows": 5,
                "candidate_duplicate_rows_removed": 0,
                "distinct_incident_candidates": 5,
                "supporting_events": 0,
                "ip_behavior_aggregates": 1,
                "protocol_anomaly_summaries": 1,
            },
            "filtered_out_breakdown": {"benign_normal_search": 9},
        }
    }
    candidates = [
        {
            "request_id": "rid-login",
            "src_ip": "192.168.56.1",
            "method": "POST",
            "uri": "/login.php",
            "status_code": 401,
            "score": 6,
            "verdict_hint": "suspicious",
            "reason_hints": [
                "xss:external_navigation",
                "error_status:401(+2)",
                "error_linked(+2)",
                "login_endpoint(+1)",
                "auth_payload_content_type(+1)",
            ],
            "raw_log": "must not be copied",
            "raw_request": "POST /login.php HTTP/1.1",
            "user_agent": "browser",
            "referer": "http://example.test/login.php",
        },
        {
            "request_id": "rid-upload",
            "src_ip": "192.168.56.1",
            "method": "POST",
            "uri": "/upload.php",
            "status_code": 400,
            "score": 5,
            "verdict_hint": "suspicious",
            "reason_hints": ["sqli:sql_comment", "upload:multipart(+1)", "error_status:400(+2)"],
        },
    ]
    write_json(window_dir / "export.json", export_payload)
    write_json(window_dir / "llm_input.json", llm_input_payload)
    write_json(window_dir / "analysis_candidates.json", candidates)
    write_json(window_dir / "noise_summary.json", [])
    return window_dir


def make_window_plan() -> dict:
    return {
        "window_id": "sw_0200_0300",
        "start": "2026-05-24T02:00:00+09:00",
        "end": "2026-05-24T03:00:00+09:00",
        "duration_minutes": 60,
        "is_partial": False,
    }


def test_build_window_summary_v1_from_window_dir(tmp_path: Path):
    module = load_module()
    window_dir = make_window_dir(tmp_path)

    summary = module.build_window_summary_from_dir(make_window_plan(), window_dir)

    assert summary["schema"] == "sliding_window_summary_v1"
    assert summary["window"] == {
        "window_id": "sw_0200_0300",
        "start": "2026-05-24T02:00:00+09:00",
        "end_exclusive": "2026-05-24T03:00:00+09:00",
        "timezone": "Asia/Seoul",
        "duration_minutes": 60,
        "is_partial": False,
    }

    assert summary["artifact_status"]["export"] == {"path": "export.json", "exists": True}
    assert summary["artifact_status"]["llm_input"] == {"path": "llm_input.json", "exists": True}
    assert summary["artifact_status"]["analysis_candidates"] == {"path": "analysis_candidates.json", "exists": True}
    assert summary["artifact_status"]["noise_summary"] == {"path": "noise_summary.json", "exists": True}
    assert summary["artifact_status"]["window_summary"] == {"path": "window_summary.json", "exists": False}

    assert summary["source"] == {
        "database": "web_logs",
        "table_option": "security",
        "selected_source_tables": ["security"],
        "analysis_primary_table": "security",
    }

    assert summary["counts"]["export"] == {"access": 0, "security": 14, "error": 0, "total": 14}
    assert summary["counts"]["prepare"]["candidate_rows"] == 5
    assert summary["counts"]["prepare"]["noise_group_count"] == 0
    assert summary["counts"]["prepare"]["context_summary_count"] == 2

    assert summary["distributions"]["candidate_status_code"] == {"400": 1, "401": 1}
    assert summary["distributions"]["candidate_method"] == {"POST": 2}
    assert summary["distributions"]["candidate_verdict_hint"] == {"suspicious": 2}
    assert summary["distributions"]["candidate_src_ip"] == {"192.168.56.1": 2}
    assert summary["distributions"]["candidate_uri"] == {"/login.php": 1, "/upload.php": 1}
    assert summary["distributions"]["candidate_reason_hint_prefix"] == {
        "auth_payload_content_type": 1,
        "error_linked": 1,
        "error_status": 2,
        "login_endpoint": 1,
        "sqli": 1,
        "upload": 1,
        "xss": 1,
    }
    assert summary["distributions"]["filtered_out_breakdown"] == {"benign_normal_search": 9}

    assert summary["candidate_index"] == [
        {
            "request_id": "rid-login",
            "src_ip": "192.168.56.1",
            "method": "POST",
            "uri": "/login.php",
            "status_code": 401,
            "score": 6,
            "verdict_hint": "suspicious",
            "reason_hint_prefixes": [
                "xss",
                "error_status",
                "error_linked",
                "login_endpoint",
                "auth_payload_content_type",
            ],
        },
        {
            "request_id": "rid-upload",
            "src_ip": "192.168.56.1",
            "method": "POST",
            "uri": "/upload.php",
            "status_code": 400,
            "score": 5,
            "verdict_hint": "suspicious",
            "reason_hint_prefixes": ["sqli", "upload", "error_status"],
        },
    ]

    forbidden = repr(summary["candidate_index"])
    assert "raw_log" not in forbidden
    assert "raw_request" not in forbidden
    assert "user_agent" not in forbidden
    assert "referer" not in forbidden

    assert summary["rollup_hints"] == {
        "has_candidates": True,
        "has_noise_groups": False,
        "has_supporting_events": False,
        "has_context_summaries": True,
        "candidate_request_ids": ["rid-login", "rid-upload"],
    }
    assert summary["guardrails"] == {
        "summary_only": True,
        "no_new_security_verdict": True,
        "no_success_inference": True,
        "no_body_inference": True,
        "no_context_promotion": True,
    }


def test_write_window_summary_creates_json_file(tmp_path: Path):
    module = load_module()
    window_dir = make_window_dir(tmp_path)

    output_path = module.write_window_summary(make_window_plan(), window_dir)

    assert output_path == window_dir / "window_summary.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "sliding_window_summary_v1"
    assert payload["artifact_status"]["window_summary"] == {"path": "window_summary.json", "exists": True}
