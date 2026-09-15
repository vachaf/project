from __future__ import annotations

from copy import deepcopy
from itertools import chain
from typing import Any

import pytest

from security_standards_summary import build_security_standards_summary


def mapping(items: list[Any], observability: Any = "attempt_only") -> dict[str, Any]:
    return {"observability": observability, "items": items}


def item(
    standard: Any,
    standard_id: Any,
    relationship: Any = "direct",
    name: Any = None,
) -> dict[str, Any]:
    value = {"standard": standard, "id": standard_id, "relationship": relationship}
    if name is not None:
        value["name"] = name
    return value


def finding(items: list[Any], observability: Any = "attempt_only", **extra: Any) -> dict[str, Any]:
    return {"standards_mapping": mapping(items, observability), **extra}


def row(summary: dict[str, Any], standard: str, standard_id: str) -> dict[str, Any]:
    return next(value for value in summary["standards"][standard] if value["id"] == standard_id)


def all_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return list(chain.from_iterable(summary["standards"].values()))


def assert_summary_invariants(summary: dict[str, Any]) -> None:
    assert summary["mapped_finding_count"] + summary["unmapped_finding_count"] == summary["total_finding_count"]
    assert sum(summary["observability_counts"].values()) == summary["total_finding_count"]
    for rows in summary["standards"].values():
        ids = [value["id"] for value in rows]
        assert len(ids) == len(set(ids))
        for value in rows:
            assert 0 < value["finding_count"] <= summary["total_finding_count"]
            assert all(count <= value["finding_count"] for count in value["relationship_counts"].values())


def test_empty_input_returns_exact_v1_shape() -> None:
    assert build_security_standards_summary([]) == {
        "schema_version": "security_standards_summary.v1",
        "source": "deterministic_security_standards_summary",
        "counting_unit": "deduplicated_finding",
        "scope": "all_stage2_deduplicated_incidents",
        "total_finding_count": 0,
        "mapped_finding_count": 0,
        "unmapped_finding_count": 0,
        "observability_counts": {
            "attempt_only": 0,
            "behavior_only": 0,
            "partial": 0,
            "not_applicable": 0,
        },
        "standards": {"OWASP_TOP10": [], "CWE": [], "WSTG": []},
        "diagnostics": {
            "invalid_finding_count": 0,
            "missing_mapping_finding_count": 0,
            "malformed_mapping_finding_count": 0,
            "skipped_mapping_item_count": 0,
        },
    }


def test_single_sqli_finding() -> None:
    summary = build_security_standards_summary(
        [
            finding(
                [
                    item("OWASP_TOP10", "A05:2025", name="wrong input name"),
                    item("CWE", "CWE-89", name="wrong input name"),
                    item("WSTG", "WSTG-INPV-05", name="wrong input name"),
                ]
            )
        ]
    )

    assert summary["total_finding_count"] == 1
    assert summary["mapped_finding_count"] == 1
    assert row(summary, "OWASP_TOP10", "A05:2025") == {
        "id": "A05:2025",
        "name": "Injection",
        "finding_count": 1,
        "relationship_counts": {"direct": 1, "conditional": 0, "related": 0},
    }
    assert row(summary, "CWE", "CWE-89")["name"] == "SQL Injection"
    assert row(summary, "WSTG", "WSTG-INPV-05")["name"] == "Testing for SQL Injection"
    assert summary["observability_counts"]["attempt_only"] == 1


def test_two_injection_findings_share_a05_count() -> None:
    summary = build_security_standards_summary(
        [
            finding([item("OWASP_TOP10", "A05:2025"), item("CWE", "CWE-89")]),
            finding([item("OWASP_TOP10", "A05:2025"), item("CWE", "CWE-79")]),
        ]
    )

    assert summary["total_finding_count"] == 2
    assert summary["mapped_finding_count"] == 2
    assert row(summary, "OWASP_TOP10", "A05:2025")["finding_count"] == 2
    assert row(summary, "OWASP_TOP10", "A05:2025")["relationship_counts"]["direct"] == 2
    assert row(summary, "CWE", "CWE-89")["finding_count"] == 1
    assert row(summary, "CWE", "CWE-79")["finding_count"] == 1


