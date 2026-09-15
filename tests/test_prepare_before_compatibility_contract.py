from __future__ import annotations

from pathlib import Path

import pytest

from src.prepare_full_output_harness.isolation import FIXED_INSTANT, PROCESS_TIMEZONE, RunRole
from src.prepare_full_output_harness.stage_e_contract import (
    CHILD_PROTOCOL_VERSION,
    MIN_REPEAT_AGGREGATE,
    MIN_SCORE,
    PARAMETER_ID,
    SOURCE_TABLES,
    SOURCE_TREE_FILES,
    SUBJECT_REVISION,
    BeforeCaptureRequest,
    StageEContractError,
    StageEIdentity,
    source_tree_digest,
)


ROOT = Path(__file__).resolve().parents[1]


def identity() -> StageEIdentity:
    return StageEIdentity(
        SUBJECT_REVISION, "1" * 40, "a" * 64, "d" * 64, "b" * 64, "c" * 64
    )


def test_approved_source_inventory_v1_is_exact() -> None:
    assert len(SOURCE_TREE_FILES) == 19
    assert SOURCE_TREE_FILES[-1] == "src/prepare_llm_input.py"
    assert "src/prepare/README.md" not in SOURCE_TREE_FILES
    assert source_tree_digest(ROOT) == source_tree_digest(ROOT)


def test_canonical_parameters_and_clock_are_frozen() -> None:
    assert (MIN_SCORE, MIN_REPEAT_AGGREGATE, SOURCE_TABLES) == (4, 3, ("security",))
    assert PARAMETER_ID == "prepare-security-score4-repeat3.v1"
    assert FIXED_INSTANT == "2026-01-01T00:00:00+09:00"
    assert PROCESS_TIMEZONE == "Asia/Seoul"


def test_request_serializes_identity_and_exact_contract() -> None:
    request = BeforeCaptureRequest(RunRole.BEFORE_1, "/subject", "/input.json", "fixture", "case", identity())
    value = request.as_dict()
    assert value["protocol_version"] == CHILD_PROTOCOL_VERSION
    assert value["parameters"] == {"min_score": 4, "min_repeat_aggregate": 3, "source_tables": ["security"]}
    assert value["identity"]["verification_revision"] == "1" * 40


def test_after_role_is_rejected() -> None:
    with pytest.raises(StageEContractError) as raised:
        BeforeCaptureRequest(RunRole.AFTER, "/subject", "/input.json", "fixture", "case", identity())
    assert raised.value.code == "invalid_run_role"
