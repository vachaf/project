"""Pure shared observations for the approved first security-signal allowlist.

This module deliberately owns no Prepare or Live policy.  A match is an
observation for review, never a candidate, verdict, severity, or confirmation
of an attack.  It performs no I/O and does not import either runtime.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import unquote_plus


SCHEMA_VERSION = "shared_security_signal_observation.v1"
DETECTOR_VERSION = "shared_security_signal_extractor.v1"
PROCESSING_STATUSES = frozenset({"complete", "partial", "unavailable", "error"})
ASSESSMENTS = frozenset({"review_required", "no_signal", "undetermined"})
INPUT_PROFILES = frozenset({"prepare_compat_v1", "live_target_v1"})


class ExtractorInputError(ValueError):
    """Raised before extraction when the typed input contract is malformed."""


@dataclass(frozen=True)
class SignalSurface:
    """One ordered, observed text surface and its source provenance."""

    source_field: str
    text: str
    surface: str | None = None
    derived_from: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_field, str) or not self.source_field:
            raise ExtractorInputError("source_field must be a non-empty string")
        if not isinstance(self.text, str):
            raise ExtractorInputError("surface text must be a string")
        if self.surface is not None and (not isinstance(self.surface, str) or not self.surface):
            raise ExtractorInputError("surface must be null or a non-empty string")
        if self.derived_from is not None and not isinstance(self.derived_from, str):
            raise ExtractorInputError("derived_from must be null or a string")


@dataclass(frozen=True)
class ExtractionBudget:
    """Optional structural caps; ``None`` means that cap is not configured.

    No time or performance number is made canonical here.  Callers may supply
    approved limits without changing detector meaning.
    """

    max_input_codepoints_per_surface: int | None = None
    max_variants_per_surface: int | None = None
    max_total_variant_codepoints: int | None = None
    max_signals: int | None = None
    max_evidence_per_signal: int | None = None

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if value is not None and (type(value) is not int or value < 1):
                raise ExtractorInputError(f"{name} must be null or a positive integer")


@dataclass(frozen=True)
class _Variant:
    surface_index: int
    source_field: str
    surface: str
    derived_from_surface: str | None
    variant_id: str
    parent_variant_id: str | None
    text: str
    decode_type: str
    decode_depth: int
    transforms: tuple[str, ...]
    input_truncated: bool


@dataclass(frozen=True)
class _Rule:
    signal_id: str
    rule_id: str
    find_spans: Callable[[str], tuple[tuple[int, int], ...]]


_SQL_BOOLEAN = re.compile(
    r"(?ix)(?:'|%27)\s*(?:\)\s*){0,4}(?:or|and)\s+"
    r"(?:"
    r"(?P<num>\d{1,8})\s*=\s*(?P=num)"
    r"|(?P<sq>'[^']{0,32}')\s*=\s*(?P=sq)"
    r"|(?P<dq>\"[^\"]{0,32}\")\s*=\s*(?P=dq)"
    r"|(?P<word>[a-z_][a-z0-9_]*)\s*=\s*(?P=word)"
    r"|true\s*=\s*true|false\s*=\s*false)"
)
_SQL_UNION = re.compile(
    r"(?is)(?:'|%27)\s*(?:\)\s*){0,4}union\s+select\s+[^\n]{0,160},\s*[^\n]{0,160}"
)
_IMG_ONERROR = re.compile(r"(?i)<\s*img\b[^>]{0,512}?\bonerror\s*=")
_SVG_ONLOAD = re.compile(r"(?i)<\s*svg\b[^>]{0,512}?\bonload\s*=")

# This is the approved narrow, pre-expansion command vocabulary.  Newer
# Prepare commands and and/subshell/shell-invocation grammars are not adopted.
_PIPE_COMMAND = re.compile(r"(?i)\|\s*(?:whoami|id|cat|uname|ls|pwd)\b")
_SEMICOLON_COMMAND = re.compile(r"(?i);\s*(?:cat|id|whoami|uname|curl|wget|bash|sh)\b")

_PHP_WRAPPER = re.compile(r"(?i)php\s*://\s*filter")
_PHP_BASE64 = re.compile(r"(?i)convert\.base64-encode")
_PHP_RESOURCE = re.compile(r"(?i)(?:^|[?&/])resource\s*=")


def _regex_spans(pattern: re.Pattern[str]) -> Callable[[str], tuple[tuple[int, int], ...]]:
    return lambda text: tuple(match.span() for match in pattern.finditer(text))


def _php_filter_spans(text: str) -> tuple[tuple[int, int], ...]:
    wrapper = _PHP_WRAPPER.search(text)
    base64_filter = _PHP_BASE64.search(text)
    resource = _PHP_RESOURCE.search(text)
    if not (wrapper and base64_filter and resource):
        return ()
    return ((min(wrapper.start(), base64_filter.start(), resource.start()), max(wrapper.end(), base64_filter.end(), resource.end())),)


_RULES = (
    _Rule("sql.termination_boolean_structure", "legacy.sql.termination_boolean.v1", _regex_spans(_SQL_BOOLEAN)),
    _Rule("sql.termination_union_structure", "legacy.sql.termination_union_columns.v1", _regex_spans(_SQL_UNION)),
    _Rule("html.event_handler_attribute", "legacy.xss.img_onerror.v1", _regex_spans(_IMG_ONERROR)),
    _Rule("html.event_handler_attribute", "legacy.xss.svg_onload.v1", _regex_spans(_SVG_ONLOAD)),
    _Rule("shell.separator_command_structure", "legacy.cmdi.pipe_exec.v1", _regex_spans(_PIPE_COMMAND)),
    _Rule("shell.separator_command_structure", "legacy.cmdi.semicolon_exec.v1", _regex_spans(_SEMICOLON_COMMAND)),
    _Rule("php.filter_resource_structure", "legacy.file.php_filter_resource.v1", _php_filter_spans),
)


def _validate_row_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ExtractorInputError("row_identity must be a mapping")
    copied: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ExtractorInputError("row_identity keys must be non-empty strings")
        if item is not None and type(item) not in (str, int, float, bool):
            raise ExtractorInputError("row_identity values must be JSON scalar values")
        copied[key] = item
    return copied


def _limited(value: str, maximum: int | None) -> tuple[str, bool]:
    if maximum is None or len(value) <= maximum:
        return value, False
    return value[:maximum], True


def _build_variants(
    surfaces: Sequence[SignalSurface], budget: ExtractionBudget
) -> tuple[list[_Variant], list[str], tuple[str, ...], tuple[str, ...]]:
    variants: list[_Variant] = []
    reasons: list[str] = []
    observed: list[str] = []
    missing: list[str] = []
    total_codepoints = 0

    for surface_index, item in enumerate(surfaces):
        label = item.surface or item.source_field
        if not item.text:
            missing.append(item.source_field)
            continue
        observed.append(item.source_field)
        raw, input_truncated = _limited(item.text, budget.max_input_codepoints_per_surface)
        if input_truncated and "input_truncated" not in reasons:
            reasons.append("input_truncated")
        raw_id = f"surface-{surface_index}:raw"
        candidates: list[tuple[str, str, str | None, str, int, tuple[str, ...]]] = [
            (raw, raw_id, None, "raw", 0, ()),
        ]
        current = raw
        parent_id = raw_id
        transforms: tuple[str, ...] = ()
        for depth in (1, 2):
            decoded = unquote_plus(current)
            if decoded == current:
                break
            variant_id = f"surface-{surface_index}:url-{depth}"
            transforms += ("url_decode",)
            candidates.append((decoded, variant_id, parent_id, "url_decode", depth, transforms))
            current = decoded
            parent_id = variant_id

        url_candidates = tuple(candidates)
        for base_index, (value, base_id, _, _, depth, transforms) in enumerate(url_candidates):
            decoded = html.unescape(value)
            if decoded != value:
                candidates.append(
                    (
                        decoded,
                        f"surface-{surface_index}:html-{base_index}",
                        base_id,
                        "html_entity",
                        depth,
                        transforms + ("html_entity_decode",),
                    )
                )

        seen: set[tuple[str, str, int]] = set()
        per_surface = 0
        for value, variant_id, parent, decode_type, depth, transforms in candidates:
            key = (value, decode_type, depth)
            if key in seen:
                continue
            if budget.max_variants_per_surface is not None and per_surface >= budget.max_variants_per_surface:
                if "variant_budget_exceeded" not in reasons:
                    reasons.append("variant_budget_exceeded")
                break
            if budget.max_total_variant_codepoints is not None and total_codepoints + len(value) > budget.max_total_variant_codepoints:
                if "variant_codepoint_budget_exceeded" not in reasons:
                    reasons.append("variant_codepoint_budget_exceeded")
                break
            seen.add(key)
            variants.append(
                _Variant(
                    surface_index=surface_index,
                    source_field=item.source_field,
                    surface=label,
                    derived_from_surface=item.derived_from,
                    variant_id=variant_id,
                    parent_variant_id=parent,
                    text=value,
                    decode_type=decode_type,
                    decode_depth=depth,
                    transforms=transforms,
                    input_truncated=input_truncated,
                )
            )
            total_codepoints += len(value)
            per_surface += 1
    return variants, reasons, tuple(observed), tuple(missing)


def extract_security_signals(
    *,
    row_identity: Mapping[str, Any],
    input_profile: str,
    surfaces: Sequence[SignalSurface],
    budget: ExtractionBudget | None = None,
) -> dict[str, Any]:
    """Return an additive observation without mutating caller-owned input."""

    identity = _validate_row_identity(row_identity)
    if input_profile not in INPUT_PROFILES:
        raise ExtractorInputError("unsupported input_profile")
    if isinstance(surfaces, (str, bytes)) or not isinstance(surfaces, Sequence):
        raise ExtractorInputError("surfaces must be an ordered sequence")
    if any(not isinstance(item, SignalSurface) for item in surfaces):
        raise ExtractorInputError("every surface must be a SignalSurface")
    limits = budget if budget is not None else ExtractionBudget()
    if not isinstance(limits, ExtractionBudget):
        raise ExtractorInputError("budget must be an ExtractionBudget")

    variants, reason_codes, observed_fields, missing_fields = _build_variants(surfaces, limits)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    signal_order: list[tuple[str, str]] = []
    evidence_seen: set[tuple[Any, ...]] = set()

    for rule in _RULES:
        for variant in variants:
            for start, end in rule.find_spans(variant.text):
                if variant.input_truncated and end == len(variant.text):
                    if "truncated_boundary_match_suppressed" not in reason_codes:
                        reason_codes.append("truncated_boundary_match_suppressed")
                    continue
                evidence_key = (rule.rule_id, variant.variant_id, start, end)
                if evidence_key in evidence_seen:
                    continue
                evidence_seen.add(evidence_key)
                signal_key = (rule.signal_id, rule.rule_id)
                if signal_key not in grouped:
                    if limits.max_signals is not None and len(signal_order) >= limits.max_signals:
                        if "output_signal_budget_exceeded" not in reason_codes:
                            reason_codes.append("output_signal_budget_exceeded")
                        continue
                    grouped[signal_key] = {
                        "signal_id": rule.signal_id,
                        "rule_id": rule.rule_id,
                        "evidence": [],
                    }
                    signal_order.append(signal_key)
                evidence = grouped[signal_key]["evidence"]
                if limits.max_evidence_per_signal is not None and len(evidence) >= limits.max_evidence_per_signal:
                    if "output_evidence_budget_exceeded" not in reason_codes:
                        reason_codes.append("output_evidence_budget_exceeded")
                    continue
                evidence.append(
                    {
                        "source_field": variant.source_field,
                        "surface": variant.surface,
                        "derived_from": variant.derived_from_surface,
                        "variant_id": variant.variant_id,
                        "parent_variant_id": variant.parent_variant_id,
                        "decode_type": variant.decode_type,
                        "decode_depth": variant.decode_depth,
                        "transforms": list(variant.transforms),
                        "span": {
                            "coordinate_system": "variant_codepoints",
                            "start": start,
                            "end": end,
                        },
                        "matched_text": variant.text[start:end],
                    }
                )

    signals = [grouped[key] for key in signal_order]
    partial = bool(reason_codes)
    if not variants:
        processing_status = "unavailable"
        assessment = "undetermined"
        if "no_observable_surface" not in reason_codes:
            reason_codes.append("no_observable_surface")
    elif partial:
        processing_status = "partial"
        assessment = "review_required" if signals else "undetermined"
    else:
        processing_status = "complete"
        assessment = "review_required" if signals else "no_signal"

    return {
        "schema_version": SCHEMA_VERSION,
        "detector_version": DETECTOR_VERSION,
        "row_identity": identity,
        "processing_status": processing_status,
        "assessment": assessment,
        "reason_codes": reason_codes,
        "observation_scope": {
            "input_profile": input_profile,
            "observed_fields": list(observed_fields),
            "missing_fields": list(missing_fields),
            "excluded_fields": [],
            "applied_rule_ids": [rule.rule_id for rule in _RULES],
            "budget": dict(limits.__dict__),
        },
        "signals": signals,
    }
