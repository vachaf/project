"""Live-only adoption of shared security-signal observations.

The adapter is deliberately additive and read-only.  It consumes only fields
already returned by the Live page SELECT and does not make a security verdict.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from src.security_signals import (
    ASSESSMENTS,
    PROCESSING_STATUSES,
    ExtractionBudget,
    SignalSurface,
    extract_security_signals,
)

LIVE_OBSERVATION_SCHEMA_VERSION = "live_observation.v1"
LIVE_ADOPTION_POLICY_VERSION = "live_allowlist.v1"
LIVE_INPUT_PROFILE = "live_target_v1"
MAX_INPUT_CODEPOINTS = 4096
MAX_VARIANTS_PER_SURFACE = 6
MAX_TOTAL_VARIANT_CODEPOINTS = 73_728
MAX_SIGNALS = 16
MAX_EVIDENCE_PER_SIGNAL = 4
MAX_EVIDENCE_TEXT_CODEPOINTS = 256
MAX_OBSERVATION_BYTES = 16 * 1024

# Exact IDs are intentional.  A new extractor signal or rule is not adopted
# merely because it belongs to an already represented family.
LIVE_ADOPTION_RULE_BY_SIGNAL = {
    "sql.termination_boolean_structure": "live.sql.termination_boolean.v1",
    "sql.termination_union_structure": "live.sql.termination_union.v1",
    "html.event_handler_attribute": "live.html.event_handler_attribute.v1",
    "shell.separator_command_structure": "live.shell.separator_command.v1",
    "php.filter_resource_structure": "live.php.filter_resource.v1",
}

_ALLOWED_RULE_IDS_BY_SIGNAL = {
    "sql.termination_boolean_structure": frozenset(
        {"legacy.sql.termination_boolean.v1"}
    ),
    "sql.termination_union_structure": frozenset(
        {"legacy.sql.termination_union_columns.v1"}
    ),
    "html.event_handler_attribute": frozenset(
        {"legacy.xss.img_onerror.v1", "legacy.xss.svg_onload.v1"}
    ),
    "shell.separator_command_structure": frozenset(
        {"legacy.cmdi.pipe_exec.v1", "legacy.cmdi.semicolon_exec.v1"}
    ),
    "php.filter_resource_structure": frozenset(
        {"legacy.file.php_filter_resource.v1"}
    ),
}

_LIVE_BUDGET = ExtractionBudget(
    max_input_codepoints_per_surface=MAX_INPUT_CODEPOINTS,
    max_variants_per_surface=MAX_VARIANTS_PER_SURFACE,
    max_total_variant_codepoints=MAX_TOTAL_VARIANT_CODEPOINTS,
    max_signals=MAX_SIGNALS,
    max_evidence_per_signal=MAX_EVIDENCE_PER_SIGNAL,
)

_EXCLUDED_FIELDS = ["request_body", "response_body", "other_headers"]
_VARIANT_REASON_CODES = {
    "variant_budget_exceeded",
    "variant_codepoint_budget_exceeded",
}
_OUTPUT_REASON_CODES = {
    "output_signal_budget_exceeded",
    "output_evidence_budget_exceeded",
    "output_size_budget_exceeded",
}
_FORBIDDEN_KEYS = {
    "score",
    "score_boost",
    "severity",
    "verdict",
    "verdict_hint",
    "confidence",
    "candidate",
}


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _append_reason(reason_codes: list[str], reason: str) -> None:
    if reason not in reason_codes:
        reason_codes.append(reason)


def _scope(
    *,
    request_target: str,
    uri: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    observed_fields = []
    missing_fields = []
    for name, value in (("request_target", request_target), ("uri", uri)):
        (observed_fields if value else missing_fields).append(name)
    return {
        "profile": LIVE_INPUT_PROFILE,
        "observed_fields": observed_fields,
        "missing_fields": missing_fields,
        "excluded_fields": list(_EXCLUDED_FIELDS),
        "input_truncated": "input_truncated" in reason_codes,
        "variant_truncated": bool(_VARIANT_REASON_CODES.intersection(reason_codes)),
        "output_truncated": bool(_OUTPUT_REASON_CODES.intersection(reason_codes)),
    }


def _assessment(processing_status: str, has_signals: bool) -> str:
    if processing_status == "complete":
        return "review_required" if has_signals else "no_signal"
    if processing_status == "partial" and has_signals:
        return "review_required"
    return "undetermined"


def _project_evidence(value: Mapping[str, Any]) -> dict[str, Any]:
    matched_text = _text(value.get("matched_text"))
    return {
        "source_field": value.get("source_field"),
        "surface": value.get("surface"),
        "derived_from": value.get("derived_from"),
        "variant_id": value.get("variant_id"),
        "parent_variant_id": value.get("parent_variant_id"),
        "decode_type": value.get("decode_type"),
        "decode_depth": value.get("decode_depth"),
        "transforms": list(value.get("transforms") or ()),
        "span": dict(value.get("span") or {}),
        "matched_text": matched_text[:MAX_EVIDENCE_TEXT_CODEPOINTS],
    }


def _evidence_is_adoptable(signal_id: str, value: Mapping[str, Any]) -> bool:
    if signal_id != "php.filter_resource_structure":
        return True
    # The shared compatibility fact preserves the legacy whole-surface match.
    # Live narrows adoption so wrapper/filter/resource cannot be assembled from
    # separate query parameters.
    matched_text = _text(value.get("matched_text")).lower()
    return any(
        "php://filter" in component
        and "convert.base64-encode" in component
        and "resource=" in component
        for component in matched_text.split("&")
    )


def _adopt_signals(
    shared_signals: Any, reason_codes: list[str]
) -> list[dict[str, Any]]:
    adopted: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    if not isinstance(shared_signals, list):
        return []

    for shared_signal in shared_signals:
        if not isinstance(shared_signal, Mapping):
            continue
        signal_id = shared_signal.get("signal_id")
        rule_id = shared_signal.get("rule_id")
        adoption_rule_id = LIVE_ADOPTION_RULE_BY_SIGNAL.get(signal_id)
        if adoption_rule_id is None:
            continue
        if rule_id not in _ALLOWED_RULE_IDS_BY_SIGNAL[signal_id]:
            continue
        if signal_id not in adopted:
            if len(order) >= MAX_SIGNALS:
                _append_reason(reason_codes, "output_signal_budget_exceeded")
                continue
            adopted[signal_id] = {
                "signal_id": signal_id,
                "adoption_rule_id": adoption_rule_id,
                "rule_ids": [],
                "evidence": [],
                "references": [],
            }
            order.append(signal_id)
        projected = adopted[signal_id]
        if rule_id not in projected["rule_ids"]:
            projected["rule_ids"].append(rule_id)
        for evidence in shared_signal.get("evidence") or ():
            if not isinstance(evidence, Mapping) or not _evidence_is_adoptable(
                signal_id, evidence
            ):
                continue
            if len(projected["evidence"]) >= MAX_EVIDENCE_PER_SIGNAL:
                _append_reason(reason_codes, "output_evidence_budget_exceeded")
                break
            projected["evidence"].append(_project_evidence(evidence))
    return [adopted[signal_id] for signal_id in order if adopted[signal_id]["evidence"]]


def _observation_size(value: Mapping[str, Any]) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _enforce_output_cap(observation: dict[str, Any]) -> None:
    if _observation_size(observation) <= MAX_OBSERVATION_BYTES:
        return
    _append_reason(observation["reason_codes"], "output_size_budget_exceeded")
    for signal in observation["signals"]:
        signal["evidence"] = signal["evidence"][:1]
    observation["scope"]["output_truncated"] = True
    observation["processing_status"] = "partial"
    observation["assessment"] = _assessment("partial", bool(observation["signals"]))
    if _observation_size(observation) > MAX_OBSERVATION_BYTES:
        for signal in observation["signals"]:
            for evidence in signal["evidence"]:
                evidence["matched_text"] = evidence["matched_text"][:64]


def _error_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    request_target = _text(row.get("request_target"))
    uri = _text(row.get("uri"))
    reasons = ["detector_error"]
    return {
        "schema_version": LIVE_OBSERVATION_SCHEMA_VERSION,
        "detector_version": "shared_security_signal_extractor.v1",
        "adoption_policy_version": LIVE_ADOPTION_POLICY_VERSION,
        "processing_status": "error",
        "assessment": "undetermined",
        "reason_codes": reasons,
        "scope": _scope(
            request_target=request_target, uri=uri, reason_codes=reasons
        ),
        "signals": [],
    }


def observe_live_security_signals(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the versioned Live observation for one repository row."""

    request_target = _text(row.get("request_target"))
    uri = _text(row.get("uri"))
    bounded_target = request_target[:MAX_INPUT_CODEPOINTS]
    surfaces: list[SignalSurface] = []
    if request_target:
        surfaces.append(
            SignalSurface("request_target", request_target, surface="request_target")
        )
        if "?" in bounded_target:
            surfaces.append(
                SignalSurface(
                    "request_target",
                    bounded_target.split("?", 1)[1],
                    surface="query",
                    derived_from="request_target",
                )
            )
    if uri:
        surfaces.append(SignalSurface("uri", uri, surface="uri"))

    try:
        shared = extract_security_signals(
            row_identity={
                "row_id": row.get("id"),
                "request_id": row.get("request_id"),
            },
            input_profile=LIVE_INPUT_PROFILE,
            surfaces=surfaces,
            budget=_LIVE_BUDGET,
        )
        reason_codes = list(shared["reason_codes"])
        signals = _adopt_signals(shared.get("signals"), reason_codes)
        processing_status = str(shared["processing_status"])
        if processing_status in {"unavailable", "error"}:
            signals = []
        if not request_target and uri:
            _append_reason(reason_codes, "request_target_missing")
            processing_status = "partial"
        elif not request_target and not uri:
            processing_status = "unavailable"
        elif reason_codes:
            processing_status = "partial"
        observation = {
            "schema_version": LIVE_OBSERVATION_SCHEMA_VERSION,
            "detector_version": str(shared["detector_version"]),
            "adoption_policy_version": LIVE_ADOPTION_POLICY_VERSION,
            "processing_status": processing_status,
            "assessment": _assessment(processing_status, bool(signals)),
            "reason_codes": reason_codes,
            "scope": _scope(
                request_target=request_target,
                uri=uri,
                reason_codes=reason_codes,
            ),
            "signals": signals,
        }
        _enforce_output_cap(observation)
        validate_live_observation(observation)
        return observation
    except Exception:
        return _error_observation(row)


