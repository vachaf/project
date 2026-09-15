from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Tuple

from security_standards_mapping import (
    build_security_standards_mapping,
    get_security_standards_mapping_schema_version,
)


MappingKey = Tuple[str, str, str]


def build_result(verdict: str, reason_hints: Iterable[Any] = (), **overrides: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "verdict": verdict,
        "reason_hints": list(reason_hints),
        "uri": overrides.pop("uri", "/"),
        "query_string": overrides.pop("query_string", ""),
        "raw_request_target": overrides.pop("raw_request_target", ""),
        "method": overrides.pop("method", "GET"),
        "status_code": overrides.pop("status_code", 200),
    }
    result.update(overrides)
    return result


def keys(mapping: Dict[str, Any]) -> set[MappingKey]:
    return {
        (item["standard"], item["id"], item["relationship"])
        for item in mapping["items"]
    }


def item_by_id(mapping: Dict[str, Any], standard_id: str) -> Dict[str, Any]:
    for item in mapping["items"]:
        if item["id"] == standard_id:
            return item
    raise AssertionError(f"missing mapping item id={standard_id}")


def assert_has(mapping: Dict[str, Any], standard: str, standard_id: str, relationship: str) -> None:
    assert (standard, standard_id, relationship) in keys(mapping)


def assert_not_id(mapping: Dict[str, Any], standard_id: str) -> None:
    assert all(item["id"] != standard_id for item in mapping["items"])


def assert_no_success_claims(mapping: Dict[str, Any]) -> None:
    text = json.dumps(mapping, ensure_ascii=False).lower()
    assert "confirm" in text
    assert "exploitation success" not in text
    assert "successful exploitation" not in text
    assert "confirmed vulnerability" not in text


def assert_schema(mapping: Dict[str, Any], observability: str) -> None:
    assert mapping["schema_version"] == get_security_standards_mapping_schema_version()
    assert mapping["source"] == "deterministic_stage1_enrichment"
    assert mapping["observability"] == observability
    assert isinstance(mapping["items"], list)
    assert "unmapped_reason" in mapping


def test_plain_traversal_maps_direct() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_path_traversal", ["traversal:dotdot_slash(+4)"])
    )

    assert_schema(mapping, "attempt_only")
    assert_has(mapping, "OWASP_TOP10", "A01:2025", "direct")
    assert_has(mapping, "CWE", "CWE-22", "direct")
    assert_has(mapping, "WSTG", "WSTG-ATHZ-01", "direct")
    assert_not_id(mapping, "CWE-552")
    assert_not_id(mapping, "WSTG-CONF-04")
    assert_no_success_claims(mapping)


def test_traversal_with_direct_sensitive_evidence_keeps_orthogonal_enrichment() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_path_traversal",
            [
                "traversal:dotdot_slash(+4)",
                "file_disclosure:sensitive_resource:os_file",
            ],
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A01:2025", "direct")
    assert_has(mapping, "CWE", "CWE-22", "direct")
    assert_has(mapping, "WSTG", "WSTG-ATHZ-01", "direct")
    assert_has(mapping, "CWE", "CWE-552", "conditional")
    assert_has(mapping, "WSTG", "WSTG-CONF-04", "related")
    assert_not_id(mapping, "A02:2025")
    assert_not_id(mapping, "WSTG-CONF-03")


def test_url_encoded_traversal_maps_direct() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_path_traversal", ["traversal:url_encoded_dotdot_slash(+4)"])
    )

    assert_has(mapping, "OWASP_TOP10", "A01:2025", "direct")
    assert_has(mapping, "CWE", "CWE-22", "direct")
    assert_has(mapping, "WSTG", "WSTG-ATHZ-01", "direct")
    assert_not_id(mapping, "CWE-552")
    assert mapping["observability"] == "attempt_only"


def test_double_encoded_traversal_maps_direct() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_path_traversal",
            ["traversal:double_encoded_dotdot_slash(+4)", "encoding:decoded_depth_2"],
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A01:2025", "direct")
    assert_has(mapping, "CWE", "CWE-22", "direct")
    assert_has(mapping, "WSTG", "WSTG-ATHZ-01", "direct")
    assert mapping == build_security_standards_mapping(
        build_result(
            "suspicious_path_traversal",
            ["traversal:double_encoded_dotdot_slash(+4)", "encoding:decoded_depth_2"],
        )
    )


def test_direct_private_secret_is_not_traversal() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_scan",
            ["sensitive_path:private_file"],
            uri="/private/secret.txt",
            raw_request_target="/private/secret.txt",
        )
    )

    assert_schema(mapping, "behavior_only")
    assert mapping["items"] == []
    assert_not_id(mapping, "CWE-22")


