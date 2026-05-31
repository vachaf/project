#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")
DEFAULT_REQUESTED_TIMEZONE = "Asia/Seoul"
DEFAULT_ANALYSIS_MODE = "full_report"


class FullReportRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class FullReportJob:
    id: int
    time_from: datetime
    time_to: datetime
    requested_timezone: str
    artifact_root: str
    analysis_mode: str

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "FullReportJob":
        return cls(
            id=int(row["id"]),
            time_from=_coerce_datetime(row["time_from"], "time_from"),
            time_to=_coerce_datetime(row["time_to"], "time_to"),
            requested_timezone=str(row.get("requested_timezone") or ""),
            artifact_root=str(row.get("artifact_root") or ""),
            analysis_mode=str(row.get("analysis_mode") or ""),
        )


@dataclass(frozen=True)
class FullReportRunResult:
    artifact_root: str
    summary: Optional[str]
    no_data: bool
    export_path: Optional[str]
    llm_input_path: Optional[str]
    analysis_candidates_path: Optional[str]
    noise_summary_path: Optional[str]
    stage1_result_path: Optional[str]
    stage2_report_path: Optional[str]
    stage2_report_md_path: Optional[str]
    viewer_payload_path: Optional[str]
    lint_result_path: Optional[str]
    window_summary_path: Optional[str] = None
    rollup_input_path: Optional[str] = None
    rollup_summary_path: Optional[str] = None
    operator_queue_items_path: Optional[str] = None
    operator_queue_summary_path: Optional[str] = None

    def as_upsert_kwargs(self) -> dict[str, Any]:
        return asdict(self)


SubprocessRun = Callable[..., subprocess.CompletedProcess[str]]


