#!/usr/bin/env python3
"""Isolated stdin/stdout child for one canonical Prepare-before capture."""

from __future__ import annotations

import copy
import importlib
import json
import sys
from pathlib import Path


VERIFICATION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFICATION_ROOT))

from src.prepare_full_output_harness.capture import encode_typed  # noqa: E402
from src.prepare_full_output_harness.isolation import (  # noqa: E402
    FIXED_INSTANT,
    PROCESS_TIMEZONE,
    patched_prepare_datetime,
    validate_import_origin,
)
from src.prepare_full_output_harness.stage_e_contract import (  # noqa: E402
    CHILD_PROTOCOL_VERSION,
    MIN_REPEAT_AGGREGATE,
    MIN_SCORE,
    PARAMETER_ID,
    SOURCE_TABLES,
    SUBJECT_REVISION,
    SOURCE_TREE_FILES,
    source_tree_digest,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def execute(request: dict[str, object]) -> dict[str, object]:
    """Validate a frozen request, import from subject, and capture all five slots."""

    _require(request.get("protocol_version") == CHILD_PROTOCOL_VERSION, "protocol mismatch")
    _require(request.get("run_role") in {"before-1", "before-2"}, "invalid run role")
    _require(request.get("parameter_id") == PARAMETER_ID, "parameter contract mismatch")
    _require(
        request.get("parameters")
        == {"min_score": MIN_SCORE, "min_repeat_aggregate": MIN_REPEAT_AGGREGATE, "source_tables": list(SOURCE_TABLES)},
        "parameter contract mismatch",
    )
    _require(
        request.get("clock") == {"fixed_instant": FIXED_INSTANT, "process_timezone": PROCESS_TIMEZONE},
        "clock contract mismatch",
    )
    identity = request.get("identity")
    _require(isinstance(identity, dict), "identity missing")
    _require(identity.get("subject_revision") == SUBJECT_REVISION, "subject revision mismatch")
    subject_root = Path(str(request.get("subject_root"))).resolve(strict=True)
    _require(source_tree_digest(subject_root) == identity.get("source_tree_digest"), "source tree digest mismatch")
    input_path = Path(str(request.get("input_path"))).resolve(strict=True)
    _require(input_path.is_file(), "input missing")
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), "input payload must be an object")
    input_before = encode_typed(payload)
    call_input = copy.deepcopy(payload)

    # -I prevents ambient PYTHONPATH injection.  Put the approved subject first,
    # while keeping the already-loaded verification harness modules intact.
    sys.path.insert(0, str(subject_root))
    for name in tuple(sys.modules):
        if name == "src.prepare_llm_input" or name.startswith("src.prepare.") or name == "src.prepare":
            del sys.modules[name]
    module = importlib.import_module("src.prepare_llm_input")
    expected_file = subject_root / SOURCE_TREE_FILES[-1]
    from src.prepare_full_output_harness.identity import sha256_file
    validate_import_origin(module, expected_file=expected_file, expected_sha256=sha256_file(expected_file))
    with patched_prepare_datetime(module):
        result = module.build_outputs(
            call_input,
            min_score=MIN_SCORE,
            min_repeat_aggregate=MIN_REPEAT_AGGREGATE,
            source_tables=list(SOURCE_TABLES),
        )
    _require(isinstance(result, tuple) and len(result) == 5, "build_outputs return contract mismatch")
    expected_types = (dict, list, list, dict, list)
    _require(all(type(value) is expected for value, expected in zip(result, expected_types)), "build_outputs slot type mismatch")
    input_after = encode_typed(call_input)
    return {
        "protocol_version": CHILD_PROTOCOL_VERSION,
        "status": "returned",
        "run_role": request["run_role"],
        "corpus_id": request["corpus_id"],
        "case_id": request["case_id"],
        "parameter_id": PARAMETER_ID,
        "identity": identity,
        "parameters": request["parameters"],
        "clock": request["clock"],
        "input_before": input_before,
        "input_after": input_after,
        "input_mutated": input_before != input_after,
        "return_value": encode_typed(result),
    }


def main() -> int:
    try:
        request = json.load(sys.stdin)
        _require(isinstance(request, dict), "request must be an object")
        response = execute(request)
    except BaseException as exc:
        # No input or output payload is reflected in the error envelope.
        response = {
            "protocol_version": CHILD_PROTOCOL_VERSION,
            "status": "raised",
            "error": {"qualified_type": f"{type(exc).__module__}.{type(exc).__qualname__}", "message": str(exc)},
        }
        json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        return 1
    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
