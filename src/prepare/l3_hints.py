from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import parse_qsl, urlparse

LOG4SHELL_JNDI_LOOKUP_RE = re.compile(r"(?i)\$\{\s*jndi\s*:\s*(ldap|rmi|dns)\s*://[^\s}]+")
LOG4SHELL_OBFUSCATED_JNDI_LOOKUP_RE = re.compile(
    r"(?i)\$\{\s*\$\{\s*::-\s*j\s*\}\s*\$\{\s*::-\s*n\s*\}\s*\$\{\s*::-\s*d\s*\}\s*\$\{\s*::-\s*i\s*\}\s*:\s*(ldap|rmi|dns)\s*://[^\s}]+"
)
LOG4SHELL_LDAP_RE = re.compile(r"(?i)\$\{\s*jndi\s*:\s*ldap\s*://[^\s}]+")
LOG4SHELL_OBFUSCATED_LDAP_RE = re.compile(
    r"(?i)\$\{\s*\$\{\s*::-\s*j\s*\}\s*\$\{\s*::-\s*n\s*\}\s*\$\{\s*::-\s*d\s*\}\s*\$\{\s*::-\s*i\s*\}\s*:\s*ldap\s*://[^\s}]+"
)
LOG4SHELL_RMI_RE = re.compile(r"(?i)\$\{\s*jndi\s*:\s*rmi\s*://[^\s}]+")
LOG4SHELL_OBFUSCATED_RMI_RE = re.compile(
    r"(?i)\$\{\s*\$\{\s*::-\s*j\s*\}\s*\$\{\s*::-\s*n\s*\}\s*\$\{\s*::-\s*d\s*\}\s*\$\{\s*::-\s*i\s*\}\s*:\s*rmi\s*://[^\s}]+"
)
LOG4SHELL_DNS_RE = re.compile(r"(?i)\$\{\s*jndi\s*:\s*dns\s*://[^\s}]+")
LOG4SHELL_OBFUSCATED_DNS_RE = re.compile(
    r"(?i)\$\{\s*\$\{\s*::-\s*j\s*\}\s*\$\{\s*::-\s*n\s*\}\s*\$\{\s*::-\s*d\s*\}\s*\$\{\s*::-\s*i\s*\}\s*:\s*dns\s*://[^\s}]+"
)
SSRF_PARAM_NAMES = {"url", "uri", "target", "next", "redirect", "callback", "webhook", "image", "fetch", "resource"}
SSRF_METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal"}
SSTI_JINJA_ARITHMETIC_RE = re.compile(r"\{\{\s*\d{1,8}\s*[\*\+\-/]\s*\d{1,8}\s*\}\}")
SSTI_JINJA_OBJECT_RE = re.compile(r"(?i)\{\{\s*(?:config\b|self(?:\.__init__)?\b|request\b|cycler\b|namespace\b|class\b)[^}]{0,120}\}\}")
SSTI_FREEMARKER_RE = re.compile(r"(?i)(?:\$\{|#\{)\s*(?:\d{1,8}\s*[\*\+\-/]\s*\d{1,8}|T\s*\(\s*java\.lang\.Runtime\s*\)|config\b|class\b)[^}]{0,120}\}")
SSTI_JSP_RE = re.compile(r"(?i)<%=\s*(?:\d{1,8}\s*[\*\+\-/]\s*\d{1,8}|T\s*\(\s*java\.lang\.Runtime\s*\)|config\b|class\b)[^%]{0,120}%>")
EDUCATIONAL_SSTI_SEARCH_TERMS = (
    "how to",
    "tutorial",
    "example",
    "guide",
    "docs",
    "documentation",
    "learn",
    "usage",
    "사용법",
    "예제",
    "튜토리얼",
    "강의",
    "문서",
)
EDUCATIONAL_SSTI_KEYWORDS = (
    "ssti",
    "jinja",
    "template",
    "freemarker",
    "mustache",
    "velocity",
)
WEBSHELL_CMD_PARAM_NAMES = {"cmd", "exec", "command", "shell", "powershell"}
WEBSHELL_KNOWN_FILENAMES = {"shell.php", "cmd.php", "webshell.php", "wso.php", "c99.php", "r57.php"}
WEBSHELL_UPLOAD_PATH_HINTS = ("/upload/", "/uploads/")

