from __future__ import annotations

import inspect
from io import StringIO
from typing import Any, Dict, Optional

import pytest

import analysis_job_worker


class FakeRepository:
    def __init__(
        self,
        claim_result: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        upsert_error: Optional[Exception] = None,
    ) -> None:
        self.claim_result = claim_result
        self.error = error
        self.upsert_error = upsert_error
        self.claim_worker_id: Optional[str] = None
        self.claim_calls = 0
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
        return self.claim_result

    def append_job_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)

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

    def run(self, job: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append(job)
        if self.error:
            raise self.error
        return self.result


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


def full_report_result() -> Dict[str, Any]:
    return {
        "artifact_root": "runs/jobs/123",
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


def test_main_loop_mode_is_not_enabled_in_claim_only_worker() -> None:
    repo = FakeRepository({"id": 1, "status": "RUNNING", "worker_id": "worker-x", "analysis_mode": "full_report"})
    stderr = StringIO()

    exit_code = analysis_job_worker.main(
        ["--worker-id", "worker-x"],
        repository_factory=lambda: repo,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 1
    assert repo.claim_calls == 0
    assert "loop mode is not enabled" in stderr.getvalue()


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
    assert repo.events == [
        {
            "job_id": 123,
            "event_type": "JOB_STARTED",
            "message": "Full report direct pipeline started",
            "detail_json": {"worker_id": "local-dev", "analysis_mode": "full_report"},
        }
    ]
    assert repo.upsert_calls[0]["job_id"] == 123
    assert repo.upsert_calls[0]["artifact_root"] == "runs/jobs/123"
    assert repo.upsert_calls[0]["stage2_report_path"] == "runs/jobs/123/stage2_report.json"
    assert repo.upsert_calls[0]["stage2_report_md_path"] == "runs/jobs/123/stage2_report.md"
    assert repo.upsert_calls[0]["viewer_payload_path"] == "runs/jobs/123/viewer_payload.json"
    assert "manifest_path" not in repo.upsert_calls[0]
    assert repo.succeeded_calls == 1
    assert repo.succeeded_kwargs[0]["job_id"] == 123
    assert repo.succeeded_kwargs[0]["worker_id"] == "local-dev"
    assert repo.failed_calls == 0
    assert "succeeded job_id=123 worker_id=local-dev" in stdout.getvalue()


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
    assert factory.calls == [{"project_root": "/tmp/project-root", "timeout_seconds": 321}]
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