def test_one_finding_can_map_to_multiple_owasp_categories() -> None:
    summary = build_security_standards_summary(
        [finding([item("OWASP_TOP10", "A01:2025"), item("OWASP_TOP10", "A05:2025", "related")])]
    )

    assert summary["total_finding_count"] == 1
    assert summary["mapped_finding_count"] == 1
    assert sum(value["finding_count"] for value in summary["standards"]["OWASP_TOP10"]) == 2


def test_five_mapping_items_still_contribute_one_finding() -> None:
    summary = build_security_standards_summary(
        [
            finding(
                [
                    item("OWASP_TOP10", "A01:2025"),
                    item("CWE", "CWE-22"),
                    item("CWE", "CWE-552", "conditional"),
                    item("WSTG", "WSTG-ATHZ-01"),
                    item("WSTG", "WSTG-CONF-04", "related"),
                ]
            )
        ]
    )

    assert summary["total_finding_count"] == 1
    assert summary["mapped_finding_count"] == 1
    assert len(all_rows(summary)) == 5
    assert all(value["finding_count"] == 1 for value in all_rows(summary))


def test_empty_valid_mapping_is_unmapped() -> None:
    summary = build_security_standards_summary([finding([], "not_applicable")])
    assert summary["total_finding_count"] == 1
    assert summary["mapped_finding_count"] == 0
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 0


def test_missing_mapping_field_is_missing_and_unmapped() -> None:
    summary = build_security_standards_summary([{"incident_ref": "old-1"}])
    assert summary["unmapped_finding_count"] == 1
    assert summary["observability_counts"]["not_applicable"] == 1
    assert summary["diagnostics"]["missing_mapping_finding_count"] == 1


