#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import prepare_llm_input as prepare  # noqa: E402


FOCUS_CHOICES = ("all", "auth", "search", "file", "l3")
SEARCH_URI_HINTS = tuple(getattr(prepare, "QUERY_HEAVY_URI_HINTS", ("/search", "/query", "/filter")))
FILE_PATH_HINTS = ("config.php", "admin/config.php", ".env", "php://filter", "resource=")
L3_HINT_PREFIXES = ("log4shell:", "ssrf:", "ssti:", "webshell:", "l3:")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize prepare_llm_input.py outputs for quick human review"
    )
    parser.add_argument("--llm-input", help="Path to <base>_llm_input.json")
    parser.add_argument("--filtered-out", help="Path to <base>_filtered_out_rows.json")
    parser.add_argument("--noise-summary", help="Path to <base>_noise_summary.json")
    parser.add_argument("--processed-dir", help="Directory containing processed prepare outputs")
    parser.add_argument("--base-name", help="Base name for processed-dir resolution")
    parser.add_argument("--focus", choices=FOCUS_CHOICES, default="all")
    parser.add_argument("--limit", type=int, default=30, help="Top N / preview row limit")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON summary")
    parser.add_argument("--show-rows", dest="show_rows", action="store_true", help="Show row previews")
    parser.add_argument("--no-rows", dest="show_rows", action="store_false", help="Skip row previews")
    parser.set_defaults(show_rows=True)
    return parser.parse_args()


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def fail(message: str) -> int:
    eprint(f"[FAIL] {message}")
    return 1


