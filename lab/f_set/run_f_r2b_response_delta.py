#!/usr/bin/env python3
"""F-set R2B response-delta runner.

Use only in approved local lab environments.
Do not execute against public external targets unless you explicitly opt in.

This runner is an experiment harness that records HTTP requests and execution
metadata for Apache-log response-surface observation. It is limited to response
surface comparison and response delta observation only. No account existence
inference, no lockout confirmation, and no auth success inference should be
derived from it. POST bodies are execution-only inputs for scenario
construction and are not assumed to be visible in the downstream Apache-log-
based analysis pipeline.
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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT_SEC = 10.0
DEFAULT_SLEEP_SCALE = 1.0
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
    expected_response: int
    interpretation_limit: str
    body: dict[str, Any] | None = None
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
            "approved lab environment.",
            file=sys.stderr,
        )
        return target_class

    raise SystemExit(
        "Refusing to execute against a public IP or general hostname target. "
        "Use an approved local lab environment, run with --dry-run/--print-plan, "
        "or explicitly pass --allow-public-target."
    )


def build_login_body(email: str, password: str) -> dict[str, str]:
    return {"email": email, "password": password}


def scenario_existing_accounts() -> list[RequestSpec]:
    targets = [
        ("admin", "admin@juice-sh.op"),
        ("user1", "user1@juice-sh.op"),
        ("jim", "jim@juice-sh.op"),
    ]
    requests = []
    for index, (name, email) in enumerate(targets, start=1):
        requests.append(
            RequestSpec(
                scenario_id="F-R2B-01",
                scenario_label="existing_account_failures_x3",
                request_label=f"existing_account_failure_{index}_{name}",
                method="POST",
                path="/rest/user/login",
                user_agent=f"lab-f-set-r2-enum-exist-{name}",
                expected_observation=(
                    "POST auth endpoint failures for accounts intended by runner "
                    "as existing; compare status_code / response_body_bytes / "
                    "duration_us / ttfb_us with nonexistent account group"
                ),
                expected_interpretation=(
                    "response surface comparison only; user-enumeration-like "
                    "probing possibility; no account existence inference"
                ),
                expected_response=401,
                interpretation_limit=(
                    "post_body_not_visible_no_account_existence_inference"
                ),
                body=build_login_body(email, "wrongpass"),
                sleep_after_sec=1.0 if index < len(targets) else 0.0,
            )
        )
    return requests


def scenario_nonexistent_accounts() -> list[RequestSpec]:
    targets = [
        "notexist1@example.invalid",
        "notexist2@example.invalid",
        "notexist3@example.invalid",
    ]
    requests = []
    for index, email in enumerate(targets, start=1):
        requests.append(
            RequestSpec(
                scenario_id="F-R2B-02",
                scenario_label="nonexistent_account_failures_x3",
                request_label=f"nonexistent_account_failure_{index}",
                method="POST",
                path="/rest/user/login",
                user_agent=f"lab-f-set-r2-enum-notexist-{index}",
                expected_observation=(
                    "POST auth endpoint failures for accounts intended by runner "
                    "as nonexistent; compare status_code / response_body_bytes / "
                    "duration_us / ttfb_us with existing account group"
                ),
                expected_interpretation=(
                    "response surface comparison only; user-enumeration-like "
                    "probing possibility; no account existence inference"
                ),
                expected_response=401,
                interpretation_limit=(
                    "post_body_not_visible_no_account_existence_inference"
                ),
                body=build_login_body(email, "wrongpass"),
                sleep_after_sec=1.0 if index < len(targets) else 0.0,
            )
        )
    return requests


def scenario_lockout_probe() -> list[RequestSpec]:
    requests = []
    for index in range(1, 6):
        requests.append(
            RequestSpec(
                scenario_id="F-R2B-03",
                scenario_label="lockout_probe_like_401_x5",
                request_label=f"lockout_probe_failure_{index}",
                method="POST",
                path="/rest/user/login",
                user_agent=f"lab-f-set-r2-lockout-probe-{index}",
                expected_observation=(
                    "repeated auth failures; observe whether status_code / "
                    "response_body_bytes / duration_us / ttfb_us changes across "
                    "attempts"
                ),
                expected_interpretation=(
                    "lockout-probing-like sequence possibility only; response "
                    "delta observation; no lockout confirmation; no auth success "
                    "inference"
                ),
                expected_response=401,
                interpretation_limit=(
                    "post_body_not_visible_no_lockout_confirmation"
                ),
                body=build_login_body("admin@juice-sh.op", "wrongpass"),
                sleep_after_sec=3.0 if index < 5 else 0.0,
            )
        )
    return requests


SCENARIO_BUILDERS = {
    "existing_accounts": scenario_existing_accounts,
    "nonexistent_accounts": scenario_nonexistent_accounts,
    "lockout_probe": scenario_lockout_probe,
}


def get_selected_scenarios(selection: str) -> list[str]:
    if selection == "all":
        return [
            "existing_accounts",
            "nonexistent_accounts",
            "lockout_probe",
        ]
    return [selection]


def build_request_plan(selection: str) -> list[RequestSpec]:
    plan: list[RequestSpec] = []
    for scenario_name in get_selected_scenarios(selection):
        plan.extend(SCENARIO_BUILDERS[scenario_name]())
    return plan


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
        "has_execution_body": request.body is not None,
        "execution_body_note": (
            "execution-only JSON body; not visible in Apache-log-based analysis"
            if request.body is not None
            else None
        ),
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
) -> str:
    lines = [
        "# F Set R2B Execution Plan",
        "",
        f"- mode: {'dry-run' if dry_run else 'execute'}",
        f"- base_url: {base_url}",
        f"- scenario: {selected_scenario}",
        f"- request_count: {len(requests)}",
        f"- sleep_scale: {sleep_scale}",
        f"- timeout_sec: {timeout_sec}",
        f"- target_class: {target_class}",
        "- safety: approved local lab only; do not execute against public external targets by default",
        "- note: POST body values are execution-only inputs and are not visible to the Apache-log-based analysis pipeline",
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
            f"{round(request.sleep_after_sec * sleep_scale, 3)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- This runner is for response surface comparison and response delta observation only.",
            "- No account existence inference, no lockout confirmation, no auth success inference, and no attack outcome confirmation from runner input values.",
            "- Apache-log-based analysis does not see POST body contents from this runner.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_summary_markdown(
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    lines = [
        "# F Set R2B Run Summary",
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
        "- safety: approved local lab only; do not execute against public external targets by default",
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
            "- Results are limited to response surface comparison and response delta observation.",
            "- No account existence inference, no lockout confirmation, and no auth success inference.",
            "- Apache-log-based analysis does not see POST body contents from this runner.",
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
    data = None
    if request.body is not None:
        data = json.dumps(request.body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    urllib_request = urllib.request.Request(
        url=url,
        method=request.method,
        headers=headers,
        data=data,
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
            "Run F-set R2B response-delta lab scenarios. "
            "Use only in approved local lab environments."
        ),
        epilog=(
            "Do not execute against public external targets by default. "
            "--dry-run and --print-plan never send HTTP requests."
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
            "existing_accounts",
            "nonexistent_accounts",
            "lockout_probe",
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
        help="Scale scenario sleep durations, e.g. 0.1",
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
    write_json(output_dir / OUTPUT_METADATA_JSON, metadata)

    print(f"Started at: {started_at}")
    print(f"Mode: {'dry-run' if dry_run else 'execute'}")
    print(f"Base URL: {base_url}")
    print(f"Scenario: {args.scenario}")
    print(f"Request count: {len(requests)}")
    print(f"Target class: {target_class}")
    print("Safety: approved local lab only; do not execute against public external targets by default.")

    if dry_run:
        ended_at = now_local_iso()
        metadata["ended_at"] = ended_at
        write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
        print("Dry-run mode: no HTTP requests were sent.")
        print(f"Ended at: {ended_at}")
        print(f"Plan JSON: {output_dir / OUTPUT_PLAN_JSON}")
        print(f"Plan Markdown: {output_dir / OUTPUT_PLAN_MD}")
        print(f"Metadata JSON: {output_dir / OUTPUT_METADATA_JSON}")
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
            f"bytes={result['response_body_bytes']} "
            f"duration_ms={result['duration_ms']} "
            f"error={result['error']}"
        )
        scaled_sleep = request.sleep_after_sec * args.sleep_scale
        if scaled_sleep > 0:
            maybe_sleep(scaled_sleep)

    ended_at = now_local_iso()
    metadata["ended_at"] = ended_at
    write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
    write_text(
        output_dir / OUTPUT_SUMMARY_MD,
        build_run_summary_markdown(metadata, results),
    )

    print(f"Ended at: {ended_at}")
    print(f"Results JSONL: {results_path}")
    print(f"Summary Markdown: {output_dir / OUTPUT_SUMMARY_MD}")
    print(f"Metadata JSON: {output_dir / OUTPUT_METADATA_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
