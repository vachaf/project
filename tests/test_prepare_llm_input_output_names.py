from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "src" / "prepare_llm_input.py"

EMPTY_EXPORT_PAYLOAD = {
    "meta": {
        "table_option": "security",
        "start": "2026-05-23T09:00:00.000+09:00",
        "end_exclusive": "2026-05-23T10:00:00.000+09:00",
        "query_timezone": "Asia/Seoul",
        "database": "test",
        "total_count": 0,
        "exported_at": "2026-05-23T10:00:00.000+09:00",
    },
    "counts": {"access": 0, "security": 0, "error": 0},
    "data": {"security": []},
}


def write_export_fixture(tmp_path: Path) -> Path:
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(EMPTY_EXPORT_PAYLOAD), encoding="utf-8")
    return export_path


def run_prepare(tmp_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    export_path = write_export_fixture(tmp_path)
    out_dir = tmp_path / "out"
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--input",
        str(export_path),
        "--out-dir",
        str(out_dir),
        *extra_args,
    ]
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)


def test_default_output_names_follow_input_stem(tmp_path: Path) -> None:
    completed = run_prepare(tmp_path)
    assert completed.returncode == 0, completed.stderr

    out_dir = tmp_path / "out"
    assert (out_dir / "export_llm_input.json").exists()
    assert (out_dir / "export_analysis_candidates.json").exists()
    assert (out_dir / "export_noise_summary.json").exists()


def test_base_name_overrides_output_prefix(tmp_path: Path) -> None:
    completed = run_prepare(tmp_path, "--base-name", "window")
    assert completed.returncode == 0, completed.stderr

    out_dir = tmp_path / "out"
    assert (out_dir / "window_llm_input.json").exists()
    assert (out_dir / "window_analysis_candidates.json").exists()
    assert (out_dir / "window_noise_summary.json").exists()


def test_flat_output_names_write_standard_files(tmp_path: Path) -> None:
    completed = run_prepare(tmp_path, "--flat-output-names", "--write-filtered-out")
    assert completed.returncode == 0, completed.stderr

    out_dir = tmp_path / "out"
    assert (out_dir / "llm_input.json").exists()
    assert (out_dir / "analysis_candidates.json").exists()
    assert (out_dir / "noise_summary.json").exists()
    assert (out_dir / "filtered_out_rows.json").exists()
    assert not (out_dir / "export_llm_input.json").exists()


def test_flat_output_names_rejects_base_name(tmp_path: Path) -> None:
    completed = run_prepare(tmp_path, "--flat-output-names", "--base-name", "window")
    assert completed.returncode != 0
    assert "--flat-output-names" in completed.stderr
    assert "--base-name" in completed.stderr
