#!/usr/bin/env python3
"""Isolated child for one honest Stage E After capture."""
from __future__ import annotations
import copy, importlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from src.prepare_full_output_harness.capture import encode_typed
from src.prepare_full_output_harness.identity import sha256_bytes, sha256_file
from src.prepare_full_output_harness.isolation import FIXED_INSTANT, PROCESS_TIMEZONE, patched_prepare_datetime, validate_import_origin
from src.prepare_full_output_harness.stage_e_after_contract import CORPUS_ID, MIN_REPEAT_AGGREGATE, MIN_SCORE, PARAMETER_ID, PROTOCOL_VERSION, SOURCE_TABLES, digest_files, expected_subject

def require(ok: bool, message: str) -> None:
    if not ok: raise ValueError(message)
def execute(request: dict[str, object]) -> dict[str, object]:
    require(request.get("protocol_version") == PROTOCOL_VERSION, "protocol mismatch")
    run_role = str(request.get("run_role")); revision, tree, source_files = expected_subject(run_role)
    require(request.get("corpus_id") == CORPUS_ID and request.get("parameter_id") == PARAMETER_ID, "case contract mismatch")
    params = {"min_score": MIN_SCORE, "min_repeat_aggregate": MIN_REPEAT_AGGREGATE, "source_tables": list(SOURCE_TABLES)}
    require(request.get("parameters") == params, "parameter contract mismatch")
    require(request.get("clock") == {"fixed_instant": FIXED_INSTANT, "process_timezone": PROCESS_TIMEZONE}, "clock contract mismatch")
    identity = request.get("identity"); require(isinstance(identity, dict), "identity missing")
    require(identity.get("subject_revision") == revision and identity.get("subject_tree") == tree, "subject identity mismatch")
    subject = Path(str(request.get("subject_root"))).resolve(strict=True)
    require(digest_files(subject, source_files) == identity.get("source_tree_digest"), "source tree digest mismatch")
    input_path = Path(str(request.get("input_path"))).resolve(strict=True); require(input_path.is_file(), "input missing")
    payload = json.loads(input_path.read_text(encoding="utf-8")); require(isinstance(payload, dict), "input payload must be an object")
    before = encode_typed(payload); call_input = copy.deepcopy(payload)
    input_identity = {"corpus_id": CORPUS_ID, "case_id": request["case_id"], "source_revision": revision,
        "source_file_sha256": sha256_file(input_path), "adapter_version": PROTOCOL_VERSION, "parameter_id": PARAMETER_ID,
        "raw_source_hash": sha256_file(input_path), "projected_payload_hash": sha256_bytes(json.dumps(before, ensure_ascii=False, separators=(",", ":")).encode())}
    sys.path.insert(0, str(subject))
    for name in tuple(sys.modules):
        if name == "src.prepare_llm_input" or name == "src.prepare" or name.startswith("src.prepare."): del sys.modules[name]
    module = importlib.import_module("src.prepare_llm_input")
    expected = subject / "src/prepare_llm_input.py"; validate_import_origin(module, expected_file=expected, expected_sha256=sha256_file(expected))
    common = {"protocol_version": PROTOCOL_VERSION, "run_role": request["run_role"], "corpus_id": CORPUS_ID,
              "case_id": request["case_id"], "parameter_id": PARAMETER_ID, "identity": identity,
              "input_identity": input_identity, "parameters": params, "clock": request["clock"], "input_before": before}
    try:
        with patched_prepare_datetime(module): result = module.build_outputs(call_input, **params)
    except Exception as exc:
        after = encode_typed(call_input); return {**common, "status": "raised", "input_after": after, "input_mutated": before != after,
            "exception": {"qualified_type": f"{type(exc).__module__}.{type(exc).__qualname__}", "message": str(exc)}}
    require(isinstance(result, tuple) and len(result) == 5, "build_outputs return contract mismatch")
    require(all(type(v) is t for v, t in zip(result, (dict, list, list, dict, list))), "build_outputs slot type mismatch")
    after = encode_typed(call_input); return {**common, "status": "returned", "input_after": after,
        "input_mutated": before != after, "return_value": encode_typed(result)}
def main() -> int:
    try: response = execute(json.load(sys.stdin))
    except BaseException as exc:
        response = {"protocol_version": PROTOCOL_VERSION, "status": "raised", "error": {"qualified_type": f"{type(exc).__module__}.{type(exc).__qualname__}", "message": str(exc)}}
        json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":")); return 1
    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":")); return 0
if __name__ == "__main__": raise SystemExit(main())
