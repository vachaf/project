#!/usr/bin/env python3
"""G-set R2 protocol anomaly runner.

Use only in approved local lab environments.
Do not execute against public external targets unless you explicitly opt in.

This runner is an experiment harness that records raw-socket HTTP request
metadata for Apache-log-based protocol / malformed-request observation. It does
not verify exploit success, bypass success, or intrusion success. Raw request
content, request body content, and response body content are not stored.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import sys
import time
import urllib.parse
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT_SEC = 10.0
DEFAULT_SLEEP_SCALE = 1.0
DEFAULT_INTER_REQUEST_SLEEP_SEC = 1.0
DEFAULT_LONG_PATH_TOKEN_LENGTH = 3072
MAX_RESPONSE_HEADER_BYTES = 65536
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
    raw_request_template_name: str
    method_token: str
    request_target: str
    request_target_summary: str
    protocol_version: str
    user_agent: str
    expected_observation: list[str]
    expected_interpretation: list[str]
    expected_response: str
    interpretation_limit: str
    host_header_mode: str
    literal_host_header: str | None = None
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
    if parsed.scheme != "http":
        if parsed.scheme == "https":
            raise SystemExit("https:// base URLs are not supported by this runner; use http://")
        raise SystemExit("--base-url must include an http:// scheme and host")
    if not parsed.netloc:
        raise SystemExit("--base-url must include an http:// scheme and host")
    if parsed.username or parsed.password:
        raise SystemExit("--base-url must not include username/password")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise SystemExit("--base-url must point to scheme://host[:port] without path/query")
    port = parsed.port
    host = parsed.hostname
    if not host:
        raise SystemExit("Could not parse hostname from --base-url")

    if ":" in host and not host.startswith("["):
        authority_host = f"[{host}]"
    else:
        authority_host = host
    authority = authority_host if port is None else f"{authority_host}:{port}"
    return f"http://{authority}"


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


def build_long_token(length: int) -> str:
    return "g" * length


def scenario_invalid_method() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R2-01",
            scenario_label="invalid_method_token",
            request_label="invalid_method_token_request",
            raw_request_template_name="invalid_method_token",
            method_token="FAKEMETHOD",
            request_target="/",
            request_target_summary="/",
            protocol_version="HTTP/1.1",
            user_agent="lab-g-set-r2-invalid-method",
            expected_observation=[
                "security/access/error 중 어디에 남는지 확인",
                "method가 FAKEMETHOD로 남는지 또는 parse failure로 남는지 확인",
            ],
            expected_interpretation=[
                "unsupported/invalid method probing possibility",
                "no exploit success inference",
            ],
            expected_response="400/405/501 등 가능",
            interpretation_limit="protocol_anomaly_context_only_no_success_inference",
            host_header_mode="target",
        )
    ]


def scenario_http10() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R2-02",
            scenario_label="http10_odd_request",
            request_label="http10_odd_request_request",
            raw_request_template_name="http10_odd_request",
            method_token="GET",
            request_target="/",
            request_target_summary="/",
            protocol_version="HTTP/1.0",
            user_agent="lab-g-set-r2-http10",
            expected_observation=[
                "protocol=HTTP/1.0으로 남는지 확인",
                "Host 없는 요청이 어떻게 기록되는지 확인",
            ],
            expected_interpretation=[
                "legacy protocol or probing-like context",
                "no vulnerability inference",
            ],
            expected_response="200/400/403 등 가능",
            interpretation_limit="protocol_surface_observation_only",
            host_header_mode="omit",
        )
    ]


def scenario_bad_protocol() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R2-03",
            scenario_label="bad_protocol_version",
            request_label="bad_protocol_version_request",
            raw_request_template_name="bad_protocol_version",
            method_token="GET",
            request_target="/",
            request_target_summary="/",
            protocol_version="HTTP/9.9",
            user_agent="lab-g-set-r2-bad-protocol",
            expected_observation=[
                "bad protocol version이 security/access/error 중 어디에 남는지 확인",
            ],
            expected_interpretation=[
                "protocol anomaly context",
                "no bypass or exploit success inference",
            ],
            expected_response="400/505/501 등 가능",
            interpretation_limit="protocol_anomaly_context_only_no_success_inference",
            host_header_mode="target",
        )
    ]


def scenario_missing_host() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R2-04",
            scenario_label="missing_host_http11",
            request_label="missing_host_http11_request",
            raw_request_template_name="missing_host_http11",
            method_token="GET",
            request_target="/",
            request_target_summary="/",
            protocol_version="HTTP/1.1",
            user_agent="lab-g-set-r2-missing-host",
            expected_observation=[
                "missing Host가 어떤 status/log surface로 남는지 확인",
            ],
            expected_interpretation=[
                "malformed HTTP/1.1 request-like context",
                "no exploit success inference",
            ],
            expected_response="400 등 가능",
            interpretation_limit="malformed_request_context_only",
            host_header_mode="omit",
        )
    ]


def scenario_odd_host() -> list[RequestSpec]:
    return [
        RequestSpec(
            scenario_id="G-R2-05",
            scenario_label="odd_host_header",
            request_label="odd_host_header_request",
            raw_request_template_name="odd_host_header",
            method_token="GET",
            request_target="/",
            request_target_summary="/",
            protocol_version="HTTP/1.1",
            user_agent="lab-g-set-r2-odd-host",
            expected_observation=[
                "odd Host header가 어떻게 기록되는지 확인",
            ],
            expected_interpretation=[
                "odd host/protocol surface observation",
                "no virtual-host bypass inference",
            ],
            expected_response="400/403/200 등 가능",
            interpretation_limit="host_header_anomaly_context_only",
            host_header_mode="literal",
            literal_host_header="invalid..host",
        )
    ]


def scenario_long_path() -> list[RequestSpec]:
    long_token = build_long_token(DEFAULT_LONG_PATH_TOKEN_LENGTH)
    return [
        RequestSpec(
            scenario_id="G-R2-06",
            scenario_label="long_path_probe",
            request_label="long_path_probe_request",
            raw_request_template_name="long_path_probe",
            method_token="GET",
            request_target=f"/g-probe/{long_token}",
            request_target_summary=(
                f"/g-probe/<long-token:{DEFAULT_LONG_PATH_TOKEN_LENGTH} chars>"
            ),
            protocol_version="HTTP/1.1",
            user_agent="lab-g-set-r2-long-path",
            expected_observation=[
                "long path가 정상 row로 남는지, 거절 status가 나는지 확인",
            ],
            expected_interpretation=[
                "malformed/long path probing-like context",
                "no exploit success inference",
            ],
            expected_response="200/400/414/404 등 가능",
            interpretation_limit="long_path_context_only_no_success_inference",
            host_header_mode="target",
        )
    ]


SCENARIO_BUILDERS = {
    "invalid_method": scenario_invalid_method,
    "http10": scenario_http10,
    "bad_protocol": scenario_bad_protocol,
    "missing_host": scenario_missing_host,
    "odd_host": scenario_odd_host,
    "long_path": scenario_long_path,
}


def get_selected_scenarios(selection: str) -> list[str]:
    if selection == "all":
        return [
            "invalid_method",
            "http10",
            "bad_protocol",
            "missing_host",
            "odd_host",
            "long_path",
        ]
    return [selection]


def add_inter_request_sleep(
    requests: list[RequestSpec],
    default_sleep_sec: float,
) -> list[RequestSpec]:
    spaced: list[RequestSpec] = []
    for index, request in enumerate(requests):
        sleep_after_sec = default_sleep_sec if index < len(requests) - 1 else 0.0
        spaced.append(replace(request, sleep_after_sec=sleep_after_sec))
    return spaced


def build_request_plan(selection: str) -> list[RequestSpec]:
    plan: list[RequestSpec] = []
    for scenario_name in get_selected_scenarios(selection):
        plan.extend(SCENARIO_BUILDERS[scenario_name]())
    return add_inter_request_sleep(plan, DEFAULT_INTER_REQUEST_SLEEP_SEC)


def resolve_target_host_header(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    hostname = parsed.hostname
    if not hostname:
        raise SystemExit("Could not parse hostname from --base-url")
    if ":" in hostname and not hostname.startswith("["):
        host_header = f"[{hostname}]"
    else:
        host_header = hostname
    if parsed.port and parsed.port != 80:
        return f"{host_header}:{parsed.port}"
    return host_header


def describe_host_header(request: RequestSpec, target_host_header: str) -> str | None:
    if request.host_header_mode == "omit":
        return None
    if request.host_header_mode == "literal":
        return request.literal_host_header
    return target_host_header


def render_plan_item(
    request: RequestSpec,
    sleep_scale: float,
    target_host_header: str,
) -> dict[str, Any]:
    host_header = describe_host_header(request, target_host_header)
    return {
        "scenario_id": request.scenario_id,
        "scenario_label": request.scenario_label,
        "request_label": request.request_label,
        "raw_request_template_name": request.raw_request_template_name,
        "request_line_preview": (
            f"{request.method_token} {request.request_target_summary} {request.protocol_version}"
        ),
        "host_header": host_header,
        "expected_observation": request.expected_observation,
        "expected_interpretation": request.expected_interpretation,
        "expected_response": request.expected_response,
        "interpretation_limit": request.interpretation_limit,
        "stores_raw_request_content": False,
        "stores_request_body_content": False,
        "stores_response_body_content": False,
        "sleep_after_sec": request.sleep_after_sec,
        "scaled_sleep_after_sec": round(request.sleep_after_sec * sleep_scale, 3),
    }


def build_plan_markdown(
    base_url: str,
    selected_scenario: str,
    sleep_scale: float,
    timeout_sec: float,
    requests: list[RequestSpec],
    dry_run: bool,
    target_class: str,
    target_host_header: str,
) -> str:
    lines = [
        "# G Set R2 Execution Plan",
        "",
        f"- mode: {'dry-run' if dry_run else 'execute'}",
        f"- base_url: {base_url}",
        f"- scenario: {selected_scenario}",
        f"- request_count: {len(requests)}",
        f"- sleep_scale: {sleep_scale}",
        f"- timeout_sec: {timeout_sec}",
        f"- target_class: {target_class}",
        "- transport: raw socket over plain HTTP only",
        "- safety: approved local lab only; public target execution is blocked by default",
        "- note: raw request content, request body content, and response body content are not stored",
        "",
        "## Requests",
        "",
        "| # | scenario_id | runner label | request_label | template | request_line_preview | host_header | expected_response | scaled_sleep_after_sec |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for index, request in enumerate(requests, start=1):
        host_header = describe_host_header(request, target_host_header) or "(omitted)"
        request_line_preview = (
            f"{request.method_token} {request.request_target_summary} {request.protocol_version}"
        )
        lines.append(
            f"| {index} | {request.scenario_id} | {request.scenario_label} | "
            f"{request.request_label} | {request.raw_request_template_name} | "
            f"{request_line_preview} | {host_header} | {request.expected_response} | "
            f"{round(request.sleep_after_sec * sleep_scale, 3)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This runner is for Apache log surface observation only and does not verify exploit, bypass, or intrusion success.",
            "- HTTP/1.1 missing Host and odd Host cases are malformed-request context only.",
            "- 400/408/501/505 class outcomes are protocol anomaly context only.",
            "- Raw request content and response body content are not written to disk.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_summary_markdown(
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    lines = [
        "# G Set R2 Run Summary",
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
        "- transport: raw socket over plain HTTP only",
        "- note: raw request content, request body content, and response body content are not stored",
        "",
        "## Results",
        "",
        "| scenario_id | request_label | connected | status_line | parsed_status_code | response_header_bytes | response_body_bytes_discarded | duration_ms | error |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in results:
        status_line = item["status_line"] or ""
        error = item["error"] or ""
        lines.append(
            f"| {item['scenario_id']} | {item['request_label']} | {item['connected']} | "
            f"{status_line} | {item['parsed_status_code']} | {item['response_header_bytes']} | "
            f"{item['response_body_bytes_discarded']} | {item['duration_ms']} | {error} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- Observations are limited to request parsing, status code, protocol, method, and error linkage at Apache log surface level.",
            "- No malformed request success inference, no intrusion success inference, and no bypass success inference are allowed.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_status_code(status_line: str | None) -> int | None:
    if not status_line:
        return None
    parts = status_line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


def extract_status_line(header_bytes: bytes) -> str | None:
    if not header_bytes:
        return None
    if b"\r\n" in header_bytes:
        first_line = header_bytes.split(b"\r\n", 1)[0]
    else:
        first_line = header_bytes
    if not first_line:
        return None
    return first_line.decode("iso-8859-1", errors="replace")


def build_raw_request_bytes(
    request: RequestSpec,
    target_host_header: str,
) -> bytes:
    lines = [f"{request.method_token} {request.request_target} {request.protocol_version}"]
    host_header = describe_host_header(request, target_host_header)
    if host_header is not None:
        lines.append(f"Host: {host_header}")
    lines.append(f"User-Agent: {request.user_agent}")
    lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


def read_response_metadata(sock: socket.socket) -> tuple[str | None, int, int]:
    header_buffer = bytearray()
    status_line: str | None = None
    response_header_bytes = 0
    response_body_bytes_discarded = 0
    header_complete = False

    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break

        if not header_complete:
            header_buffer.extend(chunk)
            separator_index = header_buffer.find(b"\r\n\r\n")
            if separator_index != -1:
                response_header_bytes = separator_index + 4
                header_complete = True
                header_bytes = bytes(header_buffer[:response_header_bytes])
                status_line = extract_status_line(header_bytes)
                response_body_bytes_discarded += len(header_buffer) - response_header_bytes
                header_buffer.clear()
                continue
            if len(header_buffer) > MAX_RESPONSE_HEADER_BYTES:
                raise ValueError("Response headers exceeded limit before header terminator")
            continue

        response_body_bytes_discarded += len(chunk)

    if not header_complete:
        header_bytes = bytes(header_buffer)
        response_header_bytes = len(header_bytes)
        status_line = extract_status_line(header_bytes)

    return status_line, response_header_bytes, response_body_bytes_discarded


def execute_request(
    base_url: str,
    request: RequestSpec,
    timeout_sec: float,
    target_host_header: str,
) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or 80
    if not host:
        raise SystemExit("Could not parse hostname from --base-url")

    started_at = now_local_iso()
    started_perf = time.perf_counter()
    connected = False
    status_line: str | None = None
    parsed_status_code: int | None = None
    response_header_bytes = 0
    response_body_bytes_discarded = 0
    error_message: str | None = None

    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            connected = True
            sock.settimeout(timeout_sec)
            raw_request = build_raw_request_bytes(request, target_host_header)
            sock.sendall(raw_request)
            status_line, response_header_bytes, response_body_bytes_discarded = (
                read_response_metadata(sock)
            )
            parsed_status_code = parse_status_code(status_line)
    except socket.timeout as error:
        error_message = f"timeout: {error}"
    except OSError as error:
        error_message = f"{error.__class__.__name__}: {error}"
    except ValueError as error:
        error_message = f"ValueError: {error}"
    except Exception as error:  # pragma: no cover - defensive logging path
        error_message = f"{error.__class__.__name__}: {error}"

    ended_at = now_local_iso()
    duration_ms = round((time.perf_counter() - started_perf) * 1000, 2)

    return {
        "scenario_id": request.scenario_id,
        "scenario_label": request.scenario_label,
        "request_label": request.request_label,
        "raw_request_template_name": request.raw_request_template_name,
        "expected_observation": request.expected_observation,
        "expected_interpretation": request.expected_interpretation,
        "expected_response": request.expected_response,
        "interpretation_limit": request.interpretation_limit,
        "started_at": started_at,
        "ended_at": ended_at,
        "connected": connected,
        "status_line": status_line,
        "parsed_status_code": parsed_status_code,
        "response_header_bytes": response_header_bytes,
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
            "Run G-set R2 protocol / malformed-request observation scenarios "
            "with raw HTTP sockets. Use only in approved local lab environments."
        ),
        epilog=(
            "The runner does not store raw request content, request body content, "
            "or response body content. --dry-run and --print-plan never send "
            "socket requests."
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
            "invalid_method",
            "http10",
            "bad_protocol",
            "missing_host",
            "odd_host",
            "long_path",
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
    target_host_header = resolve_target_host_header(base_url)

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    requests = build_request_plan(args.scenario)
    started_at = now_local_iso()
    print(f"[g-r2] started_at={started_at}")
    print(f"[g-r2] mode={'dry-run' if dry_run else 'execute'} scenario={args.scenario}")
    print(f"[g-r2] request_count={len(requests)} target_class={target_class}")

    metadata = {
        "mode": "dry-run" if dry_run else "execute",
        "base_url": base_url,
        "scenario": args.scenario,
        "request_count": len(requests),
        "sleep_scale": args.sleep_scale,
        "timeout_sec": args.timeout_sec,
        "target_class": target_class,
        "allow_public_target": args.allow_public_target,
        "transport": "raw-http-socket",
        "supports_https": False,
        "stores_raw_request_content": False,
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
            render_plan_item(request, args.sleep_scale, target_host_header)
            for request in requests
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
            target_host_header=target_host_header,
        ),
    )

    if dry_run:
        metadata["ended_at"] = now_local_iso()
        write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
        print("[g-r2] dry-run complete; no socket requests sent")
        print(f"[g-r2] ended_at={metadata['ended_at']}")
        return 0

    results_path = output_dir / OUTPUT_RESULTS_JSONL
    results: list[dict[str, Any]] = []
    for request in requests:
        result = execute_request(base_url, request, args.timeout_sec, target_host_header)
        append_jsonl(results_path, result)
        results.append(result)
        scaled_sleep = request.sleep_after_sec * args.sleep_scale
        maybe_sleep(scaled_sleep)

    metadata["ended_at"] = now_local_iso()
    write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
    write_text(output_dir / OUTPUT_SUMMARY_MD, build_run_summary_markdown(metadata, results))
    print(f"[g-r2] execution complete; results={len(results)}")
    print(f"[g-r2] ended_at={metadata['ended_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
