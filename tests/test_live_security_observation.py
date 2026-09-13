from __future__ import annotations

import json
from pathlib import Path

import pytest

import web.services.live_security_observation as adapter


BASE_ROW = {
    "id": 7,
    "request_id": "req-7",
    "request_target": "/",
    "uri": "/",
}


def observation(request_target: str | None, uri: str | None = "/") -> dict:
    return adapter.observe_live_security_signals(
        {**BASE_ROW, "request_target": request_target, "uri": uri}
    )


def test_exact_signal_to_adoption_rule_mapping_is_frozen() -> None:
    assert adapter.PROCESSING_STATUSES == {
        "complete",
        "partial",
        "unavailable",
        "error",
    }
    assert adapter.ASSESSMENTS == {
        "review_required",
        "no_signal",
        "undetermined",
    }
    assert adapter.LIVE_ADOPTION_RULE_BY_SIGNAL == {
        "sql.termination_boolean_structure": "live.sql.termination_boolean.v1",
        "sql.termination_union_structure": "live.sql.termination_union.v1",
        "html.event_handler_attribute": "live.html.event_handler_attribute.v1",
        "shell.separator_command_structure": "live.shell.separator_command.v1",
        "php.filter_resource_structure": "live.php.filter_resource.v1",
    }


@pytest.mark.parametrize(
    ("request_target", "signal_id", "adoption_rule_id"),
    [
        (
            "/search?q=%27%20OR%201%3D1",
            "sql.termination_boolean_structure",
            "live.sql.termination_boolean.v1",
        ),
        (
            "/search?q=' UNION SELECT username,password",
            "sql.termination_union_structure",
            "live.sql.termination_union.v1",
        ),
        (
            "/search?q=<img src=x onerror=alert(1)>",
            "html.event_handler_attribute",
            "live.html.event_handler_attribute.v1",
        ),
        (
            "/search?q=hello;whoami",
            "shell.separator_command_structure",
            "live.shell.separator_command.v1",
        ),
        (
            "/view?file=php://filter/convert.base64-encode/resource=index.php",
            "php.filter_resource_structure",
            "live.php.filter_resource.v1",
        ),
    ],
)
def test_approved_positive_structures_use_exact_adoption_mapping(
    request_target: str, signal_id: str, adoption_rule_id: str
) -> None:
    result = observation(request_target)
    selected = [signal for signal in result["signals"] if signal["signal_id"] == signal_id]
    assert len(selected) == 1
    assert selected[0]["adoption_rule_id"] == adoption_rule_id
    assert selected[0]["evidence"]
    assert result["processing_status"] == "complete"
    assert result["assessment"] == "review_required"


@pytest.mark.parametrize(
    "request_target",
    [
        "/download?file=../../etc/passwd",
        "/search?q=document.cookie",
        "/search?q=url(javascript:alert())",
        "/search?q=hello;environment",
        "/search?q=';INSERT INTO audit VALUES(1)",
        "/view?resource=index.php",
        "/view?a=php://filter&b=convert.base64-encode&resource=index.php",
    ],
)
def test_deferred_bare_and_unrelated_parameter_cases_are_not_adopted(
    request_target: str,
) -> None:
    result = observation(request_target)
    assert result["signals"] == []
    assert result["processing_status"] == "complete"
    assert result["assessment"] == "no_signal"


def test_future_family_members_and_rules_are_not_automatically_adopted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_extract_security_signals(**_kwargs):
        return {
            "detector_version": "shared_security_signal_extractor.v1",
            "processing_status": "complete",
            "assessment": "review_required",
            "reason_codes": [],
            "signals": [
                {
                    "signal_id": "sql.future_family_signal",
                    "rule_id": "future.sql.rule.v1",
                    "evidence": [],
                },
                {
                    "signal_id": "html.event_handler_attribute",
                    "rule_id": "future.xss.event_handler.v1",
                    "evidence": [{"matched_text": "<video onloadstart=>"}],
                },
            ],
        }

    monkeypatch.setattr(adapter, "extract_security_signals", fake_extract_security_signals)
    result = observation("/search?q=<video onloadstart=>")
    assert result["signals"] == []
    assert result["processing_status"] == "complete"
    assert result["assessment"] == "no_signal"


