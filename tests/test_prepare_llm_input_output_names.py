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


def write_filtered_reasons_fixture(tmp_path: Path) -> Path:
    export_path = tmp_path / "filtered_source.json"
    payload = {
        "meta": {
            "table_option": "all",
            "start": "2026-05-23T09:00:00.000+09:00",
            "end_exclusive": "2026-05-23T10:00:00.000+09:00",
            "query_timezone": "Asia/Seoul",
            "database": "test",
            "total_count": 4,
            "exported_at": "2026-05-23T10:00:00.000+09:00",
        },
        "counts": {"access": 2, "security": 2, "error": 0},
        "data": {
            "access": [
                {
                    "id": 1,
                    "request_id": "req_static",
                    "log_time": "2026-05-23T09:01:00.000+09:00",
                    "src_ip": "203.0.113.10",
                    "method": "GET",
                    "uri": "/static/app.js",
                    "query_string": "",
                    "status_code": 200,
                    "user_agent": "Mozilla/5.0",
                },
                {
                    "id": 2,
                    "request_id": "req_low_signal",
                    "log_time": "2026-05-23T09:02:00.000+09:00",
                    "src_ip": "203.0.113.11",
                    "method": "GET",
                    "uri": "/nothing",
                    "query_string": "",
                    "status_code": 200,
                    "user_agent": "curl/8.0",
                },
            ],
            "security": [
                {
                    "id": 3,
                    "request_id": "req_sqli",
                    "log_time": "2026-05-23T09:03:00.000+09:00",
                    "src_ip": "203.0.113.12",
                    "method": "GET",
                    "uri": "/search",
                    "query_string": "q=' OR 1=1--",
                    "status_code": 403,
                    "user_agent": "sqlmap",
                },
                {
                    "id": 4,
                    "request_id": "req_browser_query",
                    "log_time": "2026-05-23T09:04:00.000+09:00",
                    "src_ip": "203.0.113.13",
                    "method": "GET",
                    "uri": "/search",
                    "query_string": "q=shoes",
                    "status_code": 200,
                    "user_agent": "Mozilla/5.0",
                },
            ],
        },
    }
    export_path.write_text(json.dumps(payload), encoding="utf-8")
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


def run_prepare_with_input(tmp_path: Path, export_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
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
    assert (out_dir / "export_filtered_reasons.json").exists()


def test_base_name_overrides_output_prefix(tmp_path: Path) -> None:
    completed = run_prepare(tmp_path, "--base-name", "window")
    assert completed.returncode == 0, completed.stderr

    out_dir = tmp_path / "out"
    assert (out_dir / "window_llm_input.json").exists()
    assert (out_dir / "window_analysis_candidates.json").exists()
    assert (out_dir / "window_noise_summary.json").exists()
    assert (out_dir / "window_filtered_reasons.json").exists()


def test_flat_output_names_write_standard_files(tmp_path: Path) -> None:
    completed = run_prepare(tmp_path, "--flat-output-names", "--write-filtered-out")
    assert completed.returncode == 0, completed.stderr

    out_dir = tmp_path / "out"
    assert (out_dir / "llm_input.json").exists()
    assert (out_dir / "analysis_candidates.json").exists()
    assert (out_dir / "noise_summary.json").exists()
    assert (out_dir / "filtered_reasons.json").exists()
    assert (out_dir / "filtered_out_rows.json").exists()
    assert not (out_dir / "export_llm_input.json").exists()


def test_flat_output_names_rejects_base_name(tmp_path: Path) -> None:
    completed = run_prepare(tmp_path, "--flat-output-names", "--base-name", "window")
    assert completed.returncode != 0
    assert "--flat-output-names" in completed.stderr
    assert "--base-name" in completed.stderr


def test_filtered_reasons_artifact_records_conservative_exclusion_reasons(tmp_path: Path) -> None:
    export_path = write_filtered_reasons_fixture(tmp_path)
    completed = run_prepare_with_input(
        tmp_path,
        export_path,
        "--include-source-tables",
        "access,security",
        "--pretty",
    )
    assert completed.returncode == 0, completed.stderr

    out_dir = tmp_path / "out"
    payload = json.loads((out_dir / "filtered_source_filtered_reasons.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == "filtered_reasons.v1"
    assert payload["total_rows"] == 4
    assert payload["candidate_count"] == 1
    assert payload["excluded_count"] == 3
    assert payload["excluded_summary"] == {
        "known_baseline_like": 1,
        "low_signal_request": 1,
        "static_asset_like": 1,
    }
    assert payload["meta"]["excluded_sample_limit"] == 500
    assert payload["meta"]["excluded_truncated"] is False
    assert "candidate_excluded_does_not_mean_benign" in payload["guardrails"]
    assert "apache_logs_only_no_success_inference" in payload["guardrails"]

    by_id = {row["request_id"]: row for row in payload["excluded"]}
    assert by_id["req_static"]["reason"] == "static_asset_like"
    assert by_id["req_static"]["reason_detail"] == "static extension or asset path pattern"
    assert by_id["req_static"]["uri"] == "/static/app.js"
    assert by_id["req_low_signal"]["reason"] == "low_signal_request"
    assert "req_sqli" not in by_id

    disallowed_terms = ("normal", "benign", "attack_failed", "success")
    for row in payload["excluded"]:
        reason_text = f"{row['reason']} {row['reason_detail']}".lower()
        for term in disallowed_terms:
            assert term not in reason_text