class FullReportJobRunner:
    def __init__(
        self,
        *,
        project_root: Path | str | None = None,
        python_executable: str = sys.executable,
        export_table: str = "security",
        pipeline_mode: str = "routine",
        pipeline_dry_run: bool = False,
        timeout_seconds: Optional[int] = None,
        env: Optional[Mapping[str, str]] = None,
        subprocess_run: SubprocessRun = subprocess.run,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1]).expanduser().resolve()
        self.python_executable = python_executable
        self.export_table = export_table
        self.pipeline_mode = pipeline_mode
        self.pipeline_dry_run = bool(pipeline_dry_run)
        self.timeout_seconds = timeout_seconds
        self.env = dict(env) if env is not None else None
        self.subprocess_run = subprocess_run

    def run(self, job_row: Mapping[str, Any]) -> FullReportRunResult:
        job = FullReportJob.from_mapping(job_row)
        self._validate_job(job)

        artifact_root_path = self._resolve_under_project_root(job.artifact_root)
        if artifact_root_path.exists():
            raise FileExistsError(f"artifact_root already exists: {artifact_root_path}")

        scratch_root = self.project_root / "runs" / "jobs" / ".scratch" / f"job_{job.id}"
        scratch_export_path = scratch_root / f"job_{job.id}_export.json"
        scratch_work_dir = scratch_root / "work"
        scratch_root.mkdir(parents=True, exist_ok=True)
        scratch_work_dir.mkdir(parents=True, exist_ok=True)

        export_cmd = self.build_export_command(job, scratch_export_path)
        self._run_subprocess(export_cmd, "export")
        if self._is_no_data_export(scratch_export_path):
            return self._materialize_no_data_result(
                artifact_root_path=artifact_root_path,
                scratch_export_path=scratch_export_path,
            )

        pipeline_cmd = self.build_pipeline_command(
            job=job,
            scratch_export_path=scratch_export_path,
            scratch_work_dir=scratch_work_dir,
            artifact_root_path=artifact_root_path,
        )
        self._run_subprocess(pipeline_cmd, "pipeline")

        return self.build_artifact_mapping(job.artifact_root, scratch_work_dir=scratch_work_dir)

    def build_export_command(self, job: FullReportJob, scratch_export_path: Path) -> list[str]:
        return [
            self.python_executable,
            str(self.project_root / "src" / "export_db_logs_cli.py"),
            "--start",
            self.utc_naive_to_kst_text(job.time_from),
            "--end",
            self.utc_naive_to_kst_text(job.time_to),
            "--table",
            self.export_table,
            "--pretty",
            "--out",
            str(scratch_export_path),
        ]

    def build_pipeline_command(
        self,
        *,
        job: FullReportJob,
        scratch_export_path: Path,
        scratch_work_dir: Path,
        artifact_root_path: Path,
    ) -> list[str]:
        cmd = [
            self.python_executable,
            str(self.project_root / "src" / "run_analysis_pipeline.py"),
            "--export-input",
            str(scratch_export_path),
            "--work-dir",
            str(scratch_work_dir),
            "--base-name",
            f"job_{job.id}",
            "--run-dir",
            str(artifact_root_path),
            "--mode",
            self.pipeline_mode,
            "--pretty",
        ]
        if self.pipeline_dry_run:
            cmd.append("--dry-run")
        return cmd

    def build_artifact_mapping(self, artifact_root: str, *, scratch_work_dir: Path) -> FullReportRunResult:
        artifact_root_path = self._resolve_under_project_root(artifact_root)
        required_files = {
            "export_path": artifact_root_path / "export.json",
            "llm_input_path": artifact_root_path / "llm_input.json",
            "noise_summary_path": artifact_root_path / "noise_summary.json",
            "stage1_result_path": artifact_root_path / "stage1_results.json",
            "stage2_report_path": artifact_root_path / "stage2_report.json",
            "stage2_report_md_path": artifact_root_path / "stage2_report.md",
            "viewer_payload_path": artifact_root_path / "viewer_payload.json",
        }
        missing = [str(path) for path in required_files.values() if not path.exists()]
        if missing:
            raise FullReportRunnerError("required full_report artifacts missing: " + ", ".join(missing))

        analysis_candidates_path = artifact_root_path / "analysis_candidates.json"

        return FullReportRunResult(
            artifact_root=self.normalize_relative_path(artifact_root_path),
            summary=None,
            no_data=False,
            export_path=self.normalize_relative_path(required_files["export_path"]),
            llm_input_path=self.normalize_relative_path(required_files["llm_input_path"]),
            analysis_candidates_path=self.normalize_relative_path(analysis_candidates_path) if analysis_candidates_path.exists() else None,
            noise_summary_path=self.normalize_relative_path(required_files["noise_summary_path"]),
            stage1_result_path=self.normalize_relative_path(required_files["stage1_result_path"]),
            stage2_report_path=self.normalize_relative_path(required_files["stage2_report_path"]),
            stage2_report_md_path=self.normalize_relative_path(required_files["stage2_report_md_path"]),
            viewer_payload_path=self.normalize_relative_path(required_files["viewer_payload_path"]),
            lint_result_path=None,
        )

    def _is_no_data_export(self, export_path: Path) -> bool:
        try:
            with open(export_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            raise FullReportRunnerError(f"failed to read export JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise FullReportRunnerError("export JSON must be an object")
        meta = payload.get("meta")
        if not isinstance(meta, dict) or "total_count" not in meta:
            return False
        try:
            return int(meta.get("total_count") or 0) == 0
        except (TypeError, ValueError) as exc:
            raise FullReportRunnerError(f"invalid export total_count: {meta.get('total_count')}") from exc

    def _materialize_no_data_result(
        self,
        *,
        artifact_root_path: Path,
        scratch_export_path: Path,
    ) -> FullReportRunResult:
        artifact_root_path.mkdir(parents=True, exist_ok=False)
        export_path = artifact_root_path / "export.json"
        shutil.copy2(scratch_export_path, export_path)
        return FullReportRunResult(
            artifact_root=self.normalize_relative_path(artifact_root_path),
            summary="No logs found in requested time range.",
            no_data=True,
            export_path=self.normalize_relative_path(export_path),
            llm_input_path=None,
            analysis_candidates_path=None,
            noise_summary_path=None,
            stage1_result_path=None,
            stage2_report_path=None,
            stage2_report_md_path=None,
            viewer_payload_path=None,
            lint_result_path=None,
        )

    def utc_naive_to_kst_text(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")

    def normalize_relative_path(self, path: Path | str) -> str:
        resolved = Path(path).expanduser().resolve()
        try:
            return resolved.relative_to(self.project_root).as_posix()
        except ValueError:
            return resolved.as_posix()

    def _validate_job(self, job: FullReportJob) -> None:
        if job.analysis_mode != DEFAULT_ANALYSIS_MODE:
            raise ValueError(f"unsupported analysis_mode: {job.analysis_mode}")
        if job.requested_timezone != DEFAULT_REQUESTED_TIMEZONE:
            raise ValueError(f"unsupported requested_timezone: {job.requested_timezone}")
        if not job.artifact_root.strip():
            raise ValueError("artifact_root is required")

    def _resolve_under_project_root(self, path_value: str) -> Path:
        path = Path(path_value).expanduser()
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    def _run_subprocess(self, cmd: Sequence[str], step_name: str) -> None:
        completed = self.subprocess_run(
            list(cmd),
            check=False,
            capture_output=True,
            text=True,
            env=self._subprocess_env(),
            timeout=self.timeout_seconds,
        )
        if int(completed.returncode) != 0:
            raise FullReportRunnerError(
                f"{step_name} command failed rc={completed.returncode} "
                f"stdout={_tail(completed.stdout)} stderr={_tail(completed.stderr)}"
            )

    def _subprocess_env(self) -> Optional[dict[str, str]]:
        if self.env is None:
            return None
        merged = dict(os.environ)
        merged.update(self.env)
        return merged


def _coerce_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO datetime string") from exc
    raise ValueError(f"{field_name} must be datetime or string")


def _tail(value: Any, limit: int = 1000) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[-limit:]
