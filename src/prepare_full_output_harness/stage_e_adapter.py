"""Parent-side adapter for one isolated Stage E Prepare-before capture."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from .artifacts import ArtifactWriter, require_completed_read_only_baseline
from .compare import compare_typed
from .isolation import RunRole, build_isolated_environment
from .stage_e_contract import (
    BeforeCaptureRequest,
    CANONICAL_FIXTURES,
    CHILD_PROTOCOL_VERSION,
    CORPUS_ID,
    OUTPUT_SLOT_NAMES,
    StageEIdentity,
)


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
    if response.get("status") not in {"returned", "raised"}:
        raise StageEAdapterError("invalid_child_status", "capture child status is invalid")
    return response


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_before_baseline(
    *,
    run_role: RunRole,
    subject_root: str | Path,
    verification_root: str | Path,
    output_root: str | Path,
    identity: StageEIdentity,
    capture: Callable[..., dict[str, Any]] = capture_before,
) -> dict[str, Any]:
    """Capture, independently finalize, revalidate, and aggregate all 25 cases."""

    subject = Path(subject_root).resolve(strict=True)
    output = Path(output_root)
    cases_root = output.with_name(output.name + ".cases")
    fixture_root = subject / "tests/fixtures/prepare_regression"
    actual_fixtures = tuple(sorted(path.name for path in fixture_root.glob("*.json") if path.is_file()))
    if actual_fixtures != CANONICAL_FIXTURES:
        raise StageEAdapterError("inventory_mismatch", "canonical fixture inventory differs")
    if output.exists() or cases_root.exists():
        raise StageEAdapterError("output_exists", "run output or case root already exists")
    cases_root.mkdir(mode=0o700, parents=False)
    case_records = []
    mutations = []
    exceptions = []
    try:
        for fixture_name in CANONICAL_FIXTURES:
            case_id = Path(fixture_name).stem
            request = BeforeCaptureRequest(
                run_role=run_role,
                subject_root=str(subject),
                input_path=str(fixture_root / fixture_name),
                corpus_id=CORPUS_ID,
                case_id=case_id,
                identity=identity,
            )
            response = capture(request, verification_root=verification_root)
            case_writer = ArtifactWriter.create(cases_root / case_id)
            case_writer.write_json("capture.json", response)
            case_writer.finalize()
            validated = require_completed_read_only_baseline(cases_root / case_id)
            if response.get("input_mutated"):
                mutations.append(case_id)
            if response["status"] == "raised":
                exceptions.append({"case_id": case_id, "exception": response["exception"]})
            case_records.append(
                {
                    "case_id": case_id,
                    "fixture": fixture_name,
                    "artifact_path": str(validated),
                    "capture_sha256": _sha256(validated / "capture.json"),
                    "checksums_sha256": _sha256(validated / "checksums.sha256"),
                    "status": response["status"],
                    "input_identity": response["input_identity"],
                }
            )
        actual = tuple(record["fixture"] for record in case_records)
        if actual != CANONICAL_FIXTURES or len(set(actual)) != len(CANONICAL_FIXTURES):
            raise StageEAdapterError("inventory_mismatch", "canonical case inventory differs")
        writer = ArtifactWriter.create(output)
        summary = {
            "status": "PASS",
            "run_role": run_role.value,
            "case_count": len(case_records),
            "identity": identity.as_dict(),
            "corpus_id": CORPUS_ID,
            "fixtures": list(CANONICAL_FIXTURES),
            "mutation_case_count": len(mutations),
            "mutation_cases": mutations,
            "exception_case_count": len(exceptions),
            "exceptions": exceptions,
            "case_artifacts": case_records,
        }
        writer.write_json("summary.json", summary)
        writer.finalize()
        require_completed_read_only_baseline(output)
        return summary
    except BaseException:
        # An incomplete cases root is retained as non-baseline diagnostic evidence.
        raise


def _load_run(root: str | Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    baseline = require_completed_read_only_baseline(root)
    summary = json.loads((baseline / "summary.json").read_text(encoding="utf-8"))
    records = summary.get("case_artifacts")
    if not isinstance(records, list) or len(records) != len(CANONICAL_FIXTURES):
        raise StageEAdapterError("inventory_incomplete", "run inventory is incomplete")
    captures = {}
    for record in records:
        case_id = record["case_id"]
        case_root = require_completed_read_only_baseline(record["artifact_path"])
        if _sha256(case_root / "capture.json") != record["capture_sha256"]:
            raise StageEAdapterError("case_checksum_mismatch", "case reference checksum differs")
        captures[case_id] = json.loads((case_root / "capture.json").read_text(encoding="utf-8"))
    expected_ids = tuple(Path(name).stem for name in CANONICAL_FIXTURES)
    if tuple(captures) != expected_ids or len(captures) != len(records):
        raise StageEAdapterError("inventory_mismatch", "case inventory differs")
    return summary, captures


def compare_before_baselines(
    before_1_root: str | Path, before_2_root: str | Path, output_root: str | Path
) -> dict[str, Any]:
    """Strictly compare two complete runs and finalize a comparison transaction."""

    left_summary, left = _load_run(before_1_root)
    right_summary, right = _load_run(before_2_root)
    identity_equal = left_summary.get("identity") == right_summary.get("identity")
    contract_fields = ("corpus_id", "fixtures")
    contract_equal = all(left_summary.get(k) == right_summary.get(k) for k in contract_fields)
    if not identity_equal or not contract_equal:
        raise StageEAdapterError("identity_mismatch", "run identity or corpus contract differs")

    slot_counts = {name: 0 for name in OUTPUT_SLOT_NAMES}
    state_mismatch = []
    exception_type_mismatch = []
    exception_message_mismatch = []
    unexpected_exception_cases = []
    mutation_cases = []
    mismatch_cases = set()
    difference_records = []
    for case_id in left:
        before, after = left[case_id], right[case_id]
        per_case_identity = (
            "corpus_id", "case_id", "parameter_id", "identity", "input_identity",
            "parameters", "clock", "input_before",
        )
        if any(before.get(key) != after.get(key) for key in per_case_identity):
            raise StageEAdapterError("identity_mismatch", f"case identity differs: {case_id}")
        if before["status"] != after["status"]:
            state_mismatch.append(case_id); mismatch_cases.add(case_id)
            continue
        if before.get("input_mutated") or after.get("input_mutated") or before.get("input_after") != after.get("input_after"):
            mutation_cases.append(case_id); mismatch_cases.add(case_id)
        if before["status"] == "raised":
            unexpected_exception_cases.append(case_id)
            left_exception, right_exception = before["exception"], after["exception"]
            if left_exception["qualified_type"] != right_exception["qualified_type"]:
                exception_type_mismatch.append(case_id); mismatch_cases.add(case_id)
            if left_exception["message"] != right_exception["message"]:
                exception_message_mismatch.append(case_id); mismatch_cases.add(case_id)
            continue
        left_return, right_return = before["return_value"], after["return_value"]
        if left_return.get("type") != "tuple" or right_return.get("type") != "tuple" or len(left_return.get("items", ())) != 5 or len(right_return.get("items", ())) != 5:
            raise StageEAdapterError("partial_capture", f"five-output capture incomplete: {case_id}")
        for index, slot_name in enumerate(OUTPUT_SLOT_NAMES):
            differences = compare_typed(left_return["items"][index], right_return["items"][index])
            slot_counts[slot_name] += len(differences)
            if differences:
                mismatch_cases.add(case_id)
                difference_records.extend(
                    {"case_id": case_id, "slot": slot_name, "kind": item.kind.value, "path": item.path}
                    for item in differences
                )
    fail = bool(mismatch_cases or unexpected_exception_cases)
    summary = {
        "final_verdict": "FAIL" if fail else "PASS",
        "inventory_equal": tuple(left) == tuple(right),
        "identity_equal": identity_equal,
        "five_output_difference_counts": slot_counts,
        "success_exception_mismatch_count": len(state_mismatch),
        "success_exception_mismatch_cases": state_mismatch,
        "exception_type_mismatch_count": len(exception_type_mismatch),
        "exception_message_mismatch_count": len(exception_message_mismatch),
        "unexpected_exception_case_count": len(unexpected_exception_cases),
        "unexpected_exception_cases": unexpected_exception_cases,
        "mutation_case_count": len(mutation_cases),
        "mutation_cases": mutation_cases,
        "nondeterminism": "DETECTED" if mismatch_cases else "NOT DETECTED",
        "mismatch_case_count": len(mismatch_cases),
        "mismatch_cases": sorted(mismatch_cases),
    }
    writer = ArtifactWriter.create(output_root)
    writer.write_json("summary.json", summary)
    writer.write_json("inventory.json", {"before_1": list(left), "before_2": list(right)})
    writer.write_json("identity.json", {"before_1": left_summary["identity"], "before_2": right_summary["identity"]})
    writer.write_json("differences.json", difference_records)
    writer.finalize()
    require_completed_read_only_baseline(output_root)
    return summary
