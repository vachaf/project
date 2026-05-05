#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_PATH = Path(__file__).resolve()
CONTEXT_WINDOW = 60
MIN_TEXT_WARNING_PATTERNS = (
    "실제 공격",
    "차단 성공",
    "노출 실패",
)
STRONG_NEGATION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"단정하지\s*않",
        r"단정할\s*수\s*없",
        r"확인되지\s*않",
        r"확인할\s*수\s*없",
        r"확정하지\s*않",
        r"확정할\s*수\s*없",
        r"근거가\s*부족",
        r"증거가\s*없",
        r"증거[는가]?\s*제공되지\s*않",
        r"해석하지\s*않",
        r"해석할\s*수\s*없",
        r"주장하지\s*않",
        r"입증할\s*근거",
        r"볼\s*근거는\s*부족",
        r"본\s*보고서에서\s*주장하지\s*않",
        r"의미하지(?:는)?\s*않",
        r"증명하지(?:는)?\s*않",
        r"확인하지\s*않",
        r"not\s+confirmed",
        r"not\s+evidence",
        r"no\s+evidence",
    )
)
WEAK_CONSERVATIVE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"가능성",
        r"시도",
        r"정황",
        r"의심",
        r"관찰",
        r"pattern",
        r"context",
        r"추정",
        r"보수적",
        r"attempt",
        r"observed",
        r"context-only",
        r"review\s*필요",
        r"검토\s*필요",
    )
)
SAFE_ACTION_CONTEXT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"확인\s*필요",
        r"확인[이가]?\s*필요",
        r"검증\s*필요",
        r"검증[이가]?\s*필요",
        r"추가\s*확인",
        r"추가\s*분석",
        r"상관\s*분석",
        r"교차\s*검증",
        r"원시\s*로그",
        r"raw\s*log",
        r"애플리케이션\s*로그",
        r"waf\s*로그",
        r"네트워크\s*추적",
        r"모니터링",
    )
)
RECOMMENDED_ACTION_PATH_PATTERN = re.compile(r"^report\.recommended_actions\[\d+\]\.(?:action|why)$")
RECOMMENDED_ACTION_STRONG_ASSERTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"데이터\s*탈취\s*성공",
        r"명령\s*실행\s*성공",
        r"파일\s*내용이\s*반환",
    )
)
KNOWN_ASSET_CAUTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"known[_ -]?asset",
        r"내부\s*테스트",
        r"자체\s*호출",
        r"운영\s*점검",
        r"소유자\s*확인",
        r"출발지\s*목적\s*확인",
        r"내부\s*자산",
    )
)


@dataclass(frozen=True)
class RuleSpec:
    name: str
    blocker_patterns: Tuple[re.Pattern[str], ...]
    warning_patterns: Tuple[re.Pattern[str], ...]
    suggestion: str


