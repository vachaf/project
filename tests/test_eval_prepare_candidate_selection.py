from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "eval_prepare_candidate_selection.py"


def load_module():
    spec = importlib.util.spec_from_file_location("eval_prepare_candidate_selection", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def label_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "prepare_candidate_selection_eval.v1",
        "description": "test labels",
        "label_policy": {},
        "items": items,
    }


def test_metric_counts_precision_recall_and_f1() -> None:
    module = load_module()
    labels = [
        {"request_id": "tp", "human_label": "candidate_expected", "reason": "sqli_probe"},
        {"request_id": "fn", "human_label": "candidate_expected", "reason": "xss_probe"},
        {"request_id": "fp", "human_label": "candidate_not_expected", "reason": "low_signal_request"},
        {"request_id": "tn", "human_label": "candidate_not_expected", "reason": "static_asset_like"},
    ]

    result = module.evaluate_candidate_selection(labels, {"tp", "fp"})

    assert result["tp"] == 1
    assert result["fn"] == 1
    assert result["fp"] == 1
    assert result["tn"] == 1
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["f1"] == pytest.approx(0.5)
    assert [item["request_id"] for item in result["false_positives"]] == ["fp"]
    assert [item["request_id"] for item in result["false_negatives"]] == ["fn"]
    assert result["metric_name"] == "candidate selection precision/recall"


def test_unsure_is_excluded_from_metric_counts() -> None:
    module = load_module()
    labels = [
        {"request_id": "tp", "human_label": "candidate_expected"},
        {"request_id": "unsure", "human_label": "unsure"},
    ]

    result = module.evaluate_candidate_selection(labels, {"tp", "unsure"})

    assert result["total_labeled"] == 2
    assert result["evaluated_count"] == 1
    assert result["unsure_count"] == 1
    assert result["tp"] == 1
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["tn"] == 0


def test_zero_denominators_are_reported_as_null() -> None:
    module = load_module()
    labels = [
        {"request_id": "tn", "human_label": "candidate_not_expected"},
    ]

    result = module.evaluate_candidate_selection(labels, set())

    assert result["tp"] == 0
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["tn"] == 1
    assert result["precision"] is None
    assert result["recall"] is None
    assert result["f1"] is None


def test_filtered_reasons_join_for_false_negative_and_true_negative() -> None:
    module = load_module()
    labels = [
        {"request_id": "fn", "human_label": "candidate_expected", "reason": "sensitive_path_probe"},
        {"request_id": "tn", "human_label": "candidate_not_expected", "reason": "static_asset_like"},
    ]
    filtered_reasons = {
        "fn": {"reason": "outside_candidate_policy", "reason_detail": "below threshold"},
        "tn": {"reason": "static_asset_like", "reason_detail": "asset extension"},
    }

    result = module.evaluate_candidate_selection(labels, set(), filtered_reason_map=filtered_reasons)

    assert result["false_negatives"][0]["filtered_reason"]["reason"] == "outside_candidate_policy"
    assert result["true_negatives_with_filtered_reasons"][0]["request_id"] == "tn"
    assert result["true_negatives_with_filtered_reasons"][0]["filtered_reason"]["reason"] == "static_asset_like"


def test_forbidden_label_raises_validation_error(tmp_path: Path) -> None:
    module = load_module()
    labels_path = write_json(
        tmp_path / "labels.json",
        label_payload([{"request_id": "req-1", "human_label": "benign"}]),
    )

    with pytest.raises(module.EvalValidationError, match="forbidden human_label"):
        module.load_label_items(labels_path)


def test_missing_label_request_id_raises_validation_error(tmp_path: Path) -> None:
    module = load_module()
    labels_path = write_json(
        tmp_path / "labels.json",
        label_payload([{"human_label": "candidate_expected"}]),
    )

    with pytest.raises(module.EvalValidationError, match="missing request_id"):
        module.load_label_items(labels_path)


def test_candidate_rows_missing_request_id_emit_warning(tmp_path: Path) -> None:
    module = load_module()
    candidates_path = write_json(
        tmp_path / "analysis_candidates.json",
        {"analysis_candidates": [{"request_id": "candidate-1"}, {"uri": "/missing-id"}]},
    )

    candidate_ids, warnings = module.load_candidate_request_ids(candidates_path)

    assert candidate_ids == {"candidate-1"}
    assert warnings == ["analysis_candidates row 1 missing request_id; ignored"]


def test_filtered_reasons_loader_supports_excluded_wrapper(tmp_path: Path) -> None:
    module = load_module()
    filtered_path = write_json(
        tmp_path / "filtered_reasons.json",
        {
            "schema_version": "filtered_reasons.v1",
            "excluded": [
                {
                    "request_id": "req-static",
                    "reason": "static_asset_like",
                    "reason_detail": "static extension",
                }
            ],
        },
    )

    reason_map = module.load_filtered_reason_map(filtered_path)

    assert reason_map == {
        "req-static": {
            "reason": "static_asset_like",
            "reason_detail": "static extension",
        }
    }


def test_jobs12_labelset_matches_actual_artifact_request_ids() -> None:
    module = load_module()
    labels_path = PROJECT_ROOT / "data" / "eval" / "prepare_candidate_selection_jobs12.json"
    candidates_path = PROJECT_ROOT / "runs" / "jobs" / "12" / "analysis_candidates.json"
    filtered_path = PROJECT_ROOT / "runs" / "jobs" / "12" / "filtered_reasons.json"

    label_items = module.load_label_items(labels_path)
    candidate_ids, warnings = module.load_candidate_request_ids(candidates_path)
    filtered_reason_map = module.load_filtered_reason_map(filtered_path)
    label_ids = {item["request_id"] for item in label_items}

    assert len(label_items) == 14
    assert warnings == []
    assert label_ids == candidate_ids | set(filtered_reason_map)
    assert not {item["human_label"] for item in label_items} & module.FORBIDDEN_LABELS

    result = module.evaluate_candidate_selection(
        label_items,
        candidate_ids,
        filtered_reason_map=filtered_reason_map,
        warnings=warnings,
    )

    assert result["tp"] == 5
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["tn"] == 8
    assert result["unsure_count"] == 1
    assert result["precision"] == pytest.approx(1.0)
    assert result["recall"] == pytest.approx(1.0)
    assert result["f1"] == pytest.approx(1.0)
