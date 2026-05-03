#!/usr/bin/env python3
"""G-set R1 HTTP method probing runner.

Use only in approved local lab environments.
Do not execute against public external targets unless you explicitly opt in.

This runner is an experiment harness that records HTTP requests and execution
metadata for Apache-log-based method probing experiments. It does not verify
method allowance, file upload success, resource deletion success, XST success,
or CORS/method exposure success. Response body content and request body content
are not stored.
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
OUTPUT_PLAN_JSON = "execution_plan.json"
OUTPUT_PLAN_MD = "execution_plan.md"
OUTPUT_METADATA_JSON = "run_metadata.json"
OUTPUT_RESULTS_JSONL = "request_results.jsonl"
OUTPUT_SUMMARY_MD = "run_summary.md"
PUT_DUMMY_BODY = b"g-probe"


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
    request_body_bytes: int = 0
    body: bytes | None = None
    content_type: str | None = None
    sleep_after_sec: float = 0.0


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
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("--base-url must include http/https scheme and host")
    return raw_base_url.rstrip("/")


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


def scenario_options() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R1-01",
            scenario_label="options_root",
            request_label="options_root_request",
            method="OPTIONS",
            path="/",
            user_agent="lab-g-set-r1-options",
            expected_observation=[
                "method=OPTIONS",
                "status_code 관찰",
                "response_body_bytes 관찰",
            ],
            expected_interpretation=[
                "method discovery/probing possibility",
                "CORS/method exposure success must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="no_cors_or_method_exposure_success_inference",
        )
    ]


def scenario_trace() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R1-02",
            scenario_label="trace_root",
            request_label="trace_root_request",
            method="TRACE",
            path="/",
            user_agent="lab-g-set-r1-trace",
            expected_observation=[
                "method=TRACE",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "TRACE method exposure probing possibility",
                "XST success must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="no_xst_success_inference_without_response_body",
        )
    ]


def scenario_put() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R1-03",
            scenario_label="put_probe",
            request_label="put_probe_request",
            method="PUT",
            path="/upload/g_probe.txt",
            user_agent="lab-g-set-r1-put",
            expected_observation=[
                "method=PUT",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "upload/write method probing possibility",
                "file upload/write success must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="no_file_write_success_inference",
            request_body_bytes=len(PUT_DUMMY_BODY),
            body=PUT_DUMMY_BODY,
            content_type="text/plain",
        )
    ]


def scenario_delete() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R1-04",
            scenario_label="delete_probe",
            request_label="delete_probe_request",
            method="DELETE",
            path="/api/resource/g_probe",
            user_agent="lab-g-set-r1-delete",
            expected_observation=[
                "method=DELETE",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "destructive method probing possibility",
                "resource deletion success must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="no_resource_delete_success_inference",
        )
    ]


def scenario_head() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R1-05",
            scenario_label="head_root",
            request_label="head_root_request",
            method="HEAD",
            path="/",
            user_agent="lab-g-set-r1-head",
            expected_observation=[
                "method=HEAD",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "normal baseline possibility",
                "should not be promoted as attack by method alone",
            ],
            expected_response="any",
            interpretation_limit="baseline_head_no_attack_inference",
        )
    ]


def scenario_get() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R1-06",
            scenario_label="get_root",
            request_label="get_root_request",
            method="GET",
            path="/",
            user_agent="lab-g-set-r1-get",
            expected_observation=[
                "method=GET",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "normal baseline",
                "should not be promoted as method probing",
            ],
            expected_response="any",
            interpretation_limit="baseline_get_no_attack_inference",
        )
    ]


SCENARIO_BUILDERS = {
    "options": scenario_options,
    "trace": scenario_trace,
    "put": scenario_put,
    "delete": scenario_delete,
    "head": scenario_head,
    "get": scenario_get,
}


def get_selected_scenarios(selection: str) -> list[str]:
    if selection == "all":
        return ["options", "trace", "put", "delete", "head", "get"]
    return [selection]


def build_request_plan(selection: str) -> list[RequestSpec]:
    plan: list[RequestSpec] = []
    for scenario_name in get_selected_scenarios(selection):
        plan.extend(SCENARIO_BUILDERS[scenario_name]())
    return add_inter_request_sleep(plan, DEFAULT_INTER_REQUEST_SLEEP_SEC)


def add_inter_request_sleep(
    requests: list[RequestSpec],
    default_sleep_sec: float,
) -> list[RequestSpec]:
    spaced: list[RequestSpec] = []
    for index, request in enumerate(requests):
        sleep_after_sec = default_sleep_sec if index < len(requests) - 1 else 0.0
        spaced.append(replace(request, sleep_after_sec=sleep_after_sec))
    return spaced


def build_full_url(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


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
        "expected_observation": request.expected_observation,
        "expected_interpretation": request.expected_interpretation,
        "expected_response": request.expected_response,
        "interpretation_limit": request.interpretation_limit,
        "request_body_bytes": request.request_body_bytes,
        "stores_request_body_content": False,
        "stores_response_body_content": False,
        "sleep_after_sec": request.sleep_after_sec,
        "scaled_sleep_after_sec": round(request.sleep_after_sec * sleep_scale, 3),
    }


def format_list(items: list[str]) -> str:
    return "; ".join(items)


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
        "# G Set R1 Execution Plan",
        "",
        f"- mode: {'dry-run' if dry_run else 'execute'}",
        f"- base_url: {base_url}",
        f"- scenario: {selected_scenario}",
        f"- request_count: {len(requests)}",
        f"- sleep_scale: {sleep_scale}",
        f"- timeout_sec: {timeout_sec}",
        f"- target_class: {target_class}",
        "- safety: approved local lab only; public target execution is blocked by default",
        "- note: request body content and response body content are not stored",
        "",
        "## Requests",
        "",
        "| # | scenario_id | runner label | request_label | method | path | expected_response | request_body_bytes | scaled_sleep_after_sec |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for index, request in enumerate(requests, start=1):
        lines.append(
            f"| {index} | {request.scenario_id} | {request.scenario_label} | "
            f"{request.request_label} | {request.method} | {request.path} | "
            f"{request.expected_response} | {request.request_body_bytes} | "
            f"{round(request.sleep_after_sec * sleep_scale, 3)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This runner records HTTP request metadata only and does not verify method allowance or exploit success.",
            "- TRACE response bodies are not stored or printed.",
            "- PUT request bodies are execution-only dummy bytes and only body length is recorded.",
            "- DELETE targets a test path only and does not verify resource deletion.",
            "- HEAD and GET are baseline references and should not be promoted by method alone.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_summary_markdown(
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    lines = [
        "# G Set R1 Run Summary",
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
        "- safety: approved local lab only; public target execution is blocked by default",
        "- note: request body content and response body content are not stored",
        "",
        "## Results",
        "",
        "| request_label | method | path | status_code | response_body_bytes | duration_ms | error |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['request_label']} | {item['method']} | {item['path']} | "
            f"{item['status_code']} | {item['response_body_bytes']} | "
            f"{item['duration_ms']} | {item.get('error') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- OPTIONS/TRACE/PUT/DELETE observations are possibility-level method probing context only.",
            "- No method allowance inference, no file write success inference, no resource deletion success inference, no XST success inference, and no CORS success inference.",
            "- TRACE response bodies and request body contents are not stored.",
        ]
    )
    return "\n".join(lines) + "\n"


def execute_request(
    base_url: str,
    request: RequestSpec,
    timeout_sec: float,
) -> dict[str, Any]:
    started_at = now_local_iso()
    started_perf = time.perf_counter()
    url = build_full_url(base_url, request.path)
    headers = {"User-Agent": request.user_agent}
    if request.content_type:
        headers["Content-Type"] = request.content_type

    urllib_request = urllib.request.Request(
        url=url,
        method=request.method,
        headers=headers,
        data=request.body,
    )

    status_code = None
    response_body_bytes = None
    error_message = None

    try:
        with urllib.request.urlopen(urllib_request, timeout=timeout_sec) as response:
            response_body_bytes = len(response.read())
            status_code = response.getcode()
    except urllib.error.HTTPError as error:
        status_code = error.code
        try:
            response_body_bytes = len(error.read())
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
        "request_body_bytes": request.request_body_bytes,
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
            "Run G-set R1 HTTP method probing lab scenarios. "
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
        choices=["all", "options", "trace", "put", "delete", "head", "get"],
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
    print(f"[g-r1] started_at={started_at}")
    print(f"[g-r1] mode={'dry-run' if dry_run else 'execute'} scenario={args.scenario}")
    print(f"[g-r1] request_count={len(requests)} target_class={target_class}")

    metadata = {
        "mode": "dry-run" if dry_run else "execute",
        "base_url": base_url,
        "scenario": args.scenario,
        "request_count": len(requests),
        "sleep_scale": args.sleep_scale,
        "timeout_sec": args.timeout_sec,
        "target_class": target_class,
        "allow_public_target": args.allow_public_target,
        "started_at": started_at,
        "ended_at": None,
        "stores_request_body_content": False,
        "stores_response_body_content": False,
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
        print("[g-r1] dry-run complete; no HTTP requests sent")
        print(f"[g-r1] ended_at={metadata['ended_at']}")
        return 0

    results_path = output_dir / OUTPUT_RESULTS_JSONL
    results: list[dict[str, Any]] = []
    for request in requests:
        result = execute_request(base_url, request, args.timeout_sec)
        append_jsonl(results_path, result)
        results.append(result)
        scaled_sleep = request.sleep_after_sec * args.sleep_scale
        maybe_sleep(scaled_sleep)

    metadata["ended_at"] = now_local_iso()
    write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
    write_text(output_dir / OUTPUT_SUMMARY_MD, build_run_summary_markdown(metadata, results))
    print(f"[g-r1] execution complete; results={len(results)}")
    print(f"[g-r1] ended_at={metadata['ended_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