def test_live_uses_only_current_page_select_surfaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_extract_security_signals(**kwargs):
        captured.update(kwargs)
        return {
            "detector_version": "shared_security_signal_extractor.v1",
            "processing_status": "complete",
            "assessment": "no_signal",
            "reason_codes": [],
            "signals": [],
        }

    monkeypatch.setattr(adapter, "extract_security_signals", fake_extract_security_signals)
    result = observation("/search?q=value", "/search")
    surfaces = captured["surfaces"]
    assert [
        (surface.source_field, surface.surface, surface.derived_from)
        for surface in surfaces
    ] == [
        ("request_target", "request_target", None),
        ("request_target", "query", "request_target"),
        ("uri", "uri", None),
    ]
    assert not {"raw_request", "query_string", "raw_log"}.intersection(
        surface.source_field for surface in surfaces
    )
    assert result["scope"]["observed_fields"] == ["request_target", "uri"]


def test_processing_status_and_assessment_remain_independent() -> None:
    complete = observation("/clean", None)
    assert (complete["processing_status"], complete["assessment"]) == (
        "complete",
        "no_signal",
    )

    partial = observation(None, "/clean")
    assert (partial["processing_status"], partial["assessment"]) == (
        "partial",
        "undetermined",
    )
    assert "request_target_missing" in partial["reason_codes"]

    unavailable = observation(None, None)
    assert (unavailable["processing_status"], unavailable["assessment"]) == (
        "unavailable",
        "undetermined",
    )


def test_input_truncation_never_becomes_no_signal() -> None:
    result = observation("/clean?value=" + "a" * 5000)
    assert result["processing_status"] == "partial"
    assert result["assessment"] == "undetermined"
    assert result["scope"]["input_truncated"] is True

    with_signal = observation("/?q=' OR 1=1&padding=" + "a" * 5000)
    assert with_signal["processing_status"] == "partial"
    assert with_signal["assessment"] == "review_required"
    assert with_signal["signals"]


def test_detector_exception_is_isolated_to_the_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_kwargs):
        raise RuntimeError("detector unavailable")

    monkeypatch.setattr(adapter, "extract_security_signals", fail)
    result = observation("/search?q=' OR 1=1")
    assert result["processing_status"] == "error"
    assert result["assessment"] == "undetermined"
    assert result["signals"] == []


def test_schema_is_bounded_and_contains_no_decision_fields() -> None:
    result = observation(
        "/?a=' OR 1=1&b=' UNION SELECT a,b&c=<svg onload=x>&d=x|cat /etc/hosts"
    )
    adapter.validate_live_observation(result)
    encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")
    assert len(encoded) <= adapter.MAX_OBSERVATION_BYTES
    forbidden = {
        "score",
        "score_boost",
        "severity",
        "verdict",
        "verdict_hint",
        "confidence",
        "candidate",
    }

    def keys(value):
        if isinstance(value, dict):
            yield from value
            for item in value.values():
                yield from keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from keys(item)

    assert forbidden.isdisjoint(keys(result))


def test_live_adoption_imports_no_pipeline_or_decision_policy() -> None:
    source = "\n".join(
        Path(path).read_text()
        for path in (
            "web/services/live_security_observation.py",
            "web/services/live_log_service.py",
        )
    ).lower()
    for forbidden_import in (
        "prepare_llm_input",
        "llm_stage1_classifier",
        "llm_stage2_reporter",
        "analysis_job_worker",
        "run_analysis_pipeline",
        "security_standards_mapping",
    ):
        assert forbidden_import not in source
