from __future__ import annotations

import inspect
from io import StringIO
from typing import Any, Dict, Optional

import analysis_job_worker


class FakeRepository:
    def __init__(self, claim_result: Optional[Dict[str, Any]] = None, error: Optional[Exception] = None) -> None:
        self.claim_result = claim_result
        self.error = error
        self.claim_worker_id: Optional[str] = None
        self.claim_calls = 0
        self.succeeded_calls = 0
        self.failed_calls = 0

    def claim_next_pending_full_report_job(self, *, worker_id: str) -> Optional[Dict[str, Any]]:
        self.claim_calls += 1
        self.claim_worker_id = worker_id
        if self.error:
            raise self.error
        return self.claim_result

    def mark_job_succeeded(self, **_: Any) -> bool:
        self.succeeded_calls += 1
        return True

    def mark_job_failed(self, **_: Any) -> bool:
        self.failed_calls += 1
        return True


def test_run_once_claims_pending_job_and_does_not_finish_it() -> None:
    repo = FakeRepository({"id": 123, "status": "RUNNING", "worker_id": "local-dev"})
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
    repo = FakeRepository({"id": 9, "status": "RUNNING", "worker_id": "worker-x"})
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
    repo = FakeRepository({"id": 1, "status": "RUNNING", "worker_id": "worker-x"})
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


def test_worker_source_does_not_call_pipeline_modules() -> None:
    source = inspect.getsource(analysis_job_worker)

    assert "export_db_logs_cli" not in source
    assert "run_analysis_pipeline" not in source
