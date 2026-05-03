#!/usr/bin/env python3
"""H-set R4 mixed benign + scanner-like runner.

Use only in approved local lab environments.
Do not execute against public external targets unless you explicitly opt in.

This runner is an experiment harness that records HTTP request metadata for
Apache-log-based mixed baseline/reference observation. It does not verify
actual crawler authenticity, static file existence, robots/sitemap content,
WordPress presence, sensitive file exposure, backup exposure, server-status
exposure, or attack success. Request body content and response body content are
not stored.
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
READ_CHUNK_SIZE = 8192
OUTPUT_PLAN_JSON = "execution_plan.json"
OUTPUT_PLAN_MD = "execution_plan.md"
OUTPUT_METADATA_JSON = "run_metadata.json"
OUTPUT_RESULTS_JSONL = "request_results.jsonl"
OUTPUT_SUMMARY_MD = "run_summary.md"

NORMAL_BROWSER_UA = "Mozilla/5.0 regression-browser"
GOOGLEBOT_LIKE_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
GENERIC_CRAWLER_UA = "GenericCrawler/1.0"
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


def scenario_mixed_basic() -> list[RequestSpec]:
    common_observation = [
        "normal browse/static baseline and scanner-like sensitive paths in same src_ip/time window",
    ]
    common_interpretation = [
        "baseline requests and scanner-like requests should be separated",
        "no file exposure or app presence inference",
    ]
    return [
        RequestSpec(
            scenario_id="H-R4-01",
            scenario_label="mixed_benign_scanner_basic",
            request_label="mixed_basic_root_request",
            method="GET",
            path="/",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_baseline_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-01",
            scenario_label="mixed_benign_scanner_basic",
            request_label="mixed_basic_app_js_request",
            method="GET",
            path="/assets/app.js",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_baseline_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-01",
            scenario_label="mixed_benign_scanner_basic",
            request_label="mixed_basic_favicon_request",
            method="GET",
            path="/favicon.ico",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_baseline_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-01",
            scenario_label="mixed_benign_scanner_basic",
            request_label="mixed_basic_env_probe_request",
            method="GET",
            path="/.env",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_baseline_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-01",
            scenario_label="mixed_benign_scanner_basic",
            request_label="mixed_basic_wp_login_probe_request",
            method="GET",
            path="/wp-login.php",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_baseline_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-01",
            scenario_label="mixed_benign_scanner_basic",
            request_label="mixed_basic_backup_probe_request",
            method="GET",
            path="/backup.zip",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_baseline_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-01",
            scenario_label="mixed_benign_scanner_basic",
            request_label="mixed_basic_robots_request",
            method="GET",
            path="/robots.txt",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_baseline_scanner_no_success_inference",
        ),
    ]


def scenario_benign_static_only() -> list[RequestSpec]:
    common_observation = [
        "normal/static baseline only",
    ]
    common_interpretation = [
        "should remain baseline/static context",
        "should not create scanner-like context",
    ]
    return [
        RequestSpec(
            scenario_id="H-R4-02",
            scenario_label="benign_static_only",
            request_label="benign_static_root_request",
            method="GET",
            path="/",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="static_baseline_no_attack_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-02",
            scenario_label="benign_static_only",
            request_label="benign_static_app_js_request",
            method="GET",
            path="/assets/app.js",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="static_baseline_no_attack_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-02",
            scenario_label="benign_static_only",
            request_label="benign_static_style_css_request",
            method="GET",
            path="/assets/style.css",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="static_baseline_no_attack_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-02",
            scenario_label="benign_static_only",
            request_label="benign_static_favicon_request",
            method="GET",
            path="/favicon.ico",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="static_baseline_no_attack_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-02",
            scenario_label="benign_static_only",
            request_label="benign_static_robots_request",
            method="GET",
            path="/robots.txt",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="static_baseline_no_attack_inference",
        ),
    ]


def scenario_scanner_only() -> list[RequestSpec]:
    common_observation = [
        "scanner-like sensitive paths only",
    ]
    common_interpretation = [
        "sensitive path probe context",
        "no file exposure, WordPress presence, server-status exposure inference",
    ]
    return [
        RequestSpec(
            scenario_id="H-R4-03",
            scenario_label="scanner_sensitive_only",
            request_label="scanner_only_env_probe_request",
            method="GET",
            path="/.env",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="sensitive_path_probe_no_file_or_app_exposure_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-03",
            scenario_label="scanner_sensitive_only",
            request_label="scanner_only_wp_login_probe_request",
            method="GET",
            path="/wp-login.php",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="sensitive_path_probe_no_file_or_app_exposure_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-03",
            scenario_label="scanner_sensitive_only",
            request_label="scanner_only_backup_probe_request",
            method="GET",
            path="/backup.zip",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="sensitive_path_probe_no_file_or_app_exposure_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-03",
            scenario_label="scanner_sensitive_only",
            request_label="scanner_only_server_status_probe_request",
            method="GET",
            path="/server-status",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="sensitive_path_probe_no_file_or_app_exposure_inference",
        ),
    ]


def scenario_mixed_with_crawler() -> list[RequestSpec]:
    common_observation = [
        "static/browse, crawler-like, scanner-like paths mixed",
    ]
    common_interpretation = [
        "crawler-like and scanner-like contexts should be separated",
        "actual crawler authenticity, page existence, file exposure must not be inferred",
    ]
    return [
        RequestSpec(
            scenario_id="H-R4-04",
            scenario_label="mixed_static_crawler_scanner",
            request_label="mixed_crawler_root_request",
            method="GET",
            path="/",
            user_agent=NORMAL_BROWSER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_crawler_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-04",
            scenario_label="mixed_static_crawler_scanner",
            request_label="mixed_crawler_robots_googlebot_request",
            method="GET",
            path="/robots.txt",
            user_agent=GOOGLEBOT_LIKE_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_crawler_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-04",
            scenario_label="mixed_static_crawler_scanner",
            request_label="mixed_crawler_sitemap_googlebot_request",
            method="GET",
            path="/sitemap.xml",
            user_agent=GOOGLEBOT_LIKE_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_crawler_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-04",
            scenario_label="mixed_static_crawler_scanner",
            request_label="mixed_crawler_products_generic_request",
            method="GET",
            path="/products/",
            user_agent=GENERIC_CRAWLER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_crawler_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-04",
            scenario_label="mixed_static_crawler_scanner",
            request_label="mixed_crawler_env_probe_request",
            method="GET",
            path="/.env",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_crawler_scanner_no_success_inference",
        ),
        RequestSpec(
            scenario_id="H-R4-04",
            scenario_label="mixed_static_crawler_scanner",
            request_label="mixed_crawler_backup_probe_request",
            method="GET",
            path="/backup.zip",
            user_agent=GENERIC_SCANNER_UA,
            expected_observation=common_observation,
            expected_interpretation=common_interpretation,
            expected_response="any",
            interpretation_limit="mixed_crawler_scanner_no_success_inference",
        ),
    ]


SCENARIO_BUILDERS = {
    "mixed_basic": scenario_mixed_basic,
    "benign_static_only": scenario_benign_static_only,
    "scanner_only": scenario_scanner_only,
    "mixed_with_crawler": scenario_mixed_with_crawler,
}


def get_selected_scenarios(selection: str) -> list[str]:
    if selection == "all":
        return [
            "mixed_basic",
            "benign_static_only",
            "scanner_only",
            "mixed_with_crawler",
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
        "# H Set R4 Execution Plan",
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
        "| # | scenario_id | runner label | request_label | method | path | user_agent | expected_response | scaled_sleep_after_sec |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for index, request in enumerate(requests, start=1):
        lines.append(
            f"| {index} | {request.scenario_id} | {request.scenario_label} | "
            f"{request.request_label} | {request.method} | {request.path} | "
            f"`{request.user_agent}` | {request.expected_response} | "
            f"{round((request.sleep_after_sec or 0.0) * sleep_scale, 3)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This runner is mixed baseline/scanner context harness only and does not verify crawler authenticity, static file existence, file exposure, app presence, or attack success.",
            "- Baseline/static/crawler-like requests and scanner-like sensitive-path requests should be separated when they appear in the same src_ip/time window.",
            "- Status code, response body byte count, response header count, and User-Agent alone are not sufficient to infer crawler authenticity, file disclosure, WordPress presence, backup exposure, or compromise.",
            "- Request body content and response body content are not written to disk.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_summary_markdown(
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    lines = [
        "# H Set R4 Run Summary",
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
            "- Results are mixed baseline/crawler/scanner context only.",
            "- No crawler authenticity inference, no static file existence inference, no WordPress presence inference, no file exposure inference, and no attack-success inference are allowed.",
            "- Mixed same-window requests should not be over-collapsed into one successful attack narrative.",
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
            "Run H-set R4 mixed benign + scanner-like lab scenarios. "
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
            "mixed_basic",
            "benign_static_only",
            "scanner_only",
            "mixed_with_crawler",
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
    print(f"[h-r4] started_at={started_at}")
    print(f"[h-r4] mode={'dry-run' if dry_run else 'execute'} scenario={args.scenario}")
    print(f"[h-r4] request_count={len(requests)} target_class={target_class}")

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
        print("[h-r4] dry-run complete; no HTTP requests sent")
        print(f"[h-r4] ended_at={metadata['ended_at']}")
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
    print(f"[h-r4] execution complete; results={len(results)}")
    print(f"[h-r4] ended_at={metadata['ended_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
