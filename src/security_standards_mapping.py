#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic OWASP Top 10:2025 / CWE / OWASP WSTG enrichment.

This module does not detect new attacks. It maps existing Stage1 verdicts and
Prepare reason_hints to standards taxonomy/test-scenario metadata.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "security_standards_mapping.v1"
SOURCE = "deterministic_stage1_enrichment"

STANDARD_ORDER = {"OWASP_TOP10": 0, "CWE": 1, "WSTG": 2}
RELATIONSHIP_PRECEDENCE = {"direct": 3, "conditional": 2, "related": 1}

KNOWN_VERDICTS = {
    "benign_normal",
    "likely_false_positive",
    "suspicious_scan",
    "suspicious_bruteforce",
    "suspicious_sqli",
    "suspicious_xss",
    "suspicious_path_traversal",
    "suspicious_file_disclosure",
    "suspicious_command_injection",
    "suspicious_auth_abuse",
    "server_error_probe",
    "inconclusive",
}

NON_SECURITY_VERDICTS = {"benign_normal", "likely_false_positive", "inconclusive"}

ATTEMPT_VERDICTS = {
    "suspicious_path_traversal",
    "suspicious_sqli",
    "suspicious_xss",
    "suspicious_command_injection",
    "suspicious_file_disclosure",
}

BEHAVIOR_VERDICTS = {
    "suspicious_bruteforce",
    "suspicious_auth_abuse",
    "suspicious_scan",
    "server_error_probe",
}

STANDARD_NAMES = {
    ("OWASP_TOP10", "A01:2025"): "Broken Access Control",
    ("OWASP_TOP10", "A02:2025"): "Security Misconfiguration",
    ("OWASP_TOP10", "A05:2025"): "Injection",
    ("OWASP_TOP10", "A07:2025"): "Authentication Failures",
    ("CWE", "CWE-22"): "Path Traversal",
    ("CWE", "CWE-78"): "OS Command Injection",
    ("CWE", "CWE-79"): "Cross-site Scripting",
    ("CWE", "CWE-89"): "SQL Injection",
    ("CWE", "CWE-98"): "PHP Remote File Inclusion",
    ("CWE", "CWE-307"): "Improper Restriction of Excessive Authentication Attempts",
    ("CWE", "CWE-425"): "Direct Request",
    ("CWE", "CWE-552"): "Files or Directories Accessible to External Parties",
    ("WSTG", "WSTG-ATHZ-01"): "Testing Directory Traversal File Include",
    ("WSTG", "WSTG-ATHN-03"): "Testing for Weak Lock Out Mechanism",
    ("WSTG", "WSTG-INPV-01"): "Testing for Reflected Cross Site Scripting",
    ("WSTG", "WSTG-INPV-04"): "Testing for HTTP Parameter Pollution",
    ("WSTG", "WSTG-INPV-05"): "Testing for SQL Injection",
    ("WSTG", "WSTG-INPV-12"): "Testing for Command Injection",
    ("WSTG", "WSTG-CONF-03"): "Test File Extensions Handling for Sensitive Information",
    ("WSTG", "WSTG-CONF-04"): "Review Old Backup and Unreferenced Files for Sensitive Information",
    ("WSTG", "WSTG-CONF-05"): "Enumerate Infrastructure and Application Admin Interfaces",
    ("WSTG", "WSTG-CONF-06"): "Test HTTP Methods",
    ("WSTG", "WSTG-ERRH-01"): "Testing for Improper Error Handling",
    ("WSTG", "WSTG-INFO-06"): "Identify Application Entry Points",
}

