from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "src" / "sliding_window_rollup.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sliding_window_rollup", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["sliding_window_rollup"] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def make_window_summary(
    *,
    window_id: str,
    start: str,
    end: str,
    candidates: list[dict],
    distributions: dict | None = None,
    export_total: int = 10,
    candidate_rows: int | None = None,
) -> dict:
    return {
        "schema": "sliding_window_summary_v1",
        "window": {
            "window_id": window_id,
            "start": start,
            "end_exclusive": end,
            "timezone": "Asia/Seoul",
            "duration_minutes": 60,
            "is_partial": False,
        },
        "artifact_status": {
            "export": {"path": "export.json", "exists": True},
            "llm_input": {"path": "llm_input.json", "exists": True},
            "analysis_candidates": {"path": "analysis_candidates.json", "exists": True},
            "noise_summary": {"path": "noise_summary.json", "exists": True},
            "window_summary": {"path": "window_summary.json", "exists": True},
        },
        "source": {
            "database": "web_logs",
            "table_option": "security",
            "selected_source_tables": ["security"],
            "analysis_primary_table": "security",
        },
        "counts": {
            "export": {"access": 0, "security": export_total, "error": 0, "total": export_total},
            "prepare": {
                "total_exported_rows": export_total,
                "selected_source_rows": export_total,
                "filtered_out_rows": max(export_total - len(candidates), 0),
                "candidate_rows_before_dedup": len(candidates),
                "candidate_rows": candidate_rows if candidate_rows is not None else len(candidates),
                "candidate_duplicate_rows_removed": 0,
                "distinct_incident_candidates": len(candidates),
                "noise_group_count": 0,
                "supporting_events": 0,
                "context_summary_count": 0,
            },
        },
        "distributions": distributions
        or {
            "candidate_status_code": {},
            "candidate_method": {},
            "candidate_verdict_hint": {},
            "candidate_src_ip": {},
            "candidate_uri": {},
            "candidate_reason_hint_prefix": {},
            "filtered_out_breakdown": {},
        },
        "candidate_index": candidates,
        "rollup_hints": {
            "has_candidates": bool(candidates),
            "has_noise_groups": False,
            "has_supporting_events": False,
            "has_context_summaries": False,
            "candidate_request_ids": [c.get("request_id") for c in candidates if c.get("request_id")],
        },
        "guardrails": {
            "summary_only": True,
            "no_new_security_verdict": True,
            "no_success_inference": True,
            "no_body_inference": True,
            "no_context_promotion": True,
        },
    }


def candidate(request_id: str | None, uri: str, *, status_code: int = 403, score: int = 6) -> dict:
    return {
        "request_id": request_id,
        "src_ip": "192.168.56.1",
        "method": "GET",
        "uri": uri,
        "status_code": status_code,
        "score": score,
        "verdict_hint": "suspicious",
        "reason_hint_prefixes": ["sensitive_path_probe"],
        "raw_log": "must not be copied",
        "raw_request": f"GET {uri} HTTP/1.1",
        "user_agent": "browser",
    }


def test_discover_window_summary_paths_matches_scheduler_layout(tmp_path: Path):
    module = load_module()

    paths = module.discover_window_summary_paths(
        work_dir=tmp_path,
        analysis_start="2026-05-24 02:00:00",
        analysis_end="2026-05-24 04:00:00",
        window_minutes=60,
        stride_minutes=60,
        timezone="Asia/Seoul",
    )

    assert paths == [
        tmp_path / "data/windowed/2026-05-24/sw_0200_0300/window_summary.json",
        tmp_path / "data/windowed/2026-05-24/sw_0300_0400/window_summary.json",
    ]


def test_load_window_summaries_records_missing_window(tmp_path: Path):
    module = load_module()
    existing = tmp_path / "data/windowed/2026-05-24/sw_0200_0300/window_summary.json"
    missing = tmp_path / "data/windowed/2026-05-24/sw_0300_0400/window_summary.json"
    write_json(
        existing,
        make_window_summary(
            window_id="sw_0200_0300",
            start="2026-05-24T02:00:00+09:00",
            end="2026-05-24T03:00:00+09:00",
            candidates=[],
        ),
    )

    summaries, statuses = module.load_window_summaries([existing, missing], work_dir=tmp_path)

    assert len(summaries) == 1
    assert statuses[0]["status"] == "loaded"
    assert statuses[0]["path"] == "data/windowed/2026-05-24/sw_0200_0300/window_summary.json"
    assert statuses[1]["status"] == "missing"
    assert statuses[1]["reason"] == "window_summary_not_found"


