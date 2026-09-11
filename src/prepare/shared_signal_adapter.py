"""Prepare-only projection for shadow adoption of shared signal observations.

Existing Prepare detectors remain authoritative.  This adapter exposes the
shared observation and its legacy-hint relationship for compatibility checks;
it never converts assessment into score, candidate, or verdict policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

try:
    from src.security_signals import SignalSurface, extract_security_signals
except ImportError:
    from security_signals import SignalSurface, extract_security_signals


LegacyHintGroup = tuple[str, ...]

_LEGACY_HINT_GROUPS_BY_RULE: dict[str, tuple[LegacyHintGroup, ...]] = {
    "legacy.sql.termination_boolean.v1": (
        ("sqli:or_true", "sqli:and_true"),
        ("sqli:quote_termination",),
        ("sqli:boolean_true_condition",),
    ),
    "legacy.sql.termination_union_columns.v1": (
        ("sqli:union_select",),
        ("sqli:quote_termination",),
    ),
    "legacy.xss.img_onerror.v1": (("xss:img_onerror",),),
    "legacy.xss.svg_onload.v1": (("xss:svg_onload",),),
    "legacy.cmdi.pipe_exec.v1": (("cmdi:pipe_exec",),),
    "legacy.cmdi.semicolon_exec.v1": (("cmdi:semicolon_exec",),),
    "legacy.file.php_filter_resource.v1": (
        ("file_disclosure:php_filter_wrapper",),
        ("file_disclosure:base64_source_intent",),
        ("file_disclosure:resource_parameter",),
    ),
}


@dataclass(frozen=True)
class PrepareSharedSignalCompatibility:
    observation: dict[str, Any]
    legacy_hint_groups: tuple[LegacyHintGroup, ...]


def observe_prepare_security_signals(
    *,
    row_identity: Mapping[str, Any],
    combined_text: str,
    raw_query_string: str,
    raw_request_target: str,
    uri: str,
) -> PrepareSharedSignalCompatibility:
    """Project existing Prepare surfaces without changing legacy decisions."""

    observation = extract_security_signals(
        row_identity=row_identity,
        input_profile="prepare_compat_v1",
        surfaces=(
            SignalSurface("combined_text", combined_text),
            SignalSurface("query_string", raw_query_string),
            SignalSurface("raw_request_target", raw_request_target),
            SignalSurface("uri", uri),
        ),
    )
    groups: list[LegacyHintGroup] = []
    for signal in observation["signals"]:
        for group in _LEGACY_HINT_GROUPS_BY_RULE[signal["rule_id"]]:
            if group not in groups:
                groups.append(group)
    return PrepareSharedSignalCompatibility(
        observation=observation,
        legacy_hint_groups=tuple(groups),
    )
