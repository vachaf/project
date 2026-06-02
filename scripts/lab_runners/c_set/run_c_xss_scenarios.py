#!/usr/bin/env python3
"""C-set XSS scenario runner.

Use only in approved local lab environments.
Do not execute against public external targets unless you explicitly opt in.

This runner is an Apache-log-oriented experiment harness. It standardizes HTTP
request generation and execution metadata for XSS-like request targets. It does
not verify browser execution, DOM reflection, script execution, or cookie theft
success. Response body bytes may be counted, but response body content is never
stored.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any


RUNNER_NAME = "c_set_xss_runner"
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
    user_agent: str
    expected_observation: str
    expected_interpretation: str
    expected_response: str
    interpretation_limit: str
    sleep_after_sec: float | None = None


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


def scenario_basic_script() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="C-XSS-01",
            scenario_label="basic_script",
            request_label="basic_script_probe",
            method="GET",
            path="/search?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E",
            user_agent="C-Set-XSS-Runner/basic_script",
            expected_observation=(
                "URL-decoded request target contains script tag with alert call"
            ),
            expected_interpretation=(
                "potential cross-site scripting attempt; no browser execution inference"
            ),
            expected_response="200_or_4xx",
            interpretation_limit="no_browser_execution_confirmation",
        )
    ]


def scenario_url_encoded() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="C-XSS-02",
            scenario_label="url_encoded",
            request_label="url_encoded_cookie_intent_probe",
            method="GET",
            path="/products?category=%3Cscript%3Ealert%28document.cookie%29%3C%2Fscript%3E",
            user_agent="C-Set-XSS-Runner/url_encoded",
            expected_observation=(
                "URL-encoded script tag and document.cookie token are present in request target"
            ),
            expected_interpretation=(
                "document.cookie access intent in XSS-like payload; no cookie theft success inference"
            ),
            expected_response="200_or_4xx",
            interpretation_limit="no_cookie_theft_success_inference",
        )
    ]


def scenario_html_entity() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="C-XSS-03",
            scenario_label="html_entity",
            request_label="html_entity_encoded_xss_probe",
            method="GET",
            path="/view?id=%26%23x3C%3Bscript%26%23x3E%3Balert%281%29%26%23x3C%3B%2Fscript%26%23x3E%3B",
            user_agent="C-Set-XSS-Runner/html_entity",
            expected_observation=(
                "HTML entity encoded script tag appears in request target and should be recoverable by decode view"
            ),
            expected_interpretation=(
                "HTML entity encoded XSS attempt; no browser rendering inference"
            ),
            expected_response="200_or_4xx",
            interpretation_limit="no_browser_render_confirmation",
        )
    ]


def scenario_attribute_event() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="C-XSS-04",
            scenario_label="attribute_event",
            request_label="attribute_event_handler_probe",
            method="GET",
            path="/user/profile?name=x%22%20onerror%3D%22alert%281%29",
            user_agent="C-Set-XSS-Runner/attribute_event",
            expected_observation=(
                "URL-decoded request target contains event-handler-like attribute injection"
            ),
            expected_interpretation=(
                "attribute context XSS attempt; no user interaction or DOM execution inference"
            ),
            expected_response="200_or_4xx",
            interpretation_limit="no_interaction_trigger_inference",
        )
    ]


def scenario_fp_bait() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="C-XSS-05",
            scenario_label="fp_bait",
            request_label="tutorial_onerror_query",
            method="GET",
            path="/common/status?msg=tutorial%20for%20onerror%20event%20handler%20in%20javascript",
            user_agent="C-Set-XSS-Runner/fp_bait",
            expected_observation=(
                "natural-language tutorial query contains XSS-related terms"
            ),
            expected_interpretation=(
                "false positive control; should not be treated as high-confidence XSS solely due to keywords"
            ),
            expected_response="200_or_4xx",
            interpretation_limit="false_positive_review_required",
        )
    ]


SCENARIO_BUILDERS = {
    "basic_script": scenario_basic_script,
    "url_encoded": scenario_url_encoded,
    "html_entity": scenario_html_entity,
    "attribute_event": scenario_attribute_event,
    "fp_bait": scenario_fp_bait,
}


def get_selected_scenarios(selection: str) -> list[str]:
    if selection == "all":
        return [
            "basic_script",
            "url_encoded",
            "html_entity",
            "attribute_event",
            "fp_bait",
        ]
    return [selection]


def add_inter_request_sleep(
    requests: list[RequestSpec],
    default_sleep_sec: float,
) -> list[RequestSpec]:
    spaced: list[RequestSpec] = []
    for index, request in enumerate(requests):
        if request.sleep_after_sec is None:
            sleep_after_sec = default_sleep_sec if index < len(requests) - 1 else 0.0
        else:
            sleep_after_sec = request.sleep_after_sec
        spaced.append(replace(request, sleep_after_sec=sleep_after_sec))
    return spaced


def build_request_plan(selection: str) -> list[RequestSpec]:
    plan: list[RequestSpec] = []
    for scenario_name in get_selected_scenarios(selection):
        plan.extend(SCENARIO_BUILDERS[scenario_name]())
    return add_inter_request_sleep(plan, DEFAULT_INTER_REQUEST_SLEEP_SEC)


def build_full_url(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def render_request(request: RequestSpec, base_url: str, sleep_scale: float) -> dict[str, Any]:
    return {
        "scenario_id": request.scenario_id,
        "scenario_label": request.scenario_label,
        "request_label": request.request_label,
        "method": request.method,
        "path": request.path,
        "full_url": build_full_url(base_url, request.path),
        "user_agent": request.user_agent,
        "expected_observation": request.expected_observation,
        "expected_interpretation": request.expected_interpretation,
        "expected_response": request.expected_response,
        "interpretation_limit": request.interpretation_limit,
        "sleep_after_sec": request.sleep_after_sec,
        "scaled_sleep_after_sec": round((request.sleep_after_sec or 0.0) * sleep_scale, 3),
        "stores_response_body_content": False,
    }


def build_plan_markdown(
    base_url: str,
    scenario: str,
    sleep_scale: float,
    timeout_sec: float,
    requests: list[RequestSpec],
    dry_run: bool,
    target_class: str,
) -> str:
    lines = [
        "# C Set XSS Execution Plan",
        "",
        f"- mode: {'dry-run' if dry_run else 'execute'}",
        f"- base_url: {base_url}",
        f"- scenario: {scenario}",
        f"- request_count: {len(requests)}",
        f"- sleep_scale: {sleep_scale}",
        f"- timeout_sec: {timeout_sec}",
        f"- target_class: {target_class}",
        "- transport: urllib.request over http/https",
        "- safety: approved local lab only; public target execution is blocked by default",
        "- note: response body content is never stored; only byte length may be recorded in execute mode",
        "",
        "| Scenario ID | scenario_label | request_label | method | path | expected_interpretation | interpretation_limit |",
        "|---|---|---|---|---|---|---|",
    ]
    for request in requests:
        lines.append(
            f"| {request.scenario_id} | {request.scenario_label} | {request.request_label} | "
            f"{request.method} | {request.path} | {request.expected_interpretation} | "
            f"{request.interpretation_limit} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This runner reproduces Apache-log-visible request target and query structure only.",
            "- No browser execution confirmation, no DOM reflection confirmation, and no cookie theft success inference are allowed.",
            "- status_code=200 or response_body_bytes alone must not be treated as XSS success evidence.",
            "- The fp_bait scenario is a false-positive control and should remain review-oriented.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_summary_markdown(
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    status_counts: dict[str, int] = {}
    scenario_statuses: list[str] = []
    errors: list[str] = []
    body_lengths = [
        item["response_body_bytes"]
        for item in results
        if isinstance(item.get("response_body_bytes"), int)
    ]

    for item in results:
        status_key = str(item["status_code"]) if item["status_code"] is not None else "none"
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        scenario_statuses.append(
            f"- {item['scenario_id']} / {item['request_label']}: "
            f"status={item['status_code']} error={item.get('error') or 'none'}"
        )
        if item.get("error"):
            errors.append(f"- {item['request_label']}: {item['error']}")

    if body_lengths:
        body_summary = f"min={min(body_lengths)}, max={max(body_lengths)}"
    else:
        body_summary = "min=n/a, max=n/a"

    lines = [
        "# C Set XSS Run Summary",
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
        "- This runner does not verify XSS execution success, cookie theft, or browser execution.",
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
            "## Scenario Status",
            "",
        ]
    )
    lines.extend(scenario_statuses or ["- none"])

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
            "- No browser execution.",
            "- No cookie theft success.",
            "- No DOM reflection confirmation.",
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
    request: RequestSpec,
    timeout_sec: float,
) -> dict[str, Any]:
    started_at = now_local_iso()
    started_perf = time.perf_counter()
    url = build_full_url(base_url, request.path)
    urllib_request = urllib.request.Request(
        url=url,
        method=request.method,
        headers={"User-Agent": request.user_agent},
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
    except Exception as error:  # pragma: no cover - defensive logging path
        error_message = f"{error.__class__.__name__}: {error}"

    ended_at = now_local_iso()
    duration_ms = round((time.perf_counter() - started_perf) * 1000, 2)
    return {
        "scenario_id": request.scenario_id,
        "scenario_label": request.scenario_label,
        "request_label": request.request_label,
        "method": request.method,
        "path": request.path,
        "user_agent": request.user_agent,
        "expected_observation": request.expected_observation,
        "expected_interpretation": request.expected_interpretation,
        "expected_response": request.expected_response,
        "interpretation_limit": request.interpretation_limit,
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
            "Run C-set XSS lab scenarios. Use only in approved local lab environments."
        ),
        epilog=(
            "This runner does not confirm browser execution, cookie theft success, "
            "or DOM reflection. --dry-run and --print-plan never send HTTP requests."
        ),
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Target base URL, e.g. http://192.168.56.105",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output directory for plan/log files",
    )
    parser.add_argument(
        "--scenario",
        default="all",
        choices=[
            "all",
            "basic_script",
            "url_encoded",
            "html_entity",
            "attribute_event",
            "fp_bait",
        ],
        help="Scenario selection",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print and write plan only")
    parser.add_argument("--print-plan", action="store_true", help="Alias of --dry-run")
    parser.add_argument(
        "--sleep-scale",
        type=float,
        default=DEFAULT_SLEEP_SCALE,
        help="Scale inter-request sleep durations, e.g. 0.1",
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

    base_url = normalize_base_url(args.base_url)
    target_class = enforce_target_guard(
        base_url=base_url,
        dry_run=dry_run,
        allow_public_target=args.allow_public_target,
    )
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    requests = build_request_plan(args.scenario)
    started_at = now_local_iso()
    generated_at = started_at
    mode = "dry-run" if dry_run else "execute"
    print(f"[c-xss] mode={mode} scenario={args.scenario}")
    print(f"[c-xss] request_count={len(requests)} target_class={target_class}")

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
        },
        "requests": [
            render_request(request, base_url, args.sleep_scale) for request in requests
        ],
    }

    write_json(output_dir / OUTPUT_PLAN_JSON, plan_payload)
    write_text(
        output_dir / OUTPUT_PLAN_MD,
        build_plan_markdown(
            base_url=base_url,
            scenario=args.scenario,
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
        print("[c-xss] dry-run complete; no HTTP requests sent")
        return 0

    results_path = output_dir / OUTPUT_RESULTS_JSONL
    results: list[dict[str, Any]] = []
    for request in requests:
        result = execute_request(base_url, request, args.timeout_sec)
        append_jsonl(results_path, result)
        results.append(result)
        maybe_sleep((request.sleep_after_sec or 0.0) * args.sleep_scale)

    metadata["ended_at"] = now_local_iso()
    write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
    write_text(output_dir / OUTPUT_SUMMARY_MD, build_run_summary_markdown(metadata, results))
    print(f"[c-xss] execution complete; results={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
