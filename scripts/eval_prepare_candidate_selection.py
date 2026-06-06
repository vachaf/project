#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

ALLOWED_LABELS = {"candidate_expected", "candidate_not_expected", "unsure"}
FORBIDDEN_LABELS = {
    "benign",
    "normal",
    "malicious_success",
    "attack_success",
    "compromised",
    "account_takeover_success",
}
LABEL_SCHEMA_VERSION = "prepare_candidate_selection_eval.v1"
RESULT_SCHEMA_VERSION = "prepare_candidate_selection_eval_result.v1"


class EvalValidationError(ValueError):
    pass


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate prepare candidate selection against project-local labels"
    )
    parser.add_argument(
        "--labels",
        default="data/eval/prepare_candidate_selection_minimal.json",
        help="Path to prepare candidate selection label JSON",
    )
    parser.add_argument(
        "--analysis-candidates",
        required=True,
        help="Path to analysis_candidates.json from prepare output",
    )
    parser.add_argument(
        "--filtered-reasons",
        help="Optional path to filtered_reasons.json for excluded reason joins",
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON result")
    return parser.parse_args(argv)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def unwrap_rows(payload: Any, candidate_keys: Sequence[str]) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in candidate_keys:
            rows = payload.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def load_label_items(path: Path) -> List[Dict[str, Any]]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise EvalValidationError("labels payload must be a JSON object")
    schema_version = normalize_text(payload.get("schema_version"))
    if schema_version != LABEL_SCHEMA_VERSION:
        raise EvalValidationError(
            f"labels schema_version must be {LABEL_SCHEMA_VERSION}, got {schema_version or '(missing)'}"
        )
    items = payload.get("items")
    if not isinstance(items, list):
        raise EvalValidationError("labels.items must be a list")

    seen: Set[str] = set()
    validated: List[Dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise EvalValidationError(f"labels.items[{index}] must be an object")
        request_id = normalize_text(item.get("request_id"))
        if not request_id:
            raise EvalValidationError(f"labels.items[{index}] is missing request_id")
        if request_id in seen:
            raise EvalValidationError(f"duplicate label request_id: {request_id}")
        seen.add(request_id)

        label = normalize_text(item.get("human_label"))
        if label in FORBIDDEN_LABELS:
            raise EvalValidationError(f"forbidden human_label for {request_id}: {label}")
        if label not in ALLOWED_LABELS:
            raise EvalValidationError(f"unsupported human_label for {request_id}: {label or '(missing)'}")
        validated.append(item)
    return validated


def load_candidate_request_ids(path: Path) -> tuple[Set[str], List[str]]:
    rows = unwrap_rows(load_json(path), ("analysis_candidates", "candidates", "results"))
    request_ids: Set[str] = set()
    warnings: List[str] = []
    for index, row in enumerate(rows):
        request_id = normalize_text(row.get("request_id"))
        if not request_id:
            warnings.append(f"analysis_candidates row {index} missing request_id; ignored")
            continue
        request_ids.add(request_id)
    return request_ids, warnings


def load_filtered_reason_map(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if path is None:
        return {}
    payload = load_json(path)
    rows = unwrap_rows(payload, ("excluded", "filtered_reasons", "filtered_out", "items"))
    reason_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        request_id = normalize_text(row.get("request_id"))
        if not request_id:
            continue
        reason_map[request_id] = {
            "reason": normalize_text(row.get("reason")),
            "reason_detail": normalize_text(row.get("reason_detail")),
        }
    return reason_map


def safe_divide(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


def item_summary(item: Dict[str, Any], filtered_reason_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    request_id = normalize_text(item.get("request_id"))
    summary = {
        "request_id": request_id,
        "human_label": normalize_text(item.get("human_label")),
        "reason": normalize_text(item.get("reason")),
        "source": normalize_text(item.get("source")),
        "method": normalize_text(item.get("method")),
        "uri": normalize_text(item.get("uri")),
        "status_code": item.get("status_code"),
    }
    filtered = filtered_reason_map.get(request_id)
    if filtered:
        summary["filtered_reason"] = filtered
    return summary


def evaluate_candidate_selection(
    label_items: Sequence[Dict[str, Any]],
    candidate_request_ids: Set[str],
    *,
    filtered_reason_map: Optional[Dict[str, Dict[str, Any]]] = None,
    warnings: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    filtered_reason_map = filtered_reason_map or {}
    tp = fp = fn = tn = 0
    unsure_count = 0
    false_positives: List[Dict[str, Any]] = []
    false_negatives: List[Dict[str, Any]] = []
    true_negatives_with_filtered_reasons: List[Dict[str, Any]] = []

    for item in label_items:
        request_id = normalize_text(item.get("request_id"))
        label = normalize_text(item.get("human_label"))
        in_candidates = request_id in candidate_request_ids
        if label == "unsure":
            unsure_count += 1
            continue
        if label == "candidate_expected":
            if in_candidates:
                tp += 1
            else:
                fn += 1
                false_negatives.append(item_summary(item, filtered_reason_map))
        elif label == "candidate_not_expected":
            if in_candidates:
                fp += 1
                false_positives.append(item_summary(item, filtered_reason_map))
            else:
                tn += 1
                if request_id in filtered_reason_map:
                    true_negatives_with_filtered_reasons.append(item_summary(item, filtered_reason_map))

    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    labels_by_class = Counter(normalize_text(item.get("human_label")) for item in label_items)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "metric_scope": "prepare_candidate_selection",
        "metric_name": "candidate selection precision/recall",
        "total_labeled": len(label_items),
        "evaluated_count": len(label_items) - unsure_count,
        "unsure_count": unsure_count,
        "labels_by_class": dict(sorted(labels_by_class.items())),
        "candidate_count": len(candidate_request_ids),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_negatives_with_filtered_reasons": true_negatives_with_filtered_reasons,
        "warnings": list(warnings or []),
        "guardrails": [
            "candidate_expected_does_not_mean_attack_success",
            "candidate_not_expected_does_not_mean_benign",
            "apache_logs_only_no_success_inference",
        ],
    }


def format_number(value: Optional[float]) -> str:
    if value is None:
        return "null"
    return f"{value:.4f}"


def print_text_result(result: Dict[str, Any]) -> None:
    print("prepare candidate selection evaluation")
    print(f"total_labeled={result['total_labeled']} evaluated_count={result['evaluated_count']} unsure_count={result['unsure_count']}")
    print(f"tp={result['tp']} fp={result['fp']} fn={result['fn']} tn={result['tn']}")
    print(
        "candidate selection precision/recall: "
        f"precision={format_number(result['precision'])} "
        f"recall={format_number(result['recall'])} "
        f"f1={format_number(result['f1'])}"
    )
    if result["warnings"]:
        print("warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result["false_positives"]:
        print("false_positives:")
        for item in result["false_positives"]:
            print(f"- {item['request_id']} reason={item.get('reason') or '-'} uri={item.get('uri') or '-'}")
    if result["false_negatives"]:
        print("false_negatives:")
        for item in result["false_negatives"]:
            filtered = item.get("filtered_reason") or {}
            filtered_text = f" filtered_reason={filtered.get('reason')}" if filtered else ""
            print(f"- {item['request_id']} reason={item.get('reason') or '-'} uri={item.get('uri') or '-'}{filtered_text}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        label_items = load_label_items(Path(args.labels))
        candidate_ids, warnings = load_candidate_request_ids(Path(args.analysis_candidates))
        filtered_reason_map = load_filtered_reason_map(Path(args.filtered_reasons)) if args.filtered_reasons else {}
        result = evaluate_candidate_selection(
            label_items,
            candidate_ids,
            filtered_reason_map=filtered_reason_map,
            warnings=warnings,
        )
    except (OSError, json.JSONDecodeError, EvalValidationError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
