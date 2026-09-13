from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from web.services.live_log_repository import LiveLogRepository, LiveLogRepositoryError
from web.services.analysis_job_policy import (
    AnalysisJobValidationError,
    validate_selected_log_request,
)
from web.services.analysis_job_repository import (
    AnalysisJobRepository,
    AnalysisJobRepositoryError,
)
from web.services.live_log_service import (
    LiveLogService,
    LiveSnapshotRequest,
    LiveSnapshotValidationError,
)

router = APIRouter()
templates: Optional[Jinja2Templates] = None
live_service = LiveLogService(LiveLogRepository())
selected_job_repository = AnalysisJobRepository()


def init_templates(value: Jinja2Templates) -> None:
    global templates
    templates = value


def _templates() -> Jinja2Templates:
    if templates is None:
        raise RuntimeError("live routes templates are not initialized")
    return templates


def _error_response(exc: Exception) -> JSONResponse:
    if isinstance(exc, LiveSnapshotValidationError):
        return JSONResponse(
            {"ok": False, "error": exc.message, "code": exc.code}, status_code=400
        )
    if isinstance(exc, LiveLogRepositoryError):
        return JSONResponse(
            {
                "ok": False,
                "error": "원천 로그 DB를 조회하지 못했습니다.",
                "code": "live_db_unavailable",
            },
            status_code=503,
        )
    return JSONResponse(
        {
            "ok": False,
            "error": "최근 원천 로그를 불러오지 못했습니다.",
            "code": "live_snapshot_error",
        },
        status_code=500,
    )


@router.get("/live")
def live_dashboard(request: Request):
    return _templates().TemplateResponse(
        request=request, name="live_dashboard.html", context={}
    )


@router.get("/api/live/snapshot")
def live_snapshot(
    period: str = Query("all"),
    status_class: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    src_ip: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50),
    cursor: Optional[str] = Query(None),
) -> JSONResponse:
    try:
        return JSONResponse(
            live_service.snapshot(
                LiveSnapshotRequest(
                    period=period,
                    status_class=status_class,
                    method=method,
                    src_ip=src_ip,
                    keyword=q,
                    limit=limit,
                    cursor=cursor,
                )
            )
        )
    except Exception as exc:
        return _error_response(exc)


@router.get("/api/live/logs/{row_id}/raw")
def live_raw_log(row_id: int) -> JSONResponse:
    try:
        return JSONResponse(live_service.raw_log(row_id))
    except Exception as exc:
        return _error_response(exc)


def _requested_user_id(request: Request) -> Optional[int]:
    session = request.scope.get("session")
    user_id = session.get("user_id") if isinstance(session, dict) else None
    try:
        return int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        return None


@router.post("/api/live/jobs/create")
async def create_live_selected_logs_job(request: Request) -> JSONResponse:
    """Submit exact Live log IDs without converting them to a time-range job."""

    try:
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AnalysisJobValidationError(
                "invalid_request", "request body must contain valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise AnalysisJobValidationError("invalid_request", "request body must be a JSON object")
        validated = validate_selected_log_request(payload.get("selected_log_ids"))
        created = selected_job_repository.create_live_selected_logs_job(
            requested_by=_requested_user_id(request),
            validated_request=validated,
        )
        if created.no_data:
            return JSONResponse(
                {
                    "ok": True,
                    "status": "NO_DATA",
                    "code": "NO_DATA",
                    "job_id": None,
                    "missing_log_ids": list(created.missing_log_ids),
                }
            )
        if created.duplicate_existing_job_id is not None:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "same PENDING/RUNNING selected-input job already exists",
                    "code": "duplicate_active_job",
                    "existing_job_id": created.duplicate_existing_job_id,
                    "missing_log_ids": list(created.missing_log_ids),
                },
                status_code=409,
            )
        return JSONResponse(
            {
                "ok": True,
                "status": "PENDING",
                "job_id": created.job_id,
                "artifact_root": created.artifact_root,
                "selected_log_ids": list(created.selected_log_ids),
                "missing_log_ids": list(created.missing_log_ids),
            }
        )
    except AnalysisJobValidationError as exc:
        return JSONResponse(
            {"ok": False, "error": exc.message, "code": exc.code},
            status_code=400,
        )
    except AnalysisJobRepositoryError:
        return JSONResponse(
            {
                "ok": False,
                "error": "분석 작업 DB를 갱신하지 못했습니다.",
                "code": "job_db_unavailable",
            },
            status_code=503,
        )
    except Exception:
        return JSONResponse(
            {
                "ok": False,
                "error": "선택 로그 분석 작업을 만들지 못했습니다.",
                "code": "selected_job_create_error",
            },
            status_code=500,
        )