def test_request_id_dedup_merges_same_request_across_windows():
    module = load_module()
    candidates = [
        {**candidate("rid-1", "/admin.php"), "source_window_ids": ["sw_0200_0300"]},
        {**candidate("rid-1", "/admin.php"), "source_window_ids": ["sw_0300_0400"]},
        {**candidate("rid-2", "/login.php"), "source_window_ids": ["sw_0300_0400"]},
    ]

    deduped, report = module.dedup_candidates_by_request_id(candidates)

    assert len(deduped) == 2
    rid1 = next(item for item in deduped if item["request_id"] == "rid-1")
    assert rid1["source_window_ids"] == ["sw_0200_0300", "sw_0300_0400"]
    assert rid1["aggregation_type"] == "cross_window_same_request_id"
    assert report["removed_by_request_id"] == 1
    assert report["duplicate_request_ids"] == [
        {
            "request_id": "rid-1",
            "source_window_ids": ["sw_0200_0300", "sw_0300_0400"],
            "kept_source_window_id": "sw_0200_0300",
            "removed_count": 1,
            "action": "merged_by_request_id",
        }
    ]


def test_missing_request_id_is_preserved_and_fallback_duplicate_marked():
    module = load_module()
    candidates = [
        {**candidate(None, "/admin.php"), "source_window_ids": ["sw_0200_0300"]},
        {**candidate("", "/admin.php"), "source_window_ids": ["sw_0300_0400"]},
    ]

    deduped, report = module.dedup_candidates_by_request_id(candidates)

    assert len(deduped) == 2
    assert report["removed_by_request_id"] == 0
    assert report["missing_request_id_preserved"] == 2
    assert all(item["aggregation_type"] == "preserved_missing_request_id" for item in deduped)
    assert report["possible_duplicates"] == [
        {
            "fallback_key": "192.168.56.1|GET|/admin.php|403|sensitive_path_probe",
            "request_ids": [],
            "source_window_ids": ["sw_0200_0300", "sw_0300_0400"],
            "count": 2,
            "action": "marked_only_not_removed",
        }
    ]


def test_build_rollup_input_merges_distributions_and_preserves_guardrails(tmp_path: Path):
    module = load_module()
    summary1 = make_window_summary(
        window_id="sw_0200_0300",
        start="2026-05-24T02:00:00+09:00",
        end="2026-05-24T03:00:00+09:00",
        candidates=[candidate("rid-1", "/admin.php"), candidate("rid-2", "/login.php", status_code=401)],
        distributions={
            "candidate_status_code": {"403": 1, "401": 1},
            "candidate_method": {"GET": 2},
            "candidate_verdict_hint": {"suspicious": 2},
            "candidate_src_ip": {"192.168.56.1": 2},
            "candidate_uri": {"/admin.php": 1, "/login.php": 1},
            "candidate_reason_hint_prefix": {"sensitive_path_probe": 2},
            "filtered_out_breakdown": {"benign_normal_search": 3},
        },
        export_total=10,
    )
    summary2 = make_window_summary(
        window_id="sw_0300_0400",
        start="2026-05-24T03:00:00+09:00",
        end="2026-05-24T04:00:00+09:00",
        candidates=[candidate("rid-1", "/admin.php"), candidate(None, "/noid.php")],
        distributions={
            "candidate_status_code": {"403": 2},
            "candidate_method": {"GET": 2},
            "candidate_verdict_hint": {"suspicious": 2},
            "candidate_src_ip": {"192.168.56.1": 2},
            "candidate_uri": {"/admin.php": 1, "/noid.php": 1},
            "candidate_reason_hint_prefix": {"sensitive_path_probe": 2},
            "filtered_out_breakdown": {"benign_normal_search": 4},
        },
        export_total=20,
    )
    statuses = [
        {"window_id": "sw_0200_0300", "path": "data/windowed/2026-05-24/sw_0200_0300/window_summary.json", "status": "loaded"},
        {"window_id": "sw_0300_0400", "path": "data/windowed/2026-05-24/sw_0300_0400/window_summary.json", "status": "loaded"},
    ]

    rollup_input, dedup_candidates, rollup_summary = module.build_rollup_input(
        rollup_id="rollup_20260524_0200_0400",
        analysis_start="2026-05-24T02:00:00+09:00",
        analysis_end="2026-05-24T04:00:00+09:00",
        timezone="Asia/Seoul",
        duration_minutes=120,
        window_summaries=[summary1, summary2],
        window_load_status=statuses,
    )

    assert rollup_input["schema"] == "sliding_window_rollup_input_v1"
    assert rollup_input["counts"]["window_count"] == 2
    assert rollup_input["counts"]["export_total"] == 30
    assert rollup_input["counts"]["candidate_rows_total"] == 4
    assert rollup_input["counts"]["candidate_index_count"] == 3
    assert rollup_input["counts"]["dedup_removed_by_request_id"] == 1
    assert rollup_input["distributions"]["candidate_status_code"] == {"401": 1, "403": 3}
    assert rollup_input["distributions"]["filtered_out_breakdown"] == {"benign_normal_search": 7}
    assert rollup_input["guardrails"]["no_new_security_verdict"] is True
    assert rollup_input["guardrails"]["no_policy_recalculation"] is True
    assert "uri_family_hints" not in rollup_input["rollup_context"]
    assert "low_and_slow_hints" not in rollup_input["rollup_context"]

    serialized_candidates = repr(rollup_input["candidate_index"])
    assert "raw_log" not in serialized_candidates
    assert "raw_request" not in serialized_candidates
    assert "user_agent" not in serialized_candidates

    assert dedup_candidates["schema"] == "sliding_window_dedup_candidates_v1"
    assert rollup_summary["schema"] == "sliding_window_rollup_summary_v1"
    assert rollup_summary["incomplete_analysis"] is False


