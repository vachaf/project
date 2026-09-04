from __future__ import annotations

import re
from typing import List, Tuple


_CREDIBLE_EVENT_HANDLER_RE = (
    r"(?:\bon(?:abort|blur|change|click|contextmenu|dblclick|error|focus|input|keydown|keypress|keyup|"
    r"load|mousedown|mouseenter|mouseleave|mousemove|mouseout|mouseover|mouseup|reset|submit|unload)\s*="
    r"|<\s*[a-z][^>]{0,512}?\bon[a-z0-9_]+\s*="
    r"|['\"]\s*on[a-z0-9_]+\s*=)"
)
_JAVASCRIPT_EXECUTABLE_CONTEXT_RE = (
    r"(?:\bstyle\s*=\s*[^<>\r\n]{0,512}?\b[a-z-]+\s*:\s*url\s*\(\s*"
    r"|<\s*[a-z][^>]{0,512}?\b(?:href|src|action|formaction)\s*=\s*['\"]?\s*)javascript\s*:"
    r"|(?<!url\()\bjavascript\s*:"
)
_ALERT_EXECUTABLE_CONTEXT_RE = (
    r"(?:<\s*script\b[^>]*>[^<]{0,1024}?|\b(?:onload|onerror|onclick)\s*=\s*)alert\s*\("
    r"|(?:" + _JAVASCRIPT_EXECUTABLE_CONTEXT_RE + r")[^<]{0,512}?\balert\s*\("
)
_BROWSER_DATA_EXFIL_RE = (
    r"(?:(?:document\.cookie|localStorage|sessionStorage).{0,512}?"
    r"(?:document\.location|window\.location|location\s*\.\s*(?:href|assign|replace)|fetch\s*\(|"
    r"new\s+Image\s*\(\s*\)\s*\.src|navigator\.sendBeacon\s*\(|https?://)"
    r"|(?:document\.location|window\.location|location\s*\.\s*(?:href|assign|replace)|fetch\s*\(|"
    r"new\s+Image\s*\(\s*\)\s*\.src|navigator\.sendBeacon\s*\(|https?://).{0,512}?"
    r"(?:document\.cookie|localStorage|sessionStorage))"
)

XSS_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("script_tag", re.compile(r"(?i)<\s*script\b"), 5),
    ("img_onerror", re.compile(r"(?i)<\s*img\b[^>]*onerror\s*="), 5),
    ("svg_onload", re.compile(r"(?i)<\s*svg\b[^>]*onload\s*="), 5),
    ("javascript_uri", re.compile(_JAVASCRIPT_EXECUTABLE_CONTEXT_RE, re.IGNORECASE), 4),
    ("event_handler", re.compile(_CREDIBLE_EVENT_HANDLER_RE, re.IGNORECASE), 3),
    ("alert_call", re.compile(_ALERT_EXECUTABLE_CONTEXT_RE, re.IGNORECASE | re.DOTALL), 3),
    ("browser_data_exfil", re.compile(_BROWSER_DATA_EXFIL_RE, re.IGNORECASE | re.DOTALL), 4),
]

SCRIPT_TAG_PATTERN = re.compile(r"(?i)<\s*script\b")
SCRIPT_TAG_CAPTURE_RE = re.compile(r"<\s*([a-z]+)\b", re.IGNORECASE)
EVENT_HANDLER_ASSIGNMENT_RE = re.compile(r"(?i)\b(on[a-z0-9_]+)\s*=")
JAVASCRIPT_PROTOCOL_RE = re.compile(r"(?i)javascript\s*:")
BROWSER_DATA_ACCESS_RE = re.compile(r"(?i)(document\.cookie|localStorage|sessionStorage)")
EXTERNAL_NAVIGATION_RE = re.compile(
    r"(?i)(document\.location|window\.location|(?:\b|(?<![A-Za-z0-9_$]))location\s*\.\s*(?:href|assign|replace)\s*(?:=|\()|fetch\s*\(|new\s+Image\s*\(\s*\)\s*\.src|navigator\.sendBeacon\s*\()"
)
EXTERNAL_URL_RE = re.compile(r"(?i)\b(?:https?:)?//[^\s\"'<>]+")
XSS_QUOTE_BREAKOUT_PATTERN = re.compile(r"(?i)(?:['\"]\s*>|['\"]\s*<|['\"]\s*on[a-z0-9_]+\s*=)")
XSS_TAG_INJECTION_PATTERN = re.compile(r"(?i)<\s*(?:script|img|svg|iframe|body|a)\b")

EDUCATIONAL_XSS_SEARCH_TERMS = (
    "how to",
    "tutorial",
    "prevent",
    "example",
    "guide",
    "docs",
    "documentation",
    "사용법",
    "예제",
    "튜토리얼",
    "강의",
    "문서",
)

EDUCATIONAL_XSS_KEYWORDS = (
    "xss",
    "script",
    "javascript",
    "onerror",
    "onload",
    "onclick",
    "document.cookie",
    "cookie",
    "localstorage",
    "sessionstorage",
)