RULE_SPECS: Tuple[RuleSpec, ...] = (
    RuleSpec(
        name="sql_success_assertion",
        blocker_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"sql\s*injection\s*성공",
                r"sqli\s*성공",
                r"db\s*결과\s*반환",
                r"db\s*rows?\s*returned",
                r"database\s+schema\s+exposed",
                r"인증\s*우회\s*성공",
                r"데이터\s*탈취\s*성공",
                r"sleep\(\)\s*실행\s*성공",
                r"메타데이터\s*조회",
            )
        ),
        warning_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"sql\s*injection\s*시도",
                r"sqli\s*시도",
            )
        ),
        suggestion=(
            "Apache access logs alone do not confirm SQLi success, DB rows, auth bypass, or data exfiltration. "
            "Prefer request-pattern, attempt, or inconclusive wording."
        ),
    ),
    RuleSpec(
        name="xss_execution_assertion",
        blocker_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"xss\s*실행",
                r"브라우저에서\s*(?:스크립트|javascript|자바스크립트)[^\n]*실행",
                r"javascript\s*실행\s*확인",
                r"쿠키\s*탈취",
                r"세션\s*탈취",
                r"외부\s*전송\s*성공",
                r"exfiltration\s+succeeded",
            )
        ),
        warning_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"xss\s*시도",
                r"script[- ]?like\s+payload",
            )
        ),
        suggestion=(
            "Apache logs show payload structure, not browser execution. Replace confirmed XSS execution or theft wording "
            "with observed payload pattern or possible exfiltration intent."
        ),
    ),
    RuleSpec(
        name="file_disclosure_success_assertion",
        blocker_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"파일\s*내용\s*노출",
                r"파일이\s*노출",
                r"source\s+disclosed",
                r"php\s*source\s*노출",
                r"config\s*파일\s*내용\s*(?:반환|유출)",
                r"\.env\s*내용\s*유출",
                r"phpinfo\s*노출",
                r"server-status\s*노출\s*성공",
                r"backup\s*다운로드\s*성공",
                r"config\s*파일\s*내용이\s*반환",
            )
        ),
        warning_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"파일/소스\s*공개\s*시도",
                r"source\s+disclosure\s+attempt",
                r"노출\s*실패",
            )
        ),
        suggestion=(
            "Apache logs alone do not prove source disclosure or file contents returned. Keep wording at disclosure attempt, "
            "request pattern, or unconfirmed exposure."
        ),
    ),
    RuleSpec(
        name="traversal_cmdi_success_assertion",
        blocker_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"traversal\s*성공",
                r"파일\s*읽기\s*성공",
                r"/etc/passwd\s*노출",
                r"win\.ini\s*반환",
                r"command\s+executed",
                r"명령\s*실행\s*성공",
                r"shell\s+access",
                r"reverse\s+shell\s*성공",
                r"server\s+compromised",
            )
        ),
        warning_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"traversal\s*시도",
                r"command[- ]?like\s+token",
            )
        ),
        suggestion=(
            "Apache logs can show traversal-like or command-like requests, not confirmed file reads, code execution, shell access, "
            "or compromise."
        ),
    ),
    RuleSpec(
        name="auth_success_assertion",
        blocker_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"로그인\s*성공",
                r"계정\s*탈취",
                r"credential\s+stuffing\s*성공",
                r"lockout\s*발동",
                r"authentication\s+bypass\s+succeeded",
            )
        ),
        warning_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"인증\s*오용",
                r"반복된\s*401\s*실패",
            )
        ),
        suggestion=(
            "Apache logs do not confirm login success, account takeover, or bypass. Prefer failed-auth activity, repeated attempts, "
            "or inconclusive auth misuse wording."
        ),
    ),
    RuleSpec(
        name="method_protocol_success_assertion",
        blocker_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"put\s*업로드\s*성공",
                r"delete\s*삭제\s*성공",
                r"trace/xst\s*성공",
                r"cors\s*취약점\s*확인",
                r"protocol\s*bypass\s*성공",
                r"malformed\s+request\s+exploit\s+성공",
            )
        ),
        warning_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"차단\s*성공",
                r"메서드\s*탐색",
                r"프로토콜\s*이상",
            )
        ),
        suggestion=(
            "Apache logs alone do not confirm upload, delete, XST, CORS abuse, or protocol exploit success. Prefer observed method "
            "or protocol anomaly wording."
        ),
    ),
    RuleSpec(
        name="static_crawler_presence_assertion",
        blocker_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"static\s+file\s+exists",
                r"정적\s*파일\s*존재\s*확인",
                r"js\s*실행\s*확인",
                r"robots\s*정책\s*확인",
                r"sitemap\s*내용\s*확인",
                r"site\s*structure\s*확인",
                r"실제\s*crawler\s*확인",
                r"googlebot\s*verified",
                r"product/category\s*page\s*exists",
            )
        ),
        warning_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"스캐너가\s*사이트를\s*훑",
            )
        ),
        suggestion=(
            "Apache logs can suggest baseline crawling or probing patterns, but they do not confirm crawler authenticity, site structure, "
            "page existence, or JavaScript execution."
        ),
    ),
    RuleSpec(
        name="ip_ua_attribution_assertion",
        blocker_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"lab-[^\s]*\s*ua[^\n]*공격\s*근거",
                r"sqlmap/nikto/nmap\s*ua[^\n]*성공",
            )
        ),
        warning_patterns=tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"공격자\s*ip",
                r"attacker\s+ip",
                r"lab-[^\s]*\s*ua",
                r"sqlmap/nikto/nmap\s*ua",
                r"외부에서\s*접근",
            )
        ),
        suggestion=(
            "IPs and User-Agents are attribution hints, not proof of attacker identity or success. Prefer source IP, client, known asset, "
            "or test-traffic wording."
        ),
    ),
)
CONTEXT_ONLY_SUBJECTS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"context-only",
        r"baseline",
        r"기준선",
        r"정찰",
        r"crawler",
        r"sensitive\s+path",
        r"mixed\s+baseline",
        r"민감\s*경로\s*탐색",
    )
)
CONTEXT_ONLY_ESCALATIONS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"실제\s*공격",
        r"침해\s*성공",
        r"공격\s*성공",
        r"compromise",
        r"confirmed",
    )
)


