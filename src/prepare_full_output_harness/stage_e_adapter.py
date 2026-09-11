"""Parent-side adapter for one isolated Stage E Prepare-before capture."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from .isolation import build_isolated_environment
from .stage_e_contract import BeforeCaptureRequest, CHILD_PROTOCOL_VERSION


class StageEAdapterError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


RunProcess = Callable[..., subprocess.CompletedProcess[str]]


def capture_before(
    request: BeforeCaptureRequest,
    *,
    verification_root: str | Path,
    run_process: RunProcess = subprocess.run,
) -> dict[str, Any]:
    """Run exactly one capture child and validate its data-only response envelope."""

    root = Path(verification_root).resolve(strict=True)
    child = root / "scripts" / "prepare_before_capture_child.py"
    if not child.is_file():
        raise StageEAdapterError("child_missing", "capture child script is missing")
    with tempfile.TemporaryDirectory(prefix="prepare-stage-e-") as cache:
        environment = build_isolated_environment(Path(cache).resolve())
        completed = run_process(
            [sys.executable, "-I", str(child)],
            input=request.to_json(),
            text=True,
            capture_output=True,
            env=environment,
            cwd=str(root),
            check=False,
        )
    if completed.returncode != 0:
        raise StageEAdapterError("child_failed", "capture child failed without exposing payload data")
    try:
        response = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise StageEAdapterError("invalid_child_response", "capture child returned invalid JSON") from exc
    if not isinstance(response, dict) or response.get("protocol_version") != CHILD_PROTOCOL_VERSION:
        raise StageEAdapterError("protocol_mismatch", "capture child protocol does not match")
    if response.get("run_role") != request.run_role.value:
        raise StageEAdapterError("run_role_mismatch", "capture child run role does not match")
    if response.get("status") != "returned":
        raise StageEAdapterError("prepare_raised", "Prepare capture raised an exception")
    return response
