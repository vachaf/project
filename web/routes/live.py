from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from web.services.live_log_repository import LiveLogRepository, LiveLogRepositoryError
from web.services.live_log_service import (
    LiveLogService,
    LiveSnapshotRequest,
    LiveSnapshotValidationError,
)

router = APIRouter()
templates: Optional[Jinja2Templates] = None
live_service = LiveLogService(LiveLogRepository())


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
