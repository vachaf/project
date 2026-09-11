from __future__ import annotations

import copy

import pytest

from src.prepare.shared_signal_adapter import observe_prepare_security_signals
from src.prepare_llm_input import (
    build_analysis_texts,
    evaluate_row,
    extract_raw_request_target,
    raw_text,
)


def row_for(query: str, *, request_id: str = "shared-adoption") -> dict:
    target = "/search" + ("?" + query if query else "")
    return {
        "id": 41,
        "request_id": request_id,
        "error_link_id": "",
        "log_time": "2026-09-04T12:00:00+09:00",
        "src_ip": "198.51.100.41",
        "method": "GET",
        "uri": "/search",
        "query_string": query,
        "raw_request": f"GET {target} HTTP/1.1",
        "raw_log": "",
        "status_code": 200,
        "user_agent": "Mozilla/5.0",
        "referer": "https://example.test/",
        "response_body_bytes": 0,
        "resp_content_type": "text/html",
    }


def compatibility(row: dict):
    target = extract_raw_request_target(raw_text(row.get("raw_request")))
    _, combined, _, _ = build_analysis_texts(
        raw_request=raw_text(row.get("raw_request")),
        uri=row["uri"],
        query_string=raw_text(row.get("query_string")),
        raw_request_target=target,
        raw_log=raw_text(row.get("raw_log")),
    )
    return observe_prepare_security_signals(
        row_identity={
            "source_table": "security",
            "id": row["id"],
            "request_id": row["request_id"],
            "error_link_id": row["error_link_id"],
        },
        combined_text=combined,
        raw_query_string=raw_text(row.get("query_string")),
        raw_request_target=target,
        uri=row["uri"],
    )


@pytest.mark.parametrize(
    ("query", "signal_id"),
    [
        ("q=' OR 1=1", "sql.termination_boolean_structure"),
        ("q=' UNION SELECT id,password FROM users", "sql.termination_union_structure"),
        ("x=<img src=x onerror=alert(1)>", "html.event_handler_attribute"),
        ("x=<svg onload=alert(1)>", "html.event_handler_attribute"),
        ("cmd=ok|whoami", "shell.separator_command_structure"),
        ("cmd=ok;curl example.invalid", "shell.separator_command_structure"),
        (
            "file=php://filter/convert.base64-encode/resource=config.php",
            "php.filter_resource_structure",
        ),
    ],
)
def test_positive_shared_observation_maps_to_existing_prepare_hints(
    query: str, signal_id: str
) -> None:
    row = row_for(query)
    shared = compatibility(row)
    candidate, _ = evaluate_row(copy.deepcopy(row), "security", min_score=4)

    assert signal_id in {signal["signal_id"] for signal in shared.observation["signals"]}
    assert candidate is not None
    for alternatives in shared.legacy_hint_groups:
        assert any(
            any(hint.startswith(prefix) for hint in candidate.reason_hints)
            for prefix in alternatives
        )


@pytest.mark.parametrize(
    "query",
    [
        "path=../../etc/passwd",
        "cmd=ok&&whoami",
        "cmd=$(id)",
        "cmd=bash+-c+id",
        "q=normal+search",
        "q=how+to+use+SELECT+FROM+t",
        "q=document.cookie",
        "q=url(javascript:alert())",
        "q=SELECT+x;INSERT+INTO+t+VALUES(1)",
        "q=cat+/etc/passwd",
        "q=resource=config.php",
    ],
)
def test_outside_allowlist_does_not_create_shared_observation(query: str) -> None:
    shared = compatibility(row_for(query))
    assert shared.observation["signals"] == []
    assert shared.legacy_hint_groups == ()


def test_shadow_adoption_is_deterministic_preserves_provenance_and_input() -> None:
    row = row_for("q=%2527%2520OR%25201%253D1")
    before = copy.deepcopy(row)
    first = compatibility(row)
    second = compatibility(row)

    assert row == before
    assert first == second
    assert first.observation["row_identity"]["request_id"] == row["request_id"]
    evidence = first.observation["signals"][0]["evidence"]
    assert evidence
    assert all(item["source_field"] for item in evidence)
    assert all(item["variant_id"] for item in evidence)


def test_duplicate_observations_do_not_duplicate_existing_prepare_hint() -> None:
    row = row_for("q=' OR 1=1&q=' OR 1=1")
    shared = compatibility(row)
    candidate, _ = evaluate_row(row, "security", min_score=4)

    assert len(shared.observation["signals"][0]["evidence"]) > 1
    assert candidate is not None
    assert candidate.reason_hints.count("sqli:or_true(+4)") == 1


def test_assessment_is_not_a_prepare_policy_mapping() -> None:
    shared = compatibility(row_for("q=' OR 1=1"))
    assert shared.observation["assessment"] == "review_required"
    assert not hasattr(shared, "candidate")
    assert not hasattr(shared, "verdict")
    assert not hasattr(shared, "severity")
    assert not hasattr(shared, "score")
