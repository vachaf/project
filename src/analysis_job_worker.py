#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import socket
import sys
import threading
import time
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
    heartbeat_interval: float = 30.0,
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

    return _run_claimed_pipeline(
        repository,
        claimed,
        worker_id=worker_id,
        runner=runner,
        heartbeat_interval=heartbeat_interval,
        stdout=stdout,
        stderr=stderr,
    )


def run_loop(
    repository: Any,
    *,
    worker_id: str,
    runner: Any,
    max_jobs: Optional[int] = None,
    sleep_seconds: float = 5.0,
    heartbeat_interval: float = 30.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    processed_jobs = 0
    print(f"[analysis-job-worker] loop started worker_id={worker_id}", file=stdout)

    while max_jobs is None or processed_jobs < max_jobs:
        claimed = repository.claim_next_pending_full_report_job(worker_id=worker_id)
        if not claimed:
            print("[analysis-job-worker] no pending full_report job", file=stdout)
            try:
                sleep_fn(sleep_seconds)
            except KeyboardInterrupt:
                print(f"[analysis-job-worker] loop stopped worker_id={worker_id}", file=stdout)
                return 130
            continue

        job_id = claimed.get("id")
        status = claimed.get("status")
        claimed_worker_id = claimed.get("worker_id") or worker_id
        print(
            "[analysis-job-worker] "
            f"claimed job_id={job_id} status={status} worker_id={claimed_worker_id}",
            file=stdout,
        )
        _run_claimed_pipeline(
            repository,
            claimed,
            worker_id=worker_id,
            runner=runner,
            heartbeat_interval=heartbeat_interval,
            stdout=stdout,
            stderr=stderr,
        )
        processed_jobs += 1

    print(
        f"[analysis-job-worker] loop stopped worker_id={worker_id} processed_jobs={processed_jobs}",
        file=stdout,
    )
    return 0


def run_recover_stale_dry_run(
    repository: Any,
    *,
    stale_after_minutes: int = 30,
    startup_grace_minutes: int = 5,
    limit: int = 20,
    stdout: TextIO = sys.stdout,
) -> int:
    candidates = repository.find_stale_running_jobs(
        stale_after_minutes=stale_after_minutes,
        startup_grace_minutes=startup_grace_minutes,
        limit=limit,
    )
    print(
        "[analysis-job-worker] stale RUNNING recovery dry-run "
        f"candidate_count={len(candidates)} "
        f"stale_after_minutes={stale_after_minutes} "
        f"startup_grace_minutes={startup_grace_minutes} "
        f"limit={limit}",
        file=stdout,
    )
    if not candidates:
        print("[analysis-job-worker] no stale RUNNING candidates", file=stdout)
        return 0

    for candidate in candidates:
        reason = (
            "missing_heartbeat_startup_grace"
            if candidate.get("heartbeat_at") is None
            else "stale_heartbeat"
        )
        print(
            "[analysis-job-worker] stale candidate "
            f"job_id={candidate.get('id')} "
            f"worker_id={_format_cli_value(candidate.get('worker_id'))} "
            f"started_at={_format_cli_value(candidate.get('started_at'))} "
            f"heartbeat_at={_format_cli_value(candidate.get('heartbeat_at'))} "
            f"attempts={candidate.get('attempt_count')}/{candidate.get('max_attempts')} "
            f"artifact_root={_format_cli_value(candidate.get('artifact_root'))} "
            f"reason={reason}",
            file=stdout,
        )
    return 0


def run_recover_stale_mark_failed(
    repository: Any,
    *,
    reason: str,
    stale_after_minutes: int = 30,
    startup_grace_minutes: int = 5,
    limit: int = 20,
    stdout: TextIO = sys.stdout,
) -> int:
    candidates = repository.find_stale_running_jobs(
        stale_after_minutes=stale_after_minutes,
        startup_grace_minutes=startup_grace_minutes,
        limit=limit,
    )
    print(
        "[analysis-job-worker] stale RUNNING recovery mark-failed "
        f"candidate_count={len(candidates)} "
        f"stale_after_minutes={stale_after_minutes} "
        f"startup_grace_minutes={startup_grace_minutes} "
        f"limit={limit}",
        file=stdout,
    )
    if not candidates:
        print("[analysis-job-worker] no stale RUNNING candidates", file=stdout)
        return 0

    marked_count = 0
    skipped_count = 0
    for candidate in candidates:
        stale_reason = _stale_candidate_reason(candidate)
        detail_json = {
            "operator_reason": reason,
            "stale_reason": stale_reason,
            "worker_id": candidate.get("worker_id"),
            "started_at": _format_cli_value(candidate.get("started_at")),
            "heartbeat_at": _format_cli_value(candidate.get("heartbeat_at")),
            "artifact_root": candidate.get("artifact_root"),
        }
        changed = repository.mark_stale_job_failed(
            job_id=int(candidate.get("id")),
            reason=reason,
            stale_after_minutes=stale_after_minutes,
            startup_grace_minutes=startup_grace_minutes,
            detail_json=detail_json,
        )
        if changed:
            marked_count += 1
            action = "marked_failed"
        else:
            skipped_count += 1
            action = "skipped_not_stale"
        print(
            "[analysis-job-worker] stale candidate "
            f"job_id={candidate.get('id')} "
            f"worker_id={_format_cli_value(candidate.get('worker_id'))} "
            f"started_at={_format_cli_value(candidate.get('started_at'))} "
            f"heartbeat_at={_format_cli_value(candidate.get('heartbeat_at'))} "
            f"attempts={candidate.get('attempt_count')}/{candidate.get('max_attempts')} "
            f"artifact_root={_format_cli_value(candidate.get('artifact_root'))} "
            f"reason={stale_reason} "
            f"action={action}",
            file=stdout,
        )
    print(
        "[analysis-job-worker] stale RUNNING recovery mark-failed complete "
        f"marked_count={marked_count} skipped_count={skipped_count}",
        file=stdout,
    )
    return 0


def _run_claimed_pipeline(
    repository: Any,
    claimed: Mapping[str, Any],
    *,
    worker_id: str,
    runner: Optional[Any],
    heartbeat_interval: float,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    job_id = claimed.get("id")
    failed_at_stage: Optional[str] = None
    try:
        repository.append_job_event(
            job_id=job_id,
            event_type="JOB_STARTED",
            message="Full report direct pipeline started",
            detail_json={"worker_id": worker_id, "analysis_mode": claimed.get("analysis_mode")},
        )
        event_sink = _build_job_event_sink(
            repository=repository,
            job_id=job_id,
            worker_id=worker_id,
            claimed=claimed,
        )
        if runner is None:
            runner = FullReportJobRunner()
        with HeartbeatLoop(
            repository=repository,
            job_id=job_id,
            worker_id=worker_id,
            interval_seconds=heartbeat_interval,
            stderr=stderr,
        ):
            result = runner.run(claimed, event_sink=event_sink)
        upsert_kwargs = _result_to_upsert_kwargs(job_id=job_id, result=result)
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
        failed_at_stage = "report_save"
        repository.append_job_event(
            job_id=job_id,
            event_type="REPORT_SAVE_STARTED",
            message="Report metadata save started",
            detail_json={
                "worker_id": worker_id,
                "artifact_root": upsert_kwargs.get("artifact_root"),
                "stage2_report_path": upsert_kwargs.get("stage2_report_path"),
                "viewer_payload_path": upsert_kwargs.get("viewer_payload_path"),
            },
        )
        try:
            report_save_started_at = time.monotonic()
            repository.upsert_analysis_report(**upsert_kwargs)
        except Exception as exc:
            safe_report_message = redact_worker_error(exc)
            repository.append_job_event(
                job_id=job_id,
                event_type="REPORT_SAVE_FAILED",
                message="Report metadata save failed",
                detail_json={
                    "worker_id": worker_id,
                    "artifact_root": upsert_kwargs.get("artifact_root"),
                    "duration_seconds": round(time.monotonic() - report_save_started_at, 3),
                    "failed_at_stage": "report_save",
                    "error_type": exc.__class__.__name__,
                    "error_message": safe_report_message,
                },
            )
            raise
        repository.append_job_event(
            job_id=job_id,
            event_type="REPORT_SAVE_COMPLETED",
            message="Report metadata save completed",
            detail_json={
                "worker_id": worker_id,
                "artifact_root": upsert_kwargs.get("artifact_root"),
                "stage2_report_path": upsert_kwargs.get("stage2_report_path"),
                "viewer_payload_path": upsert_kwargs.get("viewer_payload_path"),
                "duration_seconds": round(time.monotonic() - report_save_started_at, 3),
            },
        )
        failed_at_stage = None
        marked_succeeded = repository.mark_job_succeeded(
            job_id=job_id,
            worker_id=worker_id,
            detail_json={
                "worker_id": worker_id,
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
        failed_stage_detail = getattr(exc, "failed_at_stage", None) or failed_at_stage
        failure_detail = {"error_type": exc.__class__.__name__, "safe_message": safe_message}
        if failed_stage_detail in {"export", "pipeline", "report_save"}:
            failure_detail["failed_at_stage"] = failed_stage_detail
        try:
            repository.mark_job_failed(
                job_id=job_id,
                worker_id=worker_id,
                error_message=safe_message,
                detail_json=failure_detail,
            )
        except Exception as mark_exc:
            safe_mark_message = redact_worker_error(mark_exc)
            print(
                f"[analysis-job-worker] error: failed to mark job_id={job_id} FAILED: {safe_mark_message}",
                file=stderr,
            )
        print(f"[analysis-job-worker] error: {safe_message}", file=stderr)
        return 1


def _build_job_event_sink(
    *,
    repository: Any,
    job_id: Any,
    worker_id: str,
    claimed: Mapping[str, Any],
) -> Callable[..., None]:
    def emit_event(*, event_type: str, message: str, detail_json: Optional[Any] = None) -> None:
        detail = dict(detail_json) if isinstance(detail_json, Mapping) else {}
        detail.setdefault("worker_id", worker_id)
        detail.setdefault("analysis_mode", claimed.get("analysis_mode"))
        repository.append_job_event(
            job_id=job_id,
            event_type=event_type,
            message=message,
            detail_json=detail,
        )

    return emit_event


class HeartbeatLoop:
    def __init__(
        self,
        *,
        repository: Any,
        job_id: Any,
        worker_id: str,
        interval_seconds: float,
        stderr: TextIO,
    ) -> None:
        self.repository = repository
        self.job_id = job_id
        self.worker_id = worker_id
        self.interval_seconds = max(float(interval_seconds), 0.001)
        self.stderr = stderr
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self) -> "HeartbeatLoop":
        self._thread = threading.Thread(target=self._run, name="analysis-job-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 1.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.repository.update_job_heartbeat(job_id=self.job_id, worker_id=self.worker_id)
            except Exception as exc:
                print(
                    "[analysis-job-worker] warning: "
                    f"heartbeat failed job_id={self.job_id}: {redact_worker_error(exc)}",
                    file=self.stderr,
                )
            self._stop.wait(self.interval_seconds)


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


def _format_cli_value(value: Any) -> str:
    if value is None:
        return "-"
    return str(value)


def _stale_candidate_reason(candidate: Mapping[str, Any]) -> str:
    if candidate.get("heartbeat_at") is None:
        return "missing_heartbeat_startup_grace"
    return "stale_heartbeat"


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
        help="seconds to sleep between empty loop-mode polls",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="loop mode only: process at most N claimed jobs and exit",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=30.0,
        help="seconds between heartbeat updates while a pipeline is running",
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
    parser.add_argument(
        "--recover-stale",
        action="store_true",
        help="list stale RUNNING full_report recovery candidates",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --recover-stale, list candidates without modifying jobs",
    )
    parser.add_argument(
        "--mark-failed",
        action="store_true",
        help="with --recover-stale, mark stale RUNNING candidates FAILED",
    )
    parser.add_argument(
        "--reason",
        default=None,
        help="operator reason required with --recover-stale --mark-failed",
    )
    parser.add_argument(
        "--stale-after-minutes",
        type=int,
        default=30,
        help="stale RUNNING heartbeat age threshold for --recover-stale",
    )
    parser.add_argument(
        "--startup-grace-minutes",
        type=int,
        default=5,
        help="missing-heartbeat startup grace threshold for --recover-stale",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="maximum stale RUNNING candidates to list for --recover-stale",
    )
    return parser


def main(
    argv: Optional[list[str]] = None,
    *,
    repository_factory: Callable[[], Any] = AnalysisJobRepository,
    runner_factory: Callable[..., Any] = FullReportJobRunner,
    sleep_fn: Callable[[float], None] = time.sleep,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.stale_after_minutes < 1:
        parser.error("--stale-after-minutes must be greater than or equal to 1")
    if args.startup_grace_minutes < 1:
        parser.error("--startup-grace-minutes must be greater than or equal to 1")
    if args.limit < 1 or args.limit > 100:
        parser.error("--limit must be between 1 and 100")
    if not args.recover_stale and args.mark_failed:
        parser.error("--mark-failed requires --recover-stale")
    if not args.recover_stale and args.reason is not None:
        parser.error("--reason requires --recover-stale --mark-failed")
    if args.recover_stale:
        if args.dry_run and args.mark_failed:
            parser.error("--dry-run cannot be used with --mark-failed")
        if not args.dry_run and not args.mark_failed:
            parser.error("--recover-stale requires either --dry-run or --mark-failed")
        if args.mark_failed and not str(args.reason or "").strip():
            parser.error("--reason is required with --recover-stale --mark-failed")
        if args.once or args.claim_only or args.run_pipeline or args.pipeline_dry_run:
            parser.error("--recover-stale cannot be combined with worker claim/run options")
        try:
            repository = repository_factory()
            if args.mark_failed:
                return run_recover_stale_mark_failed(
                    repository,
                    reason=str(args.reason or "").strip(),
                    stale_after_minutes=args.stale_after_minutes,
                    startup_grace_minutes=args.startup_grace_minutes,
                    limit=args.limit,
                    stdout=stdout,
                )
            return run_recover_stale_dry_run(
                repository,
                stale_after_minutes=args.stale_after_minutes,
                startup_grace_minutes=args.startup_grace_minutes,
                limit=args.limit,
                stdout=stdout,
            )
        except Exception as exc:
            print(f"[analysis-job-worker] error: {redact_worker_error(exc)}", file=stderr)
            return 1
    if args.dry_run:
        parser.error("--dry-run requires --recover-stale")
    if args.pipeline_dry_run and not args.run_pipeline:
        parser.error("--pipeline-dry-run requires --run-pipeline")
    if args.max_jobs is not None and args.max_jobs < 1:
        parser.error("--max-jobs must be greater than or equal to 1")
    if args.once and args.max_jobs is not None:
        parser.error("--max-jobs cannot be used with --once")
    if not args.once and args.claim_only:
        parser.error("loop mode does not support --claim-only")
    if not args.once and not args.run_pipeline:
        parser.error("loop mode requires --run-pipeline")
    worker_id = args.worker_id or build_default_worker_id()

    try:
        repository = repository_factory()
        runner = None
        if args.run_pipeline:
            runner = runner_factory(
                project_root=args.project_root,
                timeout_seconds=args.timeout_seconds,
                pipeline_dry_run=bool(args.pipeline_dry_run),
            )
        if not args.once:
            return run_loop(
                repository,
                worker_id=worker_id,
                runner=runner,
                max_jobs=args.max_jobs,
                sleep_seconds=args.sleep_seconds,
                heartbeat_interval=args.heartbeat_interval,
                sleep_fn=sleep_fn,
                stdout=stdout,
                stderr=stderr,
            )
        return run_once(
            repository,
            worker_id=worker_id,
            run_pipeline=bool(args.run_pipeline),
            runner=runner,
            heartbeat_interval=args.heartbeat_interval,
            stdout=stdout,
            stderr=stderr,
        )
    except Exception as exc:
        print(f"[analysis-job-worker] error: {redact_worker_error(exc)}", file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
