from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "src" / "sliding_window_scheduler.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sliding_window_scheduler", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None

    # dataclasses가 모듈의 __dict__를 조회할 수 있도록 sys.modules에 강제로 등록
    sys.modules["sliding_window_scheduler"] = module

    spec.loader.exec_module(module)
    return module


def build_args(tmp_path: Path, *extra_args: str):
    module = load_module()
    args = module.parse_args(
        [
            "--work-dir",
            str(tmp_path),
            "--analysis-start",
            "2026-05-23 09:00:00",
            "--analysis-end",
            "2026-05-23 11:00:00",
            *extra_args,
        ]
    )
    return module, args


def build_plan(tmp_path: Path, *extra_args: str):
    module, args = build_args(tmp_path, *extra_args)
    return module.build_plan(args)


def test_one_hour_windows_resolve_to_windowed_paths(tmp_path: Path):
    plan = build_plan(
        tmp_path,
        "--window-minutes",
        "60",
        "--stride-minutes",
        "60",
    )

    assert plan["meta"]["total_windows"] == 2
    assert plan["meta"]["window_output_root"] == "data/windowed"
    assert plan["meta"]["rollup_output_root"] == "data/rollups"
    assert plan["meta"]["runs_dir_policy"] == "do_not_create_runs_for_window_prepare"

    first, second = plan["windows"]
    assert first["window_id"] == "sw_0900_1000"
    assert first["window_dir"] == "data/windowed/2026-05-23/sw_0900_1000"
    assert first["export_path"] == "data/windowed/2026-05-23/sw_0900_1000/export.json"
    assert first["prepared_dir"] == "data/windowed/2026-05-23/sw_0900_1000/prepared"
    assert first["llm_input_path"] == "data/windowed/2026-05-23/sw_0900_1000/llm_input.json"
    assert first["analysis_candidates_path"] == "data/windowed/2026-05-23/sw_0900_1000/analysis_candidates.json"
    assert first["noise_summary_path"] == "data/windowed/2026-05-23/sw_0900_1000/noise_summary.json"
    assert first["window_summary_path"] == "data/windowed/2026-05-23/sw_0900_1000/window_summary.json"
    assert first["is_partial"] is False

    assert second["window_id"] == "sw_1000_1100"
    assert second["window_dir"] == "data/windowed/2026-05-23/sw_1000_1100"


def test_twenty_minute_windows_exclude_partial_final_by_default(tmp_path: Path):
    plan = build_plan(
        tmp_path,
        "--window-minutes",
        "20",
        "--stride-minutes",
        "15",
    )

    assert plan["meta"]["total_windows"] == 7
    assert plan["meta"]["include_partial_final"] is False
    assert [item["window_id"] for item in plan["windows"]] == [
        "sw_0900_0920",
        "sw_0915_0935",
        "sw_0930_0950",
        "sw_0945_1005",
        "sw_1000_1020",
        "sw_1015_1035",
        "sw_1030_1050",
    ]
    assert all(item["is_partial"] is False for item in plan["windows"])


def test_twenty_minute_windows_include_partial_final_when_requested(tmp_path: Path):
    plan = build_plan(
        tmp_path,
        "--window-minutes",
        "20",
        "--stride-minutes",
        "15",
        "--include-partial-final",
    )

    assert plan["meta"]["total_windows"] == 8
    assert plan["meta"]["include_partial_final"] is True

    last = plan["windows"][-1]
    assert last["window_id"] == "sw_1045_1100"
    assert last["start"] == "2026-05-23T10:45:00+09:00"
    assert last["end"] == "2026-05-23T11:00:00+09:00"
    assert last["duration_minutes"] == 15
    assert last["is_partial"] is True


def test_rollup_and_window_roots_can_be_overridden(tmp_path: Path):
    plan = build_plan(
        tmp_path,
        "--window-minutes",
        "60",
        "--stride-minutes",
        "60",
        "--window-output-root",
        "tmp/windowed",
        "--rollup-output-root",
        "tmp/rollups",
    )

    assert plan["meta"]["window_output_root"] == "tmp/windowed"
    assert plan["meta"]["rollup_output_root"] == "tmp/rollups"
    assert plan["windows"][0]["window_dir"] == "tmp/windowed/2026-05-23/sw_0900_1000"


