from __future__ import annotations

import json
from pathlib import Path

from src.prepare_llm_input import build_outputs, evaluate_row


FIXTURES = Path(__file__).parent / "fixtures" / "prepare_regression"


def build_fixture(name: str):
    payload = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return build_outputs(payload, min_score=4, min_repeat_aggregate=3, source_tables=["security"])


def test_repeated_auth_restores_representatives_and_support() -> None:
    llm_input, candidates, _, _, _ = build_fixture("f_r1_auth_behavior_context")
    assert len(candidates) == 3
    assert any(item["request_id"] == "f-r1-auth-fail-1" for item in candidates)
    support = [item for item in llm_input["supporting_events"] if item.get("supporting_role") == "auth_behavior_support"]
    assert len(support) == 1
    assert "auth_abuse:covered_by_auth_behavior_summary" in support[0]["reason_hints"]


def test_repeated_server_status_restores_one_representative_and_support() -> None:
    llm_input, candidates, _, _, _ = build_fixture("h_r3_sensitive_path_probe_context")
    assert len(candidates) == 1
    assert candidates[0]["uri"] == "/server-status"
    assert "sensitive_path:no_server_status_exposure_inference" in candidates[0]["reason_hints"]
    support = [item for item in llm_input["supporting_events"] if item.get("supporting_role") == "sensitive_path_probe_support"]
    assert len(support) == 1
    assert "sensitive_path:server_status" in support[0]["reason_hints"]
    assert "sensitive_path:covered_by_sensitive_path_probe_summary" in support[0]["reason_hints"]


def test_single_server_status_request_stays_filtered() -> None:
    payload = json.loads((FIXTURES / "h_r3_sensitive_path_probe_context.json").read_text(encoding="utf-8"))
    payload["data"]["security"] = [payload["data"]["security"][4]]
    _, candidates, _, _, _ = build_outputs(payload, min_score=4, min_repeat_aggregate=3, source_tables=["security"])
    assert candidates == []


def test_single_auth_401_request_stays_filtered() -> None:
    payload = json.loads((FIXTURES / "f_r1_auth_behavior_context.json").read_text(encoding="utf-8"))
    payload["data"]["security"] = [payload["data"]["security"][0]]
    _, candidates, _, _, _ = build_outputs(payload, min_score=4, min_repeat_aggregate=3, source_tables=["security"])
    assert candidates == []


def test_approved_path_only_webshell_candidates_and_benign_controls() -> None:
    _, candidates, _, _, filtered = build_fixture("l3_webshell_admin_tool_probe_context")
    by_id = {item["request_id"]: item for item in candidates}
    assert "webshell:script_filename" in by_id["l3-webshell-admin-1"]["reason_hints"]
    assert "webshell:known_shell_name" in by_id["l3-webshell-admin-2"]["reason_hints"]
    assert "webshell:admin_tool_probe_path" in by_id["l3-webshell-admin-3"]["reason_hints"]
    filtered_ids = {item["request_id"] for item in filtered}
    assert {"l3-webshell-benign-1", "l3-webshell-benign-2"} <= filtered_ids


def test_other_path_only_webshell_name_is_not_broadly_promoted() -> None:
    row = {
        "id": 1,
        "log_time": "2026-09-11T12:00:00+09:00",
        "src_ip": "198.51.100.10",
        "method": "GET",
        "uri": "/r57.php",
        "query_string": "",
        "status_code": 404,
        "raw_request": "GET /r57.php HTTP/1.1",
        "request_id": "unapproved-webshell-path",
        "user_agent": "Mozilla/5.0",
    }
    candidate, _ = evaluate_row(row, "security", min_score=4)
    assert candidate is None
