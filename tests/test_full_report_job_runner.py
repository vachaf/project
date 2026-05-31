from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pytest

from full_report_job_runner import FullReportJobRunner, FullReportRunnerError


def make_job(**overrides: Any) -> dict[str, Any]:
    job = {
        "id": 123,
        "time_from": datetime(2026, 5, 30, 0, 0, 0),
        "time_to": datetime(2026, 5, 30, 1, 30, 0),
        "requested_timezone": "Asia/Seoul",
        "artifact_root": "runs/jobs/123",
        "analysis_mode": "full_report",
    }
    job.update(overrides)
    return job


def option_value(cmd: list[str], option: str) -> str:
    return cmd[cmd.index(option) + 1]


class FakeSubprocess:
    def __init__(self, *, fail_step: Optional[str] = None, write_candidates: bool = False) -> None:
        self.fail_step = fail_step
        self.write_candidates = write_candidates
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((cmd, kwargs))
        script_name = Path(cmd[1]).name
        if script_name == "export_db_logs_cli.py":
            if self.fail_step == "export":
                return subprocess.CompletedProcess(cmd, 7, stdout="export out", stderr="export err")
            Path(option_value(cmd, "--out")).parent.mkdir(parents=True, exist_ok=True)
            Path(option_value(cmd, "--out")).write_text('{"ok": true}\n', encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="export ok", stderr="")

        if script_name == "run_analysis_pipeline.py":
            if self.fail_step == "pipeline":
                return subprocess.CompletedProcess(cmd, 8, stdout="pipeline out", stderr="pipeline err")
            run_dir = Path(option_value(cmd, "--run-dir"))
            run_dir.mkdir(parents=True, exist_ok=False)
            for filename in (
                "export.json",
                "llm_input.json",
                "noise_summary.json",
                "stage1_results.json",
                "stage2_report.json",
                "stage2_report.md",
                "viewer_payload.json",
                "manifest.json",
            ):
                (run_dir / filename).write_text("{}\n", encoding="utf-8")
            if self.write_candidates:
                processed_dir = Path(option_value(cmd, "--work-dir")) / "data" / "processed"
                processed_dir.mkdir(parents=True, exist_ok=True)
                (processed_dir / "job_123_analysis_candidates.json").write_text("{}\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="pipeline ok", stderr="")

        raise AssertionError(f"unexpected command: {cmd}")


def test_run_converts_utc_naive_times_to_kst_for_export_command(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    runner.run(make_job())

    export_cmd = fake.calls[0][0]
    assert option_value(export_cmd, "--start") == "2026-05-30 09:00:00"
    assert option_value(export_cmd, "--end") == "2026-05-30 10:30:00"


def test_export_command_uses_expected_cli_contract(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    runner.run(make_job())

    export_cmd = fake.calls[0][0]
    assert export_cmd[0]
    assert export_cmd[1].endswith("src/export_db_logs_cli.py")
    assert option_value(export_cmd, "--table") == "security"
    assert "--pretty" in export_cmd
    assert option_value(export_cmd, "--out").endswith("runs/jobs/.scratch/job_123/job_123_export.json")


def test_pipeline_command_uses_expected_direct_cli_contract(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    runner.run(make_job())

    pipeline_cmd = fake.calls[1][0]
    assert pipeline_cmd[1].endswith("src/run_analysis_pipeline.py")
    assert option_value(pipeline_cmd, "--export-input").endswith("job_123_export.json")
    assert option_value(pipeline_cmd, "--work-dir").endswith("runs/jobs/.scratch/job_123/work")
    assert option_value(pipeline_cmd, "--base-name") == "job_123"
    assert option_value(pipeline_cmd, "--run-dir") == str((tmp_path / "runs/jobs/123").resolve())
    assert option_value(pipeline_cmd, "--mode") == "routine"
    assert "--pretty" in pipeline_cmd
    assert "--dry-run" not in pipeline_cmd


def test_pipeline_dry_run_adds_dry_run_to_pipeline_command_only(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, pipeline_dry_run=True, subprocess_run=fake)

    runner.run(make_job())

    export_cmd = fake.calls[0][0]
    pipeline_cmd = fake.calls[1][0]
    assert "--dry-run" not in export_cmd
    assert "--dry-run" in pipeline_cmd


def test_pipeline_dry_run_false_does_not_add_dry_run(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, pipeline_dry_run=False, subprocess_run=fake)

    runner.run(make_job())

    assert "--dry-run" not in fake.calls[1][0]


def test_existing_artifact_root_fails_before_subprocess(tmp_path: Path) -> None:
    (tmp_path / "runs/jobs/123").mkdir(parents=True)
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    with pytest.raises(FileExistsError):
        runner.run(make_job())

    assert fake.calls == []


def test_export_failure_raises_runner_error(tmp_path: Path) -> None:
    fake = FakeSubprocess(fail_step="export")
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    with pytest.raises(FullReportRunnerError) as exc:
        runner.run(make_job())

    assert "export command failed rc=7" in str(exc.value)
    assert len(fake.calls) == 1


def test_pipeline_failure_raises_runner_error(tmp_path: Path) -> None:
    fake = FakeSubprocess(fail_step="pipeline")
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    with pytest.raises(FullReportRunnerError) as exc:
        runner.run(make_job())

    assert "pipeline command failed rc=8" in str(exc.value)
    assert len(fake.calls) == 2


def test_success_returns_required_artifact_mapping_without_manifest(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    result = runner.run(make_job())

    assert result.artifact_root == "runs/jobs/123"
    assert result.export_path == "runs/jobs/123/export.json"
    assert result.llm_input_path == "runs/jobs/123/llm_input.json"
    assert result.noise_summary_path == "runs/jobs/123/noise_summary.json"
    assert result.stage1_result_path == "runs/jobs/123/stage1_results.json"
    assert result.stage2_report_path == "runs/jobs/123/stage2_report.json"
    assert result.stage2_report_md_path == "runs/jobs/123/stage2_report.md"
    assert result.viewer_payload_path == "runs/jobs/123/viewer_payload.json"
    assert result.lint_result_path is None
    assert not hasattr(result, "manifest_path")


def test_window_rollup_operator_paths_are_none_by_default(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    result = runner.run(make_job())

    assert result.window_summary_path is None
    assert result.rollup_input_path is None
    assert result.rollup_summary_path is None
    assert result.operator_queue_items_path is None
    assert result.operator_queue_summary_path is None


def test_analysis_candidates_path_is_none_unless_existing_in_scratch_work_dir(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    result = runner.run(make_job())

    assert result.analysis_candidates_path is None


def test_analysis_candidates_path_is_returned_when_pipeline_leaves_flat_file(tmp_path: Path) -> None:
    fake = FakeSubprocess(write_candidates=True)
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=fake)

    result = runner.run(make_job())

    assert result.analysis_candidates_path == "runs/jobs/.scratch/job_123/work/data/processed/job_123_analysis_candidates.json"


def test_requested_timezone_must_be_asia_seoul(tmp_path: Path) -> None:
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=FakeSubprocess())

    with pytest.raises(ValueError, match="unsupported requested_timezone"):
        runner.run(make_job(requested_timezone="UTC"))


def test_analysis_mode_must_be_full_report(tmp_path: Path) -> None:
    runner = FullReportJobRunner(project_root=tmp_path, subprocess_run=FakeSubprocess())

    with pytest.raises(ValueError, match="unsupported analysis_mode"):
        runner.run(make_job(analysis_mode="windowed_triage"))


def test_env_and_timeout_are_passed_to_subprocess(tmp_path: Path) -> None:
    fake = FakeSubprocess()
    runner = FullReportJobRunner(
        project_root=tmp_path,
        timeout_seconds=123,
        env={"RUNNER_TEST_VALUE": "yes"},
        subprocess_run=fake,
    )

    runner.run(make_job())

    for _, kwargs in fake.calls:
        assert kwargs["timeout"] == 123
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["check"] is False
        assert kwargs["env"]["RUNNER_TEST_VALUE"] == "yes"