def test_direct_env_is_not_cwe22() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_file_disclosure",
            ["sensitive_path:env_file"],
            uri="/.env",
            raw_request_target="/.env",
        )
    )

    assert_schema(mapping, "attempt_only")
    assert_has(mapping, "OWASP_TOP10", "A02:2025", "related")
    assert_has(mapping, "CWE", "CWE-552", "conditional")
    assert_has(mapping, "WSTG", "WSTG-CONF-04", "related")
    assert_has(mapping, "WSTG", "WSTG-CONF-03", "related")
    assert_not_id(mapping, "CWE-22")
    assert_not_id(mapping, "CWE-200")


def test_sqli_maps_injection_direct() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_sqli", ["sqli:boolean_true_condition"])
    )

    assert_has(mapping, "OWASP_TOP10", "A05:2025", "direct")
    assert_has(mapping, "CWE", "CWE-89", "direct")
    assert_has(mapping, "WSTG", "WSTG-INPV-05", "direct")
    assert_not_id(mapping, "A01:2025")
    assert item_by_id(mapping, "CWE-89")["basis"] == [
        "stage1_verdict:suspicious_sqli",
        "prepare_hint_family:sqli",
    ]
    assert_no_success_claims(mapping)


def test_sqli_query_secret_string_does_not_add_sensitive_file_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_sqli",
            ["sqli:union_select"],
            query_string="q=UNION SELECT secret FROM users",
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A05:2025", "direct")
    assert_has(mapping, "CWE", "CWE-89", "direct")
    assert_has(mapping, "WSTG", "WSTG-INPV-05", "direct")
    assert_not_id(mapping, "CWE-552")
    assert_not_id(mapping, "WSTG-CONF-04")
    assert_not_id(mapping, "A01:2025")
    assert_not_id(mapping, "A02:2025")


def test_sqli_query_passwd_string_does_not_add_sensitive_file_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_sqli",
            ["sqli:union_select"],
            query_string="q=UNION SELECT passwd FROM users",
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A05:2025", "direct")
    assert_has(mapping, "CWE", "CWE-89", "direct")
    assert_has(mapping, "WSTG", "WSTG-INPV-05", "direct")
    assert_not_id(mapping, "CWE-552")
    assert_not_id(mapping, "WSTG-CONF-04")
    assert_not_id(mapping, "A01:2025")
    assert_not_id(mapping, "A02:2025")


def test_xss_maps_without_stored_claim() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_xss", ["xss:script_tag"])
    )

    assert_has(mapping, "OWASP_TOP10", "A05:2025", "direct")
    assert_has(mapping, "CWE", "CWE-79", "direct")
    assert_has(mapping, "WSTG", "WSTG-INPV-01", "related")
    assert_not_id(mapping, "WSTG-INPV-02")
    assert mapping["observability"] == "attempt_only"
    assert_no_success_claims(mapping)


def test_xss_query_admin_string_without_prepare_hint_does_not_add_admin_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_xss",
            ["xss:script_tag"],
            query_string="next=/admin",
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A05:2025", "direct")
    assert_has(mapping, "CWE", "CWE-79", "direct")
    assert_has(mapping, "WSTG", "WSTG-INPV-01", "related")
    assert_not_id(mapping, "WSTG-CONF-05")
    assert_not_id(mapping, "CWE-425")
    assert_not_id(mapping, "A01:2025")


def test_location_dash_xss_fp_has_empty_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "likely_false_positive",
            ["xss:external_navigation", "context:educational_xss_search"],
        )
    )

    assert_schema(mapping, "not_applicable")
    assert mapping["items"] == []
    assert_not_id(mapping, "CWE-79")
    assert_not_id(mapping, "WSTG-INPV-01")


def test_cmdi_maps_cwe78_not_cwe77() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_command_injection", ["cmdi:semicolon"])
    )

    assert_has(mapping, "OWASP_TOP10", "A05:2025", "direct")
    assert_has(mapping, "CWE", "CWE-78", "direct")
    assert_has(mapping, "WSTG", "WSTG-INPV-12", "direct")
    assert_not_id(mapping, "CWE-77")
    assert mapping["observability"] == "attempt_only"


def test_repeated_bruteforce_cwe307_conditional() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_bruteforce",
            ["auth_abuse:repeated_401", "auth_abuse:rapid_fail_burst"],
        )
    )

    assert_schema(mapping, "behavior_only")
    assert_has(mapping, "OWASP_TOP10", "A07:2025", "direct")
    assert_has(mapping, "CWE", "CWE-307", "conditional")
    assert_has(mapping, "WSTG", "WSTG-ATHN-03", "related")
    assert ("CWE", "CWE-307", "direct") not in keys(mapping)
    assert_no_success_claims(mapping)


