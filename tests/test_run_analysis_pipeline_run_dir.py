from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE = REPO_ROOT / "src" / "run_analysis_pipeline.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "prepare_regression" / "b_r2b_double_encoded_sqli.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    assert (work_dir / "data" / "processed" / f"{base}_stage1_results.json").exists()
    assert (work_dir / "reports" / f"{base}_stage2_report_input.json").exists()
    assert (work_dir / "reports" / f"{base}_stage2_report.json").exists()
    assert (work_dir / "reports" / f"{base}_stage2_report.md").exists()
    assert (work_dir / "reports" / f"{base}_viewer_payload.json").exists()

    assert (run_dir / "export.json").exists()
    assert (run_dir / "llm_input.json").exists()
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
