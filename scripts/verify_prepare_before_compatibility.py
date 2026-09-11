#!/usr/bin/env python3
"""Tracked Stage E run-level capture and strict comparison CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.prepare_full_output_harness.artifacts import ArtifactError  # noqa: E402
from src.prepare_full_output_harness.isolation import RunRole  # noqa: E402
from src.prepare_full_output_harness.stage_e_adapter import (  # noqa: E402
    StageEAdapterError,
    compare_before_baselines,
    run_before_baseline,
)
from src.prepare_full_output_harness.stage_e_contract import (  # noqa: E402
    ADAPTER_FILES,
    ExitCode,
    HARNESS_FILES,
    RUNNER_FILES,
    SUBJECT_REVISION,
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
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--subject-root", type=Path, required=True)
    run.add_argument("--run-role", required=True, choices=("before-1", "before-2"))
    run.add_argument("--output-root", type=Path, required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--before-1-root", type=Path, required=True)
    compare.add_argument("--before-2-root", type=Path, required=True)
    compare.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        if args.command == "run":
            verification_revision = validate_worktrees(args.subject_root, ROOT)
            identity = StageEIdentity(
                subject_revision=SUBJECT_REVISION,
                verification_revision=verification_revision,
                source_tree_digest=source_tree_digest(args.subject_root),
                runner_digest=digest_file_inventory(ROOT, RUNNER_FILES),
                harness_digest=digest_file_inventory(ROOT, HARNESS_FILES),
                adapter_digest=digest_file_inventory(ROOT, ADAPTER_FILES),
            )
            summary = run_before_baseline(
                run_role=RunRole(args.run_role),
                subject_root=args.subject_root,
                verification_root=ROOT,
                output_root=args.output_root,
                identity=identity,
            )
            verdict = summary["status"]
        else:
            summary = compare_before_baselines(
                args.before_1_root, args.before_2_root, args.output_root
            )
            verdict = summary["final_verdict"]
        print(json.dumps({"status": verdict, "summary": summary}, separators=(",", ":")))
        return int(ExitCode[verdict])
    except (RunnerError, StageEAdapterError, ArtifactError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error_code": getattr(exc, "code", "runner_error")}, separators=(",", ":")))
        return int(ExitCode.BLOCKED)


if __name__ == "__main__":
    raise SystemExit(main())
