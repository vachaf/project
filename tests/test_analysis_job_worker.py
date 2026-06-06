from __future__ import annotations

import inspect
import threading
import time
from io import StringIO
from typing import Any, Dict, Optional

import pytest

import analysis_job_worker


class FakeRepository:
    def __init__(
        self,
        claim_result: Optional[Dict[str, Any]] = None,
        claim_results: Optional[list[Optional[Dict[str, Any]]]] = None,
        error: Optional[Exception] = None,
        upsert_error: Optional[Exception] = None,
        heartbeat_error: Optional[Exception] = None,
        stale_jobs: Optional[list[Dict[str, Any]]] = None,
    ) -> None:
        self.claim_result = claim_result
        self.claim_results = list(claim_results) if claim_results is not None else None
        self.error = error
        self.upsert_error = upsert_error
        self.heartbeat_error = heartbeat_error
        self.stale_jobs = stale_jobs or []
        self.claim_worker_id: Optional[str] = None
        self.claim_calls = 0
        self.stale_calls: list[Dict[str, Any]] = []
        self.stale_failed_calls: list[Dict[str, Any]] = []
        self.heartbeat_calls: list[Dict[str, Any]] = []
        self.events: list[Dict[str, Any]] = []
        self.upsert_calls: list[Dict[str, Any]] = []
        self.succeeded_kwargs: list[Dict[str, Any]] = []
        self.failed_kwargs: list[Dict[str, Any]] = []
        self.succeeded_calls = 0
        self.failed_calls = 0

    def claim_next_pending_full_report_job(self, *, worker_id: str) -> Optional[Dict[str, Any]]:
        self.claim_calls += 1
        self.claim_worker_id = worker_id
        if self.error:
            raise self.error
        if self.claim_results is not None:
            if self.claim_results:
                return self.claim_results.pop(0)
            return None
        return self.claim_result

    def find_stale_running_jobs(self, **kwargs: Any) -> list[Dict[str, Any]]:
        self.stale_calls.append(kwargs)
        return self.stale_jobs

    def mark_stale_job_failed(self, **kwargs: Any) -> bool:
        self.stale_failed_calls.append(kwargs)
        job_id = int(kwargs["job_id"])
        for job in self.stale_jobs:
            if int(job["id"]) == job_id and job["status"] == "RUNNING":
                job["status"] = "FAILED"
                job["error_message"] = f"Marked FAILED by operator: {kwargs['reason']}"
                self.events.append(
                    {
                        "job_id": job_id,
                        "event_type": "JOB_MARKED_FAILED_STALE",
                        "message": job["error_message"],
                        "detail_json": kwargs.get("detail_json"),
                    }
                )
                return True
        return False

    def append_job_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)

    def update_job_heartbeat(self, **kwargs: Any) -> bool:
        self.heartbeat_calls.append(kwargs)
        if self.heartbeat_error:
            raise self.heartbeat_error
        return True

    def upsert_analysis_report(self, **kwargs: Any) -> None:
        if self.upsert_error:
            raise self.upsert_error
        self.upsert_calls.append(kwargs)

    def mark_job_succeeded(self, **kwargs: Any) -> bool:
        self.succeeded_calls += 1
        self.succeeded_kwargs.append(kwargs)
        return True

    def mark_job_failed(self, **kwargs: Any) -> bool:
        self.failed_calls += 1
        self.failed_kwargs.append(kwargs)
        return True


class FakeRunner:
    def __init__(self, result: Optional[Dict[str, Any]] = None, error: Optional[Exception] = None) -> None:
        self.result = result or full_report_result()
        self.error = error
        self.calls: list[Dict[str, Any]] = []

    def run(self, job: Dict[str, Any], event_sink: Optional[Any] = None) -> Dict[str, Any]:
        self.calls.append(job)
        if self.error:
            raise self.error
        return self.result


class BlockingRunner(FakeRunner):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, job: Dict[str, Any], event_sink: Optional[Any] = None) -> Dict[str, Any]:
        self.calls.append(job)
        self.started.set()
        assert self.release.wait(timeout=2.0)
        return self.result