@dataclass(frozen=True)
class Issue:
    rule: str
    path: str
    excerpt: str
    suggestion: str


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review-only wording lint for Stage2 report JSON under Apache logs-only constraints.",
    )
    parser.add_argument("--input", required=True, help="Stage2 report JSON path")
    parser.add_argument("--pretty", action="store_true", help="print result JSON with indentation")
    parser.add_argument("--debug", action="store_true", help="print rule matching debug output")
    parser.add_argument(
        "--fail-on-blocker",
        action="store_true",
        help="exit non-zero only when blocker_count > 0",
    )
    parser.add_argument("--output", default=None, help="optional path to write result JSON")
    return parser.parse_args(argv)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Stage2 report JSON root must be an object")
    return payload


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None


def clip_excerpt(text: str, start: int, end: int) -> str:
    left = max(0, start - CONTEXT_WINDOW)
    right = min(len(text), end + CONTEXT_WINDOW)
    excerpt = text[left:right].strip()
    if left > 0:
        excerpt = "..." + excerpt
    if right < len(text):
        excerpt = excerpt + "..."
    return excerpt


def classify_assertion_context(text: str, start: int, end: int) -> str:
    left = max(0, start - CONTEXT_WINDOW)
    right = min(len(text), end + CONTEXT_WINDOW)
    context = text[left:right]
    if any(pattern.search(context) for pattern in STRONG_NEGATION_PATTERNS):
        return "strong_negation"
    if any(pattern.search(context) for pattern in WEAK_CONSERVATIVE_PATTERNS):
        return "weak_conservative"
    return "none"


def is_recommended_action_path(path: str) -> bool:
    return RECOMMENDED_ACTION_PATH_PATTERN.search(path) is not None


def has_safe_action_context(text: str) -> bool:
    return any(pattern.search(text) for pattern in SAFE_ACTION_CONTEXT_PATTERNS)


def has_recommended_action_strong_assertion(text: str) -> bool:
    return any(pattern.search(text) for pattern in RECOMMENDED_ACTION_STRONG_ASSERTION_PATTERNS)