def test_none_mapping_is_missing_and_unmapped() -> None:
    summary = build_security_standards_summary([{"standards_mapping": None}])
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["missing_mapping_finding_count"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 0


def test_duplicate_identity_counts_once() -> None:
    summary = build_security_standards_summary(
        [finding([item("CWE", "CWE-89"), item("CWE", "CWE-89")])]
    )
    assert row(summary, "CWE", "CWE-89")["finding_count"] == 1


def test_direct_beats_conditional_and_related() -> None:
    summary = build_security_standards_summary(
        [
            finding(
                [
                    item("OWASP_TOP10", "A01:2025", "related"),
                    item("OWASP_TOP10", "A01:2025", "conditional"),
                    item("OWASP_TOP10", "A01:2025", "direct"),
                ]
            )
        ]
    )
    assert row(summary, "OWASP_TOP10", "A01:2025")["relationship_counts"] == {
        "direct": 1,
        "conditional": 0,
        "related": 0,
    }


def test_conditional_beats_related() -> None:
    summary = build_security_standards_summary(
        [finding([item("CWE", "CWE-552", "related"), item("CWE", "CWE-552", "conditional")])]
    )
    assert row(summary, "CWE", "CWE-552")["relationship_counts"] == {
        "direct": 0,
        "conditional": 1,
        "related": 0,
    }


def test_duplicated_direct_still_counts_once() -> None:
    summary = build_security_standards_summary(
        [finding([item("CWE", "CWE-89", "direct"), item("CWE", "CWE-89", "direct")])]
    )
    assert row(summary, "CWE", "CWE-89")["relationship_counts"]["direct"] == 1


def test_invalid_finding_elements_are_excluded_from_total() -> None:
    summary = build_security_standards_summary([finding([]), None, "invalid"])  # type: ignore[list-item]
    assert summary["total_finding_count"] == 1
    assert summary["diagnostics"]["invalid_finding_count"] == 2


def test_mapping_not_mapping_is_malformed() -> None:
    summary = build_security_standards_summary([{"standards_mapping": "invalid"}])
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1


def test_empty_mapping_dict_is_malformed() -> None:
    summary = build_security_standards_summary([{"standards_mapping": {}}])
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1


def test_items_missing_is_malformed() -> None:
    summary = build_security_standards_summary([{"standards_mapping": {"observability": "attempt_only"}}])
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1


def test_items_string_is_malformed() -> None:
    summary = build_security_standards_summary(
        [{"standards_mapping": {"observability": "attempt_only", "items": "invalid"}}]
    )
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1


def test_non_mapping_item_is_skipped() -> None:
    summary = build_security_standards_summary([finding([None])])
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1
    assert summary["diagnostics"]["skipped_mapping_item_count"] == 1


def test_missing_standard_is_skipped() -> None:
    summary = build_security_standards_summary([finding([{"id": "CWE-89", "relationship": "direct"}])])
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["skipped_mapping_item_count"] == 1


def test_missing_id_is_skipped() -> None:
    summary = build_security_standards_summary([finding([{"standard": "CWE", "relationship": "direct"}])])
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["skipped_mapping_item_count"] == 1


def test_unknown_relationship_is_skipped_not_coerced() -> None:
    summary = build_security_standards_summary([finding([item("CWE", "CWE-89", "unknown")])])
    assert summary["mapped_finding_count"] == 0
    assert summary["unmapped_finding_count"] == 1
    assert summary["diagnostics"]["skipped_mapping_item_count"] == 1


def test_valid_and_invalid_items_are_aggregated_fail_soft() -> None:
    summary = build_security_standards_summary(
        [finding([item("CWE", "CWE-89"), item("", "X", "related")])]
    )
    assert summary["mapped_finding_count"] == 1
    assert summary["unmapped_finding_count"] == 0
    assert row(summary, "CWE", "CWE-89")["finding_count"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1
    assert summary["diagnostics"]["skipped_mapping_item_count"] == 1


def test_invalid_observability_falls_back_and_marks_malformed() -> None:
    summary = build_security_standards_summary([finding([item("CWE", "CWE-89")], "unknown")])
    assert summary["mapped_finding_count"] == 1
    assert summary["observability_counts"]["not_applicable"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1


def test_missing_observability_falls_back_and_marks_malformed() -> None:
    summary = build_security_standards_summary([{"standards_mapping": {"items": [item("CWE", "CWE-89")]}}])
    assert summary["mapped_finding_count"] == 1
    assert summary["observability_counts"]["not_applicable"] == 1
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1


def test_unknown_standard_is_preserved() -> None:
    summary = build_security_standards_summary(
        [finding([item("ASVS", "V5.3.1", "related", "Some name")])]
    )
    assert list(summary["standards"]) == ["OWASP_TOP10", "CWE", "WSTG", "ASVS"]
    assert row(summary, "ASVS", "V5.3.1")["name"] == "Some name"
    assert summary["mapped_finding_count"] == 1


def test_unknown_standard_groups_sort_lexically() -> None:
    summary = build_security_standards_summary(
        [finding([item("ZZZ", "2"), item("asvs", "1"), item("MASVS", "3")])]
    )
    assert list(summary["standards"]) == ["OWASP_TOP10", "CWE", "WSTG", "ASVS", "MASVS", "ZZZ"]


def test_unknown_name_uses_lexical_minimum() -> None:
    summary = build_security_standards_summary(
        [
            finding([item("ASVS", "V5.3.1", "related", "Z name")]),
            finding([item("ASVS", "V5.3.1", "related", " A name ")]),
        ]
    )
    assert row(summary, "ASVS", "V5.3.1")["name"] == "A name"


def test_unknown_name_falls_back_to_id() -> None:
    summary = build_security_standards_summary([finding([item("ASVS", "V5.3.1", "related")])])
    assert row(summary, "ASVS", "V5.3.1")["name"] == "V5.3.1"


def test_owasp_ids_use_category_then_year_numeric_order() -> None:
    summary = build_security_standards_summary(
        [
            finding(
                [
                    item("OWASP_TOP10", "A10:2025"),
                    item("OWASP_TOP10", "A02:2025"),
                    item("OWASP_TOP10", "A01:2025"),
                    item("OWASP_TOP10", "A01:2021"),
                ]
            )
        ]
    )
    assert [value["id"] for value in summary["standards"]["OWASP_TOP10"]] == [
        "A01:2021",
        "A01:2025",
        "A02:2025",
        "A10:2025",
    ]


def test_cwe_ids_use_numeric_order_before_non_numeric() -> None:
    summary = build_security_standards_summary(
        [finding([item("CWE", value) for value in ("CWE-552", "CWE-X", "CWE-89", "CWE-22", "CWE-79")])]
    )
    assert [value["id"] for value in summary["standards"]["CWE"]] == [
        "CWE-22",
        "CWE-79",
        "CWE-89",
        "CWE-552",
        "CWE-X",
    ]


def test_wstg_ids_sort_lexically() -> None:
    summary = build_security_standards_summary(
        [finding([item("WSTG", value) for value in ("WSTG-INPV-05", "WSTG-ATHZ-01", "WSTG-CONF-04")])]
    )
    assert [value["id"] for value in summary["standards"]["WSTG"]] == [
        "WSTG-ATHZ-01",
        "WSTG-CONF-04",
        "WSTG-INPV-05",
    ]


def test_shuffled_findings_and_items_produce_same_output() -> None:
    first = [
        finding([item("ASVS", "V5", "related", "Z"), item("CWE", "CWE-89")]),
        finding([item("ASVS", "V5", "direct", "A"), item("OWASP_TOP10", "A05:2025")]),
    ]
    second = [
        finding([item("OWASP_TOP10", "A05:2025"), item("ASVS", "V5", "direct", "A")]),
        finding([item("CWE", "CWE-89"), item("ASVS", "V5", "related", "Z")]),
    ]
    assert build_security_standards_summary(first) == build_security_standards_summary(second)


def test_mapped_plus_unmapped_equals_total() -> None:
    summary = build_security_standards_summary([finding([item("CWE", "CWE-89")]), finding([]), {}])
    assert summary["mapped_finding_count"] + summary["unmapped_finding_count"] == summary["total_finding_count"] == 3


def test_observability_sum_equals_total() -> None:
    summary = build_security_standards_summary(
        [
            finding([], "attempt_only"),
            finding([], "behavior_only"),
            finding([], "partial"),
            finding([], "not_applicable"),
        ]
    )
    assert summary["observability_counts"] == {
        "attempt_only": 1,
        "behavior_only": 1,
        "partial": 1,
        "not_applicable": 1,
    }
    assert sum(summary["observability_counts"].values()) == summary["total_finding_count"] == 4


def test_relationship_counts_never_exceed_finding_count() -> None:
    summary = build_security_standards_summary(
        [
            finding([item("CWE", "CWE-89", "related"), item("CWE", "CWE-89", "direct")]),
            finding([item("CWE", "CWE-89", "conditional")]),
        ]
    )
    target = row(summary, "CWE", "CWE-89")
    assert target["finding_count"] == 2
    assert all(count <= target["finding_count"] for count in target["relationship_counts"].values())


def test_no_duplicate_id_per_standard_group() -> None:
    summary = build_security_standards_summary(
        [
            finding([item("CWE", "CWE-89"), item("CWE", "CWE-89")]),
            finding([item("CWE", "CWE-89")]),
        ]
    )
    ids = [value["id"] for value in summary["standards"]["CWE"]]
    assert ids == ["CWE-89"]


def test_zero_count_rows_are_absent() -> None:
    summary = build_security_standards_summary([finding([])])
    assert all(not rows for rows in summary["standards"].values())


def test_same_incident_ref_twice_is_counted_twice() -> None:
    duplicated = finding([item("CWE", "CWE-89")], incident_ref="same")
    summary = build_security_standards_summary([duplicated, deepcopy(duplicated)])
    assert summary["total_finding_count"] == 2
    assert row(summary, "CWE", "CWE-89")["finding_count"] == 2


def test_input_is_not_mutated() -> None:
    findings = [
        finding(
            [
                item(" cwe ", " CWE-89 ", " DIRECT ", " SQL Injection "),
                item("cwe", "CWE-89", "related", "Other"),
            ],
            " ATTEMPT_ONLY ",
        )
    ]
    before = deepcopy(findings)
    build_security_standards_summary(findings)
    assert findings == before


def test_diagnostics_distinguish_findings_from_items() -> None:
    summary = build_security_standards_summary(
        [
            None,
            {},
            {"standards_mapping": {}},
            finding([None, item("", "X"), item("CWE", "CWE-89")]),
        ]  # type: ignore[list-item]
    )
    assert summary["diagnostics"] == {
        "invalid_finding_count": 1,
        "missing_mapping_finding_count": 1,
        "malformed_mapping_finding_count": 2,
        "skipped_mapping_item_count": 2,
    }
    assert summary["total_finding_count"] == 3
    assert summary["mapped_finding_count"] == 1
    assert summary["unmapped_finding_count"] == 2


@pytest.mark.parametrize("bad_standard", [None, 123, "", "   "])
def test_non_string_or_empty_standard_is_skipped(bad_standard: Any) -> None:
    summary = build_security_standards_summary([finding([item(bad_standard, "CWE-89")])])
    assert summary["diagnostics"]["skipped_mapping_item_count"] == 1
    assert summary["unmapped_finding_count"] == 1


@pytest.mark.parametrize("bad_id", [None, 123, "", "   "])
def test_non_string_or_empty_id_is_skipped(bad_id: Any) -> None:
    summary = build_security_standards_summary([finding([item("CWE", bad_id)])])
    assert summary["diagnostics"]["skipped_mapping_item_count"] == 1
    assert summary["unmapped_finding_count"] == 1


def test_standard_id_relationship_and_observability_are_normalized() -> None:
    summary = build_security_standards_summary(
        [finding([item(" cwe ", " CWE-89 ", " DIRECT ")], " ATTEMPT_ONLY ")]
    )
    assert row(summary, "CWE", "CWE-89")["relationship_counts"]["direct"] == 1
    assert summary["observability_counts"]["attempt_only"] == 1


def test_known_identity_always_uses_canonical_name() -> None:
    summary = build_security_standards_summary(
        [finding([item("CWE", "CWE-89", name="A misleading alternate name")])]
    )
    assert row(summary, "CWE", "CWE-89")["name"] == "SQL Injection"


def test_malformed_mapping_count_increments_at_most_once_per_finding() -> None:
    summary = build_security_standards_summary(
        [finding([None, item("", ""), item("CWE", "CWE-89")], observability="unknown")]
    )
    assert summary["diagnostics"]["malformed_mapping_finding_count"] == 1
    assert summary["diagnostics"]["skipped_mapping_item_count"] == 2
    assert summary["mapped_finding_count"] == 1


def test_all_summary_invariants_hold_for_mixed_input() -> None:
    summary = build_security_standards_summary(
        [
            finding([item("OWASP_TOP10", "A05:2025"), item("CWE", "CWE-89")]),
            finding([item("OWASP_TOP10", "A05:2025", "related"), item("ASVS", "V5", "conditional")]),
            finding([]),
            {},
            None,
        ]  # type: ignore[list-item]
    )
    assert_summary_invariants(summary)
