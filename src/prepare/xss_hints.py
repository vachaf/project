from __future__ import annotations

import re
from typing import List, Tuple

XSS_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("script_tag", re.compile(r"(?i)<\s*script\b"), 5),
    ("img_onerror", re.compile(r"(?i)<\s*img\b[^>]*onerror\s*="), 5),
    ("svg_onload", re.compile(r"(?i)<\s*svg\b[^>]*onload\s*="), 5),
    ("javascript_uri", re.compile(r"(?i)javascript\s*:"), 4),
    ("event_handler", re.compile(r"(?i)\bon\w+\s*="), 3),
    ("alert_call", re.compile(r"(?i)\balert\s*\("), 3),
    ("document_cookie", re.compile(r"(?i)document\.cookie"), 4),
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