def test_broad_auth_abuse_no_default_cwe() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_auth_abuse",
            ["login_endpoint(+1)", "auth_abuse:no_auth_success_inference"],
        )
    )

    assert_schema(mapping, "behavior_only")
    assert_has(mapping, "OWASP_TOP10", "A07:2025", "related")
    assert_not_id(mapping, "CWE-307")
    assert_not_id(mapping, "WSTG-ATHN-03")


def test_repeated_auth_abuse_adds_conditional_cwe307() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_auth_abuse",
            ["auth_abuse:repeated_auth_endpoint", "auth_abuse:no_auth_success_inference"],
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A07:2025", "conditional")
    assert_has(mapping, "CWE", "CWE-307", "conditional")
    assert ("OWASP_TOP10", "A07:2025", "related") not in keys(mapping)
    assert_not_id(mapping, "WSTG-ATHN-03")


def test_generic_scanner_empty_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_scan", ["ua:scanner(+1)"])
    )

    assert_schema(mapping, "behavior_only")
    assert mapping["items"] == []
    assert all(item["standard"] not in {"OWASP_TOP10", "CWE"} for item in mapping["items"])


def test_admin_path_enumeration_scanner_wstg_related() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_scan",
            ["sensitive_path:admin", "dir_probe:admin_sequence"],
            uri="/admin",
        )
    )

    assert_schema(mapping, "behavior_only")
    assert_has(mapping, "WSTG", "WSTG-CONF-05", "related")
    assert all(item["standard"] != "OWASP_TOP10" for item in mapping["items"])
    assert_not_id(mapping, "CWE-425")


def test_prepare_admin_enumeration_hint_preserves_cross_category_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_sqli",
            ["sqli:union_select", "sensitive_path:admin", "dir_probe:admin_sequence"],
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A05:2025", "direct")
    assert_has(mapping, "CWE", "CWE-89", "direct")
    assert_has(mapping, "WSTG", "WSTG-INPV-05", "direct")
    assert_has(mapping, "OWASP_TOP10", "A01:2025", "related")
    assert_has(mapping, "CWE", "CWE-425", "conditional")
    assert_has(mapping, "WSTG", "WSTG-CONF-05", "related")


def test_server_error_probe_wstg_only() -> None:
    mapping = build_security_standards_mapping(
        build_result("server_error_probe", ["error_status:500(+2)", "error_table_context(+2)"])
    )

    assert_schema(mapping, "behavior_only")
    assert_has(mapping, "WSTG", "WSTG-ERRH-01", "related")
    assert_not_id(mapping, "A10:2025")
    assert_not_id(mapping, "CWE-209")
    assert all(item["standard"] not in {"OWASP_TOP10", "CWE"} for item in mapping["items"])


def test_php_wrapper_file_disclosure_conditional_cwe98() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_file_disclosure",
            [
                "file_disclosure:php_filter_wrapper",
                "file_disclosure:base64_source_intent",
                "file_disclosure:resource_parameter",
            ],
        )
    )

    assert_schema(mapping, "attempt_only")
    assert_has(mapping, "OWASP_TOP10", "A05:2025", "related")
    assert_has(mapping, "CWE", "CWE-98", "conditional")
    assert_has(mapping, "WSTG", "WSTG-ATHZ-01", "related")
    assert_not_id(mapping, "CWE-22")
    assert "stage1_guardrail:file_disclosure_wrapper_normalized" in item_by_id(mapping, "CWE-98")["basis"]


def test_traversal_based_file_disclosure_uses_traversal_branch() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_file_disclosure",
            ["traversal:dotdot_slash(+4)", "file_disclosure:sensitive_resource:config_php"],
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A01:2025", "direct")
    assert_has(mapping, "CWE", "CWE-22", "direct")
    assert_has(mapping, "WSTG", "WSTG-ATHZ-01", "direct")
    assert_not_id(mapping, "CWE-98")


def test_direct_sensitive_file_disclosure_probe() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_file_disclosure",
            ["file_disclosure:sensitive_resource:config_php"],
            uri="/config.php",
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A02:2025", "related")
    assert_has(mapping, "CWE", "CWE-552", "conditional")
    assert_has(mapping, "WSTG", "WSTG-CONF-04", "related")
    assert_has(mapping, "WSTG", "WSTG-CONF-03", "related")
    assert_not_id(mapping, "CWE-22")
    assert_not_id(mapping, "CWE-200")