def warn(message: str, warnings: List[str]) -> None:
    warnings.append(message)
    eprint(f"[WARN] {message}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def clip(value: Any, limit: int = 120) -> str:
    text = normalize_str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def unwrap_optional_collection(payload: Any, wrapper_key: str) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        rows = payload.get(wrapper_key)
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    return []


def resolve_paths(args: argparse.Namespace) -> Dict[str, Optional[Path]]:
    if args.processed_dir:
        if not args.base_name:
            raise ValueError("--base-name is required with --processed-dir")
        processed_dir = Path(args.processed_dir).resolve()
        base_name = args.base_name
        return {
            "llm_input": processed_dir / f"{base_name}_llm_input.json",
            "filtered_out": processed_dir / f"{base_name}_filtered_out_rows.json",
            "noise_summary": processed_dir / f"{base_name}_noise_summary.json",
        }

    if not args.llm_input:
        raise ValueError("either --llm-input or --processed-dir/--base-name must be provided")

    return {
        "llm_input": Path(args.llm_input).resolve(),
        "filtered_out": Path(args.filtered_out).resolve() if args.filtered_out else None,
        "noise_summary": Path(args.noise_summary).resolve() if args.noise_summary else None,
    }


def value_counter(rows: Sequence[Dict[str, Any]], field: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        text = normalize_str(row.get(field)) or "(empty)"
        counter[text] += 1
    return counter


def hint_counter(rows: Sequence[Dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        for hint in ensure_list(row.get("reason_hints")):
            text = normalize_str(hint)
            if text:
                counter[text] += 1
    return counter


def top_counter(counter: Counter[str], limit: int) -> List[Dict[str, Any]]:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [{"value": value, "count": count} for value, count in items[:limit]]


def get_row_identifier(row: Dict[str, Any]) -> str:
    for key in ("request_id", "id", "log_id"):
        value = normalize_str(row.get(key))
        if value:
            return value
    return "(missing)"


def row_label_fields(row: Dict[str, Any]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for key in ("category", "verdict_hint", "supporting_role", "supporting_reason", "noise_category", "context_role", "interpretation_limit"):
        value = normalize_str(row.get(key))
        if value:
            labels[key] = value
    return labels


def build_row_preview(row: Dict[str, Any], row_source: str) -> Dict[str, Any]:
    return {
        "row_source": row_source,
        "row_id": get_row_identifier(row),
        "method": normalize_str(row.get("method")),
        "uri": normalize_str(row.get("uri")),
        "status_code": normalize_str(row.get("status_code")),
        "response_body_bytes": row.get("response_body_bytes"),
        "duration_us": row.get("duration_us"),
        "ttfb_us": row.get("ttfb_us"),
        "user_agent": normalize_str(row.get("user_agent")),
        "labels": row_label_fields(row),
        "reason_hints": [normalize_str(hint) for hint in ensure_list(row.get("reason_hints")) if normalize_str(hint)],
    }


def format_row_preview(preview: Dict[str, Any]) -> str:
    labels = preview.get("labels") or {}
    label_text = ", ".join(f"{key}={clip(value, 80)}" for key, value in labels.items()) or "-"
    reason_text = ", ".join(clip(item, 80) for item in preview.get("reason_hints") or []) or "-"
    return (
        f"[{preview['row_source']}] id={clip(preview['row_id'], 64)} method={clip(preview['method'], 16) or '-'} "
        f"uri={clip(preview['uri'], 120) or '-'} status={clip(preview['status_code'], 16) or '-'} "
        f"bytes={preview.get('response_body_bytes')} duration_us={preview.get('duration_us')} "
        f"ttfb_us={preview.get('ttfb_us')} ua={clip(preview.get('user_agent'), 80) or '-'} "
        f"labels={label_text} reason_hints={reason_text}"
    )


def summarize_row_collection(
    rows: Sequence[Dict[str, Any]],
    *,
    row_source: str,
    category_field: str,
    extra_fields: Sequence[str],
    limit: int,
    show_rows: bool,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "count": len(rows),
        "status_code_distribution": top_counter(value_counter(rows, "status_code"), limit),
        "reason_hints_top": top_counter(hint_counter(rows), limit),
    }
    for field in extra_fields:
        summary[f"{field}_top"] = top_counter(value_counter(rows, field), limit)
    if category_field:
        summary[f"{category_field}_distribution"] = top_counter(value_counter(rows, category_field), limit)
    summary["row_previews"] = (
        [build_row_preview(row, row_source=row_source) for row in rows[:limit]]
        if show_rows
        else []
    )
    return summary


def summarize_noise_aggregates(rows: Sequence[Dict[str, Any]], limit: int) -> Dict[str, Any]:
    category_counter = value_counter(rows, "category")
    uri_counter = value_counter(rows, "uri")
    status_counter = value_counter(rows, "status_code")
    aggregate_previews = []
    for row in rows[:limit]:
        aggregate_previews.append(
            {
                "category": normalize_str(row.get("category")),
                "method": normalize_str(row.get("method")),
                "uri": normalize_str(row.get("uri")),
                "status_code": normalize_str(row.get("status_code")),
                "count": row.get("count"),
                "user_agent": normalize_str(row.get("user_agent")),
                "note": normalize_str(row.get("note")),
            }
        )
    return {
        "count": len(rows),
        "category_distribution": top_counter(category_counter, limit),
        "status_code_distribution": top_counter(status_counter, limit),
        "uri_top": top_counter(uri_counter, limit),
        "aggregate_previews": aggregate_previews,
    }


def summarize_behavior_collection(rows: Sequence[Dict[str, Any]], limit: int, summary_type: str) -> Dict[str, Any]:
    previews: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        preview = {
            "summary_type": summary_type,
            "src_ip": normalize_str(row.get("src_ip")),
            "window_start": normalize_str(row.get("window_start")),
            "window_end": normalize_str(row.get("window_end")),
            "request_count": row.get("request_count"),
            "reason_hints": [normalize_str(hint) for hint in ensure_list(row.get("reason_hints")) if normalize_str(hint)],
            "interpretation_limit": normalize_str(row.get("interpretation_limit")),
        }
        if summary_type == "ip_behavior_aggregates":
            preview.update(
                {
                    "distinct_paths": row.get("distinct_paths"),
                    "status_4xx_ratio": row.get("status_4xx_ratio"),
                    "status_5xx_count": row.get("status_5xx_count"),
                    "attack_categories_attempted": ensure_list(row.get("attack_categories_attempted")),
                    "sample_request_ids": ensure_list(row.get("sample_request_ids"))[:10],
                }
            )
        else:
            preview.update(
                {
                    "endpoint_family": normalize_str(row.get("endpoint_family")),
                    "status_counts": row.get("status_counts") or {},
                    "has_repeated_401": bool(row.get("has_repeated_401")),
                    "has_rapid_burst": bool(row.get("has_rapid_burst")),
                    "has_mixed_401_200": bool(row.get("has_mixed_401_200")),
                    "has_single_200_only": bool(row.get("has_single_200_only")),
                    "sample_request_ids": ensure_list(row.get("sample_request_ids"))[:10],
                }
            )
        previews.append(preview)
    return {
        "count": len(rows),
        "reason_hints_top": top_counter(hint_counter(rows), limit),
        "previews": previews,
    }


def row_has_hint_prefix(row: Dict[str, Any], prefixes: Sequence[str]) -> bool:
    for hint in ensure_list(row.get("reason_hints")):
        normalized = normalize_str(hint)
        if any(normalized.startswith(prefix) for prefix in prefixes):
            return True
    return False


def is_auth_row(row: Dict[str, Any]) -> bool:
    method = normalize_str(row.get("method"))
    uri = normalize_str(row.get("uri"))
    raw_request_target = normalize_str(row.get("raw_request_target"))
    if prepare.is_auth_endpoint_request(method, uri, raw_request_target=raw_request_target):
        return True
    return row_has_hint_prefix(row, ("auth_abuse:", "login_", "possible_auth_", "auth_payload_"))


def is_search_row(row: Dict[str, Any]) -> bool:
    uri = normalize_str(row.get("uri")).lower()
    raw_request_target = normalize_str(row.get("raw_request_target"))
    query_string = normalize_str(row.get("query_string"))
    if any(hint in uri for hint in SEARCH_URI_HINTS):
        return True
    if prepare.get_search_param_values(query_string, raw_request_target=raw_request_target):
        return True
    return row_has_hint_prefix(row, ("sqli:", "xss:", "context:educational_", "fp_hint:"))


def is_file_row(row: Dict[str, Any]) -> bool:
    uri = normalize_str(row.get("uri")).lower()
    raw_request_target = normalize_str(row.get("raw_request_target")).lower()
    combined = f"{uri} {raw_request_target}"
    if any(hint in combined for hint in FILE_PATH_HINTS):
        return True
    return row_has_hint_prefix(row, ("file_disclosure:",))


def is_l3_row(row: Dict[str, Any]) -> bool:
    return row_has_hint_prefix(row, L3_HINT_PREFIXES)


def combine_row_sources(collections: Sequence[Tuple[str, Sequence[Dict[str, Any]]]]) -> List[Tuple[str, Dict[str, Any]]]:
    combined: List[Tuple[str, Dict[str, Any]]] = []
    for source, rows in collections:
        for row in rows:
            combined.append((source, row))
    return combined


def filter_combined_rows(
    combined_rows: Sequence[Tuple[str, Dict[str, Any]]],
    predicate,
) -> List[Tuple[str, Dict[str, Any]]]:
    return [(source, row) for source, row in combined_rows if predicate(row)]


def status_counter_for_rows(rows: Iterable[Dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[normalize_str(row.get("status_code")) or "(empty)"] += 1
    return counter


def noise_category_exists(filtered_rows: Sequence[Dict[str, Any]], noise_rows: Sequence[Dict[str, Any]], category: str) -> bool:
    for row in filtered_rows:
        if normalize_str(row.get("noise_category")) == category:
            return True
    for row in noise_rows:
        if normalize_str(row.get("category")) == category:
            return True
    return False


def build_focus_auth(
    combined_rows: Sequence[Tuple[str, Dict[str, Any]]],
    supporting_events: Sequence[Dict[str, Any]],
    filtered_rows: Sequence[Dict[str, Any]],
    noise_rows: Sequence[Dict[str, Any]],
    auth_behavior_rows: Sequence[Dict[str, Any]],
    limit: int,
    show_rows: bool,
) -> Dict[str, Any]:
    auth_rows = filter_combined_rows(combined_rows, is_auth_row)
    post_auth_rows = [
        (source, row)
        for source, row in auth_rows
        if normalize_str(row.get("method")).upper() == "POST"
        and prepare.is_auth_endpoint_request(
            normalize_str(row.get("method")),
            normalize_str(row.get("uri")),
            raw_request_target=normalize_str(row.get("raw_request_target")),
        )
    ]
    post_auth_row_values = [row for _, row in post_auth_rows]
    auth_candidate_200 = [
        row for source, row in auth_rows
        if source == "analysis_candidates"
        and normalize_str(row.get("method")).upper() == "POST"
        and normalize_str(row.get("status_code")) == "200"
    ]
    supporting_auth_behavior = [
        row for row in supporting_events
        if normalize_str(row.get("supporting_role")) == "auth_behavior_support"
    ]
    interpretation_limit_rows = [
        (source, row)
        for source, row in auth_rows
        if "post_body_not_visible" in normalize_str(row.get("interpretation_limit"))
    ]
    return {
        "auth_like_rows_count": len(auth_rows),
        "post_auth_endpoint_rows_count": len(post_auth_rows),
        "post_auth_status_mix": top_counter(status_counter_for_rows(post_auth_row_values), limit),
        "auth_behavior_summaries_present": bool(auth_behavior_rows),
        "auth_behavior_summaries_count": len(auth_behavior_rows),
        "auth_baseline_context_present": noise_category_exists(filtered_rows, noise_rows, "auth_baseline_context"),
        "supporting_auth_behavior_support_present": bool(supporting_auth_behavior),
        "supporting_auth_behavior_support_count": len(supporting_auth_behavior),
        "post_body_not_visible_interpretation_limit_present": bool(interpretation_limit_rows),
        "post_body_not_visible_interpretation_limit_count": len(interpretation_limit_rows),
        "auth_post_200_candidates_count": len(auth_candidate_200),
        "auth_post_200_candidate_rows": (
            [build_row_preview(row, "analysis_candidates") for row in auth_candidate_200[:limit]]
            if show_rows
            else []
        ),
        "sample_rows": (
            [build_row_preview(row, source) for source, row in auth_rows[:limit]]
            if show_rows
            else []
        ),
    }


def build_focus_search(
    combined_rows: Sequence[Tuple[str, Dict[str, Any]]],
    supporting_events: Sequence[Dict[str, Any]],
    filtered_rows: Sequence[Dict[str, Any]],
    noise_rows: Sequence[Dict[str, Any]],
    limit: int,
    show_rows: bool,
) -> Dict[str, Any]:
    search_rows = filter_combined_rows(combined_rows, is_search_row)
    search_values = [row for _, row in search_rows]
    sqli_rows = [(source, row) for source, row in search_rows if row_has_hint_prefix(row, ("sqli:",))]
    xss_rows = [(source, row) for source, row in search_rows if row_has_hint_prefix(row, ("xss:",))]
    baseline_rows = [
        row for row in supporting_events
        if normalize_str(row.get("supporting_role")) == "reference_baseline"
    ]
    return {
        "search_or_query_rows_count": len(search_rows),
        "status_mix": top_counter(status_counter_for_rows(search_values), limit),
        "sqli_hint_rows_count": len(sqli_rows),
        "xss_hint_rows_count": len(xss_rows),
        "benign_normal_search_present": noise_category_exists(filtered_rows, noise_rows, "benign_normal_search"),
        "reference_baseline_present": bool(baseline_rows),
        "reference_baseline_count": len(baseline_rows),
        "sample_rows": (
            [build_row_preview(row, source) for source, row in search_rows[:limit]]
            if show_rows
            else []
        ),
    }


def build_focus_file(
    combined_rows: Sequence[Tuple[str, Dict[str, Any]]],
    limit: int,
    show_rows: bool,
) -> Dict[str, Any]:
    file_rows = filter_combined_rows(combined_rows, is_file_row)
    php_filter_rows = [(source, row) for source, row in file_rows if "file_disclosure:php_filter_wrapper" in ensure_list(row.get("reason_hints"))]
    resource_rows = [(source, row) for source, row in file_rows if "file_disclosure:resource_parameter" in ensure_list(row.get("reason_hints"))]
    base64_rows = [(source, row) for source, row in file_rows if "file_disclosure:base64_source_intent" in ensure_list(row.get("reason_hints"))]
    direct_config_candidates = [
        (source, row) for source, row in file_rows
        if "config.php" in normalize_str(row.get("uri")).lower() and source == "analysis_candidates"
    ]
    direct_config_context = [
        (source, row) for source, row in file_rows
        if "config.php" in normalize_str(row.get("uri")).lower() and source != "analysis_candidates"
    ]
    return {
        "file_disclosure_hint_rows_count": len(file_rows),
        "php_filter_wrapper_rows_count": len(php_filter_rows),
        "resource_parameter_rows_count": len(resource_rows),
        "base64_source_intent_rows_count": len(base64_rows),
        "direct_config_path_candidate_count": len(direct_config_candidates),
        "direct_config_path_context_count": len(direct_config_context),
        "sample_rows": (
            [build_row_preview(row, source) for source, row in file_rows[:limit]]
            if show_rows
            else []
        ),
    }


def build_focus_l3(
    combined_rows: Sequence[Tuple[str, Dict[str, Any]]],
    limit: int,
    show_rows: bool,
) -> Dict[str, Any]:
    l3_rows = filter_combined_rows(combined_rows, is_l3_row)

    def count_rows(prefixes: Sequence[str]) -> List[Tuple[str, Dict[str, Any]]]:
        return [(source, row) for source, row in l3_rows if row_has_hint_prefix(row, prefixes)]

    log4shell_rows = count_rows(("log4shell:", "l3:log4shell"))
    ssrf_rows = count_rows(("ssrf:", "l3:ssrf"))
    ssti_rows = count_rows(("ssti:", "l3:ssti"))
    webshell_rows = count_rows(("webshell:", "l3:webshell_probe"))
    return {
        "l3_related_rows_count": len(l3_rows),
        "log4shell_rows_count": len(log4shell_rows),
        "ssrf_rows_count": len(ssrf_rows),
        "ssti_rows_count": len(ssti_rows),
        "webshell_probe_rows_count": len(webshell_rows),
        "sample_rows": (
            [build_row_preview(row, source) for source, row in l3_rows[:limit]]
            if show_rows
            else []
        ),
    }


def build_focus_summary(
    focus: str,
    combined_rows: Sequence[Tuple[str, Dict[str, Any]]],
    supporting_events: Sequence[Dict[str, Any]],
    filtered_rows: Sequence[Dict[str, Any]],
    noise_rows: Sequence[Dict[str, Any]],
    auth_behavior_rows: Sequence[Dict[str, Any]],
    limit: int,
    show_rows: bool,
) -> Dict[str, Any]:
    focus_builders = {
        "auth": lambda: build_focus_auth(
            combined_rows, supporting_events, filtered_rows, noise_rows, auth_behavior_rows, limit, show_rows
        ),
        "search": lambda: build_focus_search(
            combined_rows, supporting_events, filtered_rows, noise_rows, limit, show_rows
        ),
        "file": lambda: build_focus_file(combined_rows, limit, show_rows),
        "l3": lambda: build_focus_l3(combined_rows, limit, show_rows),
    }
    if focus == "all":
        return {name: builder() for name, builder in focus_builders.items()}
    return {focus: focus_builders[focus]()}


def format_counter_line(items: Sequence[Dict[str, Any]]) -> str:
    if not items:
        return "(none)"
    return ", ".join(f"{item['value']}={item['count']}" for item in items)


def print_section(title: str) -> None:
    print(f"\n## {title}")


def print_collection_summary(title: str, summary: Dict[str, Any], category_field: str, extra_fields: Sequence[str]) -> None:
    print_section(title)
    print(f"count: {summary['count']}")
    print(f"status_code: {format_counter_line(summary.get('status_code_distribution') or [])}")
    if category_field:
        print(f"{category_field}: {format_counter_line(summary.get(f'{category_field}_distribution') or [])}")
    for field in extra_fields:
        print(f"{field}: {format_counter_line(summary.get(f'{field}_top') or [])}")
    print(f"reason_hints: {format_counter_line(summary.get('reason_hints_top') or [])}")
    if summary.get("row_previews"):
        print("rows:")
        for preview in summary["row_previews"]:
            print(f"- {format_row_preview(preview)}")


def print_behavior_summary(title: str, summary: Dict[str, Any]) -> None:
    print_section(title)
    print(f"count: {summary['count']}")
    print(f"reason_hints: {format_counter_line(summary.get('reason_hints_top') or [])}")
    for preview in summary.get("previews") or []:
        if preview.get("summary_type") == "ip_behavior_aggregates":
            print(
                "- "
                f"src_ip={clip(preview.get('src_ip'), 40) or '-'} request_count={preview.get('request_count')} "
                f"distinct_paths={preview.get('distinct_paths')} status_4xx_ratio={preview.get('status_4xx_ratio')} "
                f"status_5xx_count={preview.get('status_5xx_count')} hints={', '.join(preview.get('reason_hints') or []) or '-'} "
                f"interpretation_limit={clip(preview.get('interpretation_limit'), 80) or '-'}"
            )
        else:
            print(
                "- "
                f"src_ip={clip(preview.get('src_ip'), 40) or '-'} endpoint_family={clip(preview.get('endpoint_family'), 40) or '-'} "
                f"request_count={preview.get('request_count')} status_counts={preview.get('status_counts')} "
                f"repeated_401={preview.get('has_repeated_401')} mixed_401_200={preview.get('has_mixed_401_200')} "
                f"rapid_burst={preview.get('has_rapid_burst')} hints={', '.join(preview.get('reason_hints') or []) or '-'} "
                f"interpretation_limit={clip(preview.get('interpretation_limit'), 80) or '-'}"
            )


def print_focus_summary(focus_summary: Dict[str, Any]) -> None:
    print_section("Focus-Specific Checklist")
    for focus_name, payload in focus_summary.items():
        print(f"[{focus_name}]")
        for key, value in payload.items():
            if key.endswith("_rows") or key == "sample_rows":
                continue
            if isinstance(value, list) and value and isinstance(value[0], dict) and {"value", "count"} <= set(value[0].keys()):
                print(f"- {key}: {format_counter_line(value)}")
            else:
                print(f"- {key}: {value}")
        row_groups = []
        if payload.get("auth_post_200_candidate_rows"):
            row_groups.append(("auth_post_200_candidate_rows", payload["auth_post_200_candidate_rows"]))
        if payload.get("sample_rows"):
            row_groups.append(("sample_rows", payload["sample_rows"]))
        for label, rows in row_groups:
            print(f"- {label}:")
            for preview in rows:
                print(f"  {format_row_preview(preview)}")


def build_summary(args: argparse.Namespace) -> Tuple[Optional[Dict[str, Any]], int]:
    warnings: List[str] = []
    try:
        paths = resolve_paths(args)
    except ValueError as exc:
        return None, fail(str(exc))

    llm_input_path = paths["llm_input"]
    if llm_input_path is None or not llm_input_path.exists():
        return None, fail(f"llm_input file not found: {llm_input_path}")

    try:
        llm_input_payload = load_json(llm_input_path)
    except Exception as exc:  # noqa: BLE001
        return None, fail(f"failed to read llm_input JSON: {llm_input_path} ({exc})")

    if not isinstance(llm_input_payload, dict):
        return None, fail(f"llm_input payload must be a JSON object: {llm_input_path}")

    filtered_rows: List[Dict[str, Any]] = []
    filtered_rows_loaded = False
    filtered_out_path = paths["filtered_out"]
    if filtered_out_path:
        if filtered_out_path.exists():
            try:
                filtered_rows = unwrap_optional_collection(load_json(filtered_out_path), "rows")
                filtered_rows_loaded = True
            except Exception as exc:  # noqa: BLE001
                return None, fail(f"failed to read filtered_out JSON: {filtered_out_path} ({exc})")
        else:
            warn(f"filtered_out file not found; continuing without it: {filtered_out_path}", warnings)

    noise_rows: List[Dict[str, Any]] = []
    noise_rows_loaded = False
    noise_summary_path = paths["noise_summary"]
    if noise_summary_path:
        if noise_summary_path.exists():
            try:
                noise_rows = unwrap_optional_collection(load_json(noise_summary_path), "noise_summary")
                noise_rows_loaded = True
            except Exception as exc:  # noqa: BLE001
                return None, fail(f"failed to read noise_summary JSON: {noise_summary_path} ({exc})")
        else:
            warn(f"noise_summary file not found; using llm_input.noise_summary if present: {noise_summary_path}", warnings)

    if not noise_rows_loaded:
        noise_rows = unwrap_optional_collection(llm_input_payload.get("noise_summary"), "noise_summary")

    meta = llm_input_payload.get("meta") or {}
    meta_counts = meta.get("counts") or {}
    analysis_candidates = [row for row in ensure_list(llm_input_payload.get("analysis_candidates")) if isinstance(row, dict)]
    supporting_events = [row for row in ensure_list(llm_input_payload.get("supporting_events")) if isinstance(row, dict)]
    false_positive_review_candidates = [
        row for row in ensure_list(llm_input_payload.get("false_positive_review_candidates")) if isinstance(row, dict)
    ]
    probing_sequence_summaries = [
        row for row in ensure_list(llm_input_payload.get("probing_sequence_summaries")) if isinstance(row, dict)
    ]
    ip_behavior_aggregates = [row for row in ensure_list(llm_input_payload.get("ip_behavior_aggregates")) if isinstance(row, dict)]
    auth_behavior_summaries = [row for row in ensure_list(llm_input_payload.get("auth_behavior_summaries")) if isinstance(row, dict)]

    counts = {
        "total_exported_rows": meta_counts.get("total_exported_rows", meta_counts.get("selected_source_rows")),
        "candidate_rows": len(analysis_candidates),
        "distinct_incident_candidates": meta_counts.get("distinct_incident_candidates", len(analysis_candidates)),
        "supporting_events": len(supporting_events),
        "false_positive_review_candidates": len(false_positive_review_candidates),
        "filtered_out_rows": len(filtered_rows) if filtered_rows_loaded else meta_counts.get("filtered_out_rows", 0),
        "filtered_out_non_aggregated_rows": len(filtered_rows) if filtered_rows_loaded else meta_counts.get("filtered_out_non_aggregated_rows", 0),
        "probing_sequence_summaries": len(probing_sequence_summaries),
        "ip_behavior_aggregates": len(ip_behavior_aggregates),
        "auth_behavior_summaries": len(auth_behavior_summaries),
    }

    candidate_summary = summarize_row_collection(
        analysis_candidates,
        row_source="analysis_candidates",
        category_field="verdict_hint",
        extra_fields=("uri", "user_agent"),
        limit=args.limit,
        show_rows=args.show_rows,
    )
    supporting_summary = summarize_row_collection(
        supporting_events,
        row_source="supporting_events",
        category_field="supporting_role",
        extra_fields=("supporting_reason",),
        limit=args.limit,
        show_rows=args.show_rows,
    )
    filtered_summary = summarize_row_collection(
        filtered_rows,
        row_source="filtered_out_rows",
        category_field="noise_category",
        extra_fields=("uri",),
        limit=args.limit,
        show_rows=args.show_rows,
    )
    filtered_summary["noise_summary_aggregates"] = summarize_noise_aggregates(noise_rows, args.limit)

    combined_rows = combine_row_sources(
        (
            ("analysis_candidates", analysis_candidates),
            ("supporting_events", supporting_events),
            ("filtered_out_rows", filtered_rows),
        )
    )

    focus_summary = build_focus_summary(
        args.focus,
        combined_rows,
        supporting_events,
        filtered_rows,
        noise_rows,
        auth_behavior_summaries,
        args.limit,
        args.show_rows,
    )

    summary = {
        "inputs": {
            "llm_input": str(llm_input_path),
            "filtered_out": str(filtered_out_path) if filtered_out_path else None,
            "noise_summary": str(noise_summary_path) if noise_summary_path else None,
        },
        "warnings": warnings,
        "focus": args.focus,
        "limit": args.limit,
        "show_rows": args.show_rows,
        "meta_excerpt": {
            "analysis_window": meta.get("analysis_window"),
            "analysis_primary_table": meta.get("analysis_primary_table"),
            "prepared_at": meta.get("prepared_at"),
            "filtered_out_breakdown": meta.get("filtered_out_breakdown") or {},
        },
        "top_level_counts": counts,
        "candidate_summary": candidate_summary,
        "supporting_events_summary": supporting_summary,
        "filtered_out_summary": filtered_summary,
        "behavior_summaries": {
            "ip_behavior_aggregates": summarize_behavior_collection(ip_behavior_aggregates, args.limit, "ip_behavior_aggregates"),
            "auth_behavior_summaries": summarize_behavior_collection(auth_behavior_summaries, args.limit, "auth_behavior_summaries"),
        },
        "focus_specific_checklist": focus_summary,
    }
    return summary, 0


def print_text_summary(summary: Dict[str, Any]) -> None:
    print("# Prepare Output Summary")
    print(f"llm_input: {summary['inputs']['llm_input']}")
    print(f"filtered_out: {summary['inputs']['filtered_out'] or '(not provided)'}")
    print(f"noise_summary: {summary['inputs']['noise_summary'] or '(not provided)'}")
    print(f"focus: {summary['focus']} limit: {summary['limit']} show_rows: {summary['show_rows']}")
    if summary.get("warnings"):
        print("\nwarnings:")
        for item in summary["warnings"]:
            print(f"- {item}")

    print_section("Top-Level Counts")
    for key, value in summary["top_level_counts"].items():
        print(f"{key}: {value}")

    print_collection_summary(
        "Candidate Summary",
        summary["candidate_summary"],
        category_field="verdict_hint",
        extra_fields=("uri", "user_agent"),
    )
    print_collection_summary(
        "Supporting Events Summary",
        summary["supporting_events_summary"],
        category_field="supporting_role",
        extra_fields=("supporting_reason",),
    )
    print_collection_summary(
        "Filtered Out Summary",
        summary["filtered_out_summary"],
        category_field="noise_category",
        extra_fields=("uri",),
    )

    noise_aggregates = summary["filtered_out_summary"].get("noise_summary_aggregates") or {}
    print("noise_summary_aggregates:")
    print(f"- count: {noise_aggregates.get('count')}")
    print(f"- category: {format_counter_line(noise_aggregates.get('category_distribution') or [])}")
    print(f"- status_code: {format_counter_line(noise_aggregates.get('status_code_distribution') or [])}")
    print(f"- uri: {format_counter_line(noise_aggregates.get('uri_top') or [])}")
    for preview in noise_aggregates.get("aggregate_previews") or []:
        print(
            "- "
            f"category={clip(preview.get('category'), 40) or '-'} method={clip(preview.get('method'), 12) or '-'} "
            f"uri={clip(preview.get('uri'), 120) or '-'} status={clip(preview.get('status_code'), 12) or '-'} "
            f"count={preview.get('count')} ua={clip(preview.get('user_agent'), 80) or '-'} "
            f"note={clip(preview.get('note'), 120) or '-'}"
        )

    behavior = summary["behavior_summaries"]
    print_behavior_summary("IP Behavior Aggregates", behavior["ip_behavior_aggregates"])
    print_behavior_summary("Auth Behavior Summaries", behavior["auth_behavior_summaries"])
    print_focus_summary(summary["focus_specific_checklist"])


def main() -> int:
    args = parse_args()
    if args.limit <= 0:
        return fail("--limit must be greater than 0")

    summary, exit_code = build_summary(args)
    if summary is None:
        return exit_code

    if args.json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_text_summary(summary)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
