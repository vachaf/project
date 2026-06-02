#!/usr/bin/env python3
"""H-set R3 scanner-like low-signal path runner.

Use only in approved local lab environments.
Do not execute against public external targets unless you explicitly opt in.

This runner is an experiment harness that records HTTP request metadata for
Apache-log-based scanner-like path observation. It does not verify actual
WordPress presence, admin access, sensitive file exposure, phpinfo exposure,
server-status exposure, backup exposure, or attack success. Request body
content and response body content are not stored.
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
SENSITIVE_BURST_SLEEP_SEC = 2.0
READ_CHUNK_SIZE = 8192
OUTPUT_PLAN_JSON = "execution_plan.json"
OUTPUT_PLAN_MD = "execution_plan.md"
OUTPUT_METADATA_JSON = "run_metadata.json"
OUTPUT_RESULTS_JSONL = "request_results.jsonl"
OUTPUT_SUMMARY_MD = "run_summary.md"

GENERIC_SCANNER_UA = "GenericScanner/1.0"


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


def scenario_wp_login() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="H-R3-01",
            scenario_label="wp_login_probe",
            request_label="wp_login_probe_request",
            method="GET",
            path="/wp-login.php",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=[
                "common WordPress login path request",
                "status_code 관찰",
                "response_body_bytes 관찰",
            ],
            expected_interpretation=[
                "common scanner-like path context",
                "WordPress presence or vulnerability must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="scanner_path_context_no_app_presence_inference",
        )
    ]


def scenario_wp_admin() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="H-R3-02",
            scenario_label="wp_admin_probe",
            request_label="wp_admin_probe_request",
            method="GET",
            path="/wp-admin/",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=[
                "common WordPress admin path request",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "common scanner-like admin path context",
                "admin access success must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="scanner_path_context_no_admin_access_inference",
        )
    ]


def scenario_env_file() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="H-R3-03",
            scenario_label="env_file_probe",
            request_label="env_file_probe_request",
            method="GET",
            path="/.env",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=[
                "sensitive-looking config path request",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "sensitive config path probing possibility",
                ".env exposure must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="sensitive_path_context_no_file_exposure_inference",
        )
    ]


def scenario_phpinfo() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="H-R3-04",
            scenario_label="phpinfo_probe",
            request_label="phpinfo_probe_request",
            method="GET",
            path="/phpinfo.php",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=[
                "diagnostic phpinfo-like path request",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "diagnostic path probing possibility",
                "phpinfo exposure must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="sensitive_path_context_no_phpinfo_exposure_inference",
        )
    ]


def scenario_server_status() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="H-R3-05",
            scenario_label="server_status_probe",
            request_label="server_status_probe_request",
            method="GET",
            path="/server-status",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=[
                "Apache server-status-like path request",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "server-status probing possibility",
                "server-status exposure or access control success must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="sensitive_path_context_no_server_status_exposure_inference",
        )
    ]


def scenario_backup_zip() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="H-R3-06",
            scenario_label="backup_zip_probe",
            request_label="backup_zip_probe_request",
            method="GET",
            path="/backup.zip",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=[
                "backup artifact-looking path request",
                "status_code 관찰",
            ],
            expected_interpretation=[
                "backup artifact probing possibility",
                "backup file exposure must not be inferred",
            ],
            expected_response="any",
            interpretation_limit="sensitive_path_context_no_backup_exposure_inference",
        )
    ]


def scenario_sensitive_burst() -> list[RequestSpec]:
    common_observation = [
        "repeated sensitive-looking path sequence",
        "same src_ip/time window",
    ]
    common_interpretation = [
        "scanner-like sensitive path probing context",
        "no file exposure or compromise inference",
    ]
    return [
        RequestSpec(
            scenario_id="H-R3-07",
            scenario_label="sensitive_path_burst",
            request_label="sensitive_burst_env_request",
            method="GET",
            path="/.env",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="sensitive_path_burst_no_success_inference",
            sleep_after_sec=SENSITIVE_BURST_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="H-R3-07",
            scenario_label="sensitive_path_burst",
            request_label="sensitive_burst_server_status_request",
            method="GET",
            path="/server-status",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="sensitive_path_burst_no_success_inference",
            sleep_after_sec=SENSITIVE_BURST_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="H-R3-07",
            scenario_label="sensitive_path_burst",
            request_label="sensitive_burst_backup_zip_request",
            method="GET",
            path="/backup.zip",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="sensitive_path_burst_no_success_inference",
            sleep_after_sec=0.0,
        ),
    ]


SCENARIO_BUILDERS = {
    "wp_login": scenario_wp_login,
    "wp_admin": scenario_wp_admin,
    "env_file": scenario_env_file,
    "phpinfo": scenario_phpinfo,
    "server_status": scenario_server_status,
    "backup_zip": scenario_backup_zip,
    "sensitive_burst": scenario_sensitive_burst,
}


def get_selected_scenarios(selection: str) -> list[str]:
    if selection == "all":
        return [
            "wp_login",
            "wp_admin",
            "env_file",
            "phpinfo",
            "server_status",
            "backup_zip",
            "sensitive_burst",
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
        "# H Set R3 Execution Plan",
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
        "| # | scenario_id | runner label | request_label | method | path | expected_response | scaled_sleep_after_sec |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for index, request in enumerate(requests, start=1):
        lines.append(
            f"| {index} | {request.scenario_id} | {request.scenario_label} | "
            f"{request.request_label} | {request.method} | {request.path} | "
            f"{request.expected_response} | "
            f"{round((request.sleep_after_sec or 0.0) * sleep_scale, 3)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This runner is scanner-like path context harness only and does not verify WordPress presence, admin access, file exposure, phpinfo exposure, server-status exposure, backup exposure, or attack success.",
            "- Status code and response body byte count alone are not sufficient to infer file disclosure, access success, blocking success, application presence, or server compromise.",
            "- Even if `/.env`, `/phpinfo.php`, `/server-status`, or `/backup.zip` return `200`, exposure success must not be inferred.",
            "- Request body content and response body content are not written to disk.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_summary_markdown(
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    lines = [
        "# H Set R3 Run Summary",
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
            "- Results are scanner-like path context only.",
            "- No WordPress presence inference, no admin access inference, no sensitive file exposure inference, no phpinfo exposure inference, no server-status exposure inference, no backup exposure inference, and no compromise inference are allowed.",
            "- Status code and response body byte count alone are not sufficient evidence of exposure success or attack success.",
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
            "Run H-set R3 scanner-like low-signal path lab scenarios. "
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
            "wp_login",
            "wp_admin",
            "env_file",
            "phpinfo",
            "server_status",
            "backup_zip",
            "sensitive_burst",
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
    print(f"[h-r3] started_at={started_at}")
    print(f"[h-r3] mode={'dry-run' if dry_run else 'execute'} scenario={args.scenario}")
    print(f"[h-r3] request_count={len(requests)} target_class={target_class}")

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
        print("[h-r3] dry-run complete; no HTTP requests sent")
        print(f"[h-r3] ended_at={metadata['ended_at']}")
        return 0

    results_path = output_dir / OUTPUT_RESULTS_JSONL
    if results_path.exists():
        results_path.unlink()

    results: list[dict[str, Any]] = []
    for request in requests:
        result = execute_request(base_url, request, args.timeout_sec)
        append_jsonl(results_path, result)
        results.append(result)
        print(
            f"[{request.scenario_id}] {request.request_label} -> "
            f"status={result['status_code']} "
            f"headers={result['response_headers_count']} "
            f"body_bytes={result['response_body_bytes_discarded']} "
            f"duration_ms={result['duration_ms']} "
            f"error={result['error']}"
        )
        maybe_sleep((request.sleep_after_sec or 0.0) * args.sleep_scale)

    metadata["ended_at"] = now_local_iso()
    write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
    write_text(output_dir / OUTPUT_SUMMARY_MD, build_run_summary_markdown(metadata, results))
    print(f"[h-r3] execution complete; results={len(results)}")
    print(f"[h-r3] ended_at={metadata['ended_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