__all__ = [
    "classify_ssrf_target",
    "classify_webshell_path",
    "detect_educational_ssti_search_context",
    "detect_log4shell_hints",
    "detect_ssrf_hints",
    "detect_ssti_hints",
    "detect_webshell_hints",
    "extract_query_pairs_from_variants",
]


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _raw_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _append_unique_hint(hints: List[str], hint: str) -> None:
    text = _raw_text(hint)
    if text and text not in hints:
        hints.append(text)


def _extend_unique_hints(hints: List[str], extra_hints: Iterable[str]) -> None:
    for hint in extra_hints:
        _append_unique_hint(hints, hint)


def _unique_non_empty_texts(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        text = _raw_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def extract_query_pairs_from_variants(
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    seen = set()
    raw_candidates = [_raw_text(item.get("text")) for item in query_variants]
    raw_candidates.extend(
        _raw_text(item.get("text")).split("?", 1)[1]
        for item in raw_request_target_variants
        if "?" in _raw_text(item.get("text"))
    )
    for raw in raw_candidates:
        text = raw[1:] if raw.startswith("?") else raw
        if not text:
            continue
        try:
            parsed_pairs = parse_qsl(text, keep_blank_values=True)
        except Exception:
            continue
        for key, value in parsed_pairs:
            key_norm = _normalize_text(key).lower()
            value_norm = _normalize_text(value)
            if not key_norm:
                continue
            dedup_key = (key_norm, value_norm)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            pairs.append((key_norm, value_norm))
    return pairs


def detect_log4shell_hints(
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    hints: List[str] = []
    score_boost = 0
    samples = _unique_non_empty_texts(
        [combined_target] + [_raw_text(item.get("text")) for item in query_variants + raw_request_target_variants]
    )
    if not samples:
        return 0, []

    has_jndi_lookup = any(
        LOG4SHELL_JNDI_LOOKUP_RE.search(sample) or LOG4SHELL_OBFUSCATED_JNDI_LOOKUP_RE.search(sample)
        for sample in samples
    )
    if has_jndi_lookup:
        score_boost += 5
        _append_unique_hint(hints, "l3:log4shell")
        _append_unique_hint(hints, "log4shell:jndi_lookup")
        if any(LOG4SHELL_LDAP_RE.search(sample) or LOG4SHELL_OBFUSCATED_LDAP_RE.search(sample) for sample in samples):
            _append_unique_hint(hints, "log4shell:ldap_callback")
        if any(LOG4SHELL_RMI_RE.search(sample) or LOG4SHELL_OBFUSCATED_RMI_RE.search(sample) for sample in samples):
            _append_unique_hint(hints, "log4shell:rmi_callback")
        if any(LOG4SHELL_DNS_RE.search(sample) or LOG4SHELL_OBFUSCATED_DNS_RE.search(sample) for sample in samples):
            _append_unique_hint(hints, "log4shell:dns_callback")

    return score_boost, hints


def classify_ssrf_target(value: str) -> List[str]:
    text = _normalize_text(value)
    if not text:
        return []

    try:
        parsed = urlparse(text)
    except Exception:
        return []

    if parsed.scheme.lower() not in {"http", "https"}:
        return []

    hostname = _raw_text(parsed.hostname).lower()
    if not hostname:
        return []

    hints: List[str] = []
    if hostname == "localhost":
        _append_unique_hint(hints, "ssrf:localhost_target")
    elif hostname == "metadata.google.internal":
        _append_unique_hint(hints, "ssrf:cloud_metadata_target")
    else:
        try:
            host_ip = ipaddress.ip_address(hostname.strip("[]"))
        except ValueError:
            host_ip = None
        if host_ip is not None:
            if host_ip == ipaddress.ip_address("169.254.169.254"):
                _append_unique_hint(hints, "ssrf:metadata_ip")
                _append_unique_hint(hints, "ssrf:cloud_metadata_target")
            elif host_ip.is_loopback:
                _append_unique_hint(hints, "ssrf:localhost_target")
            elif host_ip.is_private:
                _append_unique_hint(hints, "ssrf:internal_ip_target")

    if hostname in SSRF_METADATA_HOSTS and "ssrf:cloud_metadata_target" not in hints:
        _append_unique_hint(hints, "ssrf:cloud_metadata_target")
    return hints


def detect_ssrf_hints(
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    hints: List[str] = []
    score_boost = 0
    pairs = extract_query_pairs_from_variants(query_variants, raw_request_target_variants)
    matched_target = False
    for key, value in pairs:
        if key not in SSRF_PARAM_NAMES:
            continue
        target_hints = classify_ssrf_target(value)
        if not target_hints:
            continue
        matched_target = True
        _append_unique_hint(hints, "ssrf:url_parameter")
        _extend_unique_hints(hints, target_hints)

    if matched_target:
        score_boost += 5
        _append_unique_hint(hints, "l3:ssrf")

    return score_boost, hints


def detect_educational_ssti_search_context(text: str) -> bool:
    lowered = _normalize_text(text).lower()
    if not lowered:
        return False
    return any(term in lowered for term in EDUCATIONAL_SSTI_SEARCH_TERMS) and any(
        keyword in lowered for keyword in EDUCATIONAL_SSTI_KEYWORDS
    )


def detect_ssti_hints(
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    hints: List[str] = []
    score_boost = 0
    samples = _unique_non_empty_texts(
        [combined_target] + [_raw_text(item.get("text")) for item in query_variants + raw_request_target_variants]
    )
    if not samples:
        return 0, []

    has_jinja = any(SSTI_JINJA_ARITHMETIC_RE.search(sample) or SSTI_JINJA_OBJECT_RE.search(sample) for sample in samples)
    has_freemarker = any(SSTI_FREEMARKER_RE.search(sample) for sample in samples)
    has_template_expression = has_jinja or has_freemarker or any(SSTI_JSP_RE.search(sample) for sample in samples)
    if not has_template_expression:
        return 0, []

    score_boost += 4
    _append_unique_hint(hints, "l3:ssti")
    _append_unique_hint(hints, "ssti:template_expression")
    if has_jinja:
        _append_unique_hint(hints, "ssti:jinja_expression")
    if has_freemarker:
        _append_unique_hint(hints, "ssti:freemarker_expression")
    return score_boost, hints


def classify_webshell_path(path: str) -> List[str]:
    normalized_path = _normalize_text(path).lower()
    if not normalized_path:
        return []

    hints: List[str] = []
    filename = normalized_path.rsplit("/", 1)[-1]
    if filename in WEBSHELL_KNOWN_FILENAMES:
        _append_unique_hint(hints, "webshell:script_filename")
        _append_unique_hint(hints, "webshell:known_shell_name")
        return hints

    if normalized_path.endswith("/shell.php") or normalized_path.endswith("/cmd.php") or normalized_path.endswith("/webshell.php"):
        _append_unique_hint(hints, "webshell:script_filename")
    if any(segment in normalized_path for segment in WEBSHELL_UPLOAD_PATH_HINTS) and normalized_path.endswith(".php"):
        _append_unique_hint(hints, "webshell:script_filename")
    return hints


def detect_webshell_hints(
    request_path: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    hints: List[str] = []
    score_boost = 0
    path_hints = classify_webshell_path(request_path)
    if not path_hints:
        return 0, []

    pairs = extract_query_pairs_from_variants(query_variants, raw_request_target_variants)
    has_cmd_parameter = any(key in WEBSHELL_CMD_PARAM_NAMES and _raw_text(value) for key, value in pairs)
    if not has_cmd_parameter:
        return 0, []

    score_boost += 4
    _append_unique_hint(hints, "l3:webshell_probe")
    _extend_unique_hints(hints, path_hints)
    _append_unique_hint(hints, "webshell:cmd_parameter")
    return score_boost, hints
