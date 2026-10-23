from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.run_analysis_pipeline import build_stage1_dry_run_placeholder


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE = REPO_ROOT / "src" / "run_analysis_pipeline.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "prepare_regression" / "b_r2b_double_encoded_sqli.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_dry_run_placeholder_preserves_optional_input_scope(tmp_path: Path) -> None:
    scope = {"kind": "time_range", "window_role": "query_filter", "window": None}
    source = tmp_path / "llm_input.json"
    output = tmp_path / "stage1_results.json"
    source.write_text(json.dumps({"meta": {"input_scope": scope}, "analysis_candidates": []}), encoding="utf-8")
    build_stage1_dry_run_placeholder(source, output, pretty=False, mode="routine", selected_model=None)
    assert load_json(output)["meta"]["source_input_scope"] == scope

    source.write_text(json.dumps({"meta": {}, "analysis_candidates": []}), encoding="utf-8")
    build_stage1_dry_run_placeholder(source, output, pretty=False, mode="routine", selected_model=None)
    assert "source_input_scope" not in load_json(output)["meta"]


@pytest.mark.parametrize("kind,role", [
    ("time_range", "query_filter"),
    ("live_selected_logs", "selected_log_timestamp_envelope"),
])
def test_dry_run_pipeline_passes_scope_through_stage2_without_changing_viewer(tmp_path: Path, kind: str, role: str) -> None:
    export = load_json(FIXTURE)
    export["meta"]["input_kind"] = kind
    if kind == "live_selected_logs":
        row = export["data"]["security"][0]
        start = datetime.fromisoformat(row["log_time"])
        export["meta"]["start"] = start.isoformat(timespec="milliseconds")
        export["meta"]["end_exclusive"] = (start + timedelta(milliseconds=1)).isoformat(timespec="milliseconds")
        export["meta"]["selected_log_ids"] = [row["id"]]
        export["meta"]["input_source_table"] = "apache_security_logs"
    source = tmp_path / "export.json"
    source.write_text(json.dumps(export), encoding="utf-8")
    work_dir = tmp_path / "work"
    completed = subprocess.run([
        sys.executable, str(PIPELINE), "--export-input", str(source), "--work-dir", str(work_dir),
        "--base-name", "scope", "--dry-run", "--pretty",
    ], cwd=REPO_ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr

    prepared = load_json(work_dir / "data/processed/scope_llm_input.json")
    stage1 = load_json(work_dir / "data/processed/scope_stage1_results.json")
    stage2_input = load_json(work_dir / "reports/scope_stage2_report_input.json")
    stage2_report = load_json(work_dir / "reports/scope_stage2_report.json")
    viewer = load_json(work_dir / "reports/scope_viewer_payload.json")
    assert prepared["meta"]["input_scope"]["kind"] == kind
    assert prepared["meta"]["input_scope"]["window_role"] == role
    assert stage1["meta"]["source_input_scope"] == prepared["meta"]["input_scope"]
    assert stage2_input["analysis_context"]["input_scope"] == prepared["meta"]["input_scope"]
    assert stage2_report["meta"]["input_scope"] == prepared["meta"]["input_scope"]
    assert "input_scope" not in viewer["meta"]

    resumed_work = tmp_path / "resumed"
    resumed = subprocess.run([
        sys.executable, str(PIPELINE), "--llm-input", str(work_dir / "data/processed/scope_llm_input.json"),
        "--work-dir", str(resumed_work), "--base-name", "scope_resumed", "--dry-run", "--pretty",
    ], cwd=REPO_ROOT, text=True, capture_output=True)
    assert resumed.returncode == 0, resumed.stderr
    resumed_stage1 = load_json(resumed_work / "data/processed/scope_resumed_stage1_results.json")
    assert resumed_stage1["meta"]["source_input_scope"] == prepared["meta"]["input_scope"]
    resumed_report = load_json(resumed_work / "reports/scope_resumed_stage2_report.json")
    assert resumed_report["meta"]["input_scope"] == prepared["meta"]["input_scope"]


def test_stage1_results_resume_rejects_scope_from_another_prepare_input(tmp_path: Path) -> None:
    stage1_path = tmp_path / "mixed_stage1_results.json"
    llm_path = tmp_path / "mixed_llm_input.json"
    stage1_scope = {"kind": "live_selected_logs", "window_role": "selected_log_timestamp_envelope",
                    "window": None, "selected_id_count": 1}
    prepared_scope = {"kind": "time_range", "window_role": "query_filter", "window": None}
    stage1_path.write_text(json.dumps({"meta": {"source_input_scope": stage1_scope}, "results": []}), encoding="utf-8")
    llm_path.write_text(json.dumps({"meta": {"input_scope": prepared_scope}}), encoding="utf-8")
    work_dir = tmp_path / "work"
    completed = subprocess.run([
        sys.executable, str(PIPELINE), "--stage1-results", str(stage1_path), "--work-dir", str(work_dir),
        "--base-name", "mixed", "--dry-run",
    ], cwd=REPO_ROOT, text=True, capture_output=True)
    assert completed.returncode != 0
    assert "input scope" in completed.stderr
    assert not (work_dir / "reports/mixed_stage2_report_input.json").exists()


def run_pipeline(work_dir: Path, base_name: str, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(PIPELINE),
        "--export-input",
        str(FIXTURE),
        "--work-dir",
        str(work_dir),
        "--base-name",
        base_name,
        "--dry-run",
        "--pretty",
    ]
    cmd.extend(extra_args)
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)


