#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Explain why prepare/stage candidates crossed the row-level candidate threshold.

Purpose
- Review prepare candidate policy without changing scoring or filtering behavior.
- Classify candidates into coarse review buckets such as explicit payload,
  status/error-only, probing/context-backed, auth/upload failure, or review.
- Help compare observability dry-runs such as PHP sample v1/v2 where many
  4xx/5xx/error_linked rows can cross min_score.

Inputs supported
- security_llm_input.json-like payloads with top-level `analysis_candidates`
- stage1_results.json-like payloads with top-level `results`
- security_stage2_report_input.json-like payloads with top-level `top_incidents`
- viewer_payload.json-like payloads with top-level `findings`
- --run-dir can auto-pick one of the above from common run artifact paths

Non-goals
- Does not modify prepare output.
- Does not infer exploit success, exposure, auth success, upload success, DB
  impact, or browser execution.
- Does not create or demote candidates. It only labels review categories.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_MIN_SCORE = 4

POINT_RE = re.compile(r"\(\+(-?\d+)\)")
SCENARIO_RE = re.compile(r"(?:^|[?&\s/])scenario=(S\d{2})(?:$|[&\s])", re.IGNORECASE)
UA_SCENARIO_RE = re.compile(r"obs-test/(S\d{2})", re.IGNORECASE)

ATTACK_PREFIXES = (
    "sqli:",
    "xss:",
    "traversal:",
    "cmdi:",
    "file_disclosure:",
    "webshell:",
    "ssrf:",
    "log4shell:",
    "ssti:",
    "xxe:",
    "graphql:",
    "open_redirect:",
)

# These XSS hints can be appended as context hints by XSS helper logic. Treat
# them as explicit payload only when another XSS structural hint is present.
CONTEXTUAL_XSS_HINTS = {
    "xss:external_navigation",
}

WEAK_SQL_COMMENT_HINTS = {
    "sqli:sql_comment",
}

STATUS_ERROR_PREFIXES = (
    "error_status:",
    "error_linked",
    "no_referer_non_browser_error",
    "error_table_context",
)

AUTH_HINT_PREFIXES = (
    "login_endpoint",
    "auth_payload_content_type",
    "login_success_json_response",
    "possible_auth_bypass_success",
    "no_referer_non_browser_login",
)

PROBE_HINT_PREFIXES = (
    "sensitive_path:",
    "probe_sequence:",
    "dir_probe:",
    "scanner:",
    "static_baseline:",
    "crawler_baseline:",
    "mixed_baseline:",
)

OBSERVABILITY_PREFIX = "observability:"

RUN_DIR_CANDIDATE_PATHS = (
    "security_llm_input.json",
    "llm_input.json",
    "stage1_results.json",
    "security_stage2_report_input.json",
    "viewer_payload.json",
    "reports/security_stage2_report_input.json",
    "reports/security_viewer_payload.json",
    "reports/viewer_payload.json",
    "data/processed/security_llm_input.json",
    "data/processed/stage1_results.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explain why prepare/stage candidates crossed candidate threshold."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Input JSON file: llm_input, stage1_results, stage2 input, or viewer_payload")
    source.add_argument("--run-dir", help="Run directory. The script searches common artifact paths inside it.")
    parser.add_argument("--out", help="Optional output path")
    parser.add_argument("--format", choices=("markdown", "json", "tsv"), default="markdown")
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--include-context-only", action="store_true", help="Include viewer_payload context_only findings if present")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of candidates displayed")
    parser.add_argument("--sort", choices=("input", "score_desc", "policy"), default="input")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object at top level: {path}")
    return data


def resolve_input_path(args: argparse.Namespace) -> Path:
    if args.input:
        path = Path(args.input).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"input not found: {path}")
        return path

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"run-dir not found: {run_dir}")
    for rel in RUN_DIR_CANDIDATE_PATHS:
        candidate = run_dir / rel
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "could not find a supported candidate artifact under run-dir. "
        f"checked: {', '.join(RUN_DIR_CANDIDATE_PATHS)}"
    )


