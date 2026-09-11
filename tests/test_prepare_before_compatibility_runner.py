from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.prepare_full_output_harness.capture import encode_typed
from src.prepare_full_output_harness.isolation import RunRole
from src.prepare_full_output_harness.stage_e_adapter import (
    StageEAdapterError,
    capture_before,
    compare_before_baselines,
    run_before_baseline,
)
from src.prepare_full_output_harness.stage_e_contract import (
    BeforeCaptureRequest,
    CANONICAL_FIXTURES,
    ExitCode,
    StageEIdentity,
    SUBJECT_REVISION,
)


ROOT = Path(__file__).resolve().parents[1]


def request() -> BeforeCaptureRequest:
    identity = StageEIdentity(
        SUBJECT_REVISION, "1" * 40, "a" * 64, "d" * 64, "b" * 64, "c" * 64
    )
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


def fake_response(request: BeforeCaptureRequest, *, ordered: bool = True) -> dict[str, object]:
    value = {"first": 1, "second": 2} if ordered else {"second": 2, "first": 1}
    input_node = encode_typed({"data": {"security": []}})
    return {
        "protocol_version": "prepare_before_capture_child.v1",
        "status": "returned",
        "run_role": request.run_role.value,
        "corpus_id": request.corpus_id,
        "case_id": request.case_id,
        "parameter_id": "prepare-security-score4-repeat3.v1",
        "identity": request.identity.as_dict(),
        "input_identity": {
            "corpus_id": request.corpus_id, "case_id": request.case_id,
            "source_revision": SUBJECT_REVISION, "source_file_sha256": "e" * 64,
            "adapter_version": "prepare_before_capture_child.v1",
            "parameter_id": "prepare-security-score4-repeat3.v1",
            "raw_source_hash": "e" * 64, "projected_payload_hash": "f" * 64,
        },
        "parameters": {"min_score": 4, "min_repeat_aggregate": 3, "source_tables": ["security"]},
        "clock": {"fixed_instant": "2026-01-01T00:00:00+09:00", "process_timezone": "Asia/Seoul"},
        "input_before": input_node,
        "input_after": input_node,
        "input_mutated": False,
        "return_value": encode_typed((value, [], [], {}, [])),
    }


def make_run(tmp_path: Path, role: RunRole, *, capture=fake_response, name: str | None = None) -> Path:
    output = tmp_path / (name or role.value)
    fixture_root = tmp_path / "tests/fixtures/prepare_regression"
    fixture_root.mkdir(parents=True, exist_ok=True)
    for fixture in CANONICAL_FIXTURES:
        (fixture_root / fixture).touch(exist_ok=True)

    def invoke(req: BeforeCaptureRequest, **_: object) -> dict[str, object]:
        return capture(req)

    run_before_baseline(
        run_role=role,
        subject_root=tmp_path,
        verification_root=ROOT,
        output_root=output,
        identity=request().identity,
        capture=invoke,
    )
    return output


def test_run_level_aggregates_25_revalidated_case_artifacts(tmp_path: Path) -> None:
    output = make_run(tmp_path, RunRole.BEFORE_1)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["case_count"] == 25
    assert len(summary["case_artifacts"]) == 25
    assert all(Path(item["artifact_path"], "completion.json").is_file() for item in summary["case_artifacts"])
    assert (output / "checksums.sha256").is_file()
    assert (output / "completion.json").is_file()


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_noncanonical_fixture_inventory_blocks_before_parent(
    tmp_path: Path, change: str
) -> None:
    fixture_root = tmp_path / "tests/fixtures/prepare_regression"
    fixture_root.mkdir(parents=True)
    for fixture in CANONICAL_FIXTURES:
        (fixture_root / fixture).touch()
    if change == "missing":
        (fixture_root / CANONICAL_FIXTURES[0]).unlink()
    else:
        (fixture_root / "extra.json").touch()
    with pytest.raises(StageEAdapterError) as raised:
        run_before_baseline(
            run_role=RunRole.BEFORE_1,
            subject_root=tmp_path,
            verification_root=ROOT,
            output_root=tmp_path / "before-1",
            identity=request().identity,
            capture=lambda req, **_: fake_response(req),
        )
    assert raised.value.code == "inventory_mismatch"


def test_strict_run_comparison_passes_and_finalizes(tmp_path: Path) -> None:
    left = make_run(tmp_path, RunRole.BEFORE_1)
    right = make_run(tmp_path, RunRole.BEFORE_2)
    comparison = tmp_path / "comparison"
    summary = compare_before_baselines(left, right, comparison)
    assert summary["final_verdict"] == "PASS"
    assert summary["nondeterminism"] == "NOT DETECTED"
    assert summary["five_output_difference_counts"] == {
        "llm_input": 0, "candidate_payload": 0, "noise_payload": 0,
        "filtered_reasons_payload": 0, "filtered_payload": 0,
    }
    assert (comparison / "completion.json").is_file()


def test_dict_insertion_order_is_a_strict_failure(tmp_path: Path) -> None:
    left = make_run(tmp_path, RunRole.BEFORE_1)
    right = make_run(
        tmp_path,
        RunRole.BEFORE_2,
        capture=lambda req: fake_response(req, ordered=False),
    )
    summary = compare_before_baselines(left, right, tmp_path / "comparison")
    assert summary["final_verdict"] == "FAIL"
    assert summary["five_output_difference_counts"]["llm_input"] == 25
    assert summary["nondeterminism"] == "DETECTED"


