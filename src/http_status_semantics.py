"""Shared Apache logs-only HTTP status wording helpers for LLM stages."""

from __future__ import annotations

import re
from typing import Optional


HTTP_STATUS_OUTCOME_WARNING = "semantic_violation:http_status_outcome_overreach"
HTTP_STATUS_BLOCK_ASSERTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:http\s*)?(?:401|403)[^.!?\n]{0,32}차단(?:되었|됐|됨|됩니다|되었다|됐다)",
        r"차단(?:이|은)?\s*(?:(?:정상|기준선\s*유사)\s*)?(?:동작|작동)(?:했|하였|한|합니다|했다|했습니다|된\s*것으로\s*보)",
        r"(?:애플리케이션|서버|waf)[^.!?\n]{0,24}차단(?:되었|됐|된)\s*것으로\s*(?:추정|보)",
        r"접근\s*제어(?:가|는|은)?\s*(?:(?:정상|기준선\s*유사)\s*)?(?:동작|작동)(?:했|하였|한|합니다|했다|했습니다)",
        r"access\s*control\s*(?:is|was|has\s+been)?\s*(?:working|worked|operational|functioning)",
    )
)
HTTP_STATUS_GENERIC_BLOCK_ASSERTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:경로\s*(?:탐색|조작)\s*시도|공격\s*시도|공격|(?:해당\s*)?요청)(?:가|는|은|이)?[^.!?\n]{0,24}차단(?:되었|됐|된)\s*(?:정황|것으로\s*(?:보|추정))",
    )
)
HTTP_STATUS_ATTACK_FAILURE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"공격(?:은|이)?\s*실패(?:했|하였|한|합니다|했다|했습니다|되었|됐다|됨)",
        r"공격\s*실패(?:가)?\s*확인(?:되었|됐|됨|되었습니다|됐다)",
        r"공격(?:은|이)?\s*실패(?!\s*여부)",
        r"우회(?:는|가)?\s*실패(?:했|하였|한|합니다|했다|했습니다|되었|됐다|됨)",
    )
)
HTTP_STATUS_FILE_ACCESS_FAILURE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:실제\s*)?파일\s*(?:접근|읽기)(?:에|를)?\s*실패(?:했|하였|한|합니다|했다|했습니다|되었|됐다|됨)",
        r"(?:실제\s*)?파일\s*(?:접근|읽기)\s*실패(?:가)?\s*확인(?:되었|됐|됨|되었습니다|됐다)",
        r"(?:실제\s*)?파일\s*(?:접근|읽기)(?:에|를)?\s*실패(?!\s*여부)",
    )
)
def _has_conservative_negation_for(text: str, subject_pattern: str) -> bool:
    subject_match = re.search(subject_pattern, text, re.IGNORECASE)
    if subject_match is None:
        return False
    subject_tail = text[subject_match.start() : subject_match.start() + 80]
    return bool(
        re.search(
            r"(?:단정(?:하지|할\s*수)|판단(?:하지|할\s*수)|볼\s*수|증명(?:하지|할\s*수))\s*없",
            subject_tail,
            re.IGNORECASE,
        )
    )


def http_status_outcome_fallback(text: str) -> Optional[str]:
    """Return a canonical fallback only for an unsupported outcome assertion."""
    if any(pattern.search(text) for pattern in HTTP_STATUS_BLOCK_ASSERTION_PATTERNS):
        if _has_conservative_negation_for(text, r"(?:차단|접근\s*제어|access\s*control)"):
            return None
        status_match = re.search(r"(?<!\d)(401|403)(?!\d)", text)
        if status_match:
            status_code = status_match.group(1)
            interpretation = "접근 제한 가능성이 있습니다." if status_code == "403" else "접근 거부 또는 인증 필요 가능성이 있습니다."
            return (
                f"HTTP {status_code} 응답이 관찰되어 {interpretation} "
                "실제 차단 여부나 접근 제어 동작은 Apache 로그만으로 판단할 수 없습니다."
            )
        return "HTTP 응답 metadata만으로 실제 차단 여부나 접근 제어 동작은 Apache 로그만으로 판단할 수 없습니다."

    if any(pattern.search(text) for pattern in HTTP_STATUS_GENERIC_BLOCK_ASSERTION_PATTERNS):
        if _has_conservative_negation_for(text, r"차단"):
            return None
        return "접근 제한 가능성은 있으나, 실제 차단 여부나 공격 성공·실패는 Apache 로그만으로 판단할 수 없습니다."

    if any(pattern.search(text) for pattern in HTTP_STATUS_ATTACK_FAILURE_PATTERNS):
        if _has_conservative_negation_for(text, r"(?:공격|우회)[^.!?\n]{0,24}실패"):
            return None
        return "공격 성공·실패 여부는 Apache 로그만으로 판단할 수 없습니다."

    if any(pattern.search(text) for pattern in HTTP_STATUS_FILE_ACCESS_FAILURE_PATTERNS):
        if _has_conservative_negation_for(text, r"파일\s*(?:접근|읽기)[^.!?\n]{0,24}실패"):
            return None
        return "실제 파일 접근 성공·실패 여부는 Apache 로그만으로 판단할 수 없습니다."

    return None