BOUNDARY_NOTES = {
    "traversal": "Observed directory traversal pattern does not confirm a path traversal vulnerability, file read, or access-control bypass.",
    "sqli": "Apache logs do not confirm DB query execution, DB results, schema exposure, or data exposure.",
    "xss": "Apache logs do not confirm response reflection, stored persistence, browser execution, or cookie/session theft.",
    "cmdi": "Apache logs do not confirm shell invocation, command execution, process creation, or compromise.",
    "bruteforce": "Repeated authentication behavior does not confirm credential success, lockout absence, CAPTCHA absence, or rate-limit absence.",
    "auth": "Observed authentication abuse context does not confirm authentication control failure, bypass, account takeover, or lockout weakness.",
    "file_traversal": "File disclosure verdict with traversal evidence still does not confirm file content exposure or exploitation success.",
    "file_php": "PHP wrapper/source disclosure pattern does not confirm include/require behavior or file content exposure.",
    "file_direct": "Direct sensitive file probing does not confirm external accessibility, sensitive information exposure, or path traversal.",
    "sensitive": "Sensitive path probing is forced-browsing context only; existence, access, and exposure are not confirmed.",
    "method": "HTTP method probing does not confirm the method is allowed, caused state change, or bypassed authorization.",
    "protocol": "Protocol anomaly context does not confirm security misconfiguration, backend confusion, or fail-open behavior.",
    "hpp": "Duplicate parameters are an HTTP Parameter Pollution test context; application-specific parameter parsing is unknown.",
    "error": "Server error probing does not confirm A10 mishandling, stack trace disclosure, fail-open behavior, or exploitation success.",
    "scan": "Scan/recon behavior is a test/discovery context and not an OWASP vulnerability category by itself.",
}

RULE_ORDER = {
    "STD-MAP-TRAVERSAL-001": 10,
    "STD-MAP-TRAVERSAL-002": 11,
    "STD-MAP-TRAVERSAL-003": 12,
    "STD-MAP-SQLI-001": 20,
    "STD-MAP-SQLI-002": 21,
    "STD-MAP-SQLI-003": 22,
    "STD-MAP-XSS-001": 30,
    "STD-MAP-XSS-002": 31,
    "STD-MAP-XSS-003": 32,
    "STD-MAP-CMDI-001": 40,
    "STD-MAP-CMDI-002": 41,
    "STD-MAP-CMDI-003": 42,
    "STD-MAP-BRUTE-001": 50,
    "STD-MAP-BRUTE-002": 51,
    "STD-MAP-BRUTE-003": 52,
    "STD-MAP-AUTH-001": 60,
    "STD-MAP-AUTH-002": 61,
    "STD-MAP-AUTH-003": 62,
    "STD-MAP-FILE-TRAV-001": 70,
    "STD-MAP-FILE-TRAV-002": 71,
    "STD-MAP-FILE-TRAV-003": 72,
    "STD-MAP-FILE-PHP-001": 80,
    "STD-MAP-FILE-PHP-002": 81,
    "STD-MAP-FILE-PHP-003": 82,
    "STD-MAP-FILE-DIRECT-001": 90,
    "STD-MAP-FILE-DIRECT-002": 91,
    "STD-MAP-FILE-DIRECT-003": 92,
    "STD-MAP-FILE-DIRECT-004": 93,
    "STD-MAP-SENSITIVE-001": 100,
    "STD-MAP-SENSITIVE-002": 101,
    "STD-MAP-SENSITIVE-003": 102,
    "STD-MAP-SENSITIVE-004": 103,
    "STD-MAP-SENSITIVE-005": 104,
    "STD-MAP-METHOD-001": 110,
    "STD-MAP-PROTOCOL-001": 120,
    "STD-MAP-HPP-001": 130,
    "STD-MAP-ERROR-001": 140,
    "STD-MAP-SCAN-001": 150,
    "STD-MAP-SCAN-002": 151,
}


def get_security_standards_mapping_schema_version() -> str:
    return SCHEMA_VERSION