def test_default_run_keeps_flat_only(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    base = "case_default"
    completed = run_pipeline(work_dir, base_name=base, extra_args=["--no-viewer-payload"])
    assert completed.returncode == 0, completed.stderr

    latest_manifest = work_dir / "pipeline_manifest.json"
    run_manifest = work_dir / "reports" / f"{base}_pipeline_manifest.json"
    assert latest_manifest.exists()
    assert run_manifest.exists()

    payload = load_json(latest_manifest)
    assert payload["run_dir_enabled"] is False
    assert payload["run_dir"] is None
    assert payload["run_id"] is None
    assert payload["run_dir_files"] == {}


def test_run_dir_creates_parallel_outputs(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    run_dir = tmp_path / "runs" / "run1"
    base = "case_run_dir"
    completed = run_pipeline(work_dir, base_name=base, extra_args=["--run-dir", str(run_dir)])
    assert completed.returncode == 0, completed.stderr

    latest_manifest = work_dir / "pipeline_manifest.json"
    run_manifest = work_dir / "reports" / f"{base}_pipeline_manifest.json"
    run_manifest_in_dir = run_dir / "manifest.json"
    assert latest_manifest.exists()
    assert run_manifest.exists()
    assert run_manifest_in_dir.exists()

    assert (work_dir / "data" / "processed" / f"{base}_llm_input.json").exists()
    assert (work_dir / "data" / "processed" / f"{base}_analysis_candidates.json").exists()
    assert (work_dir / "data" / "processed" / f"{base}_filtered_reasons.json").exists()
    assert (work_dir / "data" / "processed" / f"{base}_stage1_results.json").exists()
    assert (work_dir / "reports" / f"{base}_stage2_report_input.json").exists()
    assert (work_dir / "reports" / f"{base}_stage2_report.json").exists()
    assert (work_dir / "reports" / f"{base}_stage2_report.md").exists()
    assert (work_dir / "reports" / f"{base}_viewer_payload.json").exists()

    assert (run_dir / "export.json").exists()
    assert (run_dir / "llm_input.json").exists()
    assert (run_dir / "analysis_candidates.json").exists()
    assert (run_dir / "filtered_reasons.json").exists()
    assert (run_dir / "stage1_results.json").exists()
    assert (run_dir / "stage2_report_input.json").exists()
    assert (run_dir / "stage2_report.json").exists()
    assert (run_dir / "stage2_report.md").exists()
    assert (run_dir / "viewer_payload.json").exists()

    payload = load_json(latest_manifest)
    assert payload["run_dir_enabled"] is True
    assert payload["run_id"] == "run1"
    assert payload["run_dir"] == str(run_dir.resolve())
    assert payload["run_dir_files"]["manifest"] == str((run_dir / "manifest.json").resolve())
    assert payload["run_dir_files"]["analysis_candidates"] == str((run_dir / "analysis_candidates.json").resolve())
    assert payload["run_dir_files"]["filtered_reasons"] == str((run_dir / "filtered_reasons.json").resolve())


def test_run_dir_collision_fail_fast(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    run_dir = tmp_path / "runs" / "exists"
    run_dir.mkdir(parents=True, exist_ok=True)

    completed = run_pipeline(work_dir, base_name="case_collision", extra_args=["--run-dir", str(run_dir)])
    assert completed.returncode != 0
    assert "run_dir already exists" in completed.stderr
    assert "--overwrite is not implemented in Phase 1A." in completed.stderr
    assert not (work_dir / "pipeline_manifest.json").exists()


def test_no_viewer_payload_skips_run_dir_viewer_file(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    run_dir = tmp_path / "runs" / "no_viewer"
    base = "case_no_viewer"
    completed = run_pipeline(work_dir, base_name=base, extra_args=["--run-dir", str(run_dir), "--no-viewer-payload"])
    assert completed.returncode == 0, completed.stderr

    assert not (work_dir / "reports" / f"{base}_viewer_payload.json").exists()
    assert not (run_dir / "viewer_payload.json").exists()

    payload = load_json(work_dir / "pipeline_manifest.json")
    assert payload["meta"]["viewer_payload_enabled"] is False
    assert payload["run_dir_files"]["viewer_payload"] is None