def test_incomplete_or_corrupt_case_baseline_blocks_comparison(tmp_path: Path) -> None:
    left = make_run(tmp_path, RunRole.BEFORE_1)
    right = make_run(tmp_path, RunRole.BEFORE_2)
    capture_path = next((right.with_name(right.name + ".cases")).glob("*/capture.json"))
    capture_path.write_text("{}", encoding="utf-8")
    with pytest.raises(Exception) as raised:
        compare_before_baselines(left, right, tmp_path / "comparison")
    assert getattr(raised.value, "code", None) == "checksum_mismatch"


def test_identity_mismatch_is_blocked(tmp_path: Path) -> None:
    left = make_run(tmp_path, RunRole.BEFORE_1)
    different = StageEIdentity(
        SUBJECT_REVISION, "2" * 40, "a" * 64, "d" * 64, "b" * 64, "c" * 64
    )
    right = tmp_path / "before-2"
    run_before_baseline(
        run_role=RunRole.BEFORE_2,
        subject_root=tmp_path,
        verification_root=ROOT,
        output_root=right,
        identity=different,
        capture=lambda req, **_: fake_response(req),
    )
    with pytest.raises(StageEAdapterError) as raised:
        compare_before_baselines(left, right, tmp_path / "comparison")
    assert raised.value.code == "identity_mismatch"


def test_exception_type_and_exact_message_differences_fail(tmp_path: Path) -> None:
    def exception(req: BeforeCaptureRequest, kind: str, message: str) -> dict[str, object]:
        response = fake_response(req)
        response.pop("return_value")
        response["status"] = "raised"
        response["exception"] = {"qualified_type": kind, "message": message}
        return response

    left = make_run(
        tmp_path, RunRole.BEFORE_1,
        capture=lambda req: exception(req, "builtins.ValueError", "exact one"),
    )
    right = make_run(
        tmp_path, RunRole.BEFORE_2,
        capture=lambda req: exception(req, "builtins.TypeError", "exact two"),
    )
    summary = compare_before_baselines(left, right, tmp_path / "comparison")
    assert summary["final_verdict"] == "FAIL"
    assert summary["exception_type_mismatch_count"] == 25
    assert summary["exception_message_mismatch_count"] == 25


def test_identical_unexpected_exceptions_are_deterministic_but_fail(tmp_path: Path) -> None:
    def exception(req: BeforeCaptureRequest) -> dict[str, object]:
        response = fake_response(req)
        response.pop("return_value")
        response["status"] = "raised"
        response["exception"] = {"qualified_type": "builtins.ValueError", "message": "same"}
        return response

    left = make_run(tmp_path, RunRole.BEFORE_1, capture=exception)
    right = make_run(tmp_path, RunRole.BEFORE_2, capture=exception)
    summary = compare_before_baselines(left, right, tmp_path / "comparison")
    assert summary["final_verdict"] == "FAIL"
    assert summary["unexpected_exception_case_count"] == 25
    assert summary["exception_type_mismatch_count"] == 0
    assert summary["exception_message_mismatch_count"] == 0
    assert summary["nondeterminism"] == "NOT DETECTED"


def test_mutation_aggregation_causes_failure(tmp_path: Path) -> None:
    def mutated(req: BeforeCaptureRequest) -> dict[str, object]:
        response = fake_response(req)
        response["input_mutated"] = True
        return response

    left = make_run(tmp_path, RunRole.BEFORE_1)
    right = make_run(tmp_path, RunRole.BEFORE_2, capture=mutated)
    summary = compare_before_baselines(left, right, tmp_path / "comparison")
    assert summary["final_verdict"] == "FAIL"
    assert summary["mutation_case_count"] == 25


def test_cli_exit_codes_are_fixed() -> None:
    assert (int(ExitCode.PASS), int(ExitCode.FAIL), int(ExitCode.BLOCKED)) == (0, 1, 2)


@pytest.mark.parametrize(("verdict", "expected"), [("PASS", 0), ("FAIL", 1)])
def test_compare_cli_returns_verdict_exit_code(
    monkeypatch: pytest.MonkeyPatch, verdict: str, expected: int
) -> None:
    from scripts import verify_prepare_before_compatibility as runner

    monkeypatch.setattr(
        runner,
        "compare_before_baselines",
        lambda *_: {"final_verdict": verdict},
    )
    assert runner.main(
        [
            "compare", "--before-1-root", "/before-1",
            "--before-2-root", "/before-2", "--output-root", "/comparison",
        ]
    ) == expected


def test_compare_cli_returns_blocked_for_precondition_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import verify_prepare_before_compatibility as runner

    def blocked(*_: object) -> dict[str, object]:
        raise StageEAdapterError("baseline_incomplete", "incomplete")

    monkeypatch.setattr(runner, "compare_before_baselines", blocked)
    assert runner.main(
        [
            "compare", "--before-1-root", "/before-1",
            "--before-2-root", "/before-2", "--output-root", "/comparison",
        ]
    ) == int(ExitCode.BLOCKED)
