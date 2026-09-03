from __future__ import annotations

import re
from typing import List, Tuple

TRAVERSAL_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    (
        "dotdot_slash",
        re.compile(
            r"(?i)(?:^|[\s/\\?&=])"
            r"(?:\.\.(?:/|\\)|%2e%2e%2f|%2e%2e/|\.\.%2f|%252e%252e%252f)"
        ),
        4,
    ),
    ("triple_dot_slash", re.compile(r"(?i)(?:^|[\s/\\?&=])\.\.\./"), 4),
]

CMDI_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("pipe_exec", re.compile(r"(?i)\|\s*(?:whoami|id|cat|uname|ls|pwd)\b"), 4),
    ("semicolon_exec", re.compile(r"(?i);\s*(?:cat|id|whoami|uname|curl|wget|bash|sh)\b"), 4),
    ("subshell", re.compile(r"(?i)(?:\$\((?:id|whoami|uname|cat)|`(?:id|whoami|uname|cat))"), 4),
]
