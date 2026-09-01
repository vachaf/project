#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure deterministic aggregation for finding-level standards mappings.

The caller owns incident deduplication.  Each valid input mapping is counted as
one finding, even when identifiers such as ``incident_ref`` are duplicated.
This module performs taxonomy aggregation only; it does not detect attacks or
read from external systems.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from security_standards_mapping import RELATIONSHIP_PRECEDENCE, STANDARD_NAMES


SCHEMA_VERSION = "security_standards_summary.v1"
SOURCE = "deterministic_security_standards_summary"
COUNTING_UNIT = "deduplicated_finding"
SCOPE = "all_stage2_deduplicated_incidents"

KNOWN_STANDARD_ORDER = ("OWASP_TOP10", "CWE", "WSTG")
RELATIONSHIP_ORDER = ("direct", "conditional", "related")
OBSERVABILITY_ORDER = ("attempt_only", "behavior_only", "partial", "not_applicable")


def build_security_standards_summary(
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize already-deduplicated findings without mutating the input.

    A sequence element is a finding only when it implements ``Mapping``.
    Mapping items are deduplicated within that finding by ``(standard, id)``;
    relationship conflicts use the canonical mapping precedence.
    """

    observability_counts = {name: 0 for name in OBSERVABILITY_ORDER}
    diagnostics = {
        "invalid_finding_count": 0,
        "missing_mapping_finding_count": 0,
        "malformed_mapping_finding_count": 0,
        "skipped_mapping_item_count": 0,
    }
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}

    total_finding_count = 0
    mapped_finding_count = 0
    unmapped_finding_count = 0

    for finding in findings:
        if not isinstance(finding, Mapping):
            diagnostics["invalid_finding_count"] += 1
            continue

        total_finding_count += 1

        if "standards_mapping" not in finding or finding.get("standards_mapping") is None:
            diagnostics["missing_mapping_finding_count"] += 1
            unmapped_finding_count += 1
            observability_counts["not_applicable"] += 1
            continue

        standards_mapping = finding.get("standards_mapping")
        if not isinstance(standards_mapping, Mapping):
            diagnostics["malformed_mapping_finding_count"] += 1
            unmapped_finding_count += 1
            observability_counts["not_applicable"] += 1
            continue

        items = standards_mapping.get("items")
        if not isinstance(items, list):
            diagnostics["malformed_mapping_finding_count"] += 1
            unmapped_finding_count += 1
            observability_counts["not_applicable"] += 1
            continue

        finding_is_malformed = False
        observability = standards_mapping.get("observability")
        if isinstance(observability, str):
            normalized_observability = observability.strip().lower()
        else:
            normalized_observability = ""
        if normalized_observability not in OBSERVABILITY_ORDER:
            normalized_observability = "not_applicable"
            finding_is_malformed = True
        observability_counts[normalized_observability] += 1

        local_identities: dict[tuple[str, str], dict[str, Any]] = {}
        for raw_item in items:
            normalized_item = _normalize_mapping_item(raw_item)
            if normalized_item is None:
                diagnostics["skipped_mapping_item_count"] += 1
                finding_is_malformed = True
                continue

            standard, standard_id, relationship, name = normalized_item
            identity = (standard, standard_id)
            local = local_identities.get(identity)
            if local is None:
                local_identities[identity] = {
                    "relationship": relationship,
                    "names": {name} if name else set(),
                }
                continue

            if name:
                local["names"].add(name)
            if RELATIONSHIP_PRECEDENCE[relationship] > RELATIONSHIP_PRECEDENCE[local["relationship"]]:
                local["relationship"] = relationship

        if finding_is_malformed:
            diagnostics["malformed_mapping_finding_count"] += 1

        if not local_identities:
            unmapped_finding_count += 1
            continue

        mapped_finding_count += 1
        for identity, local in local_identities.items():
            aggregate = aggregates.get(identity)
            if aggregate is None:
                aggregate = {
                    "finding_count": 0,
                    "relationship_counts": {name: 0 for name in RELATIONSHIP_ORDER},
                    "names": set(),
                }
                aggregates[identity] = aggregate

            aggregate["finding_count"] += 1
            aggregate["relationship_counts"][local["relationship"]] += 1
            aggregate["names"].update(local["names"])

    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "counting_unit": COUNTING_UNIT,
        "scope": SCOPE,
        "total_finding_count": total_finding_count,
        "mapped_finding_count": mapped_finding_count,
        "unmapped_finding_count": unmapped_finding_count,
        "observability_counts": observability_counts,
        "standards": _materialize_standards(aggregates),
        "diagnostics": diagnostics,
    }


def _normalize_mapping_item(raw_item: Any) -> tuple[str, str, str, str] | None:
    if not isinstance(raw_item, Mapping):
        return None

    standard = raw_item.get("standard")
    standard_id = raw_item.get("id")
    relationship = raw_item.get("relationship")
    if not isinstance(standard, str) or not standard.strip():
        return None
    if not isinstance(standard_id, str) or not standard_id.strip():
        return None
    if not isinstance(relationship, str):
        return None

    normalized_relationship = relationship.strip().lower()
    if normalized_relationship not in RELATIONSHIP_PRECEDENCE:
        return None

    name = raw_item.get("name")
    normalized_name = name.strip() if isinstance(name, str) and name.strip() else ""
    return standard.strip().upper(), standard_id.strip(), normalized_relationship, normalized_name


def _materialize_standards(
    aggregates: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for (standard, standard_id), aggregate in aggregates.items():
        grouped.setdefault(standard, []).append((standard_id, aggregate))

    standards: dict[str, list[dict[str, Any]]] = {}
    group_order = list(KNOWN_STANDARD_ORDER)
    group_order.extend(sorted(standard for standard in grouped if standard not in KNOWN_STANDARD_ORDER))

    for standard in group_order:
        identities = grouped.get(standard, [])
        identities.sort(key=lambda pair: _standard_id_sort_key(standard, pair[0]))
        standards[standard] = [
            {
                "id": standard_id,
                "name": _resolve_name(standard, standard_id, aggregate.get("names")),
                "finding_count": int(aggregate.get("finding_count", 0)),
                "relationship_counts": {
                    relationship: int((aggregate.get("relationship_counts") or {}).get(relationship, 0))
                    for relationship in RELATIONSHIP_ORDER
                },
            }
            for standard_id, aggregate in identities
            if int(aggregate.get("finding_count", 0)) > 0
        ]

    return standards


def _resolve_name(standard: str, standard_id: str, names: Any) -> str:
    canonical_name = STANDARD_NAMES.get((standard, standard_id))
    if canonical_name:
        return canonical_name
    if isinstance(names, set):
        candidates = sorted(name for name in names if isinstance(name, str) and name)
        if candidates:
            return candidates[0]
    return standard_id


def _standard_id_sort_key(standard: str, standard_id: str) -> tuple[Any, ...]:
    if standard == "OWASP_TOP10":
        return _owasp_sort_key(standard_id)
    if standard == "CWE":
        return _cwe_sort_key(standard_id)
    return (standard_id,)


def _owasp_sort_key(standard_id: str) -> tuple[Any, ...]:
    category_text, separator, year_text = standard_id.partition(":")
    category_number = category_text[1:] if category_text.startswith("A") else ""
    if not category_number.isdigit():
        return (1, 0, 1, 0, standard_id)

    has_numeric_year = bool(separator and year_text.isdigit())
    return (
        0,
        int(category_number),
        0 if has_numeric_year else 1,
        int(year_text) if has_numeric_year else 0,
        standard_id,
    )


def _cwe_sort_key(standard_id: str) -> tuple[Any, ...]:
    number_text = standard_id[4:] if standard_id.startswith("CWE-") else ""
    if number_text.isdigit():
        return 0, int(number_text), standard_id
    return 1, 0, standard_id