def test_window_prepare_plan_does_not_reference_runs_directory(tmp_path: Path):
    plan = build_plan(
        tmp_path,
        "--window-minutes",
        "60",
        "--stride-minutes",
        "60",
    )

    serialized = repr(plan)
    assert "runs/" not in serialized
    assert "runs_dir_policy" in plan["meta"]


def test_export_mode_builds_export_commands_without_runs_dir(tmp_path: Path, monkeypatch):
    module, args = build_args(
        tmp_path,
        "--window-minutes",
        "60",
        "--stride-minutes",
        "60",
        "--mode",
        "export",
        "--table",
        "security",
        "--export-pretty",
    )
    plan = module.build_plan(args)

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    export_script = scripts_dir / "export_db_logs_cli.py"
    export_script.write_text("# fake export script\n", encoding="utf-8")
    args.scripts_dir = str(scripts_dir)

    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append({
            "cmd": cmd,
            "cwd": cwd,
            "text": text,
            "capture_output": capture_output,
            "check": check,
        })
        # Simulate export_db_logs_cli.py creating the requested file.
        out_path = Path(cmd[cmd.index("--out") + 1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text('{"meta":{"table_option":"security"},"data":{"security":[]}}', encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="[OK] fake export\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    summary = module.run_export_mode(args, plan)

    assert summary["exported_count"] == 2
    assert summary["skipped_existing_count"] == 0
    assert summary["failed_count"] == 0
    assert len(calls) == 2

    first_cmd = calls[0]["cmd"]
    assert first_cmd[:2] == [sys.executable, str(export_script)]
    assert first_cmd[first_cmd.index("--start") + 1] == "2026-05-23 09:00:00"
    assert first_cmd[first_cmd.index("--end") + 1] == "2026-05-23 10:00:00"
    assert first_cmd[first_cmd.index("--table") + 1] == "security"
    assert first_cmd[first_cmd.index("--out") + 1] == str(tmp_path / "data/windowed/2026-05-23/sw_0900_1000/export.json")
    assert "--pretty" in first_cmd

    assert calls[0]["cwd"] == str(tmp_path)
    assert "runs/" not in repr(summary)


def test_export_mode_skips_existing_export_without_overwrite(tmp_path: Path):
    module, args = build_args(
        tmp_path,
        "--window-minutes",
        "60",
        "--stride-minutes",
        "60",
        "--mode",
        "export",
    )
    plan = module.build_plan(args)

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "export_db_logs_cli.py").write_text("# fake export script\n", encoding="utf-8")
    args.scripts_dir = str(scripts_dir)

    existing = tmp_path / "data/windowed/2026-05-23/sw_0900_1000/export.json"
    existing.parent.mkdir(parents=True)
    existing.write_text("{}", encoding="utf-8")

    summary = module.run_export_mode(args, plan)

    assert summary["exported_count"] == 1
    assert summary["skipped_existing_count"] == 1
    assert summary["failed_count"] == 0
    assert summary["results"][0]["status"] == "skipped_existing"
    assert summary["results"][1]["status"] == "exported"


def test_export_mode_reports_failure_and_stops_by_default(tmp_path: Path, monkeypatch):
    module, args = build_args(
        tmp_path,
        "--window-minutes",
        "60",
        "--stride-minutes",
        "60",
        "--mode",
        "export",
    )
    plan = module.build_plan(args)

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "export_db_logs_cli.py").write_text("# fake export script\n", encoding="utf-8")
    args.scripts_dir = str(scripts_dir)

    calls = []

    def fake_run(cmd, cwd, text, capture_output, check):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 7, stdout="", stderr="boom\n")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    summary = module.run_export_mode(args, plan)

    assert summary["exported_count"] == 0
    assert summary["failed_count"] == 1
    assert summary["first_error_return_code"] == 7
    assert len(calls) == 1
