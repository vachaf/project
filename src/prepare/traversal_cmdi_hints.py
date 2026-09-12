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

# Prepare's pipe vocabulary outside the Shared Extractor S1 subset remains an
# explicit compatibility fallback.  Keep the full CMDI_PATTERNS entry below
# unchanged for every caller that still needs the complete legacy grammar.
CMDI_SHARED_S1_PIPE_COMMANDS = ("whoami", "id", "cat", "uname", "ls", "pwd")
CMDI_LEGACY_ONLY_PIPE_COMMANDS = tuple(
    command for command in CMDI_COMMANDS if command not in CMDI_SHARED_S1_PIPE_COMMANDS
)
_CMDI_LEGACY_ONLY_PIPE_COMMAND_RE = "(?:" + "|".join(CMDI_LEGACY_ONLY_PIPE_COMMANDS) + ")"
CMDI_LEGACY_ONLY_PIPE_PATTERN = re.compile(
    rf"(?i)\|\s*{_CMDI_LEGACY_ONLY_PIPE_COMMAND_RE}\b"
)


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
