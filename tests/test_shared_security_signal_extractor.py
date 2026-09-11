from __future__ import annotations

import copy
import json

import pytest

from src.security_signals import (
    ExtractionBudget,
    ExtractorInputError,
    SignalSurface,
    extract_security_signals,
)


def extract(text: str, **kwargs: object) -> dict[str, object]:
    return extract_security_signals(
        row_identity={"source_table": "security", "id": 17, "request_id": "req-17"},
        input_profile="prepare_compat_v1",
        surfaces=[SignalSurface("request_target", text)],
        **kwargs,
    )


@pytest.mark.parametrize(
    ("text", "signal_id"),
    [
        ("/search?q=' OR 1=1", "sql.termination_boolean_structure"),
        ("/item?q=' UNION SELECT id,password FROM users", "sql.termination_union_structure"),
        ("/x?q=<img src=x onerror=alert(1)>", "html.event_handler_attribute"),
        ("/x?q=<svg onload=alert(1)>", "html.event_handler_attribute"),
        ("/run?q=ok|whoami", "shell.separator_command_structure"),
        ("/run?q=ok;curl example.invalid", "shell.separator_command_structure"),
        (
            "/view?file=php://filter/convert.base64-encode/resource=config.php",
            "php.filter_resource_structure",
        ),
    ],
)
def test_approved_allowlist_positive_cases(text: str, signal_id: str) -> None:
    result = extract(text)
    assert signal_id in [signal["signal_id"] for signal in result["signals"]]
    assert result["processing_status"] == "complete"
    assert result["assessment"] == "review_required"


@pytest.mark.parametrize(
    "text",
    [
        "/docs?q=normal+search",
        "/docs?q=;environment",
        "/docs?q=document.cookie",
        "/docs?q=url(javascript:alert())",
        "/query?q=SELECT value;INSERT INTO audit VALUES(1)",
        "/docs?q=cat /etc/passwd",
        "/docs?q=$(id)",
        "/docs?q=ok&&whoami",
        "/docs?q=bash -c id",
    ],
)
def test_benign_and_outside_allowlist_controls_emit_no_signal(text: str) -> None:
    result = extract(text)
    assert result["signals"] == []
    assert result["processing_status"] == "complete"
    assert result["assessment"] == "no_signal"


@pytest.mark.parametrize(
    "text",
    ["/../../etc/passwd", "/..%2f..%2fetc/passwd", r"/..\windows\win.ini", "/.../secret"],
)
def test_traversal_is_not_in_the_first_allowlist(text: str) -> None:
    result = extract(text)
    assert result["signals"] == []
    assert all("traversal" not in rule for rule in result["observation_scope"]["applied_rule_ids"])


def test_output_is_deterministic_and_repeated_result_is_identical() -> None:
    surfaces = [
        SignalSurface("request_target", "/x?q=%2527%2520OR%25201%253D1"),
        SignalSurface("uri", "/x?q=<svg onload=alert(1)>", derived_from="request_target"),
    ]
    first = extract_security_signals(
        row_identity={"id": 1}, input_profile="live_target_v1", surfaces=surfaces
    )
    second = extract_security_signals(
        row_identity={"id": 1}, input_profile="live_target_v1", surfaces=surfaces
    )
    assert first == second
    assert json.dumps(first, ensure_ascii=False, separators=(",", ":")) == json.dumps(
        second, ensure_ascii=False, separators=(",", ":")
    )


def test_provenance_and_row_identity_are_preserved_without_input_mutation() -> None:
    identity = {"source_table": "security", "id": 5, "request_id": None}
    surfaces = [SignalSurface("request_target", "/?q=%27%20OR%201%3D1", surface="query", derived_from="request_target")]
    identity_before = copy.deepcopy(identity)
    surfaces_before = copy.deepcopy(surfaces)
    result = extract_security_signals(
        row_identity=identity, input_profile="live_target_v1", surfaces=surfaces
    )
    assert identity == identity_before
    assert surfaces == surfaces_before
    assert result["row_identity"] == identity
    evidence = result["signals"][0]["evidence"][0]
    assert evidence["source_field"] == "request_target"
    assert evidence["surface"] == "query"
    assert evidence["derived_from"] == "request_target"
    assert evidence["decode_type"] == "url_decode"
    assert evidence["decode_depth"] == 1
    assert evidence["variant_id"] == "surface-0:url-1"
    assert evidence["parent_variant_id"] == "surface-0:raw"
    assert evidence["transforms"] == ["url_decode"]
    assert evidence["span"]["coordinate_system"] == "variant_codepoints"