def as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value)
    return default if text == "None" else text


def as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [as_text(item) for item in value if as_text(item)]
    if isinstance(value, tuple):
        return [as_text(item) for item in value if as_text(item)]
    text = as_text(value)
    return [text] if text else []


def extract_candidates(payload: Dict[str, Any], include_context_only: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
    if isinstance(payload.get("analysis_candidates"), list):
        return "analysis_candidates", [item for item in payload["analysis_candidates"] if isinstance(item, dict)]
    if isinstance(payload.get("results"), list):
        return "stage1_results", [item for item in payload["results"] if isinstance(item, dict)]
    if isinstance(payload.get("top_incidents"), list):
        return "top_incidents", [item for item in payload["top_incidents"] if isinstance(item, dict)]
    if isinstance(payload.get("findings"), list):
        findings = [item for item in payload["findings"] if isinstance(item, dict)]
        if not include_context_only:
            findings = [item for item in findings if not item.get("context_only")]
        return "viewer_payload.findings", findings
    raise ValueError(
        "unsupported input: expected one of analysis_candidates, results, top_incidents, findings"
    )


def get_reason_hints(candidate: Dict[str, Any]) -> List[str]:
    hints = as_list(candidate.get("reason_hints"))
    if hints:
        return hints
    hints = as_list(candidate.get("evidence_fields"))
    if hints:
        return hints
    return as_list(candidate.get("evidence"))


def hint_base(hint: str) -> str:
    return POINT_RE.sub("", hint).strip()


def hint_points(hint: str) -> int:
    total = 0
    for match in POINT_RE.finditer(hint):
        total += as_int(match.group(1), 0)
    return total


def starts_with_any(text: str, prefixes: Sequence[str]) -> bool:
    return any(text.startswith(prefix) for prefix in prefixes)


def is_explicit_attack_hint(hint: str, hints: Sequence[str]) -> bool:
    base = hint_base(hint)
    if not starts_with_any(base, ATTACK_PREFIXES):
        return False
    if base in CONTEXTUAL_XSS_HINTS:
        return any(
            other.startswith("xss:") and hint_base(other) not in CONTEXTUAL_XSS_HINTS
            for other in hints
        )
    if base.startswith("traversal:html_fallback_like_response"):
        return any(other.startswith("traversal:") and other != base for other in map(hint_base, hints))
    return True


def detect_scenario(candidate: Dict[str, Any]) -> str:
    texts = [
        as_text(candidate.get("scenario")),
        as_text(candidate.get("user_agent")),
        as_text(candidate.get("query_string")),
        as_text(candidate.get("raw_request_target")),
        as_text(candidate.get("raw_request")),
        as_text(candidate.get("uri")),
    ]
    for text in texts:
        if not text:
            continue
        m = UA_SCENARIO_RE.search(text)
        if m:
            return m.group(1).upper()
        m = SCENARIO_RE.search(text)
        if m:
            return m.group(1).upper()
    return ""


def group_reasons(hints: Sequence[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {
        "attack_payload": [],
        "status_error": [],
        "auth": [],
        "probe_context": [],
        "observability": [],
        "length_complexity": [],
        "automation_or_client": [],
        "performance": [],
        "other": [],
    }
    for hint in hints:
        base = hint_base(hint)
        if is_explicit_attack_hint(base, hints):
            groups["attack_payload"].append(hint)
        elif starts_with_any(base, STATUS_ERROR_PREFIXES):
            groups["status_error"].append(hint)
        elif starts_with_any(base, AUTH_HINT_PREFIXES):
            groups["auth"].append(hint)
        elif starts_with_any(base, PROBE_HINT_PREFIXES):
            groups["probe_context"].append(hint)
        elif base.startswith(OBSERVABILITY_PREFIX):
            groups["observability"].append(hint)
        elif base.startswith(("long_query", "very_long_query", "special_char_ratio")):
            groups["length_complexity"].append(hint)
        elif base.startswith(("ua:", "no_referer")):
            groups["automation_or_client"].append(hint)
        elif base.startswith(("high_duration", "very_high_duration", "high_ttfb")):
            groups["performance"].append(hint)
        else:
            groups["other"].append(hint)
    return groups


def top_point_hints(hints: Sequence[str], max_items: int = 5) -> List[str]:
    scored = [(hint, hint_points(hint)) for hint in hints]
    scored.sort(key=lambda item: (item[1], item[0]), reverse=True)
    positives = [hint for hint, points in scored if points > 0]
    return positives[:max_items] if positives else list(hints[:max_items])


def attack_hint_bases(groups: Dict[str, List[str]]) -> List[str]:
    return [hint_base(hint) for hint in groups.get("attack_payload", [])]


def has_only_weak_sql_comment_attack_signal(groups: Dict[str, List[str]]) -> bool:
    bases = attack_hint_bases(groups)
    return bool(bases) and set(bases).issubset(WEAK_SQL_COMMENT_HINTS)


def is_upload_like_context(candidate: Dict[str, Any], joined: str) -> bool:
    uri = as_text(candidate.get("uri")).lower()
    raw_request = as_text(candidate.get("raw_request")).lower()
    req_content_type = as_text(candidate.get("req_content_type")).lower()
    method = as_text(candidate.get("method")).upper()
    if method != "POST":
        return False
    return (
        "upload" in uri
        or "upload" in joined
        or "multipart/form-data" in joined
        or "multipart/form-data" in raw_request
        or "multipart/form-data" in req_content_type
    )


def infer_policy(candidate: Dict[str, Any], groups: Dict[str, List[str]], hints: Sequence[str]) -> Tuple[str, str]:
    uri = as_text(candidate.get("uri"))
    method = as_text(candidate.get("method")).upper()
    status = as_int(candidate.get("status_code"), 0)
    verdict_hint = as_text(candidate.get("verdict_hint") or candidate.get("verdict"))
    raw_target = as_text(candidate.get("raw_request_target"))
    joined = " ".join([uri, raw_target, as_text(candidate.get("raw_request")), " ".join(hints)]).lower()

    if is_upload_like_context(candidate, joined) and has_only_weak_sql_comment_attack_signal(groups):
        return (
            "context_candidate_upload_failure",
            "upload-like POST has only weak sqli:sql_comment payload signal; multipart boundary/comment-marker false positive is possible, so review as upload failure context unless stronger SQLi evidence exists",
        )

    if groups["attack_payload"]:
        return (
            "keep_candidate_payload",
            "explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof",
        )

    if "server-status" in joined:
        return (
            "context_only_server_status",
            "server-status observation should remain context-only unless external exposure is separately verified",
        )

    if method == "POST" and ("login" in uri.lower() or groups["auth"]):
        return (
            "context_candidate_auth_failure",
            "login/auth POST metadata does not prove auth success; consider auth behavior context unless repeated/combined with payload",
        )

    if method == "POST" and ("upload" in uri.lower() or "multipart" in joined):
        return (
            "context_candidate_upload_failure",
            "upload-like POST metadata does not prove stored upload; consider upload failure context unless payload evidence exists",
        )

    if groups["probe_context"] or any(token in joined for token in ("/.env", "/wp-login", "/admin", "does-not-exist")):
        return (
            "context_candidate_probe",
            "probe/sensitive-path signal may be better represented by probing/sensitive-path/mixed-baseline summaries",
        )

    if groups["status_error"] and not groups["attack_payload"]:
        return (
            "demotion_candidate_status_error_only",
            "candidate appears driven mainly by status/error metadata; review before demoting because real logs may need this signal",
        )

    if status >= 400 or verdict_hint in {"suspicious", "suspicious_scan"}:
        return (
            "review_candidate",
            "non-success status or suspicious verdict without clear payload; manual policy review recommended",
        )

    return ("review_candidate", "candidate does not match a specific policy bucket; manual review recommended")


def explain_candidate(candidate: Dict[str, Any], index: int, min_score: int) -> Dict[str, Any]:
    hints = get_reason_hints(candidate)
    groups = group_reasons(hints)
    policy, note = infer_policy(candidate, groups, hints)
    score = as_int(candidate.get("score"), 0)
    threshold_margin = score - min_score
    scenario = detect_scenario(candidate)

    return {
        "index": index,
        "candidate_index": candidate.get("candidate_index", index),
        "scenario": scenario,
        "request_id": as_text(candidate.get("request_id")),
        "source_table": as_text(candidate.get("source_table")),
        "log_id": candidate.get("log_id"),
        "method": as_text(candidate.get("method")),
        "uri": as_text(candidate.get("uri")),
        "query_string": as_text(candidate.get("query_string")),
        "status_code": candidate.get("status_code"),
        "score": score,
        "min_score": min_score,
        "threshold_margin": threshold_margin,
        "verdict_hint": as_text(candidate.get("verdict_hint") or candidate.get("verdict")),
        "severity": as_text(candidate.get("severity")),
        "handler": as_text(candidate.get("handler")),
        "log_schema": as_text(candidate.get("log_schema")),
        "raw_request_target": as_text(candidate.get("raw_request_target")),
        "user_agent": as_text(candidate.get("user_agent")),
        "policy_class": policy,
        "policy_note": note,
        "top_threshold_reasons": top_point_hints(hints),
        "reason_groups": {key: value for key, value in groups.items() if value},
        "reason_hints": hints,
        "estimated_known_points": sum(hint_points(hint) for hint in hints),
    }


def summarize(explanations: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    policy_counts: Dict[str, int] = {}
    scenario_counts: Dict[str, int] = {}
    for item in explanations:
        policy = item.get("policy_class") or "unknown"
        policy_counts[policy] = policy_counts.get(policy, 0) + 1
        scenario = item.get("scenario") or "unknown"
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
    return {
        "candidate_count": len(explanations),
        "policy_counts": dict(sorted(policy_counts.items())),
        "scenario_counts": dict(sorted(scenario_counts.items())),
    }


def sort_explanations(explanations: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    if mode == "score_desc":
        return sorted(explanations, key=lambda item: (as_int(item.get("score")), as_text(item.get("uri"))), reverse=True)
    if mode == "policy":
        return sorted(explanations, key=lambda item: (as_text(item.get("policy_class")), -as_int(item.get("score")), as_text(item.get("uri"))))
    return explanations


def markdown_escape(text: Any) -> str:
    value = as_text(text)
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(payload_source: str, input_path: Path, explanations: Sequence[Dict[str, Any]]) -> str:
    summary = summarize(explanations)
    lines: List[str] = []
    lines.append("# Prepare Candidate Explanation")
    lines.append("")
    lines.append(f"- input: `{input_path}`")
    lines.append(f"- source: `{payload_source}`")
    lines.append(f"- candidate_count: `{summary['candidate_count']}`")
    lines.append("")
    lines.append("## Policy counts")
    lines.append("")
    lines.append("| policy_class | count |")
    lines.append("|---|---:|")
    for policy, count in summary["policy_counts"].items():
        lines.append(f"| `{markdown_escape(policy)}` | {count} |")
    lines.append("")
    lines.append("## Candidate table")
    lines.append("")
    lines.append(
        "| # | scenario | method | uri | status | score | verdict_hint | policy_class | top reasons |"
    )
    lines.append("|---:|---|---|---|---:|---:|---|---|---|")
    for item in explanations:
        top = ", ".join(item.get("top_threshold_reasons") or [])
        lines.append(
            "| {idx} | {scenario} | {method} | {uri} | {status} | {score} | {verdict} | `{policy}` | {top} |".format(
                idx=item["index"],
                scenario=markdown_escape(item.get("scenario") or "-"),
                method=markdown_escape(item.get("method") or "-"),
                uri=markdown_escape(item.get("uri") or "-"),
                status=markdown_escape(item.get("status_code")),
                score=markdown_escape(item.get("score")),
                verdict=markdown_escape(item.get("verdict_hint") or "-"),
                policy=markdown_escape(item.get("policy_class")),
                top=markdown_escape(top),
            )
        )
    lines.append("")
    lines.append("## Details")
    for item in explanations:
        title = "{idx}. {scenario} {method} {uri}".format(
            idx=item["index"],
            scenario=item.get("scenario") or "-",
            method=item.get("method") or "-",
            uri=item.get("uri") or "-",
        )
        lines.append("")
        lines.append(f"### {markdown_escape(title)}")
        lines.append("")
        lines.append(f"- request_id: `{markdown_escape(item.get('request_id'))}`")
        lines.append(f"- status_code: `{markdown_escape(item.get('status_code'))}`")
        lines.append(f"- score/min_score/margin: `{item.get('score')}/{item.get('min_score')}/{item.get('threshold_margin')}`")
        lines.append(f"- verdict_hint: `{markdown_escape(item.get('verdict_hint'))}`")
        lines.append(f"- policy_class: `{markdown_escape(item.get('policy_class'))}`")
        lines.append(f"- policy_note: {markdown_escape(item.get('policy_note'))}")
        groups = item.get("reason_groups") or {}
        if groups:
            lines.append("- reason_groups:")
            for group, hints in groups.items():
                lines.append(f"  - `{markdown_escape(group)}`: {markdown_escape(', '.join(hints))}")
        else:
            lines.append("- reason_groups: none")
    lines.append("")
    return "\n".join(lines)


def render_tsv(explanations: Sequence[Dict[str, Any]]) -> str:
    columns = [
        "index",
        "scenario",
        "method",
        "uri",
        "status_code",
        "score",
        "min_score",
        "threshold_margin",
        "verdict_hint",
        "policy_class",
        "top_threshold_reasons",
        "policy_note",
    ]
    rows = ["\t".join(columns)]
    for item in explanations:
        values = []
        for column in columns:
            value = item.get(column)
            if isinstance(value, list):
                value = ", ".join(as_text(v) for v in value)
            values.append(as_text(value).replace("\t", " ").replace("\n", " "))
        rows.append("\t".join(values))
    return "\n".join(rows) + "\n"


def render_json(payload_source: str, input_path: Path, explanations: Sequence[Dict[str, Any]]) -> str:
    output = {
        "input": str(input_path),
        "source": payload_source,
        "summary": summarize(explanations),
        "candidates": list(explanations),
    }
    return json.dumps(output, ensure_ascii=False, indent=2) + "\n"


def write_or_print(text: str, out_path: Optional[str]) -> None:
    if out_path:
        path = Path(out_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"[OK] wrote: {path}")
        return
    print(text, end="")


def main() -> int:
    args = parse_args()
    try:
        input_path = resolve_input_path(args)
        payload = read_json(input_path)
        payload_source, candidates = extract_candidates(payload, include_context_only=args.include_context_only)
        explanations = [explain_candidate(candidate, idx + 1, args.min_score) for idx, candidate in enumerate(candidates)]
        explanations = sort_explanations(explanations, args.sort)
        if args.limit is not None:
            explanations = explanations[: args.limit]

        if args.format == "json":
            rendered = render_json(payload_source, input_path, explanations)
        elif args.format == "tsv":
            rendered = render_tsv(explanations)
        else:
            rendered = render_markdown(payload_source, input_path, explanations)
        write_or_print(rendered, args.out)
        return 0
    except KeyboardInterrupt:
        print("\n[INFO] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
