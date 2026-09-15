from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "convert_observability_logs_to_export_json.py"
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "apache_security_io_v2_sample.log"


def run_converter(tmp_path: Path) -> dict:
    output_path = tmp_path / "security.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--security-log",
            str(FIXTURE),
            "--run-id",
            "test_v2_fixture",
            "--out",
            str(output_path),
            "--pretty",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    with output_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_v2_export_meta_and_counts(tmp_path: Path) -> None:
    payload = run_converter(tmp_path)

    assert payload["meta"]["source"] == "observability_raw_log"
    assert payload["meta"]["table_option"] == "security"
    assert payload["meta"]["run_id"] == "test_v2_fixture"
    assert payload["meta"]["log_schema"] == "apache_security_io_v2"
    assert payload["meta"]["log_schemas"] == ["apache_security_io_v2"]
    assert payload["meta"]["total_count"] == 4
    assert payload["meta"]["skipped_lines"] == 0
    assert payload["meta"]["malformed_lines"] == 0
    assert payload["counts"] == {"access": 0, "security": 4, "error": 0}
    assert payload["data"]["access"] == []
    assert payload["data"]["error"] == []


def test_v2_request_target_and_host_fields_are_preserved(tmp_path: Path) -> None:
    payload = run_converter(tmp_path)
    row = payload["data"]["security"][0]

    assert row["log_schema"] == "apache_security_io_v2"
    assert row["request_target"] == "/index.php?obs_run=obs_php_sample_v2_001&scenario=S01"
    assert row["raw_request_target"] == "/?obs_run=obs_php_sample_v2_001&scenario=S01"
    assert row["req_host"] == "apache-v2-test.local"
    assert row["host"] == "apache-v2-test.local"
    assert row["client_ip_source"] == "direct"
    assert row["method"] == "GET"
    assert row["handler"] == "application/x-httpd-php"
    assert row["status_code"] == 200


def test_v2_cookie_and_authorization_presence_flags_are_normalized(tmp_path: Path) -> None:
    payload = run_converter(tmp_path)
    rows = payload["data"]["security"]

    no_presence = rows[0]
    with_presence = rows[1]

    assert no_presence["has_cookie"] is False
    assert no_presence["has_authorization"] is False
    assert with_presence["has_cookie"] is True
    assert with_presence["has_authorization"] is True

    # Values are presence flags only. The raw sensitive header values must not be
    # emitted as first-class JSON fields.
    assert "session=test" not in json.dumps(with_presence, ensure_ascii=False)
    assert "Bearer test-token" not in json.dumps(with_presence, ensure_ascii=False)


def test_v2_traversal_like_row_preserves_request_targets(tmp_path: Path) -> None:
    payload = run_converter(tmp_path)
    row = payload["data"]["security"][2]

    assert row["uri"] == "/download.php"
    assert row["query_string"].startswith("?file=..%2F..%2F..%2Fetc%2Fpasswd")
    assert row["request_target"] == "/download.php?file=..%2F..%2F..%2Fetc%2Fpasswd&obs_run=obs_php_sample_v2_001&scenario=S15"
    assert row["raw_request_target"] == "/download.php?file=..%2F..%2F..%2Fetc%2Fpasswd&obs_run=obs_php_sample_v2_001&scenario=S15"
    assert row["status_code"] == 404
    assert row["ttfb_us"] is None


def test_v2_timeout_row_is_fallback_safe(tmp_path: Path) -> None:
    payload = run_converter(tmp_path)
    row = payload["data"]["security"][3]

    assert row["status_code"] == 408
    assert row["method"] is None
    assert row["raw_request"] is None
    assert row["request_target"] is None
    assert row["raw_request_target"] == ""
    assert row["uri"] is None
    assert row["query_string"] == ""
    assert row["ttfb_us"] is None
    assert row["in_bytes"] == 0
    assert row["out_bytes"] == 0
    assert row["has_cookie"] is False
    assert row["has_authorization"] is False