def test_direct_os_file_disclosure_is_not_traversal() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_file_disclosure",
            ["file_disclosure:sensitive_resource:os_file"],
            query_string="?file=News&op=/etc/passwd%00",
        )
    )

    assert_has(mapping, "OWASP_TOP10", "A02:2025", "related")
    assert_has(mapping, "CWE", "CWE-552", "conditional")
    assert_has(mapping, "WSTG", "WSTG-CONF-04", "related")
    assert_has(mapping, "WSTG", "WSTG-CONF-03", "related")
    assert_not_id(mapping, "CWE-22")


def test_benign_normal_empty_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result("benign_normal", ["baseline:static_asset"])
    )

    assert_schema(mapping, "not_applicable")
    assert mapping["items"] == []
    assert mapping["unmapped_reason"] == "non_security_verdict"


def test_likely_false_positive_empty_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "likely_false_positive",
            ["fp_hint:sql_keyword_without_attack_structure", "sqli:select_keyword"],
        )
    )

    assert_schema(mapping, "not_applicable")
    assert mapping["items"] == []
    assert_not_id(mapping, "A05:2025")
    assert_not_id(mapping, "CWE-89")


def test_inconclusive_empty_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result("inconclusive", ["special_char_ratio_high(+1)"])
    )

    assert_schema(mapping, "not_applicable")
    assert mapping["items"] == []


def test_unknown_future_verdict_empty_mapping() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_new_future", ["l3:new_hint"])
    )

    assert_schema(mapping, "not_applicable")
    assert mapping["items"] == []
    assert mapping["unmapped_reason"] == "unknown_verdict"


def test_invalid_input_safe_empty_mapping() -> None:
    mapping = build_security_standards_mapping(None)  # type: ignore[arg-type]

    assert_schema(mapping, "not_applicable")
    assert mapping["items"] == []
    assert mapping["unmapped_reason"] == "invalid_input"


def test_malformed_reason_hints_safe_empty_when_no_rule_applies() -> None:
    mapping = build_security_standards_mapping(
        {"verdict": "suspicious_scan", "reason_hints": {"unexpected": "shape"}}
    )

    assert_schema(mapping, "behavior_only")
    assert mapping["items"] == []


def test_duplicate_reason_hints_deduplicate_items() -> None:
    mapping = build_security_standards_mapping(
        build_result(
            "suspicious_sqli",
            [
                "sqli:boolean_true_condition",
                "sqli:boolean_true_condition",
                "sqli:comment_sequence",
            ],
        )
    )

    assert len(mapping["items"]) == 3
    assert len(keys(mapping)) == 3
    assert_has(mapping, "OWASP_TOP10", "A05:2025", "direct")
    assert_has(mapping, "CWE", "CWE-89", "direct")
    assert_has(mapping, "WSTG", "WSTG-INPV-05", "direct")


def test_deterministic_output_ordering() -> None:
    result = build_result(
        "suspicious_sqli",
        ["sqli:boolean_true_condition", "hpp:duplicate_param_names", "sensitive_path:admin"],
        uri="/admin/search",
    )

    first = build_security_standards_mapping(result)
    second = build_security_standards_mapping(result)

    assert first == second
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(second, sort_keys=True, ensure_ascii=False)
    standard_order = [item["standard"] for item in first["items"]]
    assert standard_order == sorted(standard_order, key={"OWASP_TOP10": 0, "CWE": 1, "WSTG": 2}.get)
    assert [item["rule_id"] for item in first["items"]] == [
        "STD-MAP-SQLI-001",
        "STD-MAP-SENSITIVE-001",
        "STD-MAP-SQLI-002",
        "STD-MAP-SENSITIVE-002",
        "STD-MAP-SQLI-003",
        "STD-MAP-SENSITIVE-004",
        "STD-MAP-HPP-001",
    ]


def test_candidate_reason_hints_are_used_when_stage1_result_lacks_them() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_file_disclosure", []),
        candidate={
            "reason_hints": [
                "file_disclosure:php_filter_wrapper",
                "file_disclosure:base64_source_intent",
                "file_disclosure:resource_parameter",
            ]
        },
    )

    assert_has(mapping, "CWE", "CWE-98", "conditional")
    assert "prepare_hint_family:file_disclosure" in item_by_id(mapping, "CWE-98")["basis"]


def test_basis_uses_canonical_tokens_not_raw_reason_hints() -> None:
    mapping = build_security_standards_mapping(
        build_result("suspicious_sqli", ["sqli:boolean_true_condition(+4)"])
    )

    for item in mapping["items"]:
        assert "reason_hint:" not in item["basis"]
        assert "sqli:boolean_true_condition(+4)" not in item["basis"]
        assert item["basis"] == [
            "stage1_verdict:suspicious_sqli",
            "prepare_hint_family:sqli",
        ]
