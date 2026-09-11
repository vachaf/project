"""Frozen contracts for the Stage E Prepare-before verification runner."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from .identity import require_sha256_digest
from .isolation import FIXED_INSTANT, PROCESS_TIMEZONE, RunRole


SUBJECT_REVISION = "4eab95703e00373428e7ea3ec8ca58e0f09ae7c2"
PARAMETER_ID = "prepare-security-score4-repeat3.v1"
MIN_SCORE = 4
MIN_REPEAT_AGGREGATE = 3
SOURCE_TABLES = ("security",)
CHILD_PROTOCOL_VERSION = "prepare_before_capture_child.v1"

# Approved source_tree_digest inventory v1.  README.md is deliberately absent.
SOURCE_TREE_INVENTORY_VERSION = "prepare_source_tree_inventory.v1"
SOURCE_TREE_FILES = (
    "src/prepare/__init__.py",
    "src/prepare/apache_observability_context.py",
    "src/prepare/auth_behavior.py",
    "src/prepare/crawler_baseline.py",
    "src/prepare/decoders.py",
    "src/prepare/file_disclosure_hints.py",
    "src/prepare/ip_behavior.py",
    "src/prepare/l3_hints.py",
    "src/prepare/method_summaries.py",
    "src/prepare/mixed_baseline_scanner.py",
    "src/prepare/models.py",
    "src/prepare/probing_sequence.py",
    "src/prepare/protocol_anomalies.py",
    "src/prepare/sensitive_path_probe.py",
    "src/prepare/sqli_hints.py",
    "src/prepare/static_baseline.py",
    "src/prepare/traversal_cmdi_hints.py",
    "src/prepare/xss_hints.py",
    "src/prepare_llm_input.py",
)

HARNESS_FILES = (
    "src/prepare_full_output_harness/artifacts.py",
    "src/prepare_full_output_harness/capture.py",
    "src/prepare_full_output_harness/compare.py",
    "src/prepare_full_output_harness/identity.py",
    "src/prepare_full_output_harness/inventory.py",
    "src/prepare_full_output_harness/isolation.py",
    "src/prepare_full_output_harness/stage_e_contract.py",
)
ADAPTER_FILES = (
    "src/prepare_full_output_harness/stage_e_adapter.py",
    "scripts/prepare_before_capture_child.py",
    "scripts/verify_prepare_before_compatibility.py",
)


class StageEContractError(ValueError):
    """A frozen Stage E identity or request contract was violated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def digest_file_inventory(root: str | Path, relative_paths: Iterable[str]) -> str:
    """Hash an ordered path-and-bytes inventory without normalizing file content."""

    base = Path(root).resolve(strict=True)
    paths = tuple(relative_paths)
    if not paths or len(paths) != len(set(paths)):
        raise StageEContractError("invalid_inventory", "inventory must be non-empty and unique")
    digest = hashlib.sha256()
    for relative in paths:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or str(pure) != relative:
            raise StageEContractError("invalid_inventory_path", "inventory path is unsafe")
        path = base.joinpath(*pure.parts)
        if not path.is_file() or path.is_symlink():
            raise StageEContractError("inventory_file_missing", f"inventory file missing: {relative}")
        payload = path.read_bytes()
        encoded_path = relative.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def source_tree_digest(root: str | Path) -> str:
    return digest_file_inventory(root, SOURCE_TREE_FILES)


@dataclass(frozen=True)
class StageEIdentity:
    subject_revision: str
    verification_revision: str
    source_tree_digest: str
    harness_digest: str
    adapter_digest: str

    def __post_init__(self) -> None:
        if self.subject_revision != SUBJECT_REVISION:
            raise StageEContractError("subject_revision_mismatch", "subject revision is not canonical")
        if re.fullmatch(r"[0-9a-f]{40}", self.verification_revision) is None:
            raise StageEContractError("invalid_verification_revision", "verification revision must be a commit SHA")
        for name in ("source_tree_digest", "harness_digest", "adapter_digest"):
            require_sha256_digest(name, getattr(self, name))

    def as_dict(self) -> dict[str, str]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BeforeCaptureRequest:
    run_role: RunRole
    subject_root: str
    input_path: str
    corpus_id: str
    case_id: str
    identity: StageEIdentity
    protocol_version: str = CHILD_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.run_role not in (RunRole.BEFORE_1, RunRole.BEFORE_2):
            raise StageEContractError("invalid_run_role", "only before-1 and before-2 are allowed")
        if self.protocol_version != CHILD_PROTOCOL_VERSION:
            raise StageEContractError("protocol_mismatch", "child protocol version does not match")
        if any(not value for value in (self.subject_root, self.input_path, self.corpus_id, self.case_id)):
            raise StageEContractError("invalid_request", "capture request fields are required")

    def as_dict(self) -> dict[str, object]:
        return {
            "protocol_version": self.protocol_version,
            "run_role": self.run_role.value,
            "subject_root": self.subject_root,
            "input_path": self.input_path,
            "corpus_id": self.corpus_id,
            "case_id": self.case_id,
            "parameter_id": PARAMETER_ID,
            "parameters": {
                "min_score": MIN_SCORE,
                "min_repeat_aggregate": MIN_REPEAT_AGGREGATE,
                "source_tables": list(SOURCE_TABLES),
            },
            "clock": {"fixed_instant": FIXED_INSTANT, "process_timezone": PROCESS_TIMEZONE},
            "identity": self.identity.as_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, separators=(",", ":"))
