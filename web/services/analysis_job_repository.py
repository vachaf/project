from __future__ import annotations

import os
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import pymysql
from pymysql.cursors import DictCursor

from web.services.analysis_job_policy import (
    ValidatedAnalysisJobRequest,
    build_job_artifact_root,
    redact_secret_text,
)

DEFAULT_STATUS_COUNTS = {"PENDING": 0, "RUNNING": 0, "SUCCEEDED": 0, "FAILED": 0}
ACTIVE_JOB_STATUSES = ("PENDING", "RUNNING")
ANALYSIS_REPORT_UPSERT_COLUMNS = (
    "job_id",
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
)


class AnalysisJobRepositoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class CreatedAnalysisJob:
    job_id: int
    artifact_root: str
    duplicate_existing_job_id: Optional[int] = None

    @property
    def created(self) -> bool:
        return self.duplicate_existing_job_id is None


def get_app_db_config() -> Dict[str, Any]:
    """Return MariaDB connection config for the DB-backed Web UI/API.

    The dashboard uses APP_DB_USER when present. This keeps it separate from
    log_reader/log_writer roles used by export/log shipper flows.
    """

    user = os.getenv("APP_DB_USER") or os.getenv("LOG_DB_USER") or "analysis_app"
    password = os.getenv("APP_DB_PASSWORD") or os.getenv("LOG_DB_PASSWORD") or ""
    host = os.getenv("DB_HOST") or os.getenv("LOG_DB_HOST") or "127.0.0.1"
    database = os.getenv("DB_NAME") or os.getenv("LOG_DB_NAME") or "web_logs"
    port = int(os.getenv("DB_PORT") or os.getenv("LOG_DB_PORT") or "3306")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "charset": "utf8mb4",
        "autocommit": False,
        "connect_timeout": int(os.getenv("APP_DB_CONNECT_TIMEOUT_SEC", "5")),
        "read_timeout": int(os.getenv("APP_DB_READ_TIMEOUT_SEC", "10")),
        "write_timeout": int(os.getenv("APP_DB_WRITE_TIMEOUT_SEC", "10")),
        "cursorclass": DictCursor,
    }


@contextmanager
def app_db_connection() -> Iterator[pymysql.connections.Connection]:
    conn = pymysql.connect(**get_app_db_config())
    try:
        yield conn
    finally:
        conn.close()