def build_security_standards_mapping(
    stage1_result: Mapping[str, Any],
    candidate: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return deterministic standards mapping for one Stage1 result.

    Invalid inputs fail open to an empty mapping. The function intentionally
    avoids URL decoding and attack regexes; it reuses verdict and reason_hints.
    """

    try:
        if not isinstance(stage1_result, Mapping):
            return _empty_mapping("not_applicable", "invalid_input")

        source = _InputView(stage1_result, candidate if isinstance(candidate, Mapping) else None)
        verdict = source.verdict
        observability = _observability_for_verdict(verdict)

        if verdict not in KNOWN_VERDICTS:
            return _empty_mapping("not_applicable", "unknown_verdict")
        if verdict in NON_SECURITY_VERDICTS:
            return _empty_mapping(observability, "non_security_verdict")

        items: List[Dict[str, Any]] = []
        if verdict == "suspicious_path_traversal":
            _add_path_traversal(items, verdict, source)
        elif verdict == "suspicious_sqli":
            _add_sqli(items, verdict, source)
        elif verdict == "suspicious_xss":
            _add_xss(items, verdict, source)
        elif verdict == "suspicious_command_injection":
            _add_cmdi(items, verdict, source)
        elif verdict == "suspicious_bruteforce":
            _add_bruteforce(items, verdict, source)
        elif verdict == "suspicious_auth_abuse":
            _add_auth_abuse(items, verdict, source)
        elif verdict == "suspicious_file_disclosure":
            _add_file_disclosure(items, verdict, source)
        elif verdict == "server_error_probe":
            _add_server_error(items, verdict, source)
        elif verdict == "suspicious_scan":
            _add_scan(items, verdict, source)

        if verdict != "suspicious_scan":
            _add_evidence_combination_rules(items, verdict, source)

        normalized_items = _dedupe_and_sort(items)
        return {
            "schema_version": SCHEMA_VERSION,
            "source": SOURCE,
            "observability": observability,
            "items": normalized_items,
            "unmapped_reason": "" if normalized_items else "no_applicable_rule",
        }
    except (AttributeError, TypeError, ValueError):
        return _empty_mapping("not_applicable", "mapping_error")


class _InputView:
    def __init__(self, stage1_result: Mapping[str, Any], candidate: Optional[Mapping[str, Any]]) -> None:
        self.stage1_result = stage1_result
        self.candidate = candidate or {}
        self.verdict = _normalize_str(stage1_result.get("verdict"))
        self.verdict_hint = _normalize_str(_first_non_empty(stage1_result.get("verdict_hint"), self.candidate.get("verdict_hint")))
        self.uri = _normalize_str(_first_non_empty(stage1_result.get("uri"), self.candidate.get("uri"))).lower()
        self.query_string = _normalize_str(_first_non_empty(stage1_result.get("query_string"), self.candidate.get("query_string"))).lower()
        self.raw_request_target = _normalize_str(
            _first_non_empty(stage1_result.get("raw_request_target"), self.candidate.get("raw_request_target"))
        ).lower()
        self.method = _normalize_str(_first_non_empty(stage1_result.get("method"), self.candidate.get("method"))).upper()
        self.reason_hints = _merge_unique_strings(
            _normalize_string_list(self.candidate.get("reason_hints")),
            _normalize_string_list(stage1_result.get("reason_hints")),
        )
        self.reason_hints_lower = [hint.lower() for hint in self.reason_hints]

    def has_hint_prefix(self, prefix: str) -> bool:
        return any(hint.startswith(prefix) for hint in self.reason_hints_lower)

    def has_hint(self, value: str) -> bool:
        return value.lower() in self.reason_hints_lower


def _empty_mapping(observability: str, unmapped_reason: str) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "observability": observability,
        "items": [],
        "unmapped_reason": unmapped_reason,
    }


def _normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return ""


def _normalize_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [_normalize_str(item) for item in value if _normalize_str(item)]
    if isinstance(value, tuple):
        return [_normalize_str(item) for item in value if _normalize_str(item)]
    if isinstance(value, str):
        text = _normalize_str(value)
        return [text] if text else []
    return []


def _merge_unique_strings(*groups: Sequence[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for group in groups:
        for value in group:
            text = _normalize_str(value)
            if text and text not in seen:
                merged.append(text)
                seen.add(text)
    return merged


def _observability_for_verdict(verdict: str) -> str:
    if verdict in ATTEMPT_VERDICTS:
        return "attempt_only"
    if verdict in BEHAVIOR_VERDICTS:
        return "behavior_only"
    return "not_applicable"


def _basis(verdict: str, source: _InputView, hint_families: Iterable[str] = (), extras: Iterable[str] = ()) -> List[str]:
    basis = [f"stage1_verdict:{verdict}"]
    for family in hint_families:
        if _has_family(source, family):
            basis.append(f"prepare_hint_family:{family}")
    for extra in extras:
        if extra not in basis:
            basis.append(extra)
    return basis


def _has_family(source: _InputView, family: str) -> bool:
    if family == "auth_abuse":
        return source.has_hint_prefix("auth_abuse:")
    return source.has_hint_prefix(f"{family}:")


def _item(
    rule_id: str,
    standard: str,
    standard_id: str,
    relationship: str,
    basis: Sequence[str],
    boundary_note: str,
) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "standard": standard,
        "id": standard_id,
        "name": STANDARD_NAMES.get((standard, standard_id), ""),
        "relationship": relationship,
        "basis": list(basis),
        "boundary_note": boundary_note,
    }


def _add(items: List[Dict[str, Any]], rule_id: str, standard: str, standard_id: str, relationship: str, basis: Sequence[str], boundary: str) -> None:
    items.append(_item(rule_id, standard, standard_id, relationship, basis, BOUNDARY_NOTES[boundary]))


def _add_path_traversal(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    basis = _basis(verdict, source, ("traversal",))
    _add(items, "STD-MAP-TRAVERSAL-001", "OWASP_TOP10", "A01:2025", "direct", basis, "traversal")
    _add(items, "STD-MAP-TRAVERSAL-002", "CWE", "CWE-22", "direct", basis, "traversal")
    _add(items, "STD-MAP-TRAVERSAL-003", "WSTG", "WSTG-ATHZ-01", "direct", basis, "traversal")


def _add_sqli(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    basis = _basis(verdict, source, ("sqli",))
    _add(items, "STD-MAP-SQLI-001", "OWASP_TOP10", "A05:2025", "direct", basis, "sqli")
    _add(items, "STD-MAP-SQLI-002", "CWE", "CWE-89", "direct", basis, "sqli")
    _add(items, "STD-MAP-SQLI-003", "WSTG", "WSTG-INPV-05", "direct", basis, "sqli")


def _add_xss(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    basis = _basis(verdict, source, ("xss",))
    _add(items, "STD-MAP-XSS-001", "OWASP_TOP10", "A05:2025", "direct", basis, "xss")
    _add(items, "STD-MAP-XSS-002", "CWE", "CWE-79", "direct", basis, "xss")
    _add(items, "STD-MAP-XSS-003", "WSTG", "WSTG-INPV-01", "related", basis, "xss")


def _add_cmdi(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    basis = _basis(verdict, source, ("cmdi",))
    _add(items, "STD-MAP-CMDI-001", "OWASP_TOP10", "A05:2025", "direct", basis, "cmdi")
    _add(items, "STD-MAP-CMDI-002", "CWE", "CWE-78", "direct", basis, "cmdi")
    _add(items, "STD-MAP-CMDI-003", "WSTG", "WSTG-INPV-12", "direct", basis, "cmdi")


def _add_bruteforce(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    basis = _basis(verdict, source, ("auth_abuse",))
    _add(items, "STD-MAP-BRUTE-001", "OWASP_TOP10", "A07:2025", "direct", basis, "bruteforce")
    _add(items, "STD-MAP-BRUTE-002", "CWE", "CWE-307", "conditional", basis, "bruteforce")
    _add(items, "STD-MAP-BRUTE-003", "WSTG", "WSTG-ATHN-03", "related", basis, "bruteforce")


def _add_auth_abuse(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    basis = _basis(verdict, source, ("auth_abuse",))
    if _has_repeated_auth_evidence(source):
        _add(items, "STD-MAP-AUTH-002", "OWASP_TOP10", "A07:2025", "conditional", basis, "auth")
        _add(items, "STD-MAP-AUTH-003", "CWE", "CWE-307", "conditional", basis, "auth")
    else:
        _add(items, "STD-MAP-AUTH-001", "OWASP_TOP10", "A07:2025", "related", basis, "auth")


def _add_file_disclosure(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    if source.has_hint_prefix("traversal:"):
        basis = _basis(verdict, source, ("traversal", "file_disclosure"))
        _add(items, "STD-MAP-FILE-TRAV-001", "OWASP_TOP10", "A01:2025", "direct", basis, "file_traversal")
        _add(items, "STD-MAP-FILE-TRAV-002", "CWE", "CWE-22", "direct", basis, "file_traversal")
        _add(items, "STD-MAP-FILE-TRAV-003", "WSTG", "WSTG-ATHZ-01", "direct", basis, "file_traversal")
        return

    if _has_php_wrapper_evidence(source):
        extras = []
        if source.has_hint("file_disclosure:php_filter_wrapper") and source.has_hint("file_disclosure:base64_source_intent") and source.has_hint("file_disclosure:resource_parameter"):
            extras.append("stage1_guardrail:file_disclosure_wrapper_normalized")
        basis = _basis(verdict, source, ("file_disclosure",), extras)
        _add(items, "STD-MAP-FILE-PHP-001", "OWASP_TOP10", "A05:2025", "related", basis, "file_php")
        _add(items, "STD-MAP-FILE-PHP-002", "CWE", "CWE-98", "conditional", basis, "file_php")
        _add(items, "STD-MAP-FILE-PHP-003", "WSTG", "WSTG-ATHZ-01", "related", basis, "file_php")
        return

    if _has_direct_sensitive_file_evidence(source):
        basis = _basis(verdict, source, ("file_disclosure", "sensitive_path"))
        _add(items, "STD-MAP-FILE-DIRECT-001", "OWASP_TOP10", "A02:2025", "related", basis, "file_direct")
        _add(items, "STD-MAP-FILE-DIRECT-002", "CWE", "CWE-552", "conditional", basis, "file_direct")
        _add(items, "STD-MAP-FILE-DIRECT-003", "WSTG", "WSTG-CONF-04", "related", basis, "file_direct")
        _add(items, "STD-MAP-FILE-DIRECT-004", "WSTG", "WSTG-CONF-03", "related", basis, "file_direct")


def _add_server_error(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    basis = _basis(verdict, source, ("protocol_anomaly",))
    _add(items, "STD-MAP-ERROR-001", "WSTG", "WSTG-ERRH-01", "related", basis, "error")


def _add_scan(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    basis = _basis(verdict, source, ("sensitive_path", "dir_probe", "file_probe"))
    if _has_admin_enumeration_evidence(source):
        _add(items, "STD-MAP-SCAN-001", "WSTG", "WSTG-CONF-05", "related", basis, "scan")
    elif source.has_hint_prefix("dir_probe:") or source.has_hint_prefix("file_probe:"):
        _add(items, "STD-MAP-SCAN-002", "WSTG", "WSTG-INFO-06", "related", basis, "scan")


def _add_evidence_combination_rules(items: List[Dict[str, Any]], verdict: str, source: _InputView) -> None:
    if verdict in NON_SECURITY_VERDICTS or verdict not in KNOWN_VERDICTS:
        return

    if verdict != "suspicious_file_disclosure" and _has_sensitive_path_evidence(source):
        basis = _basis(verdict, source, ("sensitive_path", "dir_probe", "file_probe"))
        if _has_admin_enumeration_evidence(source):
            _add(items, "STD-MAP-SENSITIVE-001", "OWASP_TOP10", "A01:2025", "related", basis, "sensitive")
            _add(items, "STD-MAP-SENSITIVE-002", "CWE", "CWE-425", "conditional", basis, "sensitive")
            _add(items, "STD-MAP-SENSITIVE-004", "WSTG", "WSTG-CONF-05", "related", basis, "sensitive")
        elif _has_direct_sensitive_file_evidence(source):
            _add(items, "STD-MAP-SENSITIVE-003", "CWE", "CWE-552", "conditional", basis, "sensitive")
            _add(items, "STD-MAP-SENSITIVE-005", "WSTG", "WSTG-CONF-04", "related", basis, "sensitive")

    if source.has_hint_prefix("method_probe:"):
        _add(items, "STD-MAP-METHOD-001", "WSTG", "WSTG-CONF-06", "related", _basis(verdict, source, ("method_probe",)), "method")

    if source.has_hint_prefix("protocol_anomaly:") and verdict != "server_error_probe":
        _add(items, "STD-MAP-PROTOCOL-001", "WSTG", "WSTG-ERRH-01", "related", _basis(verdict, source, ("protocol_anomaly",)), "protocol")

    if source.has_hint("hpp:duplicate_param_names") or source.has_hint_prefix("hpp:duplicate_param_names("):
        _add(items, "STD-MAP-HPP-001", "WSTG", "WSTG-INPV-04", "related", _basis(verdict, source, ("hpp",)), "hpp")


def _has_repeated_auth_evidence(source: _InputView) -> bool:
    return any(
        hint.startswith("auth_abuse:repeated_")
        or hint == "auth_abuse:rapid_fail_burst"
        or hint.startswith("auth_abuse:rapid_fail_burst(")
        for hint in source.reason_hints_lower
    )


def _has_php_wrapper_evidence(source: _InputView) -> bool:
    return (
        source.has_hint("file_disclosure:php_filter_wrapper")
        or (
            source.has_hint("file_disclosure:base64_source_intent")
            and source.has_hint("file_disclosure:resource_parameter")
        )
    )


def _has_direct_sensitive_file_evidence(source: _InputView) -> bool:
    return (
        source.has_hint_prefix("file_disclosure:sensitive_resource:")
        or source.has_hint_prefix("sensitive_path:")
    )


def _has_sensitive_path_evidence(source: _InputView) -> bool:
    return (
        source.has_hint_prefix("sensitive_path:")
        or source.has_hint_prefix("dir_probe:")
        or source.has_hint_prefix("file_probe:")
        or _has_admin_enumeration_evidence(source)
        or _has_direct_sensitive_file_evidence(source)
    )


def _has_admin_enumeration_evidence(source: _InputView) -> bool:
    return (
        any(
            hint.startswith("sensitive_path:admin")
            or hint.startswith("dir_probe:admin")
            or hint.startswith("file_probe:admin")
            for hint in source.reason_hints_lower
        )
    )


def _dedupe_and_sort(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in items:
        key = (
            _normalize_str(item.get("standard")),
            _normalize_str(item.get("id")),
        )
        if not all(key) or key in deduped:
            existing = deduped.get(key)
            if existing is None:
                continue
            if _should_replace_mapping_item(existing, item):
                deduped[key] = item
            continue
        deduped[key] = item
    return sorted(
        deduped.values(),
        key=lambda item: (
            STANDARD_ORDER.get(_normalize_str(item.get("standard")), 99),
            RULE_ORDER.get(_normalize_str(item.get("rule_id")), 9999),
            _normalize_str(item.get("id")),
            _normalize_str(item.get("relationship")),
        ),
    )


def _should_replace_mapping_item(existing: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    existing_relationship = _normalize_str(existing.get("relationship"))
    candidate_relationship = _normalize_str(candidate.get("relationship"))
    existing_rank = RELATIONSHIP_PRECEDENCE.get(existing_relationship, 0)
    candidate_rank = RELATIONSHIP_PRECEDENCE.get(candidate_relationship, 0)
    if candidate_rank != existing_rank:
        return candidate_rank > existing_rank
    return RULE_ORDER.get(_normalize_str(candidate.get("rule_id")), 9999) < RULE_ORDER.get(
        _normalize_str(existing.get("rule_id")),
        9999,
    )
