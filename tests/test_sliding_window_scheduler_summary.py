from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "src" / "sliding_window_scheduler.py"


def load_scheduler_module():
    spec = importlib.util.spec_from_file_location("sliding_window_scheduler", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["sliding_window_scheduler"] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_export(path: Path) -> None:
    write_json(
        path,
        {
            "meta": {
                "database": "web_logs",
                "query_timezone": "Asia/Seoul",
                "start": "2026-05-23T09:00:00.000+09:00",
                "end_exclusive": "2026-05-23T10:00:00.000+09:00",
                "table_option": "security",
                "total_count": 2,
            },
            "counts": {"access": 0, "security": 2, "error": 0},
            "data": {"security": []},
        },
    )


def write_prepare_outputs(window_dir: Path) -> None:
    write_json(
        window_dir / "llm_input.json",
        {
            "meta": {
                "query_timezone": "Asia/Seoul",
                "analysis_window": {
                    "start": "2026-05-23T09:00:00.000+09:00",
                    "end_exclusive": "2026-05-23T10:00:00.000+09:00",
                },
                "source_database": "web_logs",
                "source_table_option": "security",
                "selected_source_tables": ["security"],
                "analysis_primary_table": "security",
                "counts": {
                    "total_exported_rows": 2,
                    "selected_source_rows": 2,
                    "filtered_out_rows": 1,
                    "candidate_rows_before_dedup": 1,
                    "candidate_rows": 1,
                    "candidate_duplicate_rows_removed": 0,
                    "distinct_incident_candidates": 1,
                    "noise_group_count": 0,
                    "supporting_events": 0,
                    "ip_behavior_aggregates": 1,
                },
                "filtered_out_breakdown": {"benign_normal_search": 1},
            }
        },
    )
    write_json(
        window_dir / "analysis_candidates.json",
        [
            {
                "request_id": "rid-1",
                "src_ip": "192.168.56.1",
                "method": "POST",
                "uri": "/login.php",
                "status_code": 401,
                "score": 6,
                "verdict_hint": "suspicious",
                "reason_hints": ["error_status:401(+2)", "error_linked(+2)"],
                "raw_log": "must not be copied",
            }
        ],
    )
    write_json(window_dir / "noise_summary.json", [])


def build_args(tmp_path: Path, *extra: str):
    module = load_scheduler_module()
    args = module.parse_args(
        [
            "--work-dir",
            str(tmp_path),
            "--analysis-start",
            "2026-05-23 09:00:00",
            "--analysis-end",
            "2026-05-23 10:00:00",
            "--window-minutes",
            "60",
            "--stride-minutes",
            "60",
            "--mode",
            "prepare",
            *extra,
        ]
    )
    return module, args


def make_scripts_dir(tmp_path: Path) -> Path:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "prepare_llm_input.py").write_text("# fake prepare\n", encoding="utf-8")
    return scripts_dir


def test_prepare_mode_writes_window_summary_after_prepare_success(tmp_path: Path, monkeypatch):
    module, args = build_args(tmp_path)
    args.scripts_dir = str(make_scripts_dir(tmp_path))
    plan = module.build_plan(args)

    window_dir = tmp_path / "data/windowed/2026-05-23/sw_0900_1000"
    write_export(window_dir / "export.json")

    def fake_run(cmd, cwd, text, capture_output, check):
        out_dir = Path(cmd[cmd.index("--out-dir") + 1])
        write_prepare_outputs(out_dir)
        return subprocess.CompletedProcess(cmd, 0, stdout="[OK] fake prepare\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    summary = module.run_prepare_mode(args, plan)

    assert summary["prepared_count"] == 1
    assert summary["summary_written_count"] == 1
    assert summary["summary_failed_count"] == 0

    window_summary_path = window_dir / "window_summary.json"
    assert window_summary_path.exists()
    payload = json.loads(window_summary_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "sliding_window_summary_v1"
    assert payload["counts"]["export"] == {"access": 0, "security": 2, "error": 0, "total": 2}
    assert payload["counts"]["prepare"]["candidate_rows"] == 1
    assert payload["rollup_hints"]["candidate_request_ids"] == ["rid-1"]
    assert "raw_log" not in repr(payload["candidate_index"])


def test_prepare_mode_skipped_existing_writes_missing_window_summary(tmp_path: Path):
    module, args = build_args(tmp_path)
    args.scripts_dir = str(make_scripts_dir(tmp_path))
    plan = module.build_plan(args)

    window_dir = tmp_path / "data/windowed/2026-05-23/sw_0900_1000"
    write_export(window_dir / "export.json")
    write_prepare_outputs(window_dir)

    summary = module.run_prepare_mode(args, plan)

    assert summary["prepared_count"] == 0
    assert summary["skipped_existing_count"] == 1
    assert summary["summary_written_count"] == 1
    assert (window_dir / "window_summary.json").exists()


def test_prepare_mode_skips_existing_window_summary_when_present(tmp_path: Path):
    module, args = build_args(tmp_path)
    args.scripts_dir = str(make_scripts_dir(tmp_path))
    plan = module.build_plan(args)

    window_dir = tmp_path / "data/windowed/2026-05-23/sw_0900_1000"
    write_export(window_dir / "export.json")
    write_prepare_outputs(window_dir)
    write_json(window_dir / "window_summary.json", {"schema": "existing"})

    summary = module.run_prepare_mode(args, plan)

    assert summary["skipped_existing_count"] == 1
    assert summary["summary_written_count"] == 0
    assert summary["summary_skipped_existing_count"] == 1
    payload = json.loads((window_dir / "window_summary.json").read_text(encoding="utf-8"))
    assert payload == {"schema": "existing"}