def validate_live_observation(value: Mapping[str, Any]) -> None:
    """Validate the narrow runtime schema without importing policy engines."""

    required = {
        "schema_version",
        "detector_version",
        "adoption_policy_version",
        "processing_status",
        "assessment",
        "reason_codes",
        "scope",
        "signals",
    }
    if set(value) != required:
        raise ValueError("invalid Live observation fields")
    if value["schema_version"] != LIVE_OBSERVATION_SCHEMA_VERSION:
        raise ValueError("invalid Live observation schema version")
    if value["adoption_policy_version"] != LIVE_ADOPTION_POLICY_VERSION:
        raise ValueError("invalid Live adoption policy version")
    if value["processing_status"] not in PROCESSING_STATUSES:
        raise ValueError("invalid Live processing status")
    if value["assessment"] not in ASSESSMENTS:
        raise ValueError("invalid Live assessment")
    if value["processing_status"] == "complete" and value["signals"]:
        expected_assessment = "review_required"
    elif value["processing_status"] == "complete":
        expected_assessment = "no_signal"
    elif value["processing_status"] == "partial" and value["signals"]:
        expected_assessment = "review_required"
    else:
        expected_assessment = "undetermined"
    if value["assessment"] != expected_assessment:
        raise ValueError("invalid Live status and assessment combination")
    if not isinstance(value["reason_codes"], list):
        raise ValueError("invalid Live reason codes")
    if not isinstance(value["scope"], Mapping):
        raise ValueError("invalid Live observation scope")
    if not isinstance(value["signals"], list):
        raise ValueError("invalid Live signals")
    for signal in value["signals"]:
        if not isinstance(signal, Mapping):
            raise ValueError("invalid Live signal")
        signal_id = signal.get("signal_id")
        if set(signal) != {
            "signal_id",
            "adoption_rule_id",
            "rule_ids",
            "evidence",
            "references",
        }:
            raise ValueError("invalid Live signal fields")
        if LIVE_ADOPTION_RULE_BY_SIGNAL.get(signal_id) != signal.get(
            "adoption_rule_id"
        ):
            raise ValueError("signal is outside the exact Live allowlist")
        if not set(signal["rule_ids"]).issubset(
            _ALLOWED_RULE_IDS_BY_SIGNAL[signal_id]
        ):
            raise ValueError("rule is outside the exact Live allowlist")
    stack: list[Any] = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            if _FORBIDDEN_KEYS.intersection(current):
                raise ValueError("forbidden decision field in Live observation")
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    if _observation_size(value) > MAX_OBSERVATION_BYTES:
        raise ValueError("Live observation exceeds output cap")
