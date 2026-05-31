#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any, Callable, Optional, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.services.analysis_job_repository import AnalysisJobRepository  # noqa: E402


SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)=([^\s]+)"),
    re.compile(r"(?i)(bearer)\s+([A-Za-z0-9._\-]+)"),
]


def build_default_worker_id() -> str:
    hostname = socket.gethostname() or "localhost"
    return f"{hostname}-{os.getpid()}"


def redact_worker_error(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r"\1=[REDACTED]", text)
    return text


def run_once(
    repository: Any,
    *,
    worker_id: str,
    stdout: TextIO = sys.stdout,
) -> int:
    claimed = repository.claim_next_pending_full_report_job(worker_id=worker_id)
    if not claimed:
        print("[analysis-job-worker] no pending full_report job", file=stdout)
        return 0

    job_id = claimed.get("id")
    status = claimed.get("status")
    claimed_worker_id = claimed.get("worker_id") or worker_id
    print(
        "[analysis-job-worker] "
        f"claimed job_id={job_id} status={status} worker_id={claimed_worker_id}",
        file=stdout,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Claim-only Analysis Job Worker for DB-backed full_report jobs"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="try one PENDING full_report claim and exit",
    )
    parser.add_argument(
        "--worker-id",
        default=None,
        help="explicit worker id; defaults to hostname-pid",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=5.0,
        help="reserved for future loop mode when no PENDING job exists",
    )
    parser.add_argument(
        "--claim-only",
        action="store_true",
        default=True,
        help="claim jobs without running the analysis pipeline",
    )
    return parser


def main(
    argv: Optional[list[str]] = None,
    *,
    repository_factory: Callable[[], Any] = AnalysisJobRepository,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    worker_id = args.worker_id or build_default_worker_id()

    if not args.once:
        print(
            "[analysis-job-worker] loop mode is not enabled for this claim-only worker; use --once",
            file=stderr,
        )
        return 1

    try:
        repository = repository_factory()
        return run_once(repository, worker_id=worker_id, stdout=stdout)
    except Exception as exc:
        print(f"[analysis-job-worker] error: {redact_worker_error(exc)}", file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
