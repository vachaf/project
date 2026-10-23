from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.export_db_logs_cli import RangeConfig, build_export_payload
from src import llm_stage2_reporter as stage2
from src.prepare_llm_input import build_outputs


def export_range() -> RangeConfig:
    start = datetime(2026, 10, 15, 15, 20, 23, 804000, tzinfo=ZoneInfo("Asia/Seoul"))
    end = datetime(2026, 10, 15, 15, 20, 23, 805000, tzinfo=ZoneInfo("Asia/Seoul"))
    return RangeConfig("custom", "Asia/Seoul", "UTC", start, end, start, end)


def prepared_meta(export: dict) -> dict:
    llm_input, *_ = build_outputs(export, min_score=4, min_repeat_aggregate=3, source_tables=["security"])
    return llm_input["meta"]


def test_new_exports_identify_actual_query_mode_and_keep_existing_shape() -> None:
    selected = build_export_payload("web_logs", "security", export_range(), None,
                                    {"access": [], "security": [], "error": []}, selected_log_ids=[10, 30])
    ranged = build_export_payload("web_logs", "security", export_range(), None,
                                  {"access": [], "security": [], "error": []})
    assert set(selected) == set(ranged) == {"meta", "counts", "data"}
    assert selected["meta"]["input_kind"] == "live_selected_logs"
    assert selected["meta"]["selected_log_ids"] == [10, 30]
    assert ranged["meta"]["input_kind"] == "time_range"
    assert "selected_log_ids" not in ranged["meta"]
    assert selected["meta"]["start"] == ranged["meta"]["start"]
    assert selected["meta"]["end_exclusive"] == ranged["meta"]["end_exclusive"]


def test_prepare_preserves_selected_scope_without_equating_ids_and_rows() -> None:
    rows = [
        {"id": 10, "log_time": "2026-10-15T15:20:23.804+09:00", "uri": "/a", "method": "GET", "status_code": 200},
        {"id": 30, "log_time": "2026-10-15T15:20:23.804+09:00", "uri": "/b", "method": "GET", "status_code": 200},
    ]
    export = build_export_payload("web_logs", "security", export_range(), None,
                                  {"access": [], "security": rows, "error": []}, selected_log_ids=[10, 30, 40])
    meta = prepared_meta(export)
    assert meta["input_scope"] == {
        "kind": "live_selected_logs",
        "window_role": "selected_log_timestamp_envelope",
        "window": {
            "start": export["meta"]["start"],
            "end_exclusive": export["meta"]["end_exclusive"],
            "timezone": "Asia/Seoul",
        },
        "selected_id_count": 3,
    }
    assert "selected_log_ids" not in meta["input_scope"]
    assert meta["analysis_window"] == {
        "start": export["meta"]["start"], "end_exclusive": export["meta"]["end_exclusive"]
    }
    assert meta["counts"]["total_exported_rows"] == 2
    assert meta["counts"]["selected_source_rows"] == 2
    assert meta["counts"]["candidate_rows"] == 0


def test_prepare_marks_time_range_as_query_filter() -> None:
    export = build_export_payload("web_logs", "security", export_range(), None,
                                  {"access": [], "security": [], "error": []})
    scope = prepared_meta(export)["input_scope"]
    assert scope["kind"] == "time_range"
    assert scope["window_role"] == "query_filter"
    assert scope["window"]["end_exclusive"] == export["meta"]["end_exclusive"]
    assert "selected_id_count" not in scope


def test_prepare_keeps_export_rows_separate_from_selected_source_rows() -> None:
    export = build_export_payload("web_logs", "all", export_range(), None,
                                  {"access": [{"id": 1}], "security": [{"id": 2}], "error": [{"id": 3}]})
    meta = prepared_meta(export)
    assert meta["input_scope"]["kind"] == "time_range"
    assert meta["counts"]["total_exported_rows"] == 3
    assert meta["counts"]["selected_source_rows"] == 1


def test_legacy_export_without_kind_does_not_infer_scope_from_one_ms_window() -> None:
    export = build_export_payload("web_logs", "security", export_range(), None,
                                  {"access": [], "security": [], "error": []})
    export["meta"].pop("input_kind")
    meta = prepared_meta(export)
    assert "input_scope" not in meta
    assert meta["analysis_window"]["start"] == export["meta"]["start"]
    export["meta"]["selected_log_ids"] = [10]
    assert "input_scope" not in prepared_meta(export)


def test_explicit_null_input_kind_stays_distinct_from_missing() -> None:
    export = build_export_payload("web_logs", "security", export_range(), None,
                                  {"access": [], "security": [], "error": []})
    export["meta"]["input_kind"] = None
    assert prepared_meta(export)["input_scope"] is None


@pytest.mark.parametrize("changes", [
    {"input_kind": "invalid"},
    {"input_kind": "live_selected_logs"},
    {"input_kind": "live_selected_logs", "selected_log_ids": []},
    {"input_kind": "live_selected_logs", "selected_log_ids": [3, 3]},
    {"input_kind": "live_selected_logs", "selected_log_ids": [True]},
    {"input_kind": "time_range", "selected_log_ids": [3]},
    {"input_kind": None, "selected_log_ids": [3]},
    {"input_kind": None, "window_role": "query_filter"},
    {"input_kind": "time_range", "window_role": "selected_log_timestamp_envelope"},
    {"input_kind": "time_range", "end_exclusive": None},
    {"input_kind": "time_range", "query_timezone": "Invalid/Zone"},
    {"input_kind": "time_range", "end_exclusive": "2026-10-15T15:20:23.803+09:00"},
])
def test_prepare_rejects_explicitly_invalid_or_conflicting_scope(changes: dict) -> None:
    export = build_export_payload("web_logs", "security", export_range(), None,
                                  {"access": [], "security": [], "error": []})
    export["meta"].update(changes)
    with pytest.raises(ValueError, match="input scope"):
        prepared_meta(export)


def test_stage2_existing_input_builder_ignores_new_prepare_metadata_until_b2() -> None:
    export = build_export_payload("web_logs", "security", export_range(), None,
                                  {"access": [], "security": [], "error": []}, selected_log_ids=[10])
    llm_input, *_ = build_outputs(export, min_score=4, min_repeat_aggregate=3, source_tables=["security"])
    scope = llm_input["meta"]["input_scope"]
    report_input = stage2.build_report_input(
        {"meta": {"source_input_scope": scope}, "results": []}, llm_input, None,
        top_incidents=6, top_noise_groups=3, top_ips=3, known_asset_ips=[],
    )
    assert report_input["analysis_context"]["window"] == llm_input["meta"]["analysis_window"]
    assert "input_scope" not in report_input["analysis_context"]
    assert "input_scope" not in stage2.build_messages(report_input)[1]["content"]
