#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import List, Tuple


SQLI_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("union_select", re.compile(r"(?i)\bunion\b\s+\bselect\b"), 5),
    ("or_true", re.compile(r"(?i)(?:'|%27|\")?\s*\bor\b\s+[\w\"']+\s*=\s*[\w\"']+"), 4),
    ("and_true", re.compile(r"(?i)(?:'|%27|\")?\s*\band\b\s+[\w\"']+\s*=\s*[\w\"']+"), 3),
    ("sql_comment", re.compile(r"(?i)(--|#|/\*)"), 2),
    ("sleep_func", re.compile(r"(?i)\bsleep\s*\("), 5),
    ("benchmark_func", re.compile(r"(?i)\bbenchmark\s*\("), 5),
    ("waitfor_delay", re.compile(r"(?i)\bwaitfor\b\s+\bdelay\b"), 5),
    ("information_schema", re.compile(r"(?i)\binformation_schema\b"), 5),
    ("select_from", re.compile(r"(?i)\bselect\b.+\bfrom\b"), 4),
    ("drop_table", re.compile(r"(?i)\bdrop\b\s+\btable\b"), 5),
    ("insert_into", re.compile(r"(?i)\binsert\b\s+\binto\b"), 4),
    ("update_set", re.compile(r"(?i)\bupdate\b.+\bset\b"), 4),
    ("delete_from", re.compile(r"(?i)\bdelete\b\s+\bfrom\b"), 4),
    ("quote_termination", re.compile(r"(?i)(?:'|%27)\s*(?:or|and|union|;|--)"), 4),
]

EDUCATIONAL_SQL_SEARCH_TERMS = (
    "how to",
    "tutorial",
    "example",
    "guide",
    "docs",
    "documentation",
    "learn",
    "syntax",
    "sql tutorial",
    "select tutorial",
    "union tutorial",
    "사용법",
    "예제",
    "튜토리얼",
    "강의",
    "문서",
    "학습",
    "설명",
)

SUPPORTING_SQL_KEYWORDS = (
    "select",
    "union",
    "from",
    "where",
    "or",
    "and",
    "users",
    "sqlite_master",
    "information_schema",
)

SQLI_BOOLEAN_CONDITION_PATTERN = re.compile(r"(?i)\b(?:or|and)\b\s+(?:\d+|[\w\"']+)\s*=\s*(?:\d+|[\w\"']+)")
SQLI_BOOLEAN_TRUE_CONDITION_PATTERN = re.compile(
    r"(?ix)"
    r"\b(?:or|and)\b\s+"
    r"(?:"
    r"(?P<num>\d{1,8})\s*=\s*(?P=num)"
    r"|(?P<sq>'[^']{0,32}')\s*=\s*(?P=sq)"
    r"|(?P<dq>\"[^\"]{0,32}\")\s*=\s*(?P=dq)"
    r"|(?P<word>[a-z_][a-z0-9_]*)\s*=\s*(?P=word)"
    r"|true\s*=\s*true"
    r"|false\s*=\s*false"
    r")"
)
SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN = re.compile(
    r"(?ix)"
    r"(?:'|%27)\s*(?:\)\s*){0,4}(?:or|and|union|;|--|\#|/\*)"
)
SQLI_PAREN_TERMINATION_PATTERN = re.compile(
    r"(?ix)"
    r"(?:'|%27|\"|%22)?\s*(?:\)\s*){1,4}(?:or|and|union|--|\#|/\*)"
)
SQLI_XCLOSE_PATTERN = re.compile(r"(?i)\b[a-z0-9_]{1,16}\s*'\s*\)\s*\)")
SQLI_UNION_COLUMN_ENUM_PATTERN = re.compile(r"(?i)\bunion\b\s+\bselect\b\s+[^\n]{0,160},\s*[^\n]{0,160}")
SQLI_SCHEMA_ACCESS_PATTERN = re.compile(r"(?i)\b(?:information_schema|sqlite_master|mysql\.user)\b")
SQLI_FROM_USERS_PATTERN = re.compile(r"(?i)\bfrom\b\s+users\b")
SQLI_COMMENT_PATTERN = re.compile(r"(?i)(--|#|/\*)")
REPEATED_QUOTE_PATTERN = re.compile(r"(?i)(?:'|%27|%2527|\"|%22){2,}")


def detect_educational_sql_search_context(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    return any(term in lowered for term in EDUCATIONAL_SQL_SEARCH_TERMS)