class SequencedRunner:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[Dict[str, Any]] = []

    def run(self, job: Dict[str, Any], event_sink: Optional[Any] = None) -> Dict[str, Any]:
        self.calls.append(job)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingRunnerFactory:
    def __init__(self, runner: FakeRunner) -> None:
        self.runner = runner
        self.calls: list[Dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> FakeRunner:
        self.calls.append(kwargs)
        return self.runner


def claimed_job() -> Dict[str, Any]:
    return {
        "id": 123,
        "status": "RUNNING",
        "worker_id": "local-dev",
        "analysis_mode": "full_report",
        "artifact_root": "runs/jobs/123",
    }


def claimed_job_with_id(job_id: int) -> Dict[str, Any]:
    job = claimed_job()
    job.update(
        {
            "id": job_id,
            "artifact_root": f"runs/jobs/{job_id}",
        }
    )
    return job


def stale_running_job(
    *,
    job_id: int = 123,
    heartbeat_at: Optional[str] = "2026-06-01 10:00:00.000",
) -> Dict[str, Any]:
    return {
        "id": job_id,
        "status": "RUNNING",
        "analysis_mode": "full_report",
        "worker_id": "worker-stale",
        "started_at": "2026-06-01 09:55:00.000",
        "heartbeat_at": heartbeat_at,
        "attempt_count": 1,
        "max_attempts": 1,
        "artifact_root": f"runs/jobs/{job_id}",
        "error_message": None,
    }


def full_report_result() -> Dict[str, Any]:
    return {
        "artifact_root": "runs/jobs/123",
        "summary": None,
        "no_data": False,
        "export_path": "runs/jobs/123/export.json",
        "llm_input_path": "runs/jobs/123/llm_input.json",
        "analysis_candidates_path": None,
        "noise_summary_path": "runs/jobs/123/noise_summary.json",
        "stage1_result_path": "runs/jobs/123/stage1_results.json",
        "stage2_report_path": "runs/jobs/123/stage2_report.json",
        "stage2_report_md_path": "runs/jobs/123/stage2_report.md",
        "viewer_payload_path": "runs/jobs/123/viewer_payload.json",
        "lint_result_path": None,
        "window_summary_path": None,
        "rollup_input_path": None,
        "rollup_summary_path": None,
        "operator_queue_items_path": None,
        "operator_queue_summary_path": None,
        "manifest_path": "runs/jobs/123/manifest.json",
    }


def no_data_result() -> Dict[str, Any]:
    result = full_report_result()
    result.update(
        {
            "summary": "No logs found in requested time range.",
            "no_data": True,
            "llm_input_path": None,
            "analysis_candidates_path": None,
            "noise_summary_path": None,
            "stage1_result_path": None,
            "stage2_report_path": None,
            "stage2_report_md_path": None,
            "viewer_payload_path": None,
            "lint_result_path": None,
        }
    )
    return result


class StageError(RuntimeError):
    def __init__(
        self,
        message: str,
        failed_at_stage: str,
        *,
        command_label: Optional[str] = None,
        returncode: Optional[int] = None,
        stdout_tail: Optional[str] = None,
        stderr_tail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.failed_at_stage = failed_at_stage
        self.command_label = command_label
        self.returncode = returncode
        self.stdout_tail = stdout_tail
        self.stderr_tail = stderr_tail


def _eventually(predicate: Any, *, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_run_once_claims_pending_job_and_does_not_finish_it() -> None:
    repo = FakeRepository(claimed_job())
    stdout = StringIO()

    exit_code = analysis_job_worker.run_once(repo, worker_id="local-dev", stdout=stdout)

    assert exit_code == 0
    assert repo.claim_calls == 1
    assert repo.claim_worker_id == "local-dev"
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 0
    assert "[analysis-job-worker] claimed job_id=123 status=RUNNING worker_id=local-dev" in stdout.getvalue()


def test_run_once_returns_zero_when_no_pending_job_exists() -> None:
    repo = FakeRepository(None)
    stdout = StringIO()

    exit_code = analysis_job_worker.run_once(repo, worker_id="local-dev", stdout=stdout)

    assert exit_code == 0
    assert repo.claim_calls == 1
    assert "[analysis-job-worker] no pending full_report job" in stdout.getvalue()


def test_main_once_passes_explicit_worker_id_to_repository() -> None:
    repo = FakeRepository({"id": 9, "status": "RUNNING", "worker_id": "worker-x", "analysis_mode": "full_report"})
    stdout = StringIO()
    stderr = StringIO()

    exit_code = analysis_job_worker.main(
        ["--once", "--worker-id", "worker-x"],
        repository_factory=lambda: repo,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert repo.claim_worker_id == "worker-x"
    assert stderr.getvalue() == ""


def test_main_once_generates_default_worker_id_when_not_provided() -> None:
    repo = FakeRepository(None)

    exit_code = analysis_job_worker.main(
        ["--once"],
        repository_factory=lambda: repo,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repo.claim_worker_id


def test_recover_stale_dry_run_lists_candidates_without_mutation() -> None:
    stale_with_heartbeat = stale_running_job(job_id=123)
    stale_missing_heartbeat = stale_running_job(job_id=124, heartbeat_at=None)
    repo = FakeRepository(stale_jobs=[stale_with_heartbeat, stale_missing_heartbeat])
    stdout = StringIO()

    exit_code = analysis_job_worker.main(
        [
            "--recover-stale",
            "--dry-run",
            "--stale-after-minutes",
            "30",
            "--startup-grace-minutes",
            "5",
            "--limit",
            "20",
        ],
        repository_factory=lambda: repo,
        stdout=stdout,
        stderr=StringIO(),
    )

    output = stdout.getvalue()
    assert exit_code == 0
    assert repo.stale_calls == [
        {"stale_after_minutes": 30, "startup_grace_minutes": 5, "limit": 20}
    ]
    assert repo.claim_calls == 0
    assert repo.events == []
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 0
    assert stale_with_heartbeat["status"] == "RUNNING"
    assert stale_with_heartbeat["artifact_root"] == "runs/jobs/123"
    assert stale_missing_heartbeat["status"] == "RUNNING"
    assert stale_missing_heartbeat["artifact_root"] == "runs/jobs/124"
    assert "candidate_count=2" in output
    assert "job_id=123" in output
    assert "worker_id=worker-stale" in output
    assert "attempts=1/1" in output
    assert "artifact_root=runs/jobs/123" in output
    assert "reason=stale_heartbeat" in output
    assert "job_id=124" in output
    assert "heartbeat_at=-" in output
    assert "reason=missing_heartbeat_startup_grace" in output


def test_recover_stale_dry_run_returns_zero_when_no_candidates() -> None:
    repo = FakeRepository(stale_jobs=[])
    stdout = StringIO()

    exit_code = analysis_job_worker.main(
        ["--recover-stale", "--dry-run"],
        repository_factory=lambda: repo,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repo.stale_calls == [
        {"stale_after_minutes": 30, "startup_grace_minutes": 5, "limit": 20}
    ]
    assert repo.claim_calls == 0
    assert repo.events == []
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 0
    assert "candidate_count=0" in stdout.getvalue()
    assert "no stale RUNNING candidates" in stdout.getvalue()


def test_recover_stale_without_dry_run_is_unsupported_and_does_not_mutate() -> None:
    stale_job = stale_running_job()
    repo = FakeRepository(stale_jobs=[stale_job])

    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(
            ["--recover-stale"],
            repository_factory=lambda: repo,
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert exc.value.code == 2
    assert repo.stale_calls == []
    assert repo.claim_calls == 0
    assert repo.events == []
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 0
    assert stale_job["status"] == "RUNNING"
    assert stale_job["artifact_root"] == "runs/jobs/123"


def test_recover_stale_mark_failed_marks_candidates_and_records_events() -> None:
    stale_with_heartbeat = stale_running_job(job_id=123)
    stale_missing_heartbeat = stale_running_job(job_id=124, heartbeat_at=None)
    repo = FakeRepository(stale_jobs=[stale_with_heartbeat, stale_missing_heartbeat])
    stdout = StringIO()

    exit_code = analysis_job_worker.main(
        [
            "--recover-stale",
            "--mark-failed",
            "--reason",
            "manual smoke confirmed worker stopped",
            "--stale-after-minutes",
            "30",
            "--startup-grace-minutes",
            "5",
            "--limit",
            "20",
        ],
        repository_factory=lambda: repo,
        stdout=stdout,
        stderr=StringIO(),
    )

    output = stdout.getvalue()
    assert exit_code == 0
    assert repo.stale_calls == [
        {"stale_after_minutes": 30, "startup_grace_minutes": 5, "limit": 20}
    ]
    assert [call["job_id"] for call in repo.stale_failed_calls] == [123, 124]
    assert all(call["reason"] == "manual smoke confirmed worker stopped" for call in repo.stale_failed_calls)
    assert repo.stale_failed_calls[0]["detail_json"]["stale_reason"] == "stale_heartbeat"
    assert repo.stale_failed_calls[1]["detail_json"]["stale_reason"] == "missing_heartbeat_startup_grace"
    assert stale_with_heartbeat["status"] == "FAILED"
    assert stale_missing_heartbeat["status"] == "FAILED"
    assert stale_with_heartbeat["artifact_root"] == "runs/jobs/123"
    assert stale_with_heartbeat["attempt_count"] == 1
    assert len(repo.events) == 2
    assert repo.events[0]["event_type"] == "JOB_MARKED_FAILED_STALE"
    assert "candidate_count=2" in output
    assert "job_id=123" in output
    assert "reason=stale_heartbeat action=marked_failed" in output
    assert "job_id=124" in output
    assert "reason=missing_heartbeat_startup_grace action=marked_failed" in output
    assert "marked_count=2 skipped_count=0" in output
    assert repo.claim_calls == 0
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 0


def test_recover_stale_mark_failed_returns_zero_when_no_candidates() -> None:
    repo = FakeRepository(stale_jobs=[])
    stdout = StringIO()

    exit_code = analysis_job_worker.main(
        ["--recover-stale", "--mark-failed", "--reason", "manual check"],
        repository_factory=lambda: repo,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repo.stale_calls == [
        {"stale_after_minutes": 30, "startup_grace_minutes": 5, "limit": 20}
    ]
    assert repo.stale_failed_calls == []
    assert repo.events == []
    assert "candidate_count=0" in stdout.getvalue()
    assert "no stale RUNNING candidates" in stdout.getvalue()


def test_recover_stale_dry_run_and_mark_failed_are_mutually_exclusive() -> None:
    repo = FakeRepository(stale_jobs=[stale_running_job()])

    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(
            ["--recover-stale", "--dry-run", "--mark-failed", "--reason", "manual check"],
            repository_factory=lambda: repo,
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert exc.value.code == 2
    assert repo.stale_calls == []
    assert repo.stale_failed_calls == []
    assert repo.events == []


def test_recover_stale_mark_failed_requires_reason() -> None:
    repo = FakeRepository(stale_jobs=[stale_running_job()])

    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(
            ["--recover-stale", "--mark-failed"],
            repository_factory=lambda: repo,
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert exc.value.code == 2
    assert repo.stale_calls == []
    assert repo.stale_failed_calls == []
    assert repo.events == []


def test_mark_failed_without_recover_stale_is_argparse_error() -> None:
    repo = FakeRepository(stale_jobs=[stale_running_job()])

    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(
            ["--mark-failed", "--reason", "manual check"],
            repository_factory=lambda: repo,
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert exc.value.code == 2
    assert repo.stale_calls == []
    assert repo.stale_failed_calls == []
    assert repo.events == []


def test_build_default_worker_id_uses_hostname_and_pid(monkeypatch: Any) -> None:
    monkeypatch.setattr(analysis_job_worker.socket, "gethostname", lambda: "host-a")
    monkeypatch.setattr(analysis_job_worker.os, "getpid", lambda: 4321)

    assert analysis_job_worker.build_default_worker_id() == "host-a-4321"


def test_main_returns_one_and_redacts_repository_exception() -> None:
    repo = FakeRepository(error=RuntimeError("db failed password=plain token=abc123"))
    stderr = StringIO()

    exit_code = analysis_job_worker.main(
        ["--once", "--worker-id", "worker-x"],
        repository_factory=lambda: repo,
        stdout=StringIO(),
        stderr=stderr,
    )

    output = stderr.getvalue()
    assert exit_code == 1
    assert "[analysis-job-worker] error:" in output
    assert "plain" not in output
    assert "abc123" not in output
    assert "[REDACTED]" in output


def test_main_loop_mode_without_run_pipeline_is_argparse_error() -> None:
    repo = FakeRepository({"id": 1, "status": "RUNNING", "worker_id": "worker-x", "analysis_mode": "full_report"})

    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(
            ["--worker-id", "worker-x"],
            repository_factory=lambda: repo,
            stdout=StringIO(),
            stderr=StringIO(),
        )

    assert exc.value.code == 2
    assert repo.claim_calls == 0


def test_main_claim_only_flag_does_not_call_runner() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner()
    factory = RecordingRunnerFactory(runner)

    exit_code = analysis_job_worker.main(
        ["--once", "--claim-only", "--worker-id", "local-dev"],
        repository_factory=lambda: repo,
        runner_factory=factory,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert factory.calls == []
    assert runner.calls == []
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 0


def test_main_once_without_run_pipeline_preserves_claim_only_default() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner()
    factory = RecordingRunnerFactory(runner)

    exit_code = analysis_job_worker.main(
        ["--once", "--worker-id", "local-dev"],
        repository_factory=lambda: repo,
        runner_factory=factory,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert runner.calls == []
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 0


def test_run_pipeline_without_dry_run_passes_pipeline_dry_run_false() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner()
    factory = RecordingRunnerFactory(runner)

    exit_code = analysis_job_worker.main(
        ["--once", "--run-pipeline", "--worker-id", "local-dev"],
        repository_factory=lambda: repo,
        runner_factory=factory,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert factory.calls == [{"project_root": None, "timeout_seconds": None, "pipeline_dry_run": False}]


def test_run_pipeline_with_pipeline_dry_run_passes_true_to_runner_factory() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner()
    factory = RecordingRunnerFactory(runner)

    exit_code = analysis_job_worker.main(
        ["--once", "--run-pipeline", "--pipeline-dry-run", "--worker-id", "local-dev"],
        repository_factory=lambda: repo,
        runner_factory=factory,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert factory.calls == [{"project_root": None, "timeout_seconds": None, "pipeline_dry_run": True}]


def test_main_without_once_and_run_pipeline_enters_loop_mode() -> None:
    repo = FakeRepository(claim_results=[claimed_job_with_id(1)])
    runner = FakeRunner()
    factory = RecordingRunnerFactory(runner)
    stdout = StringIO()

    exit_code = analysis_job_worker.main(
        ["--run-pipeline", "--max-jobs", "1", "--worker-id", "local-dev"],
        repository_factory=lambda: repo,
        runner_factory=factory,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repo.claim_calls == 1
    assert runner.calls == [claimed_job_with_id(1)]
    assert repo.succeeded_calls == 1
    assert "loop started worker_id=local-dev" in stdout.getvalue()


def test_loop_mode_processes_two_pending_jobs_sequentially() -> None:
    repo = FakeRepository(claim_results=[claimed_job_with_id(1), claimed_job_with_id(2)])
    runner = FakeRunner()

    exit_code = analysis_job_worker.run_loop(
        repo,
        worker_id="local-dev",
        runner=runner,
        max_jobs=2,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert [call["id"] for call in runner.calls] == [1, 2]
    assert [call["job_id"] for call in repo.upsert_calls] == [1, 2]
    assert repo.succeeded_calls == 2


def test_loop_mode_max_jobs_one_processes_one_job_and_exits() -> None:
    repo = FakeRepository(claim_results=[claimed_job_with_id(1), claimed_job_with_id(2)])
    runner = FakeRunner()

    exit_code = analysis_job_worker.run_loop(
        repo,
        worker_id="local-dev",
        runner=runner,
        max_jobs=1,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repo.claim_calls == 1
    assert [call["id"] for call in runner.calls] == [1]


def test_loop_mode_sleeps_when_no_pending_job_then_polls_again() -> None:
    repo = FakeRepository(claim_results=[None, claimed_job_with_id(1)])
    runner = FakeRunner()
    sleep_calls: list[float] = []

    exit_code = analysis_job_worker.run_loop(
        repo,
        worker_id="local-dev",
        runner=runner,
        max_jobs=1,
        sleep_seconds=0.25,
        sleep_fn=sleep_calls.append,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repo.claim_calls == 2
    assert sleep_calls == [0.25]
    assert [call["id"] for call in runner.calls] == [1]


def test_loop_mode_claim_only_is_argparse_error() -> None:
    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(["--claim-only"])

    assert exc.value.code == 2


def test_max_jobs_with_once_is_argparse_error() -> None:
    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(["--once", "--max-jobs", "1"])

    assert exc.value.code == 2


def test_pipeline_dry_run_without_run_pipeline_is_argparse_error() -> None:
    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(["--once", "--pipeline-dry-run"])

    assert exc.value.code == 2


def test_claim_only_with_pipeline_dry_run_is_argparse_error() -> None:
    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(["--once", "--claim-only", "--pipeline-dry-run"])

    assert exc.value.code == 2


def test_run_pipeline_success_runs_runner_upserts_report_and_marks_succeeded() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner()
    stdout = StringIO()

    exit_code = analysis_job_worker.run_once(
        repo,
        worker_id="local-dev",
        run_pipeline=True,
        runner=runner,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert runner.calls == [claimed_job()]
    assert [event["event_type"] for event in repo.events] == [
        "JOB_STARTED",
        "REPORT_SAVE_STARTED",
        "REPORT_SAVE_COMPLETED",
    ]
    assert repo.events[0] == {
        "job_id": 123,
        "event_type": "JOB_STARTED",
        "message": "Full report direct pipeline started",
        "detail_json": {"worker_id": "local-dev", "analysis_mode": "full_report"},
    }
    assert repo.upsert_calls[0]["job_id"] == 123
    assert repo.upsert_calls[0]["summary"] is None
    assert repo.upsert_calls[0]["artifact_root"] == "runs/jobs/123"
    assert repo.upsert_calls[0]["stage2_report_path"] == "runs/jobs/123/stage2_report.json"
    assert repo.upsert_calls[0]["stage2_report_md_path"] == "runs/jobs/123/stage2_report.md"
    assert repo.upsert_calls[0]["viewer_payload_path"] == "runs/jobs/123/viewer_payload.json"
    assert "manifest_path" not in repo.upsert_calls[0]
    assert "no_data" not in repo.upsert_calls[0]
    assert repo.succeeded_calls == 1
    assert repo.succeeded_kwargs[0]["job_id"] == 123
    assert repo.succeeded_kwargs[0]["worker_id"] == "local-dev"
    assert repo.succeeded_kwargs[0]["detail_json"]["worker_id"] == "local-dev"
    assert "duration_seconds" in repo.events[2]["detail_json"]
    assert repo.events[2]["detail_json"]["duration_seconds"] >= 0
    assert repo.failed_calls == 0
    assert "succeeded job_id=123 worker_id=local-dev" in stdout.getvalue()


def test_run_pipeline_no_data_upserts_summary_appends_event_and_marks_succeeded() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner(result=no_data_result())

    exit_code = analysis_job_worker.run_once(
        repo,
        worker_id="local-dev",
        run_pipeline=True,
        runner=runner,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repo.upsert_calls[0]["summary"] == "No logs found in requested time range."
    assert repo.upsert_calls[0]["export_path"] == "runs/jobs/123/export.json"
    assert repo.upsert_calls[0]["stage2_report_path"] is None
    assert [event["event_type"] for event in repo.events] == [
        "JOB_STARTED",
        "JOB_NO_DATA",
        "REPORT_SAVE_STARTED",
        "REPORT_SAVE_COMPLETED",
    ]
    assert repo.events[1] == {
        "job_id": 123,
        "event_type": "JOB_NO_DATA",
        "message": "No logs found in requested time range",
        "detail_json": {
            "worker_id": "local-dev",
            "artifact_root": "runs/jobs/123",
            "export_path": "runs/jobs/123/export.json",
        },
    }
    assert repo.succeeded_calls == 1
    assert repo.succeeded_kwargs[0]["detail_json"]["worker_id"] == "local-dev"
    assert "duration_seconds" in repo.events[3]["detail_json"]
    assert repo.events[3]["detail_json"]["duration_seconds"] >= 0
    assert repo.failed_calls == 0


def test_run_pipeline_passes_event_sink_to_runner() -> None:
    repo = FakeRepository(claimed_job())

    class EmittingRunner(FakeRunner):
        def run(self, job: Dict[str, Any], event_sink: Optional[Any] = None) -> Dict[str, Any]:
            self.calls.append(job)
            assert event_sink is not None
            event_sink(
                event_type="EXPORT_STARTED",
                message="Export started",
                detail_json={"artifact_root": "runs/jobs/123"},
            )
            return self.result

    runner = EmittingRunner()

    exit_code = analysis_job_worker.run_once(
        repo,
        worker_id="local-dev",
        run_pipeline=True,
        runner=runner,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert repo.events[1] == {
        "job_id": 123,
        "event_type": "EXPORT_STARTED",
        "message": "Export started",
        "detail_json": {
            "worker_id": "local-dev",
            "analysis_mode": "full_report",
            "artifact_root": "runs/jobs/123",
        },
    }


def test_run_pipeline_runner_failure_marks_failed_with_redacted_error() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner(error=RuntimeError("pipeline failed token=abc123"))
    stderr = StringIO()

    exit_code = analysis_job_worker.run_once(
        repo,
        worker_id="local-dev",
        run_pipeline=True,
        runner=runner,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 1
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 1
    assert repo.failed_kwargs[0]["job_id"] == 123
    assert repo.failed_kwargs[0]["worker_id"] == "local-dev"
    assert "abc123" not in repo.failed_kwargs[0]["error_message"]
    assert "[REDACTED]" in repo.failed_kwargs[0]["error_message"]
    assert "abc123" not in stderr.getvalue()


def test_run_pipeline_runner_stage_failure_marks_failed_at_stage() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner(error=StageError("pipeline failed token=abc123", "pipeline"))

    exit_code = analysis_job_worker.run_once(
        repo,
        worker_id="local-dev",
        run_pipeline=True,
        runner=runner,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 1
    assert repo.failed_calls == 1
    assert repo.failed_kwargs[0]["detail_json"]["failed_at_stage"] == "pipeline"
    assert "abc123" not in repo.failed_kwargs[0]["error_message"]


def test_run_pipeline_runner_subprocess_failure_records_limited_diagnostics() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner(
        error=StageError(
            "full_report pipeline failed at pipeline: returncode=8 stderr_tail=failed token=abc123",
            "pipeline",
            command_label="run_analysis_pipeline.py",
            returncode=8,
            stdout_tail="pipeline stdout tail",
            stderr_tail="pipeline stderr tail token=abc123",
        )
    )

    exit_code = analysis_job_worker.run_once(
        repo,
        worker_id="local-dev",
        run_pipeline=True,
        runner=runner,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    detail = repo.failed_kwargs[0]["detail_json"]
    assert exit_code == 1
    assert detail["failed_at_stage"] == "pipeline"
    assert detail["command_label"] == "run_analysis_pipeline.py"
    assert detail["returncode"] == 8
    assert detail["stdout_tail"] == "pipeline stdout tail"
    assert "abc123" not in detail["stderr_tail"]
    assert "[REDACTED]" in detail["stderr_tail"]
    assert "abc123" not in repo.failed_kwargs[0]["error_message"]


def test_loop_mode_runner_failure_marks_failed_then_continues() -> None:
    repo = FakeRepository(claim_results=[claimed_job_with_id(1), claimed_job_with_id(2)])
    runner = SequencedRunner([RuntimeError("pipeline failed token=abc123"), full_report_result()])
    stderr = StringIO()

    exit_code = analysis_job_worker.run_loop(
        repo,
        worker_id="local-dev",
        runner=runner,
        max_jobs=2,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 0
    assert [call["id"] for call in runner.calls] == [1, 2]
    assert repo.failed_calls == 1
    assert repo.failed_kwargs[0]["job_id"] == 1
    assert "abc123" not in repo.failed_kwargs[0]["error_message"]
    assert repo.succeeded_calls == 1
    assert repo.succeeded_kwargs[0]["job_id"] == 2


def test_heartbeat_updater_is_called_while_runner_executes() -> None:
    repo = FakeRepository(claimed_job())
    runner = BlockingRunner()
    stdout = StringIO()
    stderr = StringIO()
    result_holder: Dict[str, Any] = {}

    thread = threading.Thread(
        target=lambda: result_holder.update(
            {
                "exit_code": analysis_job_worker.run_once(
                    repo,
                    worker_id="local-dev",
                    run_pipeline=True,
                    runner=runner,
                    heartbeat_interval=0.01,
                    stdout=stdout,
                    stderr=stderr,
                )
            }
        )
    )
    thread.start()
    assert runner.started.wait(timeout=2.0)
    assert _eventually(lambda: len(repo.heartbeat_calls) >= 1)
    runner.release.set()
    thread.join(timeout=2.0)

    assert result_holder["exit_code"] == 0
    assert repo.heartbeat_calls[0] == {"job_id": 123, "worker_id": "local-dev"}


def test_heartbeat_failure_does_not_block_runner_success() -> None:
    repo = FakeRepository(claimed_job(), heartbeat_error=RuntimeError("db failed token=abc123"))
    runner = FakeRunner()
    stderr = StringIO()

    exit_code = analysis_job_worker.run_once(
        repo,
        worker_id="local-dev",
        run_pipeline=True,
        runner=runner,
        heartbeat_interval=0.01,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 0
    assert repo.succeeded_calls == 1
    assert "heartbeat failed job_id=123" in stderr.getvalue()
    assert "abc123" not in stderr.getvalue()


def test_loop_mode_keyboard_interrupt_during_idle_sleep_returns_130() -> None:
    repo = FakeRepository(claim_results=[None])

    def interrupting_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    exit_code = analysis_job_worker.run_loop(
        repo,
        worker_id="local-dev",
        runner=FakeRunner(),
        sleep_fn=interrupting_sleep,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 130
    assert repo.claim_calls == 1


def test_run_pipeline_upsert_failure_marks_failed() -> None:
    repo = FakeRepository(claimed_job(), upsert_error=RuntimeError("db failed password=plain"))
    runner = FakeRunner()
    stderr = StringIO()

    exit_code = analysis_job_worker.run_once(
        repo,
        worker_id="local-dev",
        run_pipeline=True,
        runner=runner,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 1
    assert repo.succeeded_calls == 0
    assert repo.failed_calls == 1
    assert "plain" not in repo.failed_kwargs[0]["error_message"]
    assert "[REDACTED]" in repo.failed_kwargs[0]["error_message"]
    assert [event["event_type"] for event in repo.events] == [
        "JOB_STARTED",
        "REPORT_SAVE_STARTED",
        "REPORT_SAVE_FAILED",
    ]
    assert repo.events[-1]["detail_json"]["failed_at_stage"] == "report_save"
    assert "duration_seconds" in repo.events[-1]["detail_json"]
    assert repo.events[-1]["detail_json"]["duration_seconds"] >= 0
    assert repo.failed_kwargs[0]["detail_json"]["failed_at_stage"] == "report_save"


def test_claim_exception_before_job_does_not_mark_failed() -> None:
    repo = FakeRepository(error=RuntimeError("claim failed token=abc123"))
    stderr = StringIO()

    exit_code = analysis_job_worker.main(
        ["--once", "--run-pipeline", "--worker-id", "local-dev"],
        repository_factory=lambda: repo,
        runner_factory=RecordingRunnerFactory(FakeRunner()),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 1
    assert repo.failed_calls == 0
    assert "abc123" not in stderr.getvalue()


def test_run_pipeline_and_claim_only_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit) as exc:
        analysis_job_worker.main(["--once", "--run-pipeline", "--claim-only"])

    assert exc.value.code == 2


def test_main_passes_timeout_and_project_root_to_runner_factory() -> None:
    repo = FakeRepository(claimed_job())
    runner = FakeRunner()
    factory = RecordingRunnerFactory(runner)

    exit_code = analysis_job_worker.main(
        [
            "--once",
            "--run-pipeline",
            "--worker-id",
            "worker-x",
            "--timeout-seconds",
            "321",
            "--project-root",
            "/tmp/project-root",
        ],
        repository_factory=lambda: repo,
        runner_factory=factory,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert factory.calls == [{"project_root": "/tmp/project-root", "timeout_seconds": 321, "pipeline_dry_run": False}]
    assert repo.claim_worker_id == "worker-x"
    assert repo.succeeded_kwargs[0]["worker_id"] == "worker-x"


def test_worker_source_does_not_call_pipeline_modules() -> None:
    source = inspect.getsource(analysis_job_worker)

    assert "export_db_logs_cli" not in source
    assert "run_analysis_pipeline" not in source


def test_worker_does_not_upsert_manifest_or_handle_windowed_triage() -> None:
    source = inspect.getsource(analysis_job_worker)

    assert "manifest_path" not in source
    assert "windowed_triage" not in source
