from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.config import DEBUG
from web.routes.reports import _apply_src_ip_display_mode
from web.routes.reports import _is_mask_src_ip_enabled
from web.routes.reports import init_templates as init_report_templates
from web.routes.reports import router as reports_router
from web.routes.reports import sanitize_payload_contexts
from web.routes.reports import sanitize_payload_findings
from web.routes.reports import sanitize_viewer_payload_summary
from web.services.analysis_job_policy import (
    AnalysisJobValidationError,
    redact_secret_text,
    validate_analysis_job_request,
)
from web.services.analysis_job_repository import (
    AnalysisJobRepository,
    AnalysisJobRepositoryError,
    DEFAULT_STATUS_COUNTS,
    serialize_job_for_dashboard,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Security Intelligence Console", debug=DEBUG)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
init_report_templates(templates)
app.include_router(reports_router)
job_repository = AnalysisJobRepository()


def _default_new_job_range() -> Dict[str, str]:
    now = datetime.now().replace(second=0, microsecond=0)
    start = now - timedelta(hours=1)
    return {
        "time_from_default": start.strftime("%Y-%m-%dT%H:%M"),
        "time_to_default": now.strftime("%Y-%m-%dT%H:%M"),
    }


def _public_error(exc: Exception) -> str:
    return redact_secret_text(str(exc), max_length=500) or "요청 처리 중 오류가 발생했습니다."


def _get_requested_user_id(request: Request) -> Optional[int]:
    """Return authenticated user id when auth middleware is added.

    Current MVP skeleton does not enforce login yet. Keeping this helper makes the
    later auth integration local to one place.
    """

    user_id = getattr(request, "session", {}).get("user_id") if hasattr(request, "session") else None
    try:
        return int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        return None


@app.get("/")
def job_dashboard(request: Request):
    error = ""
    jobs = []
    status_counts = dict(DEFAULT_STATUS_COUNTS)
    try:
        status_counts = job_repository.count_by_status()
        jobs = [serialize_job_for_dashboard(row) for row in job_repository.list_recent_jobs(limit=100)]
    except Exception as exc:
        error = _public_error(exc)

    return templates.TemplateResponse(
        request=request,
        name="job_dashboard.html",
        context={
            "jobs": jobs,
            "status_counts": status_counts,
            "error": error,
        },
    )


@app.get("/new-job")
def new_job_page(request: Request):
    defaults = _default_new_job_range()
    return templates.TemplateResponse(
        request=request,
        name="new_job.html",
        context={**defaults, "error": ""},
    )


@app.post("/new-job")
def create_job_from_form(
    request: Request,
    time_from: str = Form(...),
    time_to: str = Form(...),
    requested_timezone: str = Form("Asia/Seoul"),
    analysis_mode: str = Form("full_report"),
):
    try:
        validated = validate_analysis_job_request(
            time_from=time_from,
            time_to=time_to,
            requested_timezone=requested_timezone,
            analysis_mode=analysis_mode,
        )
        created = job_repository.create_job(
            requested_by=_get_requested_user_id(request),
            validated_request=validated,
        )
        return RedirectResponse(url=f"/job/{created.job_id}", status_code=303)
    except AnalysisJobValidationError as exc:
        defaults = _default_new_job_range()
        return templates.TemplateResponse(
            request=request,
            name="new_job.html",
            status_code=400,
            context={**defaults, "error": exc.message},
        )
    except AnalysisJobRepositoryError as exc:
        defaults = _default_new_job_range()
        return templates.TemplateResponse(
            request=request,
            name="new_job.html",
            status_code=500,
            context={**defaults, "error": _public_error(exc)},
        )


@app.post("/api/jobs/create")
async def create_job_api(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        validated = validate_analysis_job_request(
            time_from=payload.get("time_from"),
            time_to=payload.get("time_to"),
            requested_timezone=str(payload.get("requested_timezone") or "Asia/Seoul"),
            analysis_mode=str(payload.get("analysis_mode") or "full_report"),
        )
        created = job_repository.create_job(
            requested_by=_get_requested_user_id(request),
            validated_request=validated,
        )
        if created.duplicate_existing_job_id:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "same PENDING/RUNNING job already exists",
                    "existing_job_id": created.duplicate_existing_job_id,
                },
                status_code=409,
            )
        return JSONResponse({"ok": True, "job_id": created.job_id, "artifact_root": created.artifact_root})
    except AnalysisJobValidationError as exc:
        return JSONResponse({"ok": False, "error": exc.message, "code": exc.code}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": _public_error(exc)}, status_code=500)


@app.get("/api/jobs/count")
def api_jobs_count() -> JSONResponse:
    try:
        return JSONResponse({"ok": True, "data": job_repository.count_by_status()})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": _public_error(exc)}, status_code=500)


@app.get("/api/jobs/list")
def api_jobs_list() -> JSONResponse:
    try:
        jobs = [serialize_job_for_dashboard(row) for row in job_repository.list_recent_jobs(limit=100)]
        return JSONResponse({"ok": True, "data": jobs, "count": len(jobs)})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": _public_error(exc)}, status_code=500)


@app.get("/job/{job_id}")
def job_detail(request: Request, job_id: int):
    job_row = job_repository.get_job(job_id)
    if job_row is None:
        return templates.TemplateResponse(
            request=request,
            name="job_detail.html",
            status_code=404,
            context={
                "job": {"id": job_id, "status": "NOT_FOUND", "time_from": "-", "time_to": "-", "analysis_mode": "-", "created_at": "-", "artifact_root": "", "error_message": "Job not found"},
                "events": [],
                "report": None,
            },
        )

    job = serialize_job_for_dashboard(job_row)
    events = job_repository.get_job_events(job_id)
    report = job_repository.get_latest_report_for_job(job_id)
    return templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context={"job": job, "events": events, "report": report},
    )


@app.get("/api/job/{job_id}/status")
def api_job_status(job_id: int) -> JSONResponse:
    try:
        row = job_repository.get_job(job_id)
        if row is None:
            return JSONResponse({"ok": False, "error": "job not found"}, status_code=404)
        job = serialize_job_for_dashboard(row)
        events = job_repository.get_job_events(job_id)
        latest_event = events[-1] if events else None
        return JSONResponse(
            {
                "ok": True,
                "data": {
                    "id": job["id"],
                    "status": job["status"],
                    "error_message": job.get("error_message") or "",
                    "latest_event": latest_event.get("event_type") if latest_event else None,
                },
            }
        )
    except Exception as exc:
        return JSONResponse({"ok": False, "error": _public_error(exc)}, status_code=500)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}
