#!/usr/bin/env python3
"""G-set R3 baseline / FP bait runner.

Use only in approved local lab environments.
Do not execute against public external targets unless you explicitly opt in.

This runner is an experiment harness that records HTTP request metadata for
Apache-log-based baseline/reference observation. It does not verify attack
success, CORS weakness, method allowance, or server-configuration weakness.
Request body content and response body content are not stored.
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


DEFAULT_TIMEOUT_SEC = 10.0
DEFAULT_SLEEP_SCALE = 1.0
DEFAULT_INTER_REQUEST_SLEEP_SEC = 1.0
DEFAULT_REPEAT_SLEEP_SEC = 2.0
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
    expected_observation: list[str]
    expected_interpretation: list[str]
    expected_response: str
    interpretation_limit: str
    additional_headers: dict[str, str] | None = None
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
        if normalized == "example.test" or normalized.endswith(".example.test"):
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


def scenario_head_health() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R3-01",
            scenario_label="normal_head_health_check",
            request_label="head_health_request",
            method="HEAD",
            path="/health",
            user_agent="HealthCheck/1.0",
            expected_observation=[
                "method=HEAD",
                "health-check-like path",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "normal health check or monitoring baseline possibility",
                "should not be promoted as attack by method alone",
            ],
            expected_response="any",
            interpretation_limit="baseline_head_no_attack_inference",
        )
    ]


def scenario_options_preflight() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R3-02",
            scenario_label="browser_like_options_preflight",
            request_label="options_preflight_request",
            method="OPTIONS",
            path="/",
            user_agent="Mozilla/5.0 regression-browser",
            expected_observation=[
                "method=OPTIONS",
                "preflight-like headers were sent",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "browser-like preflight baseline possibility",
                "CORS vulnerability must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="preflight_context_no_cors_success_inference",
            additional_headers={
                "Origin": "http://example.test",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    ]


def scenario_get_browse() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R3-03",
            scenario_label="normal_get_browse",
            request_label="get_browse_request",
            method="GET",
            path="/",
            user_agent="Mozilla/5.0 regression-browser",
            expected_observation=[
                "method=GET",
                "normal browse-like request",
            ],
            expected_interpretation=[
                "normal baseline",
                "should not be promoted as method probing",
            ],
            expected_response="any",
            interpretation_limit="baseline_get_no_attack_inference",
        )
    ]


def scenario_monitoring_ua() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R3-04",
            scenario_label="internal_monitoring_get",
            request_label="monitoring_ua_request",
            method="GET",
            path="/",
            user_agent="InternalMonitor/1.0",
            expected_observation=[
                "method=GET",
                "monitoring-like User-Agent",
            ],
            expected_interpretation=[
                "internal monitoring or automation baseline possibility",
                "User-Agent alone is not attack evidence",
            ],
            expected_response="any",
            interpretation_limit="monitoring_ua_no_attack_inference",
        )
    ]


def scenario_repeated_head() -> list[RequestSpec]:
    requests: list[RequestSpec] = []
    for index in range(3):
        requests.append(
            RequestSpec(
                scenario_id="G-R3-05",
                scenario_label="repeated_head_monitoring_x3",
                request_label=f"repeated_head_monitoring_{index + 1:02d}",
                method="HEAD",
                path="/",
                user_agent="InternalMonitor/1.0",
                expected_observation=[
                    "repeated HEAD requests",
                    "same src_ip/time window",
                ],
                expected_interpretation=[
                    "monitoring-like repeated baseline possibility",
                    "repeated HEAD alone should not be promoted as probing",
                ],
                expected_response="any",
                interpretation_limit="repeated_head_baseline_no_attack_inference",
                sleep_after_sec=DEFAULT_REPEAT_SLEEP_SEC if index < 2 else 0.0,
            )
        )
    return requests


SCENARIO_BUILDERS = {
    "head_health": scenario_head_health,
    "options_preflight": scenario_options_preflight,
    "get_browse": scenario_get_browse,
    "monitoring_ua": scenario_monitoring_ua,
    "repeated_head": scenario_repeated_head,
}

SCENARIO_ALIASES = {
    "repeated_head_monitoring": "repeated_head",
}


def canonicalize_scenario(selection: str) -> str:
    return SCENARIO_ALIASES.get(selection, selection)


def get_selected_scenarios(selection: str) -> list[str]:
    if selection == "all":
        return [
            "head_health",
            "options_preflight",
            "get_browse",
            "monitoring_ua",
            "repeated_head",
        ]
    return [canonicalize_scenario(selection)]


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


def summarize_additional_header_names(request: RequestSpec) -> list[str]:
    return sorted((request.additional_headers or {}).keys())


def render_plan_item(
    base_url: str,
    request: RequestSpec,
    sleep_scale: float,
) -> dict[str, Any]:
    return {
        "scenario_id": request.scenario_id,
        "scenario_label": request.scenario_label,
        "request_label": request.request_label,
        "method": request.method,
        "path": request.path,
        "full_url": build_full_url(base_url, request.path),
        "user_agent": request.user_agent,
        "additional_request_header_names": summarize_additional_header_names(request),
        "expected_observation": request.expected_observation,
        "expected_interpretation": request.expected_interpretation,
        "expected_response": request.expected_response,
        "interpretation_limit": request.interpretation_limit,
        "stores_request_body_content": False,
        "stores_response_body_content": False,
        "sleep_after_sec": request.sleep_after_sec,
        "scaled_sleep_after_sec": round((request.sleep_after_sec or 0.0) * sleep_scale, 3),
    }


def build_plan_markdown(
    base_url: str,
    selected_scenario: str,
    sleep_scale: float,
    timeout_sec: float,
    requests: list[RequestSpec],
    dry_run: bool,
    target_class: str,
) -> str:
    lines = [
        "# G Set R3 Execution Plan",
        "",
        f"- mode: {'dry-run' if dry_run else 'execute'}",
        f"- base_url: {base_url}",
        f"- scenario: {selected_scenario}",
        f"- request_count: {len(requests)}",
        f"- sleep_scale: {sleep_scale}",
        f"- timeout_sec: {timeout_sec}",
        f"- target_class: {target_class}",
        "- transport: urllib.request over http/https",
        "- safety: approved local lab only; public target execution is blocked by default",
        "- note: request body content and response body content are not stored",
        "",
        "## Requests",
        "",
        "| # | scenario_id | runner label | request_label | method | path | extra_header_names | expected_response | scaled_sleep_after_sec |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for index, request in enumerate(requests, start=1):
        header_names = ",".join(summarize_additional_header_names(request)) or "(none)"
        lines.append(
            f"| {index} | {request.scenario_id} | {request.scenario_label} | "
            f"{request.request_label} | {request.method} | {request.path} | "
            f"{header_names} | {request.expected_response} | "
            f"{round((request.sleep_after_sec or 0.0) * sleep_scale, 3)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This runner is baseline/reference harness only and does not verify attack success.",
            "- HEAD, OPTIONS, and GET observations must not be promoted by method alone.",
            "- Monitoring-like User-Agent values are context only and are not attack evidence by themselves.",
            "- Preflight-like OPTIONS headers are execution inputs only; CORS weakness must not be inferred.",
            "- Request body content and response body content are not written to disk.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_summary_markdown(
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    lines = [
        "# G Set R3 Run Summary",
        "",
        f"- mode: {metadata['mode']}",
        f"- base_url: {metadata['base_url']}",
        f"- scenario: {metadata['scenario']}",
        f"- started_at: {metadata['started_at']}",
        f"- ended_at: {metadata['ended_at']}",
        f"- request_count: {metadata['request_count']}",
        f"- sleep_scale: {metadata['sleep_scale']}",
        f"- timeout_sec: {metadata['timeout_sec']}",
        f"- target_class: {metadata['target_class']}",
        "- transport: urllib.request over http/https",
        "- note: request body content and response body content are not stored",
        "",
        "## Results",
        "",
        "| scenario_id | request_label | method | path | status_code | response_headers_count | response_body_bytes_discarded | duration_ms | error |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['scenario_id']} | {item['request_label']} | {item['method']} | "
            f"{item['path']} | {item['status_code']} | {item['response_headers_count']} | "
            f"{item['response_body_bytes_discarded']} | {item['duration_ms']} | "
            f"{item.get('error') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- Results are baseline/reference context only.",
            "- No CORS success inference, no method allowance inference, no server-configuration weakness inference, and no attack-success inference are allowed.",
            "- User-Agent strings and repeated HEAD alone are not sufficient to label an attack.",
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
    headers = {"User-Agent": request.user_agent}
    if request.additional_headers:
        headers.update(request.additional_headers)

    urllib_request = urllib.request.Request(
        url=url,
        method=request.method,
        headers=headers,
        data=None,
    )

    status_code = None
    response_headers_count = None
    response_body_bytes_discarded = None
    error_message = None

    try:
        with urllib.request.urlopen(urllib_request, timeout=timeout_sec) as response:
            status_code = response.getcode()
            response_headers_count = len(response.headers.items())
            response_body_bytes_discarded = discard_response_body(response)
    except urllib.error.HTTPError as error:
        status_code = error.code
        response_headers_count = len(error.headers.items()) if error.headers else None
        try:
            response_body_bytes_discarded = discard_response_body(error)
        except Exception:
            response_body_bytes_discarded = None
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
        "additional_request_header_names": summarize_additional_header_names(request),
        "expected_observation": request.expected_observation,
        "expected_interpretation": request.expected_interpretation,
        "expected_response": request.expected_response,
        "interpretation_limit": request.interpretation_limit,
        "started_at": started_at,
        "ended_at": ended_at,
        "status_code": status_code,
        "response_headers_count": response_headers_count,
        "response_body_bytes_discarded": response_body_bytes_discarded,
        "duration_ms": duration_ms,
        "error": error_message,
    }


def maybe_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run G-set R3 baseline / FP bait lab scenarios. "
            "Use only in approved local lab environments."
        ),
        epilog=(
            "The runner does not store request body content or response body "
            "content. --dry-run and --print-plan never send HTTP requests."
        ),
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Target base URL, e.g. http://192.168.56.105",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        choices=[
            "all",
            "head_health",
            "options_preflight",
            "get_browse",
            "monitoring_ua",
            "repeated_head",
            "repeated_head_monitoring",
        ],
        help="Scenario selection",
    )
    parser.add_argument("--out", required=True, help="Output directory for plan/log files")
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
    print(f"[g-r3] started_at={started_at}")
    print(f"[g-r3] mode={'dry-run' if dry_run else 'execute'} scenario={args.scenario}")
    print(f"[g-r3] request_count={len(requests)} target_class={target_class}")

    metadata = {
        "mode": "dry-run" if dry_run else "execute",
        "base_url": base_url,
        "scenario": args.scenario,
        "request_count": len(requests),
        "sleep_scale": args.sleep_scale,
        "timeout_sec": args.timeout_sec,
        "target_class": target_class,
        "allow_public_target": args.allow_public_target,
        "transport": "urllib.request",
        "supports_https": True,
        "stores_request_body_content": False,
        "stores_response_body_content": False,
        "started_at": started_at,
        "ended_at": None,
        "files": {
            "plan_json": str(output_dir / OUTPUT_PLAN_JSON),
            "plan_md": str(output_dir / OUTPUT_PLAN_MD),
            "metadata_json": str(output_dir / OUTPUT_METADATA_JSON),
        },
    }
    if not dry_run:
        metadata["files"]["results_jsonl"] = str(output_dir / OUTPUT_RESULTS_JSONL)
        metadata["files"]["summary_md"] = str(output_dir / OUTPUT_SUMMARY_MD)

    plan_payload = {
        "metadata": metadata,
        "requests": [
            render_plan_item(base_url, request, args.sleep_scale) for request in requests
        ],
    }

    write_json(output_dir / OUTPUT_PLAN_JSON, plan_payload)
    write_text(
        output_dir / OUTPUT_PLAN_MD,
        build_plan_markdown(
            base_url=base_url,
            selected_scenario=args.scenario,
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
        print("[g-r3] dry-run complete; no HTTP requests sent")
        print(f"[g-r3] ended_at={metadata['ended_at']}")
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
    print(f"[g-r3] execution complete; results={len(results)}")
    print(f"[g-r3] ended_at={metadata['ended_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