class AnalysisJobRepository:
    def __init__(self, connection_factory=app_db_connection):
        self.connection_factory = connection_factory

    def _select_job_by_id(self, cur: Any, job_id: int) -> Optional[Dict[str, Any]]:
        cur.execute(
            """
            SELECT id, requested_by, time_from, time_to, requested_timezone,
                   status, analysis_mode, created_at, started_at, finished_at,
                   worker_id, heartbeat_at, attempt_count, max_attempts,
                   error_message, artifact_root
            FROM analysis_jobs
            WHERE id = %s
            """,
            (job_id,),
        )
        return cur.fetchone()

    def count_by_status(self) -> Dict[str, int]:
        counts = dict(DEFAULT_STATUS_COUNTS)
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM analysis_jobs
                    GROUP BY status
                    """
                )
                for row in cur.fetchall():
                    status = str(row.get("status") or "").upper()
                    if status in counts:
                        counts[status] = int(row.get("count") or 0)
        return counts

    def list_recent_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 1000))
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, requested_by, time_from, time_to, requested_timezone,
                           status, analysis_mode, created_at, started_at, finished_at,
                           worker_id, heartbeat_at, attempt_count, max_attempts,
                           error_message, artifact_root
                    FROM analysis_jobs
                    ORDER BY created_at DESC, id DESC
                    LIMIT {safe_limit}
                    """
                )
                return list(cur.fetchall())

    def find_stale_running_jobs(
        self,
        *,
        stale_after_minutes: int = 30,
        startup_grace_minutes: int = 5,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        safe_stale_after_minutes = max(1, int(stale_after_minutes))
        safe_startup_grace_minutes = max(1, int(startup_grace_minutes))
        safe_limit = max(1, min(int(limit), 100))
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, status, analysis_mode, worker_id, started_at, heartbeat_at,
                           attempt_count, max_attempts, artifact_root, error_message
                    FROM analysis_jobs
                    WHERE status = 'RUNNING'
                      AND analysis_mode = 'full_report'
                      AND (
                        (
                          heartbeat_at IS NOT NULL
                          AND heartbeat_at < UTC_TIMESTAMP(3) - INTERVAL %s MINUTE
                        )
                        OR (
                          heartbeat_at IS NULL
                          AND started_at < UTC_TIMESTAMP(3) - INTERVAL %s MINUTE
                        )
                      )
                    ORDER BY COALESCE(heartbeat_at, started_at) ASC, started_at ASC, id ASC
                    LIMIT {safe_limit}
                    """,
                    (safe_stale_after_minutes, safe_startup_grace_minutes),
                )
                return list(cur.fetchall())

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, requested_by, time_from, time_to, requested_timezone,
                           status, analysis_mode, created_at, started_at, finished_at,
                           worker_id, heartbeat_at, attempt_count, max_attempts,
                           error_message, artifact_root
                    FROM analysis_jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                return cur.fetchone()

    def claim_next_pending_full_report_job(self, *, worker_id: str) -> Optional[Dict[str, Any]]:
        """Atomically claim one PENDING full_report job for a worker.

        This intentionally uses SELECT ... FOR UPDATE followed by UPDATE by id so
        the claimed row is unambiguous without relying on worker_id lookups,
        LAST_INSERT_ID tricks, or SKIP LOCKED.
        """

        safe_worker_id = str(worker_id or "").strip()
        if not safe_worker_id:
            raise AnalysisJobRepositoryError("worker_id is required")

        with self.connection_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("START TRANSACTION")
                    cur.execute(
                        """
                        SELECT *
                        FROM analysis_jobs
                        WHERE status = 'PENDING'
                          AND analysis_mode = 'full_report'
                          AND attempt_count < max_attempts
                        ORDER BY created_at ASC, id ASC
                        LIMIT 1
                        FOR UPDATE
                        """
                    )
                    candidate = cur.fetchone()
                    if not candidate:
                        conn.rollback()
                        return None

                    job_id = int(candidate["id"])
                    cur.execute(
                        """
                        UPDATE analysis_jobs
                        SET status = 'RUNNING',
                            started_at = COALESCE(started_at, UTC_TIMESTAMP(3)),
                            worker_id = %s,
                            heartbeat_at = UTC_TIMESTAMP(3),
                            attempt_count = attempt_count + 1,
                            error_message = NULL
                        WHERE id = %s
                          AND status = 'PENDING'
                        """,
                        (safe_worker_id, job_id),
                    )
                    if cur.rowcount != 1:
                        conn.rollback()
                        return None

                    claimed = self._select_job_by_id(cur, job_id)
                    cur.execute(
                        """
                        INSERT INTO job_events (
                            job_id, event_time, event_type, message, detail_json
                        ) VALUES (
                            %s, UTC_TIMESTAMP(3), %s, %s, %s
                        )
                        """,
                        (
                            job_id,
                            "JOB_CLAIMED",
                            "Job claimed by Analysis Job Worker",
                            _event_detail_json({"worker_id": safe_worker_id}),
                        ),
                    )
                conn.commit()
                return claimed
            except Exception as exc:
                conn.rollback()
                raise AnalysisJobRepositoryError(redact_secret_text(exc)) from exc

    def get_job_events(self, job_id: int) -> List[Dict[str, Any]]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, job_id, event_time, event_type, message, detail_json
                    FROM job_events
                    WHERE job_id = %s
                    ORDER BY event_time ASC, id ASC
                    """,
                    (job_id,),
                )
                return list(cur.fetchall())

    def get_latest_report_for_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, job_id, summary, artifact_root, export_path, llm_input_path,
                           analysis_candidates_path, noise_summary_path, window_summary_path,
                           rollup_input_path, rollup_summary_path, operator_queue_items_path,
                           operator_queue_summary_path, stage1_result_path,
                           stage2_report_path, stage2_report_md_path, viewer_payload_path,
                           lint_result_path, created_at
                    FROM analysis_reports
                    WHERE job_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (job_id,),
                )
                return cur.fetchone()

    def upsert_analysis_report(
        self,
        *,
        job_id: int,
        artifact_root: str,
        summary: Optional[str] = None,
        export_path: Optional[str] = None,
        llm_input_path: Optional[str] = None,
        analysis_candidates_path: Optional[str] = None,
        noise_summary_path: Optional[str] = None,
        stage1_result_path: Optional[str] = None,
        stage2_report_path: Optional[str] = None,
        stage2_report_md_path: Optional[str] = None,
        viewer_payload_path: Optional[str] = None,
        lint_result_path: Optional[str] = None,
        window_summary_path: Optional[str] = None,
        rollup_input_path: Optional[str] = None,
        rollup_summary_path: Optional[str] = None,
        operator_queue_items_path: Optional[str] = None,
        operator_queue_summary_path: Optional[str] = None,
    ) -> None:
        """Insert or update analysis_reports metadata for one job.

        The direct full_report runner is expected to populate only export,
        prepare, Stage1, Stage2, viewer_payload, and lint paths. Window,
        rollup, and operator queue paths are accepted for the later
        windowed_triage mode but should remain NULL for the full_report MVP.
        """

        safe_artifact_root = str(artifact_root or "").strip()
        if not safe_artifact_root:
            raise AnalysisJobRepositoryError("artifact_root is required")

        values = {
            "job_id": int(job_id),
            "summary": summary,
            "artifact_root": safe_artifact_root,
            "export_path": export_path,
            "llm_input_path": llm_input_path,
            "analysis_candidates_path": analysis_candidates_path,
            "noise_summary_path": noise_summary_path,
            "stage1_result_path": stage1_result_path,
            "stage2_report_path": stage2_report_path,
            "stage2_report_md_path": stage2_report_md_path,
            "viewer_payload_path": viewer_payload_path,
            "lint_result_path": lint_result_path,
            "window_summary_path": window_summary_path,
            "rollup_input_path": rollup_input_path,
            "rollup_summary_path": rollup_summary_path,
            "operator_queue_items_path": operator_queue_items_path,
            "operator_queue_summary_path": operator_queue_summary_path,
        }
        column_list = ", ".join(ANALYSIS_REPORT_UPSERT_COLUMNS)
        placeholders = ", ".join(["%s"] * len(ANALYSIS_REPORT_UPSERT_COLUMNS))
        update_list = ", ".join(
            f"{column} = VALUES({column})"
            for column in ANALYSIS_REPORT_UPSERT_COLUMNS
            if column != "job_id"
        )

        with self.connection_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO analysis_reports (
                            {column_list}
                        ) VALUES (
                            {placeholders}
                        )
                        ON DUPLICATE KEY UPDATE
                            {update_list}
                        """,
                        tuple(values[column] for column in ANALYSIS_REPORT_UPSERT_COLUMNS),
                    )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise AnalysisJobRepositoryError(redact_secret_text(exc)) from exc

    def append_job_event(
        self,
        *,
        job_id: int,
        event_type: str,
        message: Optional[str] = None,
        detail_json: Optional[Any] = None,
    ) -> None:
        with self.connection_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO job_events (
                            job_id, event_time, event_type, message, detail_json
                        ) VALUES (
                            %s, UTC_TIMESTAMP(3), %s, %s, %s
                        )
                        """,
                        (
                            int(job_id),
                            str(event_type),
                            message,
                            _event_detail_json(detail_json),
                        ),
                    )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise AnalysisJobRepositoryError(redact_secret_text(exc)) from exc

    def mark_job_failed(
        self,
        *,
        job_id: int,
        worker_id: str,
        error_message: str,
        detail_json: Optional[Any] = None,
    ) -> bool:
        safe_error = redact_secret_text(error_message)
        with self.connection_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("START TRANSACTION")
                    cur.execute(
                        """
                        UPDATE analysis_jobs
                        SET status = 'FAILED',
                            finished_at = UTC_TIMESTAMP(3),
                            heartbeat_at = UTC_TIMESTAMP(3),
                            error_message = %s
                        WHERE id = %s
                          AND status = 'RUNNING'
                          AND worker_id = %s
                        """,
                        (safe_error, int(job_id), str(worker_id)),
                    )
                    if cur.rowcount != 1:
                        conn.rollback()
                        return False
                    cur.execute(
                        """
                        INSERT INTO job_events (
                            job_id, event_time, event_type, message, detail_json
                        ) VALUES (
                            %s, UTC_TIMESTAMP(3), %s, %s, %s
                        )
                        """,
                        (
                            int(job_id),
                            "JOB_FAILED",
                            safe_error,
                            _event_detail_json(detail_json),
                        ),
                    )
                conn.commit()
                return True
            except Exception as exc:
                conn.rollback()
                raise AnalysisJobRepositoryError(redact_secret_text(exc)) from exc

    def mark_job_succeeded(
        self,
        *,
        job_id: int,
        worker_id: str,
        detail_json: Optional[Any] = None,
    ) -> bool:
        with self.connection_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("START TRANSACTION")
                    cur.execute(
                        """
                        UPDATE analysis_jobs
                        SET status = 'SUCCEEDED',
                            finished_at = UTC_TIMESTAMP(3),
                            heartbeat_at = UTC_TIMESTAMP(3),
                            error_message = NULL
                        WHERE id = %s
                          AND status = 'RUNNING'
                          AND worker_id = %s
                        """,
                        (int(job_id), str(worker_id)),
                    )
                    if cur.rowcount != 1:
                        conn.rollback()
                        return False
                    cur.execute(
                        """
                        INSERT INTO job_events (
                            job_id, event_time, event_type, message, detail_json
                        ) VALUES (
                            %s, UTC_TIMESTAMP(3), %s, %s, %s
                        )
                        """,
                        (
                            int(job_id),
                            "JOB_SUCCEEDED",
                            "Job succeeded",
                            _event_detail_json(detail_json),
                        ),
                    )
                conn.commit()
                return True
            except Exception as exc:
                conn.rollback()
                raise AnalysisJobRepositoryError(redact_secret_text(exc)) from exc

    def update_job_heartbeat(self, *, job_id: int, worker_id: str) -> bool:
        with self.connection_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE analysis_jobs
                        SET heartbeat_at = UTC_TIMESTAMP(3)
                        WHERE id = %s
                          AND status = 'RUNNING'
                          AND worker_id = %s
                        """,
                        (int(job_id), str(worker_id)),
                    )
                    changed = cur.rowcount == 1
                conn.commit()
                return changed
            except Exception as exc:
                conn.rollback()
                raise AnalysisJobRepositoryError(redact_secret_text(exc)) from exc

    def create_job(
        self,
        *,
        requested_by: Optional[int],
        validated_request: ValidatedAnalysisJobRequest,
    ) -> CreatedAnalysisJob:
        """Create a PENDING full_report job or return active duplicate.

        Creates analysis_jobs and JOB_CREATED job_events in one transaction.
        artifact_root is job-scoped and assigned after lastrowid is known.
        """

        with self.connection_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("START TRANSACTION")
                    cur.execute(
                        """
                        SELECT id, artifact_root
                        FROM analysis_jobs
                        WHERE ((requested_by = %s) OR (requested_by IS NULL AND %s IS NULL))
                          AND analysis_mode = %s
                          AND time_from = %s
                          AND time_to = %s
                          AND requested_timezone = %s
                          AND status IN ('PENDING', 'RUNNING')
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (
                            requested_by,
                            requested_by,
                            validated_request.analysis_mode,
                            validated_request.time_from_db,
                            validated_request.time_to_db,
                            validated_request.requested_timezone,
                        ),
                    )
                    existing = cur.fetchone()
                    if existing:
                        conn.rollback()
                        return CreatedAnalysisJob(
                            job_id=int(existing["id"]),
                            artifact_root=str(existing.get("artifact_root") or ""),
                            duplicate_existing_job_id=int(existing["id"]),
                        )

                    cur.execute(
                        """
                        INSERT INTO analysis_jobs (
                            requested_by, time_from, time_to, requested_timezone,
                            status, analysis_mode, created_at, artifact_root
                        ) VALUES (
                            %s, %s, %s, %s,
                            'PENDING', %s, UTC_TIMESTAMP(3), NULL
                        )
                        """,
                        (
                            requested_by,
                            validated_request.time_from_db,
                            validated_request.time_to_db,
                            validated_request.requested_timezone,
                            validated_request.analysis_mode,
                        ),
                    )
                    job_id = int(cur.lastrowid)
                    artifact_root = build_job_artifact_root(job_id)
                    cur.execute(
                        """
                        UPDATE analysis_jobs
                        SET artifact_root = %s
                        WHERE id = %s
                        """,
                        (artifact_root, job_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO job_events (
                            job_id, event_time, event_type, message, detail_json
                        ) VALUES (
                            %s, UTC_TIMESTAMP(3), 'JOB_CREATED', %s, %s
                        )
                        """,
                        (
                            job_id,
                            "Job created via Web UI/API",
                            _job_created_detail_json(requested_by, validated_request),
                        ),
                    )
                conn.commit()
                return CreatedAnalysisJob(job_id=job_id, artifact_root=artifact_root)
            except Exception as exc:
                conn.rollback()
                raise AnalysisJobRepositoryError(redact_secret_text(exc)) from exc


def _job_created_detail_json(requested_by: Optional[int], request: ValidatedAnalysisJobRequest) -> str:
    import json

    return json.dumps(
        {
            "requested_by": requested_by,
            "requested_timezone": request.requested_timezone,
            "analysis_mode": request.analysis_mode,
            "time_from_db": request.time_from_db,
            "time_to_db": request.time_to_db,
            "time_from_local": request.time_from_local.isoformat(),
            "time_to_local": request.time_to_local.isoformat(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _event_detail_json(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def utc_naive_to_kst_text(value: Any, fmt: str = "%Y-%m-%d %H:%M") -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return str(value)
    from zoneinfo import ZoneInfo

    utc = ZoneInfo("UTC")
    kst = ZoneInfo("Asia/Seoul")
    return value.replace(tzinfo=utc).astimezone(kst).strftime(fmt)


def serialize_job_for_dashboard(row: Dict[str, Any]) -> Dict[str, Any]:
    status = str(row.get("status") or "unknown").upper()
    worker_id = str(row.get("worker_id") or "-")
    heartbeat_at = utc_naive_to_kst_text(row.get("heartbeat_at"), "%m-%d %H:%M")
    status_hint = {
        "PENDING": "Waiting for worker",
        "RUNNING": f"Running by {worker_id}" if worker_id != "-" else "Running",
        "SUCCEEDED": "Complete",
        "FAILED": "Failed",
    }.get(status, "Status unknown")

    return {
        "id": int(row.get("id")),
        "status": status,
        "status_hint": status_hint,
        "time_from": utc_naive_to_kst_text(row.get("time_from")),
        "time_to": utc_naive_to_kst_text(row.get("time_to")),
        "requested_timezone": str(row.get("requested_timezone") or "Asia/Seoul"),
        "analysis_mode": str(row.get("analysis_mode") or "full_report"),
        "created_at": utc_naive_to_kst_text(row.get("created_at"), "%m-%d %H:%M"),
        "started_at": utc_naive_to_kst_text(row.get("started_at"), "%m-%d %H:%M"),
        "finished_at": utc_naive_to_kst_text(row.get("finished_at"), "%m-%d %H:%M"),
        "heartbeat_at": heartbeat_at,
        "worker_id": worker_id,
        "attempt_count": int(row.get("attempt_count") or 0),
        "error_message": redact_secret_text(row.get("error_message") or ""),
        "artifact_root": str(row.get("artifact_root") or ""),
    }
