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

CMDI_UNIX_COMMANDS = (
    "id",
    "whoami",
    "who",
    "cat",
    "uname",
    "ls",
    "pwd",
    "ps",
    "curl",
    "wget",
    "bash",
    "sh",
)
CMDI_WINDOWS_COMMANDS = ("cmd", "iwr", "iwmi", "mshta", "dsmod")
CMDI_COMMANDS = CMDI_UNIX_COMMANDS + CMDI_WINDOWS_COMMANDS
_CMDI_COMMAND_RE = "(?:" + "|".join(CMDI_COMMANDS) + ")"


CMDI_PATTERNS: List[Tuple[str, re.Pattern[str], int]] = [
    ("pipe_exec", re.compile(rf"(?i)\|\s*{_CMDI_COMMAND_RE}\b"), 4),
    ("semicolon_exec", re.compile(rf"(?i);\s*{_CMDI_COMMAND_RE}\b"), 4),
    ("subshell", re.compile(rf"(?i)(?:\$\(|`)\s*{_CMDI_COMMAND_RE}\b"), 4),
    ("and_exec", re.compile(rf"(?i)&&\s*(?:\(\s*)?{_CMDI_COMMAND_RE}\b"), 4),
    (
        "shell_invocation",
        re.compile(rf"(?i)\b(?:sh|bash)\s+-c\s+{_CMDI_COMMAND_RE}\b|\bcmd\s+/c\s+{_CMDI_COMMAND_RE}\b"),
        4,
    ),
]
