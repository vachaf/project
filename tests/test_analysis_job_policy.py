from __future__ import annotations

import pytest

from web.services.analysis_job_policy import (
    AnalysisJobValidationError,
    build_job_artifact_root,
    redact_secret_text,
    validate_analysis_job_request,
    validate_relative_artifact_path,
)


def test_validate_analysis_job_request_converts_kst_to_utc_db_strings() -> None:
    request = validate_analysis_job_request(
        time_from="2026-05-28 18:30:00.123",
        time_to="2026-05-28 19:45:00.456",
    )

    assert request.requested_timezone == "Asia/Seoul"
    assert request.analysis_mode == "full_report"
    assert request.time_from_db == "2026-05-28 09:30:00.123"
    assert request.time_to_db == "2026-05-28 10:45:00.456"
    assert request.to_insert_params(requested_by=7, artifact_root="runs/jobs/7") == {
        "requested_by": 7,
        "time_from": "2026-05-28 09:30:00.123",
        "time_to": "2026-05-28 10:45:00.456",
        "requested_timezone": "Asia/Seoul",
        "status": "PENDING",
        "analysis_mode": "full_report",
        "artifact_root": "runs/jobs/7",
    }
    assert request.duplicate_key(requested_by=7) == (
        7,
        "full_report",
        "2026-05-28 09:30:00.123",
        "2026-05-28 10:45:00.456",
        "Asia/Seoul",
    )


def test_validate_analysis_job_request_accepts_aware_input_and_normalizes_to_kst_policy() -> None:
    request = validate_analysis_job_request(
        time_from="2026-05-28T09:30:00+00:00",
        time_to="2026-05-28T10:00:00+00:00",
    )

    assert request.time_from_local.isoformat() == "2026-05-28T18:30:00+09:00"
    assert request.time_from_db == "2026-05-28 09:30:00.000"
    assert request.time_to_db == "2026-05-28 10:00:00.000"


@pytest.mark.parametrize(
    "time_from,time_to,expected_code",
    [
        ("2026-05-28 10:00:00", "2026-05-28 10:00:00", "invalid_time_range"),
        ("2026-05-28 11:00:00", "2026-05-28 10:00:00", "invalid_time_range"),
        ("2026-05-28 00:00:00", "2026-05-29 00:00:01", "time_range_too_large"),
    ],
)
def test_validate_analysis_job_request_rejects_invalid_time_ranges(
    time_from: str,
    time_to: str,
    expected_code: str,
) -> None:
    with pytest.raises(AnalysisJobValidationError) as exc:
        validate_analysis_job_request(time_from=time_from, time_to=time_to)

    assert exc.value.code == expected_code


def test_validate_analysis_job_request_rejects_unsupported_timezone_and_mode() -> None:
    with pytest.raises(AnalysisJobValidationError) as timezone_exc:
        validate_analysis_job_request(
            time_from="2026-05-28 10:00:00",
            time_to="2026-05-28 11:00:00",
            requested_timezone="UTC",
        )
    assert timezone_exc.value.code == "unsupported_timezone"

    with pytest.raises(AnalysisJobValidationError) as mode_exc:
        validate_analysis_job_request(
            time_from="2026-05-28 10:00:00",
            time_to="2026-05-28 11:00:00",
            analysis_mode="operator_queue_only",
        )
    assert mode_exc.value.code == "unsupported_analysis_mode"


def test_redact_secret_text_masks_common_provider_secret_shapes() -> None:
    text = (
        "Authorization: Bearer sk-test-secret-value "
        "api_key=abc123 token='tok_456' secret=mysecret x-api-key: xyz789"
    )

    redacted = redact_secret_text(text)

    assert "sk-test-secret-value" not in redacted
    assert "abc123" not in redacted
    assert "tok_456" not in redacted
    assert "mysecret" not in redacted
    assert "xyz789" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_secret_text_truncates_long_messages() -> None:
    redacted = redact_secret_text("a" * 50, max_length=10)

    assert redacted == "aaaaaaa..."


def test_build_job_artifact_root_is_job_scoped_and_relative() -> None:
    assert build_job_artifact_root(42) == "runs/jobs/42"
    assert build_job_artifact_root(42, prefix="runs/web_job") == "runs/web_job/42"


@pytest.mark.parametrize("path_value", ["/tmp/out", "../runs/jobs/1", "runs/../jobs/1", ""])
def test_validate_relative_artifact_path_rejects_absolute_or_traversal(path_value: str) -> None:
    with pytest.raises(AnalysisJobValidationError) as exc:
        validate_relative_artifact_path(path_value)

    assert exc.value.code == "invalid_artifact_path"


def test_validate_relative_artifact_path_normalizes_backslashes() -> None:
    assert validate_relative_artifact_path("runs\\jobs\\1") == "runs/jobs/1"
