from __future__ import annotations

from datetime import timezone
from pathlib import Path
from types import ModuleType

import pytest

from src.prepare_full_output_harness.identity import IdentityError, sha256_file
from src.prepare_full_output_harness.isolation import (
    FIXED_INSTANT,
    PROCESS_TIMEZONE,
    ChildProcessRequest,
    FixedDateTime,
    IsolationError,
    RunRole,
    patched_prepare_datetime,
    validate_import_origin,
)


def child_request(tmp_path: Path) -> ChildProcessRequest:
    source = tmp_path / "prepare_llm_input.py"
    source.write_text("# synthetic source\n", encoding="utf-8")
    return ChildProcessRequest(
        run_role=RunRole.BEFORE_1,
        source_root=str(tmp_path),
        module_name="src.prepare_llm_input",
        expected_module_file=str(source),
        expected_source_sha256=sha256_file(source),
        corpus_id="synthetic",
        case_id="case-1",
        parameter_id="default",
    )


def test_fixed_clock_distinguishes_naive_and_aware_now() -> None:
    naive = FixedDateTime.now()
    aware = FixedDateTime.now(timezone.utc)
    assert naive.tzinfo is None
    assert naive.isoformat() == "2026-01-01T00:00:00"
    assert aware.isoformat() == "2025-12-31T15:00:00+00:00"
    assert FIXED_INSTANT == "2026-01-01T00:00:00+09:00"
    assert PROCESS_TIMEZONE == "Asia/Seoul"


def test_prepare_datetime_patch_is_process_local_and_restored() -> None:
    module = ModuleType("synthetic_prepare")
    sentinel = object()
    module.datetime = sentinel
    with patched_prepare_datetime(module):
        assert module.datetime is FixedDateTime
    assert module.datetime is sentinel


def test_import_origin_mismatch_is_rejected(tmp_path: Path) -> None:
    expected = tmp_path / "expected.py"
    actual = tmp_path / "actual.py"
    expected.write_text("# expected\n", encoding="utf-8")
    actual.write_text("# actual\n", encoding="utf-8")
    module = ModuleType("synthetic_prepare")
    module.__file__ = str(actual)
    with pytest.raises(IsolationError) as raised:
        validate_import_origin(
            module,
            expected_file=expected,
            expected_sha256=sha256_file(expected),
        )
    assert raised.value.code == "import_origin_mismatch"


def test_child_process_request_has_no_forbidden_execution_fields(tmp_path: Path) -> None:
    request = child_request(tmp_path)
    forbidden = {
        "db",
        "llm",
        "network",
        "stage1",
        "mapping",
        "stage2",
        "worker",
        "job",
    }
    assert forbidden.isdisjoint(request.__dataclass_fields__)
    assert request.run_role == RunRole.BEFORE_1


def test_child_process_request_rejects_noncanonical_source_sha256(tmp_path: Path) -> None:
    request = child_request(tmp_path)
    with pytest.raises(IdentityError) as raised:
        ChildProcessRequest(
            run_role=request.run_role,
            source_root=request.source_root,
            module_name=request.module_name,
            expected_module_file=request.expected_module_file,
            expected_source_sha256="A" * 64,
            corpus_id=request.corpus_id,
            case_id=request.case_id,
            parameter_id=request.parameter_id,
        )
    assert raised.value.code == "invalid_sha256"
