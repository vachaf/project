"""Contracts for deterministic child-process capture isolation.

This module defines requests and scoped helpers only.  It never starts a
process or imports the production Prepare module.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, tzinfo
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Iterator
from zoneinfo import ZoneInfo

from .compare import GateStatus
from .identity import require_sha256_digest, sha256_file


FIXED_INSTANT = "2026-01-01T00:00:00+09:00"
PROCESS_TIMEZONE = "Asia/Seoul"
_FIXED_AWARE = datetime.fromisoformat(FIXED_INSTANT)


class IsolationError(RuntimeError):
    """Raised when isolation or source-origin evidence violates the contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RunRole(str, Enum):
    """Required independent process roles."""

    BEFORE_1 = "before-1"
    BEFORE_2 = "before-2"
    AFTER = "after"


@dataclass(frozen=True)
class ChildProcessRequest:
    """Data-only capture request with no pipeline or external-service actions."""

    run_role: RunRole
    source_root: str
    module_name: str
    expected_module_file: str
    expected_source_sha256: str
    corpus_id: str
    case_id: str
    parameter_id: str
    fixed_instant: str = FIXED_INSTANT
    timezone_name: str = PROCESS_TIMEZONE

    def __post_init__(self) -> None:
        required = (
            self.source_root,
            self.module_name,
            self.expected_module_file,
            self.expected_source_sha256,
            self.corpus_id,
            self.case_id,
            self.parameter_id,
        )
        if any(not value for value in required):
            raise IsolationError("invalid_request", "child-process request fields are required")
        require_sha256_digest("expected_source_sha256", self.expected_source_sha256)
        if self.fixed_instant != FIXED_INSTANT or self.timezone_name != PROCESS_TIMEZONE:
            raise IsolationError("clock_contract_mismatch", "fixed clock contract does not match")


@dataclass(frozen=True)
class ChildProcessResponse:
    """Raw-free response envelope; payload transfer is an artifact-layer concern."""

    status: GateStatus
    run_role: RunRole
    corpus_id: str
    case_id: str
    parameter_id: str
    error_code: str | None = None


def validate_independent_requests(requests: tuple[ChildProcessRequest, ...]) -> None:
    """Require before-1, before-2, and after to use distinct source roots."""

    if {request.run_role for request in requests} != set(RunRole):
        raise IsolationError("missing_run_role", "all three independent run roles are required")
    resolved_roots = [Path(request.source_root).resolve(strict=False) for request in requests]
    if len(set(resolved_roots)) != len(resolved_roots):
        raise IsolationError("shared_source_root", "run roles must use separate source roots")


def validate_import_origin(
    module: ModuleType,
    *,
    expected_file: str | Path,
    expected_sha256: str,
) -> None:
    """Verify imported module origin and bytes against approved evidence."""

    require_sha256_digest("expected_source_sha256", expected_sha256)
    origin = getattr(module, "__file__", None)
    if not origin:
        raise IsolationError("import_origin_missing", "imported module has no file origin")
    actual_path = Path(origin).resolve(strict=True)
    required_path = Path(expected_file).resolve(strict=True)
    if actual_path != required_path:
        raise IsolationError("import_origin_mismatch", "imported module origin does not match")
    if sha256_file(actual_path) != expected_sha256:
        raise IsolationError("source_sha256_mismatch", "imported module source digest does not match")


class FixedDateTime(datetime):
    """Datetime shim preserving distinct naive and timezone-aware now contracts."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "FixedDateTime":
        if tz is None:
            value = _FIXED_AWARE.astimezone(ZoneInfo(PROCESS_TIMEZONE)).replace(tzinfo=None)
        else:
            value = _FIXED_AWARE.astimezone(tz)
        return cls(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            tzinfo=value.tzinfo,
            fold=value.fold,
        )


@contextmanager
def patched_prepare_datetime(module: ModuleType) -> Iterator[None]:
    """Patch only a supplied process-local Prepare module and always restore it."""

    if not hasattr(module, "datetime"):
        raise IsolationError("datetime_target_missing", "target module has no datetime attribute")
    original = module.datetime
    module.datetime = FixedDateTime
    try:
        yield
    finally:
        module.datetime = original


def build_isolated_environment(cache_root: str | Path) -> dict[str, str]:
    """Build a minimal environment that redirects bytecode and caches off source."""

    root = Path(cache_root)
    if not root.is_absolute():
        raise IsolationError("cache_root_not_absolute", "cache root must be absolute")
    return {
        "PATH": os.defpath,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(root / "pycache"),
        "TMPDIR": str(root / "tmp"),
        "TZ": PROCESS_TIMEZONE,
    }
