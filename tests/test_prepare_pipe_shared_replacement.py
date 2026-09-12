from __future__ import annotations

import copy

import pytest

from src.prepare.shared_signal_adapter import observe_prepare_security_signals
from src.prepare_llm_input import evaluate_row


S1_COMMANDS = ("whoami", "id", "cat", "uname", "ls", "pwd")
LEGACY_ONLY_COMMANDS = (
    "who",
    "ps",
    "curl",
    "wget",
    "bash",
    "sh",
    "cmd",
    "iwr",
    "iwmi",
    "mshta",
    "dsmod",
)


def row_for(query: str = "", *, uri: str = "/search", raw_target: str | None = None) -> dict:
    target = raw_target if raw_target is not None else uri + ("?" + query if query else "")
    return {
        "id": 71,
        "request_id": "pipe-shared-replacement",
        "error_link_id": "",
        "log_time": "2026-09-12T12:00:00+09:00",
        "src_ip": "198.51.100.71",
        "method": "GET",
        "uri": uri,
        "query_string": query,
        "raw_request": f"GET {target} HTTP/1.1",
        "raw_log": "",
        "status_code": 200,
        "user_agent": "Mozilla/5.0",
        "referer": "https://example.test/",
        "response_body_bytes": 0,
        "resp_content_type": "text/html",
    }


def evaluate(query: str = "", **kwargs):
    return evaluate_row(row_for(query, **kwargs), "security", min_score=4)[0]


def pipe_hint_count(candidate) -> int:
    if candidate is None:
        return 0
    return candidate.reason_hints.count("cmdi:pipe_exec(+4)")


@pytest.mark.parametrize("command", S1_COMMANDS)
def test_shared_s1_pipe_commands_preserve_one_prepare_hit(command: str) -> None:
    candidate = evaluate(f"cmd=ok|{command}")
    assert candidate is not None
    assert pipe_hint_count(candidate) == 1


@pytest.mark.parametrize("command", LEGACY_ONLY_COMMANDS)
def test_legacy_only_pipe_commands_preserve_one_prepare_hit(command: str) -> None:
    candidate = evaluate(f"cmd=ok|{command}")
    assert candidate is not None
    assert pipe_hint_count(candidate) == 1


def test_shared_and_legacy_pipe_matches_do_not_duplicate_score_or_hint() -> None:
    shared = evaluate("cmd=ok|id")
    mixed = evaluate("cmd=ok|id|curl")
    assert shared is not None and mixed is not None
    assert pipe_hint_count(mixed) == 1
    assert mixed.score == shared.score


@pytest.mark.parametrize("query", ["cmd=whoami", "cmd=id", "cmd=cat+/etc/passwd"])
def test_bare_commands_remain_negative(query: str) -> None:
    assert pipe_hint_count(evaluate(query)) == 0


@pytest.mark.parametrize(
    ("query", "expected_hint"),
    [
        ("cmd=ok;id", "cmdi:semicolon_exec(+4)"),
        ("cmd=ok&&id", "cmdi:and_exec(+4)"),
        ("cmd=$(id)", "cmdi:subshell(+4)"),
        ("cmd=bash+-c+id", "cmdi:shell_invocation(+4)"),
    ],
)
def test_other_cmdi_grammars_are_unchanged(query: str, expected_hint: str) -> None:
    candidate = evaluate(query)
    assert candidate is not None
    assert expected_hint in candidate.reason_hints
    assert pipe_hint_count(candidate) == 0


def test_traversal_is_unchanged() -> None:
    candidate = evaluate("path=../../etc/passwd")
    assert candidate is not None
    assert "traversal:dotdot_slash(+4)" in candidate.reason_hints
    assert pipe_hint_count(candidate) == 0


@pytest.mark.parametrize("query", ["cmd=ok|id", "cmd=ok%7Cid", "cmd=ok%257Cid"])
def test_url_decode_depth_zero_one_two_preserves_pipe_result(query: str) -> None:
    candidate = evaluate(query)
    assert candidate is not None
    assert pipe_hint_count(candidate) == 1


@pytest.mark.parametrize(
    "row",
    [
        row_for("cmd=ok|id", raw_target="/search"),
        row_for("", raw_target="/search?cmd=ok|id"),
        row_for("", uri="/search|id", raw_target="/search"),
    ],
    ids=("query", "raw-target", "combined"),
)
def test_prepare_surface_boundaries_preserve_pipe_result(row: dict) -> None:
    candidate, _ = evaluate_row(row, "security", min_score=4)
    assert candidate is not None
    assert pipe_hint_count(candidate) == 1


def test_shared_rule_identity_provenance_determinism_and_input_immutability() -> None:
    row = row_for("cmd=ok%257Cid")
    before = copy.deepcopy(row)
    kwargs = {
        "row_identity": {"source_table": "security", "id": row["id"]},
        "combined_text": "GET /search?cmd=ok%257Cid HTTP/1.1 /search cmd=ok%257Cid",
        "raw_query_string": row["query_string"],
        "raw_request_target": "/search?cmd=ok%257Cid",
        "uri": row["uri"],
    }
    first = observe_prepare_security_signals(**kwargs)
    second = observe_prepare_security_signals(**kwargs)
    evaluate_row(row, "security", min_score=4)

    assert row == before
    assert first == second
    signal = next(
        item for item in first.observation["signals"]
        if item["rule_id"] == "legacy.cmdi.pipe_exec.v1"
    )
    assert signal["signal_id"] == "shell.separator_command_structure"
    assert signal["evidence"]
    assert all(item["source_field"] and item["variant_id"] for item in signal["evidence"])
