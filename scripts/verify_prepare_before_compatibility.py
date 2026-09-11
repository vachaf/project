#!/usr/bin/env python3
"""Stage E verification-only parent runner for one approved Before role."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.prepare_full_output_harness.artifacts import ArtifactWriter  # noqa: E402
from src.prepare_full_output_harness.isolation import RunRole  # noqa: E402
from src.prepare_full_output_harness.stage_e_adapter import capture_before  # noqa: E402
from src.prepare_full_output_harness.stage_e_contract import (  # noqa: E402
    ADAPTER_FILES,
    HARNESS_FILES,
    SUBJECT_REVISION,
    BeforeCaptureRequest,
    StageEIdentity,
    digest_file_inventory,
    source_tree_digest,
)


class RunnerError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RunnerError("git identity check failed")
    return completed.stdout.strip()


def _is_detached(root: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RunnerError("git detached-state check failed")
    return completed.returncode == 1


def validate_worktrees(subject_root: Path, verification_root: Path) -> str:
    if subject_root.resolve() == verification_root.resolve():
        raise RunnerError("subject and verification worktrees must be distinct")
    if _git(subject_root, "rev-parse", "HEAD") != SUBJECT_REVISION:
        raise RunnerError("subject revision mismatch")
    if not _is_detached(subject_root):
        raise RunnerError("subject worktree must be detached")
    if _git(subject_root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RunnerError("subject worktree must be fully clean")
    verification_revision = _git(verification_root, "rev-parse", "HEAD")
    if _git(verification_root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RunnerError("verification worktree must be clean")
    return verification_revision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-role", required=True, choices=("before-1", "before-2"))
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    verification_revision = validate_worktrees(args.subject_root, ROOT)
    identity = StageEIdentity(
        subject_revision=SUBJECT_REVISION,
        verification_revision=verification_revision,
        source_tree_digest=source_tree_digest(args.subject_root),
        harness_digest=digest_file_inventory(ROOT, HARNESS_FILES),
        adapter_digest=digest_file_inventory(ROOT, ADAPTER_FILES),
    )
    request = BeforeCaptureRequest(
        run_role=RunRole(args.run_role),
        subject_root=str(args.subject_root.resolve(strict=True)),
        input_path=str(args.input.resolve(strict=True)),
        corpus_id=args.corpus_id,
        case_id=args.case_id,
        identity=identity,
    )
    capture = capture_before(request, verification_root=ROOT)
    if capture["input_mutated"]:
        raise RunnerError("Prepare mutated its input")
    writer = ArtifactWriter.create(args.output_root)
    writer.write_json("capture.json", capture)
    writer.finalize()
    print(json.dumps({"status": "PASS", "run_role": args.run_role, "case_id": args.case_id}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