def iter_report_fields(report: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    mappings = (
        ("report_title", None),
        ("overall_assessment", None),
        ("executive_summary", None),
        ("key_findings", "title"),
        ("key_findings", "detail"),
        ("notable_incidents", "why_it_matters"),
        ("notable_source_ips", "reason"),
        ("noise_interpretation", None),
        ("recommended_actions", "action"),
        ("recommended_actions", "why"),
        ("confidence_and_limitations", None),
        ("presentation_takeaway", None),
    )

    for field_name, nested_name in mappings:
        value = report.get(field_name)
        base_path = f"report.{field_name}"
        if isinstance(value, list):
            if nested_name is None:
                for index, item in enumerate(value):
                    text = normalize_text(item)
                    if text:
                        yield f"{base_path}[{index}]", text
                continue
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    continue
                text = normalize_text(item.get(nested_name))
                if text:
                    yield f"{base_path}[{index}].{nested_name}", text
            continue

        if nested_name is not None:
            continue

        text = normalize_text(value)
        if text:
            yield base_path, text


def detect_rule_issue(
    spec: RuleSpec,
    path: str,
    text: str,
    *,
    debug_rows: List[str],
) -> List[Tuple[str, Issue]]:
    issues: List[Tuple[str, Issue]] = []
    recommended_action_path = is_recommended_action_path(path)
    for severity_name, patterns in (("blocker", spec.blocker_patterns), ("warning", spec.warning_patterns)):
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            excerpt = clip_excerpt(text, match.start(), match.end())
            context_class = classify_assertion_context(text, match.start(), match.end())
            effective_severity = severity_name
            if severity_name == "blocker" and context_class == "strong_negation":
                effective_severity = "info"
            elif severity_name == "blocker" and context_class == "weak_conservative":
                effective_severity = "warning"
            elif severity_name == "warning" and context_class in ("strong_negation", "weak_conservative"):
                effective_severity = "info"
            if (
                recommended_action_path
                and severity_name == "blocker"
                and (context_class == "strong_negation" or has_safe_action_context(text))
            ):
                if has_recommended_action_strong_assertion(text):
                    effective_severity = "warning"
                else:
                    effective_severity = "info"
            if debug_rows is not None:
                debug_rows.append(
                    f"{path}: rule={spec.name} severity={effective_severity} matched={match.group(0)!r} context={context_class}"
                )
            issues.append(
                (
                    effective_severity,
                    Issue(
                        rule=spec.name,
                        path=path,
                        excerpt=excerpt,
                        suggestion=spec.suggestion,
                    ),
                )
            )
            return issues
    return issues


def detect_context_only_escalation(path: str, text: str, *, debug_rows: List[str]) -> List[Tuple[str, Issue]]:
    if not any(pattern.search(text) for pattern in CONTEXT_ONLY_SUBJECTS):
        return []
    for pattern in CONTEXT_ONLY_ESCALATIONS:
        match = pattern.search(text)
        if not match:
            continue
        context_class = classify_assertion_context(text, match.start(), match.end())
        severity_name = "info" if context_class != "none" else "warning"
        if debug_rows is not None:
            debug_rows.append(
                f"{path}: rule=context_only_escalation severity={severity_name} matched={match.group(0)!r} context={context_class}"
            )
        return [
            (
                severity_name,
                Issue(
                    rule="context_only_escalation",
                    path=path,
                    excerpt=clip_excerpt(text, match.start(), match.end()),
                    suggestion=(
                        "Context-only, baseline, crawler, and probing summaries should stay at observed context level. "
                        "Avoid escalating them to confirmed attack or compromise wording."
                    ),
                ),
            )
        ]
    return []


def maybe_add_known_asset_caution(
    fields: Sequence[Tuple[str, str]],
    *,
    debug_rows: List[str],
) -> List[Tuple[str, Issue]]:
    joined_text = "\n".join(text for _, text in fields)
    if not joined_text:
        return []
    if any(pattern.search(joined_text) for pattern in KNOWN_ASSET_CAUTION_PATTERNS):
        return []
    for _, text in fields:
        for pattern_text in ("공격자 ip", "attacker ip", "lab-", "외부에서 접근"):
            index = text.lower().find(pattern_text)
            if index < 0:
                continue
            if debug_rows is not None:
                debug_rows.append(
                    "global: rule=known_asset_caution_missing severity=info matched="
                    f"{pattern_text!r} conservative=False"
                )
            return [
                (
                    "info",
                    Issue(
                        rule="known_asset_caution_missing",
                        path="report",
                        excerpt=clip_excerpt(text, index, index + len(pattern_text)),
                        suggestion=(
                            "When attributing source IPs or tool-like User-Agents, also mention known asset, internal test, "
                            "self-call, or operational check possibilities when evidence is Apache logs only."
                        ),
                    ),
                )
            ]
    return []


def build_verdict(blocker_count: int, warning_count: int) -> str:
    if blocker_count > 0:
        return "FAIL"
    if warning_count > 0:
        return "WARN"
    return "PASS"


def analyze_stage2_report_data(data: Dict[str, Any], *, debug: bool = False) -> Dict[str, Any]:
    report = data.get("report")
    if report is None:
        return {
            "verdict": "PASS",
            "blockers": [],
            "warnings": [],
            "info": [],
            "summary": {
                "checked_fields": 0,
                "blocker_count": 0,
                "warning_count": 0,
                "info_count": 0,
            },
        }
    if not isinstance(report, dict):
        raise ValueError("report must be an object or null")

    fields = list(iter_report_fields(report))
    blocker_issues: List[Issue] = []
    warning_issues: List[Issue] = []
    info_issues: List[Issue] = []
    debug_rows: List[str] = []

    for path, text in fields:
        for spec in RULE_SPECS:
            for severity_name, issue in detect_rule_issue(spec, path, text, debug_rows=debug_rows):
                if severity_name == "blocker":
                    blocker_issues.append(issue)
                elif severity_name == "warning":
                    warning_issues.append(issue)
                else:
                    info_issues.append(issue)
        for severity_name, issue in detect_context_only_escalation(path, text, debug_rows=debug_rows):
            if severity_name == "warning":
                warning_issues.append(issue)
            else:
                info_issues.append(issue)

        lowered = text.lower()
        for token in MIN_TEXT_WARNING_PATTERNS:
            token_lower = token.lower()
            index = lowered.find(token_lower)
            if index < 0:
                continue
            context_class = classify_assertion_context(text, index, index + len(token))
            severity_name = "info" if context_class != "none" else "warning"
            issue = Issue(
                rule="context_only_escalation",
                path=path,
                excerpt=clip_excerpt(text, index, index + len(token)),
                suggestion=(
                    "This lint is a wording-risk review tool, not an attack verdict. Prefer observed request pattern, attempt, "
                    "or blocked activity wording over direct attack-success phrasing."
                ),
            )
            if debug:
                debug_rows.append(
                    f"{path}: rule=context_only_escalation severity={severity_name} matched={token!r} context={context_class}"
                )
            if severity_name == "warning":
                warning_issues.append(issue)
            else:
                info_issues.append(issue)
            break

    for severity_name, issue in maybe_add_known_asset_caution(fields, debug_rows=debug_rows):
        if severity_name == "info":
            info_issues.append(issue)

    if debug and debug_rows:
        for row in debug_rows:
            print(f"[debug] {row}", file=sys.stderr)

    result = {
        "verdict": build_verdict(len(blocker_issues), len(warning_issues)),
        "blockers": [asdict(issue) for issue in blocker_issues],
        "warnings": [asdict(issue) for issue in warning_issues],
        "info": [asdict(issue) for issue in info_issues],
        "summary": {
            "checked_fields": len(fields),
            "blocker_count": len(blocker_issues),
            "warning_count": len(warning_issues),
            "info_count": len(info_issues),
        },
    }
    return result


def format_summary(input_path: Path, result: Dict[str, Any], output_path: Optional[Path]) -> str:
    summary = result["summary"]
    lines = [
        f"Target: {input_path}",
        f"Verdict: {result['verdict']}",
        (
            "Summary: checked_fields={checked_fields} blocker_count={blocker_count} "
            "warning_count={warning_count} info_count={info_count}"
        ).format(**summary),
    ]
    if output_path is not None:
        lines.append(f"Output written: {output_path}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    try:
        data = load_json(input_path)
        result = analyze_stage2_report_data(data, debug=args.debug)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to lint Stage2 report: {exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else None
    if output_path is not None:
        dump_json(output_path, result)

    print(format_summary(input_path, result, output_path))
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.fail_on_blocker and result["summary"]["blocker_count"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
