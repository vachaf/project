#!/usr/bin/env python3
"""E-set R3/R3B OpenCart search scenario runner.

Use only in approved local lab environments.
This runner is an Apache-log-oriented experiment harness. It standardizes
request generation and execution metadata. It does not verify SQLi success,
DB result changes, or XSS browser execution.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any


RUNNER_NAME = "e_set_r3_search_runner"
RUNNER_VERSION = "1.0"
DEFAULT_TIMEOUT_SEC = 10.0
DEFAULT_SLEEP_SCALE = 1.0
DEFAULT_INTER_REQUEST_SLEEP_SEC = 1.0
READ_CHUNK_SIZE = 8192
OUTPUT_PLAN_JSON = "execution_plan.json"
OUTPUT_PLAN_MD = "execution_plan.md"
OUTPUT_METADATA_JSON = "run_metadata.json"
OUTPUT_RESULTS_JSONL = "request_results.jsonl"
OUTPUT_SUMMARY_MD = "run_summary.md"


@dataclass(frozen=True)
class RequestSpec:
    scenario_id: str
    scenario_label: str
    request_label: str
    method: str
    path: str
    expected_observation: str
    expected_interpretation: str
    expected_response: str
    interpretation_limit: str
    params: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    sleep_after_sec: float | None = None
    is_optional: bool = False


def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json_dumps(payload) + "\n")


def append_jsonl(path: Path, payload: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def normalize_base_url(raw_base_url: str) -> str:
    parsed = urllib.parse.urlparse(raw_base_url)
    if parsed.scheme not in {"http", "https"}:
        raise SystemExit("--base-url must include an http:// or https:// scheme")
    if not parsed.netloc:
        raise SystemExit("--base-url must include a host")
    if parsed.username or parsed.password:
        raise SystemExit("--base-url must not include username/password")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise SystemExit("--base-url must point to scheme://host[:port] without path/query")

    host = parsed.hostname
    if not host:
        raise SystemExit("Could not parse hostname from --base-url")
    if ":" in host and not host.startswith("["):
        authority_host = f"[{host}]"
    else:
        authority_host = host
    authority = authority_host if parsed.port is None else f"{authority_host}:{parsed.port}"
    return f"{parsed.scheme}://{authority}"


def classify_target_host(hostname: str) -> str:
    try:
        ip_obj = ipaddress.ip_address(hostname)
    except ValueError:
        normalized = hostname.lower()
        if normalized == "localhost" or normalized.endswith(".localhost"):
            return "local-hostname"
        if normalized.endswith(".local"):
            return "local-hostname"
        if normalized.endswith(".test"):
            return "test-hostname"
        return "general-hostname"

    if ip_obj.is_loopback:
        return "loopback-ip"
    if ip_obj.is_private:
        return "private-ip"
    return "public-ip"


def enforce_target_guard(
    base_url: str,
    dry_run: bool,
    allow_public_target: bool,
) -> str:
    parsed = urllib.parse.urlparse(base_url)
    hostname = parsed.hostname
    if not hostname:
        raise SystemExit("Could not parse hostname from --base-url")

    target_class = classify_target_host(hostname)
    if dry_run:
        return target_class

    if target_class in {"loopback-ip", "private-ip", "local-hostname", "test-hostname"}:
        return target_class

    if allow_public_target:
        print(
            "Warning: public/general target override enabled. Execute only in an "
            "approved local lab environment.",
            file=sys.stderr,
        )
        return target_class

    raise SystemExit(
        "Refusing to execute against a public IP or general hostname target. "
        "Use an approved local lab environment, run with --dry-run/--print-plan, "
        "or explicitly pass --allow-public-target."
    )


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def user_agent_for(prefix: str, scenario_id: str, request_label: str) -> str:
    return f"{prefix}-{slugify(scenario_id)}-{slugify(request_label)}"


def params_as_objects(params: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    return [{"name": name, "value": value} for name, value in params]


def params_for_display(params: tuple[tuple[str, str], ...]) -> str:
    if not params:
        return "[]"
    return ", ".join(f"{name}={value}" for name, value in params)


def escape_md_cell(text: str) -> str:
    return text.replace("|", "\\|")


REQUESTS_BY_SCENARIO_ID: dict[str, list[RequestSpec]] = {
    "E-R3-01": [
        RequestSpec(
            scenario_id="E-R3-01",
            scenario_label="normal_search_baseline",
            request_label="normal_search_apple",
            method="GET",
            path="/search",
            params=(("q", "apple"),),
            expected_observation="normal search query without attack structure",
            expected_interpretation="benign search baseline / reference baseline",
            expected_response="200",
            interpretation_limit="baseline_only_do_not_promote_to_attack_candidate",
        )
    ],
    "E-R3-02": [
        RequestSpec(
            scenario_id="E-R3-02",
            scenario_label="search_sqli",
            request_label="search_sqli_xclose_or_true",
            method="GET",
            path="/search",
            params=(("q", "x')) OR 1=1 --"),),
            expected_observation=(
                "quote/parenthesis termination and OR true SQLi structure in search query"
            ),
            expected_interpretation="SQLi attempt in search context",
            expected_response="200_or_4xx",
            interpretation_limit="no_db_result_or_exfiltration_confirmation_without_response_body",
        )
    ],
    "E-R3-03": [
        RequestSpec(
            scenario_id="E-R3-03",
            scenario_label="search_xss",
            request_label="search_xss_script_tag",
            method="GET",
            path="/search",
            params=(("q", "<script>alert(1)</script>"),),
            expected_observation="script tag and alert call in search query",
            expected_interpretation="XSS attempt in search context",
            expected_response="200_or_4xx",
            interpretation_limit="no_browser_execution_confirmation",
        )
    ],
    "E-R3-04": [
        RequestSpec(
            scenario_id="E-R3-04",
            scenario_label="search_xss",
            request_label="search_xss_html_entity",
            method="GET",
            path="/search",
            params=(("q", "&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;"),),
            expected_observation=(
                "HTML entity encoded script tag in search query; decode view should recover XSS"
            ),
            expected_interpretation="HTML entity encoded XSS attempt in search context",
            expected_response="200_or_4xx",
            interpretation_limit="no_browser_render_confirmation",
        )
    ],
    "E-R3-05": [
        RequestSpec(
            scenario_id="E-R3-05",
            scenario_label="normal_search_baseline",
            request_label="normal_search_phone",
            method="GET",
            path="/search",
            params=(("q", "phone"),),
            expected_observation="second normal search baseline",
            expected_interpretation="benign reference baseline / normal search context",
            expected_response="200",
            interpretation_limit="baseline_only_do_not_promote_to_attack_candidate",
        )
    ],
}

BASELINE_IDS = ["E-R3-01", "E-R3-05"]
SQLI_IDS = ["E-R3-02"]
XSS_IDS = ["E-R3-03", "E-R3-04"]
ALL_IDS = BASELINE_IDS[:1] + SQLI_IDS + XSS_IDS + BASELINE_IDS[1:]


def expand_scenario_selection(selection: str) -> list[str]:
    normalized = selection.strip()
    if not normalized:
        raise SystemExit("--scenario must not be empty")

    lowered = normalized.lower()
    if lowered == "all":
        return ALL_IDS
    if lowered == "baseline":
        return BASELINE_IDS
    if lowered == "sqli":
        return SQLI_IDS
    if lowered == "xss":
        return XSS_IDS

    scenario_ids: list[str] = []
    for raw_item in normalized.split(","):
        item = raw_item.strip().upper()
        if not item:
            raise SystemExit("Invalid --scenario: empty item in comma-separated list")
        if item not in REQUESTS_BY_SCENARIO_ID:
            valid_items = ", ".join(
                ["all", "baseline", "sqli", "xss"] + list(REQUESTS_BY_SCENARIO_ID)
            )
            raise SystemExit(f"Unknown scenario '{raw_item.strip()}'. Valid values: {valid_items}")
        if item not in scenario_ids:
            scenario_ids.append(item)
    return scenario_ids


def add_inter_request_sleep(
    requests: list[RequestSpec],
    default_sleep_sec: float,
) -> list[RequestSpec]:
    spaced: list[RequestSpec] = []
    for index, request_spec in enumerate(requests):
        if request_spec.sleep_after_sec is None:
            sleep_after_sec = default_sleep_sec if index < len(requests) - 1 else 0.0
        else:
            sleep_after_sec = request_spec.sleep_after_sec
        if index == len(requests) - 1:
            sleep_after_sec = 0.0
        spaced.append(replace(request_spec, sleep_after_sec=sleep_after_sec))
    return spaced


def build_request_plan(selection: str) -> list[RequestSpec]:
    plan: list[RequestSpec] = []
    for scenario_id in expand_scenario_selection(selection):
        plan.extend(REQUESTS_BY_SCENARIO_ID[scenario_id])
    return add_inter_request_sleep(plan, DEFAULT_INTER_REQUEST_SLEEP_SEC)


def build_query_string(params: tuple[tuple[str, str], ...]) -> str:
    if not params:
        return ""
    return urllib.parse.urlencode(params, doseq=True, quote_via=urllib.parse.quote)


def build_full_url(base_url: str, path: str, params: tuple[tuple[str, str], ...]) -> str:
    if not path.startswith("/"):
        raise SystemExit(f"Request path must start with '/': {path}")
    query_string = build_query_string(params)
    if query_string:
        return f"{base_url}{path}?{query_string}"
    return f"{base_url}{path}"


def render_request(
    request_spec: RequestSpec,
    base_url: str,
    ua_prefix: str,
    sleep_scale: float,
) -> dict[str, Any]:
    user_agent = user_agent_for(ua_prefix, request_spec.scenario_id, request_spec.request_label)
    return {
        "scenario_id": request_spec.scenario_id,
        "scenario_label": request_spec.scenario_label,
        "request_label": request_spec.request_label,
        "method": request_spec.method,
        "path": request_spec.path,
        "params": params_as_objects(request_spec.params),
        "user_agent": user_agent,
        "expected_observation": request_spec.expected_observation,
        "expected_interpretation": request_spec.expected_interpretation,
        "expected_response": request_spec.expected_response,
        "interpretation_limit": request_spec.interpretation_limit,
        "sleep_after_sec": request_spec.sleep_after_sec,
        "is_optional": request_spec.is_optional,
        "scaled_sleep_after_sec": round((request_spec.sleep_after_sec or 0.0) * sleep_scale, 3),
        "stores_response_body_content": False,
        "full_url": build_full_url(base_url, request_spec.path, request_spec.params),
    }


def build_plan_markdown(
    base_url: str,
    scenario: str,
    ua_prefix: str,
    sleep_scale: float,
    timeout_sec: float,
    requests: list[RequestSpec],
    dry_run: bool,
    target_class: str,
) -> str:
    lines = [
        "# E Set R3 Search Execution Plan",
        "",
        f"- mode: {'dry-run' if dry_run else 'execute'}",
        f"- base_url: {base_url}",
        f"- scenario: {scenario}",
        f"- ua_prefix: {ua_prefix}",
        f"- request_count: {len(requests)}",
        f"- sleep_scale: {sleep_scale}",
        f"- timeout_sec: {timeout_sec}",
        f"- target_class: {target_class}",
        "- transport: urllib.request over http/https",
        "- safety: approved OpenCart search lab only; public target execution is blocked by default",
        "- note: response body content is never stored; only body length may be recorded in execute mode",
        "",
        "| Scenario ID | scenario_label | request_label | method | path | params | optional | expected_interpretation | interpretation_limit |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for request_spec in requests:
        lines.append(
            f"| {escape_md_cell(request_spec.scenario_id)} | "
            f"{escape_md_cell(request_spec.scenario_label)} | "
            f"{escape_md_cell(request_spec.request_label)} | "
            f"{escape_md_cell(request_spec.method)} | "
            f"{escape_md_cell(request_spec.path)} | "
            f"{escape_md_cell(params_for_display(request_spec.params))} | "
            f"{str(request_spec.is_optional).lower()} | "
            f"{escape_md_cell(request_spec.expected_interpretation)} | "
            f"{escape_md_cell(request_spec.interpretation_limit)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This runner does not confirm SQLi success, DB result changes, or XSS execution.",
            "- normal search baseline rows are reference-only and must not be promoted to attack candidates by runner semantics.",
            "- status_code=200, text/html, or response_body_bytes alone must not be treated as SQLi success or XSS execution evidence.",
            "- Response body raw content is never stored or inspected.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_summary_markdown(
    metadata: dict[str, Any],
    requests: list[RequestSpec],
    results: list[dict[str, Any]],
) -> str:
    status_counts: dict[str, int] = {}
    errors: list[str] = []
    body_lengths = [
        item["response_body_bytes"]
        for item in results
        if isinstance(item.get("response_body_bytes"), int)
    ]
    scenario_totals: dict[str, dict[str, int]] = {}

    for item in results:
        status_key = str(item["status_code"]) if item["status_code"] is not None else "none"
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        scenario_bucket = scenario_totals.setdefault(
            item["scenario_id"],
            {"count": 0, "error_count": 0},
        )
        scenario_bucket["count"] += 1
        if item.get("error"):
            scenario_bucket["error_count"] += 1
            errors.append(f"- {item['request_label']}: {item['error']}")

    selected_ids: list[str] = []
    for request_spec in requests:
        if request_spec.scenario_id not in selected_ids:
            selected_ids.append(request_spec.scenario_id)

    if body_lengths:
        body_summary = f"min={min(body_lengths)}, max={max(body_lengths)}"
    else:
        body_summary = "min=n/a, max=n/a"

    lines = [
        "# E Set R3 Search Run Summary",
        "",
        f"- mode: {metadata['mode']}",
        f"- base_url: {metadata['base_url']}",
        f"- scenario: {metadata['scenario']}",
        f"- generated_at: {metadata['generated_at']}",
        f"- started_at: {metadata['started_at']}",
        f"- ended_at: {metadata['ended_at']}",
        f"- request_count: {metadata['request_count']}",
        f"- sleep_scale: {metadata['sleep_scale']}",
        f"- timeout_sec: {metadata['timeout_sec']}",
        f"- target_class: {metadata['target_class']}",
        "- transport: urllib.request over http/https",
        "- 이 runner는 PHP wrapper 실행 성공, 파일 노출, SQLi 성공, XSS 실행을 검증하지 않는다.",
        "",
        "## Status Code Distribution",
        "",
    ]
    if status_counts:
        for status_key in sorted(status_counts):
            lines.append(f"- {status_key}: {status_counts[status_key]}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Scenario Results",
            "",
        ]
    )
    for scenario_id in selected_ids:
        bucket = scenario_totals.get(scenario_id, {"count": 0, "error_count": 0})
        lines.append(f"- {scenario_id}: requests={bucket['count']} errors={bucket['error_count']}")

    lines.extend(
        [
            "",
            "## Error Summary",
            "",
        ]
    )
    lines.extend(errors or ["- none"])

    lines.extend(
        [
            "",
            "## Response Body Bytes",
            "",
            f"- {body_summary}",
            "",
            "## Interpretation Guardrails",
            "",
            "- No SQLi success confirmation.",
            "- No DB result or exfiltration confirmation.",
            "- No XSS browser execution or render confirmation.",
            "- Response body raw content not inspected or stored.",
        ]
    )
    return "\n".join(lines) + "\n"


def discard_response_body(response: Any) -> int:
    total = 0
    while True:
        chunk = response.read(READ_CHUNK_SIZE)
        if not chunk:
            return total
        total += len(chunk)


def execute_request(
    base_url: str,
    request_spec: RequestSpec,
    ua_prefix: str,
    timeout_sec: float,
) -> dict[str, Any]:
    started_at = now_local_iso()
    started_perf = time.perf_counter()
    user_agent = user_agent_for(ua_prefix, request_spec.scenario_id, request_spec.request_label)
    url = build_full_url(base_url, request_spec.path, request_spec.params)
    urllib_request = urllib.request.Request(
        url=url,
        method=request_spec.method,
        headers={"User-Agent": user_agent},
        data=None,
    )

    status_code = None
    response_body_bytes = None
    error_message = None

    try:
        with urllib.request.urlopen(urllib_request, timeout=timeout_sec) as response:
            status_code = response.getcode()
            response_body_bytes = discard_response_body(response)
    except urllib.error.HTTPError as error:
        status_code = error.code
        try:
            response_body_bytes = discard_response_body(error)
        except Exception:
            response_body_bytes = None
    except urllib.error.URLError as error:
        error_message = f"URLError: {error}"
    except Exception as error:  # pragma: no cover
        error_message = f"{error.__class__.__name__}: {error}"

    ended_at = now_local_iso()
    duration_ms = round((time.perf_counter() - started_perf) * 1000, 2)
    return {
        "scenario_id": request_spec.scenario_id,
        "scenario_label": request_spec.scenario_label,
        "request_label": request_spec.request_label,
        "method": request_spec.method,
        "path": request_spec.path,
        "params": params_as_objects(request_spec.params),
        "user_agent": user_agent,
        "expected_observation": request_spec.expected_observation,
        "expected_interpretation": request_spec.expected_interpretation,
        "expected_response": request_spec.expected_response,
        "interpretation_limit": request_spec.interpretation_limit,
        "is_optional": request_spec.is_optional,
        "started_at": started_at,
        "ended_at": ended_at,
        "status_code": status_code,
        "response_body_bytes": response_body_bytes,
        "duration_ms": duration_ms,
        "error": error_message,
    }


def maybe_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run E-set R3/R3B OpenCart search lab scenarios. Use only in approved local lab environments."
        ),
        epilog=(
            "This runner does not confirm SQLi success or XSS execution. "
            "--dry-run and --print-plan never send HTTP requests."
        ),
    )
    parser.add_argument("--base-url", required=True, help="Target base URL")
    parser.add_argument("--out", required=True, help="Output directory for plan/log files")
    parser.add_argument(
        "--scenario",
        default="all",
        help="Scenario selector: all, baseline, sqli, xss, or comma-separated IDs",
    )
    parser.add_argument(
        "--ua-prefix",
        default="lab-e-set",
        help="User-Agent prefix for generated requests",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print and write plan only")
    parser.add_argument("--print-plan", action="store_true", help="Alias of --dry-run")
    parser.add_argument(
        "--sleep-scale",
        type=float,
        default=DEFAULT_SLEEP_SCALE,
        help="Scale inter-request sleep durations",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=DEFAULT_TIMEOUT_SEC,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--allow-public-target",
        action="store_true",
        help="Explicitly allow execution against a public/general target",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = args.dry_run or args.print_plan
    if args.sleep_scale < 0:
        raise SystemExit("--sleep-scale must be >= 0")
    if args.timeout_sec <= 0:
        raise SystemExit("--timeout-sec must be > 0")
    if not args.ua_prefix.strip():
        raise SystemExit("--ua-prefix must not be empty")

    base_url = normalize_base_url(args.base_url)
    target_class = enforce_target_guard(
        base_url=base_url,
        dry_run=dry_run,
        allow_public_target=args.allow_public_target,
    )
    requests = build_request_plan(args.scenario)

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    started_at = now_local_iso()
    generated_at = started_at
    mode = "dry-run" if dry_run else "execute"
    print(f"[e-r3] mode={mode} scenario={args.scenario}")
    print(f"[e-r3] request_count={len(requests)} target_class={target_class}")

    metadata = {
        "runner": RUNNER_NAME,
        "version": RUNNER_VERSION,
        "base_url": base_url,
        "scenario": args.scenario,
        "mode": mode,
        "generated_at": generated_at,
        "started_at": started_at,
        "ended_at": None,
        "request_count": len(requests),
        "sleep_scale": args.sleep_scale,
        "timeout_sec": args.timeout_sec,
        "target_class": target_class,
        "args": {
            "base_url": args.base_url,
            "out": args.out,
            "scenario": args.scenario,
            "ua_prefix": args.ua_prefix,
            "dry_run": args.dry_run,
            "print_plan": args.print_plan,
            "sleep_scale": args.sleep_scale,
            "timeout_sec": args.timeout_sec,
            "allow_public_target": args.allow_public_target,
        },
    }

    plan_payload = {
        "metadata": {
            "runner": RUNNER_NAME,
            "version": RUNNER_VERSION,
            "base_url": base_url,
            "scenario": args.scenario,
            "mode": mode,
            "generated_at": generated_at,
            "ua_prefix": args.ua_prefix,
            "request_count": len(requests),
            "target_class": target_class,
        },
        "requests": [
            render_request(request_spec, base_url, args.ua_prefix, args.sleep_scale)
            for request_spec in requests
        ],
    }

    write_json(output_dir / OUTPUT_PLAN_JSON, plan_payload)
    write_text(
        output_dir / OUTPUT_PLAN_MD,
        build_plan_markdown(
            base_url=base_url,
            scenario=args.scenario,
            ua_prefix=args.ua_prefix,
            sleep_scale=args.sleep_scale,
            timeout_sec=args.timeout_sec,
            requests=requests,
            dry_run=dry_run,
            target_class=target_class,
        ),
    )

    if dry_run:
        metadata["ended_at"] = now_local_iso()
        write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
        print("[e-r3] dry-run complete; no HTTP requests sent")
        return 0

    results_path = output_dir / OUTPUT_RESULTS_JSONL
    write_text(results_path, "")
    results: list[dict[str, Any]] = []
    for request_spec in requests:
        result = execute_request(base_url, request_spec, args.ua_prefix, args.timeout_sec)
        append_jsonl(results_path, result)
        results.append(result)
        maybe_sleep((request_spec.sleep_after_sec or 0.0) * args.sleep_scale)

    metadata["ended_at"] = now_local_iso()
    write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
    write_text(output_dir / OUTPUT_SUMMARY_MD, build_run_summary_markdown(metadata, requests, results))
    print(f"[e-r3] execution complete; results={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
