#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.services.analysis_job_repository import AnalysisJobRepository  # noqa: E402
from full_report_job_runner import FullReportJobRunner  # noqa: E402


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
    run_pipeline: bool = False,
    runner: Optional[Any] = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
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
    if not run_pipeline:
        return 0

    try:
        repository.append_job_event(
            job_id=job_id,
            event_type="JOB_STARTED",
            message="Full report direct pipeline started",
            detail_json={"worker_id": worker_id, "analysis_mode": claimed.get("analysis_mode")},
        )
        if runner is None:
            runner = FullReportJobRunner()
        result = runner.run(claimed)
        upsert_kwargs = _result_to_upsert_kwargs(job_id=job_id, result=result)
        repository.upsert_analysis_report(**upsert_kwargs)
        if _result_no_data(result):
            repository.append_job_event(
                job_id=job_id,
                event_type="JOB_NO_DATA",
                message="No logs found in requested time range",
                detail_json={
                    "worker_id": worker_id,
                    "artifact_root": upsert_kwargs.get("artifact_root"),
                    "export_path": upsert_kwargs.get("export_path"),
                },
            )
        marked_succeeded = repository.mark_job_succeeded(
            job_id=job_id,
            worker_id=worker_id,
            detail_json={
                "artifact_root": upsert_kwargs.get("artifact_root"),
                "stage2_report_path": upsert_kwargs.get("stage2_report_path"),
                "viewer_payload_path": upsert_kwargs.get("viewer_payload_path"),
            },
        )
        if not marked_succeeded:
            raise RuntimeError(f"mark_job_succeeded returned False for job_id={job_id}")
        print(f"[analysis-job-worker] succeeded job_id={job_id} worker_id={worker_id}", file=stdout)
        return 0
    except Exception as exc:
        safe_message = redact_worker_error(exc)
        try:
            repository.mark_job_failed(
                job_id=job_id,
                worker_id=worker_id,
                error_message=safe_message,
                detail_json={"error_type": exc.__class__.__name__, "safe_message": safe_message},
            )
        except Exception as mark_exc:
            safe_mark_message = redact_worker_error(mark_exc)
            print(
                f"[analysis-job-worker] error: failed to mark job_id={job_id} FAILED: {safe_mark_message}",
                file=stderr,
            )
        print(f"[analysis-job-worker] error: {safe_message}", file=stderr)
        return 1


def _result_to_upsert_kwargs(*, job_id: Any, result: Any) -> dict[str, Any]:
    if hasattr(result, "as_upsert_kwargs"):
        raw = result.as_upsert_kwargs()
    elif isinstance(result, Mapping):
        raw = dict(result)
    else:
        raw = dict(vars(result))

    allowed = {
        "summary",
        "artifact_root",
        "export_path",
        "llm_input_path",
        "analysis_candidates_path",
        "noise_summary_path",
        "stage1_result_path",
        "stage2_report_path",
        "stage2_report_md_path",
        "viewer_payload_path",
        "lint_result_path",
        "window_summary_path",
        "rollup_input_path",
        "rollup_summary_path",
        "operator_queue_items_path",
        "operator_queue_summary_path",
    }
    return {"job_id": int(job_id), **{key: raw.get(key) for key in allowed}}


def _result_no_data(result: Any) -> bool:
    if isinstance(result, Mapping):
        return bool(result.get("no_data"))
    return bool(getattr(result, "no_data", False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analysis Job Worker for DB-backed full_report jobs"
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
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--claim-only",
        action="store_true",
        help="claim jobs without running the analysis pipeline (default unless --run-pipeline is set)",
    )
    mode_group.add_argument(
        "--run-pipeline",
        action="store_true",
        help="run the full_report direct pipeline after claiming a job",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="overall timeout passed to full_report subprocess calls",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="project root passed to FullReportJobRunner",
    )
    parser.add_argument(
        "--pipeline-dry-run",
        action="store_true",
        help="ask the full_report runner to execute the pipeline in dry-run mode",
    )
    return parser


def main(
    argv: Optional[list[str]] = None,
    *,
    repository_factory: Callable[[], Any] = AnalysisJobRepository,
    runner_factory: Callable[..., Any] = FullReportJobRunner,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.pipeline_dry_run and not args.run_pipeline:
        parser.error("--pipeline-dry-run requires --run-pipeline")
    worker_id = args.worker_id or build_default_worker_id()

    if not args.once:
        print(
            "[analysis-job-worker] loop mode is not enabled for this claim-only worker; use --once",
            file=stderr,
        )
        return 1

    try:
        repository = repository_factory()
        runner = None
        if args.run_pipeline:
            runner = runner_factory(
                project_root=args.project_root,
                timeout_seconds=args.timeout_seconds,
                pipeline_dry_run=bool(args.pipeline_dry_run),
            )
        return run_once(
            repository,
            worker_id=worker_id,
            run_pipeline=bool(args.run_pipeline),
            runner=runner,
            stdout=stdout,
            stderr=stderr,
        )
    except Exception as exc:
        print(f"[analysis-job-worker] error: {redact_worker_error(exc)}", file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
