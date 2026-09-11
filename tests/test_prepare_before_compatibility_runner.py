from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.prepare_full_output_harness.isolation import RunRole
from src.prepare_full_output_harness.stage_e_adapter import StageEAdapterError, capture_before
from src.prepare_full_output_harness.stage_e_contract import BeforeCaptureRequest, StageEIdentity, SUBJECT_REVISION


ROOT = Path(__file__).resolve().parents[1]


def request() -> BeforeCaptureRequest:
    identity = StageEIdentity(SUBJECT_REVISION, "1" * 40, "a" * 64, "b" * 64, "c" * 64)
    return BeforeCaptureRequest(RunRole.BEFORE_1, "/subject", "/input", "fixture", "case", identity)


def test_adapter_uses_isolated_child_and_accepts_returned_capture() -> None:
    calls = []
    response = {"protocol_version": "prepare_before_capture_child.v1", "status": "returned", "run_role": "before-1"}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps(response), "")

    assert capture_before(request(), verification_root=ROOT, run_process=fake_run) == response
    command, kwargs = calls[0]
    assert command[1] == "-I"
    assert kwargs["capture_output"] is True
    assert kwargs["env"]["TZ"] == "Asia/Seoul"
    assert "PYTHONPATH" not in kwargs["env"]


def test_adapter_does_not_echo_failed_child_payload() -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "raw-secret", "raw-secret")

    with pytest.raises(StageEAdapterError, match="without exposing payload data"):
        capture_before(request(), verification_root=ROOT, run_process=fake_run)


def test_child_captures_all_five_slots_with_fixed_clock(tmp_path: Path) -> None:
    payload = {"meta": {}, "data": {"security": []}}
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    # This focused test uses the current tree only as a synthetic subject.  It
    # invokes the child directly, not the canonical Before runner.
    from scripts.prepare_before_capture_child import execute
    from src.prepare_full_output_harness.stage_e_contract import source_tree_digest

    req = request().as_dict()
    req["subject_root"] = str(ROOT)
    req["input_path"] = str(input_path)
    req["identity"]["source_tree_digest"] = source_tree_digest(ROOT)
    result = execute(req)
    assert result["input_mutated"] is False
    assert result["return_value"]["type"] == "tuple"
    assert len(result["return_value"]["items"]) == 5
    llm_input = result["return_value"]["items"][0]
    assert "2026-01-01T00:00:00.000+09:00" in json.dumps(llm_input)