def test_build_and_write_rollup_creates_three_artifacts(tmp_path: Path):
    module = load_module()
    win1 = tmp_path / "data/windowed/2026-05-24/sw_0200_0300/window_summary.json"
    win2 = tmp_path / "data/windowed/2026-05-24/sw_0300_0400/window_summary.json"
    write_json(
        win1,
        make_window_summary(
            window_id="sw_0200_0300",
            start="2026-05-24T02:00:00+09:00",
            end="2026-05-24T03:00:00+09:00",
            candidates=[candidate("rid-1", "/admin.php")],
        ),
    )
    write_json(
        win2,
        make_window_summary(
            window_id="sw_0300_0400",
            start="2026-05-24T03:00:00+09:00",
            end="2026-05-24T04:00:00+09:00",
            candidates=[candidate("rid-1", "/admin.php"), candidate("rid-2", "/login.php")],
        ),
    )

    result = module.build_and_write_rollup(
        work_dir=tmp_path,
        analysis_start="2026-05-24 02:00:00",
        analysis_end="2026-05-24 04:00:00",
        window_minutes=60,
        stride_minutes=60,
        timezone="Asia/Seoul",
        window_output_root="data/windowed",
        rollup_output_root="data/rollups",
        out_dir=None,
        strict=False,
        pretty=True,
    )

    out_dir = tmp_path / "data/rollups/2026-05-24/rollup_20260524_0200_0400"
    assert result["out_dir"] == "data/rollups/2026-05-24/rollup_20260524_0200_0400"
    assert (out_dir / "rollup_input.json").exists()
    assert (out_dir / "dedup_candidates.json").exists()
    assert (out_dir / "rollup_summary.json").exists()

    rollup_input = json.loads((out_dir / "rollup_input.json").read_text(encoding="utf-8"))
    assert rollup_input["counts"]["candidate_rows_total"] == 3
    assert rollup_input["counts"]["candidate_index_count"] == 2
    assert rollup_input["dedup"]["removed_by_request_id"] == 1
    assert rollup_input["source_windows"][0]["path"] == "data/windowed/2026-05-24/sw_0200_0300/window_summary.json"


def test_missing_window_is_recorded_in_rollup_summary(tmp_path: Path):
    module = load_module()
    win1 = tmp_path / "data/windowed/2026-05-24/sw_0200_0300/window_summary.json"
    write_json(
        win1,
        make_window_summary(
            window_id="sw_0200_0300",
            start="2026-05-24T02:00:00+09:00",
            end="2026-05-24T03:00:00+09:00",
            candidates=[candidate("rid-1", "/admin.php")],
        ),
    )

    result = module.build_and_write_rollup(
        work_dir=tmp_path,
        analysis_start="2026-05-24 02:00:00",
        analysis_end="2026-05-24 04:00:00",
        window_minutes=60,
        stride_minutes=60,
        timezone="Asia/Seoul",
        window_output_root="data/windowed",
        rollup_output_root="data/rollups",
        out_dir=None,
        strict=False,
        pretty=True,
    )

    rollup_summary = json.loads((tmp_path / result["rollup_summary_path"]).read_text(encoding="utf-8"))
    assert rollup_summary["counts"]["window_count"] == 2
    assert rollup_summary["counts"]["windows_successfully_loaded"] == 1
    assert rollup_summary["counts"]["windows_missing_or_failed"] == 1
    assert rollup_summary["incomplete_analysis"] is True
    assert rollup_summary["source_windows"][1]["status"] == "missing"