def test_stable_rule_surface_variant_and_position_ordering() -> None:
    result = extract_security_signals(
        row_identity={"id": 1},
        input_profile="prepare_compat_v1",
        surfaces=[
            SignalSurface("request_target", "/?q=<svg onload=x>|id;whoami"),
            SignalSurface("query_string", "' OR 1=1 ' UNION SELECT a,b"),
        ],
    )
    assert [signal["signal_id"] for signal in result["signals"]] == [
        "sql.termination_boolean_structure",
        "sql.termination_union_structure",
        "html.event_handler_attribute",
        "shell.separator_command_structure",
        "shell.separator_command_structure",
    ]
    shell_evidence = result["signals"][3]["evidence"] + result["signals"][4]["evidence"]
    assert [item["matched_text"] for item in shell_evidence] == ["|id", ";whoami"]


def test_duplicate_text_with_distinct_provenance_is_preserved() -> None:
    result = extract_security_signals(
        row_identity={"id": 1},
        input_profile="prepare_compat_v1",
        surfaces=[
            SignalSurface("request_target", "/?q=' OR 1=1"),
            SignalSurface("query_string", "/?q=' OR 1=1"),
        ],
    )
    evidence = result["signals"][0]["evidence"]
    assert [item["source_field"] for item in evidence] == ["request_target", "query_string"]


def test_structure_fragments_from_different_surfaces_are_not_combined() -> None:
    result = extract_security_signals(
        row_identity={"id": 1},
        input_profile="prepare_compat_v1",
        surfaces=[
            SignalSurface("request_target", "php://filter/convert.base64-encode/"),
            SignalSurface("query_string", "resource=config.php"),
        ],
    )
    assert result["signals"] == []


def test_processing_and_assessment_remain_independent_when_partially_observed() -> None:
    result = extract(
        "/?q=' OR 1=1 and trailing-data",
        budget=ExtractionBudget(max_input_codepoints_per_surface=13),
    )
    assert result["processing_status"] == "partial"
    assert result["assessment"] == "review_required"
    assert result["signals"]
    assert "input_truncated" in result["reason_codes"]


def test_partial_without_signal_is_undetermined_not_no_signal() -> None:
    result = extract(
        "/ordinary/path/with/trailing-data",
        budget=ExtractionBudget(max_input_codepoints_per_surface=8),
    )
    assert result["processing_status"] == "partial"
    assert result["assessment"] == "undetermined"
    assert result["signals"] == []


def test_signal_and_evidence_caps_are_explicit_and_preserve_found_evidence() -> None:
    result = extract(
        "/?a=' OR 1=1&b=' OR 2=2&x=<img onerror=x>",
        budget=ExtractionBudget(max_signals=1, max_evidence_per_signal=1),
    )
    assert len(result["signals"]) == 1
    assert len(result["signals"][0]["evidence"]) == 1
    assert result["processing_status"] == "partial"
    assert result["assessment"] == "review_required"
    assert "output_evidence_budget_exceeded" in result["reason_codes"]
    assert "output_signal_budget_exceeded" in result["reason_codes"]


def test_variant_budget_boundary_is_reported_without_false_no_signal() -> None:
    result = extract(
        "/?q=%2527%2520OR%25201%253D1",
        budget=ExtractionBudget(max_variants_per_surface=1),
    )
    assert result["signals"] == []
    assert result["processing_status"] == "partial"
    assert result["assessment"] == "undetermined"
    assert result["reason_codes"] == ["variant_budget_exceeded"]


def test_no_candidate_verdict_severity_or_score_is_created() -> None:
    result = extract("/?q=' OR 1=1")
    forbidden = {"candidate", "verdict", "verdict_hint", "severity", "score", "confidence"}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            assert forbidden.isdisjoint(value)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(result)


def test_empty_surface_is_unavailable_and_not_no_signal() -> None:
    result = extract_security_signals(
        row_identity={"id": 1},
        input_profile="live_target_v1",
        surfaces=[SignalSurface("request_target", "")],
    )
    assert result["processing_status"] == "unavailable"
    assert result["assessment"] == "undetermined"
    assert result["reason_codes"] == ["no_observable_surface"]


@pytest.mark.parametrize(
    "call",
    [
        lambda: extract_security_signals(row_identity=[], input_profile="live_target_v1", surfaces=[]),
        lambda: extract_security_signals(row_identity={"id": []}, input_profile="live_target_v1", surfaces=[]),
        lambda: extract_security_signals(row_identity={}, input_profile="unknown", surfaces=[]),
        lambda: extract_security_signals(row_identity={}, input_profile="live_target_v1", surfaces="bad"),
        lambda: SignalSurface("", "text"),
        lambda: SignalSurface("uri", None),
        lambda: ExtractionBudget(max_signals=0),
    ],
)
def test_malformed_input_is_rejected(call: object) -> None:
    with pytest.raises(ExtractorInputError):
        call()


def test_json_serialization_round_trip_preserves_type_and_value() -> None:
    result = extract("/?q=<img src=x onerror=alert(1)>")
    restored = json.loads(json.dumps(result, ensure_ascii=False))
    assert restored == result
