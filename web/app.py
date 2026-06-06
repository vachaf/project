from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.config import DEBUG, PROJECT_ROOT
from web.routes.reports import _apply_src_ip_display_mode
from web.routes.reports import _is_mask_src_ip_enabled
from web.routes.reports import init_templates as init_report_templates
from web.routes.reports import router as reports_router
from web.routes.reports import sanitize_payload_contexts
from web.routes.reports import sanitize_payload_findings
from web.routes.reports import sanitize_viewer_payload_summary
from web.routes.reports import sort_payload_findings_for_timeline
from web.services.analysis_job_policy import (
    AnalysisJobValidationError,
    redact_secret_text,
    validate_relative_artifact_path,
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

ARTIFACT_KEY_TO_REPORT_COLUMN = {
    "export": "export_path",
    "llm_input": "llm_input_path",
    "analysis_candidates": "analysis_candidates_path",
    "noise_summary": "noise_summary_path",
    "stage1_result": "stage1_result_path",
    "stage2_report": "stage2_report_path",
    "stage2_report_md": "stage2_report_md_path",
    "viewer_payload": "viewer_payload_path",
    "lint_result": "lint_result_path",
}
FILTERED_REASONS_ARTIFACT_KEY = "filtered_reasons"
FILTERED_REASONS_FILENAME = "filtered_reasons.json"
FILTERED_REASONS_TOP_N = 6
FILTERED_REASON_GUARDRAIL_LABELS = {
    "candidate_excluded_does_not_mean_benign": "Candidate-excluded rows are not safety verdicts.",
    "candidate_excluded_does_not_mean_safety_verdict": "Candidate-excluded rows are not safety verdicts.",
    "apache_logs_only_no_success_inference": "Apache logs alone do not prove exploit success.",
    "status_code_response_size_route_or_user_agent_do_not_prove_success_or_benign": (
        "Status, size, route, or user-agent alone are not proof."
    ),
}

ALLOWED_JOB_STATUSES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED")
KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")


def _default_new_job_range() -> Dict[str, str]:
    now = datetime.now().replace(second=0, microsecond=0)
    start = now - timedelta(hours=1)
    return {
        "time_from_default": start.strftime("%Y-%m-%dT%H:%M"),
        "time_to_default": now.strftime("%Y-%m-%dT%H:%M"),
    }


def _public_error(exc: Exception) -> str:
    return redact_secret_text(str(exc), max_length=500) or "요청 처리 중 오류가 발생했습니다."


def _parse_dashboard_date_filter(raw_value: str, *, label: str) -> tuple[Optional[datetime], Optional[str]]:
    value = str(raw_value or "").strip()
    if not value:
        return None, None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, f"Invalid {label} date filter ignored: use YYYY-MM-DD."
    if parsed.isoformat() != value:
        return None, f"Invalid {label} date filter ignored: use YYYY-MM-DD."
    kst_start = datetime.combine(parsed, time.min, tzinfo=KST)
    return kst_start.astimezone(UTC).replace(tzinfo=None), None


def _build_dashboard_filters(request: Request) -> Dict[str, Any]:
    params = request.query_params
    warnings = []
    status = None
    raw_status = str(params.get("status") or "").strip().upper()
    if raw_status:
        if raw_status in ALLOWED_JOB_STATUSES:
            status = raw_status
        else:
            warnings.append("Invalid status filter ignored.")

    raw_from = str(params.get("from") or "").strip()
    time_from, from_warning = _parse_dashboard_date_filter(raw_from, label="from")
    if from_warning:
        warnings.append(from_warning)
        raw_from = ""

    raw_to = str(params.get("to") or "").strip()
    time_to, to_warning = _parse_dashboard_date_filter(raw_to, label="to")
    if to_warning:
        warnings.append(to_warning)
        raw_to = ""
    if time_to is not None:
        time_to = time_to + timedelta(days=1)

    stale_only = params.get("stale") == "1"
    filter_state = {
        "status": status or "",
        "from": raw_from if time_from is not None else "",
        "to": raw_to if time_to is not None else "",
        "stale": stale_only,
    }
    active_chips = []
    if status:
        active_chips.append(f"Status: {status}")
    if time_from is not None:
        active_chips.append(f"From: {filter_state['from']} KST")
    if time_to is not None:
        active_chips.append(f"To: {filter_state['to']} KST")
    if stale_only:
        active_chips.append("Potentially stale")

    return {
        "status": status,
        "time_from": time_from,
        "time_to": time_to,
        "stale_only": stale_only,
        "filter_state": filter_state,
        "filter_warnings": warnings,
        "active_filter_chips": active_chips,
        "has_active_filters": bool(active_chips),
    }


def _get_requested_user_id(request: Request) -> Optional[int]:
    """Return authenticated user id when auth middleware is added.

    Current MVP skeleton does not enforce login yet. Avoid request.session unless
    SessionMiddleware has installed a session object in request.scope.
    """

    session = request.scope.get("session")
    user_id = session.get("user_id") if isinstance(session, dict) else None
    try:
        return int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        return None


def _artifact_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="artifact not found")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_report_artifact_path(report: Dict[str, Any], artifact_key: str) -> Path:
    if artifact_key == FILTERED_REASONS_ARTIFACT_KEY:
        return _resolve_artifact_root_child(report, FILTERED_REASONS_FILENAME)

    column = ARTIFACT_KEY_TO_REPORT_COLUMN.get(artifact_key)
    if not column:
        raise _artifact_not_found()

    raw_path = report.get(column)
    if not raw_path:
        raise _artifact_not_found()

    try:
        relative_path = validate_relative_artifact_path(raw_path)
    except AnalysisJobValidationError:
        raise _artifact_not_found() from None

    project_root = PROJECT_ROOT.resolve()
    resolved_path = (project_root / relative_path).resolve()
    if not _is_relative_to(resolved_path, project_root):
        raise _artifact_not_found()

    try:
        relative_artifact_root = validate_relative_artifact_path(report.get("artifact_root"))
    except AnalysisJobValidationError:
        raise _artifact_not_found() from None
    artifact_root_path = (project_root / relative_artifact_root).resolve()
    if not _is_relative_to(resolved_path, artifact_root_path):
        raise _artifact_not_found()

    if not resolved_path.is_file():
        raise _artifact_not_found()
    return resolved_path


def _resolve_artifact_root_child(report: Dict[str, Any], filename: str) -> Path:
    try:
        relative_artifact_root = validate_relative_artifact_path(report.get("artifact_root"))
    except AnalysisJobValidationError:
        raise _artifact_not_found() from None

    project_root = PROJECT_ROOT.resolve()
    artifact_root_path = (project_root / relative_artifact_root).resolve()
    if not _is_relative_to(artifact_root_path, project_root):
        raise _artifact_not_found()

    resolved_path = (artifact_root_path / filename).resolve()
    if not _is_relative_to(resolved_path, artifact_root_path):
        raise _artifact_not_found()
    if not resolved_path.is_file():
        raise _artifact_not_found()
    return resolved_path


def _artifact_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".md":
        return "text/markdown; charset=utf-8"
    return "text/plain; charset=utf-8"


def _load_viewer_payload_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid viewer payload JSON: {exc}") from None
    except OSError:
        raise _artifact_not_found() from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid viewer payload JSON: expected object")
    return payload


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_count(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "-"


def _load_artifact_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _build_unavailable_usage_summary(stage: str, reason: str) -> Dict[str, Any]:
    return {
        "stage": stage,
        "available": False,
        "call_count": 0,
        "call_count_display": "0",
        "input_tokens": 0,
        "input_tokens_display": "0",
        "output_tokens": 0,
        "output_tokens_display": "0",
        "total_tokens": 0,
        "total_tokens_display": "0",
        "provider": "",
        "selected_model": "",
        "unavailable_count": 0,
        "unavailable_count_display": "0",
        "unavailable_reason": reason,
    }


def _build_usage_summary(stage: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not payload:
        return _build_unavailable_usage_summary(stage, "artifact_unavailable")

    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    if stage == "stage1":
        totals = meta.get("llm_usage_totals") if isinstance(meta.get("llm_usage_totals"), dict) else None
        provider = str((totals or {}).get("provider") or "")
        selected_model = str((totals or {}).get("selected_model") or "")
        available = bool((totals or {}).get("available", True))
    else:
        usage = meta.get("llm_usage") if isinstance(meta.get("llm_usage"), dict) else {}
        totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else None
        calls = usage.get("calls") if isinstance(usage.get("calls"), list) else []
        first_call = calls[0] if calls and isinstance(calls[0], dict) else {}
        provider = str(meta.get("provider") or first_call.get("provider") or "")
        selected_model = str(meta.get("selected_model") or first_call.get("model") or "")
        available = bool(usage.get("available", True))

    if not totals:
        return _build_unavailable_usage_summary(stage, "usage_totals_missing")

    call_count = _safe_int(totals.get("call_count"))
    input_tokens = _safe_int(totals.get("input_tokens"))
    output_tokens = _safe_int(totals.get("output_tokens"))
    total_tokens = _safe_int(totals.get("total_tokens"))
    unavailable_count = _safe_int(totals.get("unavailable_count"))
    return {
        "stage": stage,
        "available": available,
        "call_count": call_count,
        "call_count_display": _format_count(call_count),
        "input_tokens": input_tokens,
        "input_tokens_display": _format_count(input_tokens),
        "output_tokens": output_tokens,
        "output_tokens_display": _format_count(output_tokens),
        "total_tokens": total_tokens,
        "total_tokens_display": _format_count(total_tokens),
        "provider": provider,
        "selected_model": selected_model,
        "unavailable_count": unavailable_count,
        "unavailable_count_display": _format_count(unavailable_count),
        "unavailable_reason": str(totals.get("unavailable_reason") or ""),
    }


def _build_combined_usage_summary(*usages: Dict[str, Any]) -> Dict[str, Any]:
    available_usages = [usage for usage in usages if isinstance(usage, dict) and usage.get("available")]
    call_count = sum(_safe_int(usage.get("call_count")) for usage in available_usages)
    input_tokens = sum(_safe_int(usage.get("input_tokens")) for usage in available_usages)
    output_tokens = sum(_safe_int(usage.get("output_tokens")) for usage in available_usages)
    total_tokens = sum(_safe_int(usage.get("total_tokens")) for usage in available_usages)
    stage_totals = {
        str(usage.get("stage") or ""): _safe_int(usage.get("total_tokens"))
        for usage in available_usages
        if usage.get("stage")
    }
    return {
        "available": bool(available_usages),
        "total_calls": call_count,
        "total_calls_display": _format_count(call_count),
        "total_input_tokens": input_tokens,
        "total_input_tokens_display": _format_count(input_tokens),
        "total_output_tokens": output_tokens,
        "total_output_tokens_display": _format_count(output_tokens),
        "total_tokens": total_tokens,
        "total_tokens_display": _format_count(total_tokens),
        "stage1_tokens": stage_totals.get("stage1", 0),
        "stage1_tokens_display": _format_count(stage_totals.get("stage1", 0)),
        "stage2_tokens": stage_totals.get("stage2", 0),
        "stage2_tokens_display": _format_count(stage_totals.get("stage2", 0)),
    }


def _format_guardrail_label(raw_key: Any) -> str:
    key = str(raw_key or "").strip()
    if not key:
        return "Additional artifact guardrail."
    return FILTERED_REASON_GUARDRAIL_LABELS.get(key, "Additional artifact guardrail.")


def _build_filtered_reasons_summary(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not payload:
        return {"found": False, "reason": "not_found"}

    excluded_summary = payload.get("excluded_summary") if isinstance(payload.get("excluded_summary"), dict) else {}
    top_reasons = sorted(
        (
            {"reason": str(reason), "count": _safe_int(count), "count_display": _format_count(count)}
            for reason, count in excluded_summary.items()
        ),
        key=lambda item: (-item["count"], item["reason"]),
    )[:FILTERED_REASONS_TOP_N]
    guardrails = [
        {"label": _format_guardrail_label(item)}
        for item in payload.get("guardrails", [])
        if isinstance(item, (str, int, float))
    ][:FILTERED_REASONS_TOP_N]
    total_rows = _safe_int(payload.get("total_rows"))
    candidate_count = _safe_int(payload.get("candidate_count"))
    excluded_count = _safe_int(payload.get("excluded_count"))
    return {
        "found": True,
        "total_rows": total_rows,
        "total_rows_display": _format_count(total_rows),
        "candidate_count": candidate_count,
        "candidate_count_display": _format_count(candidate_count),
        "excluded_count": excluded_count,
        "excluded_count_display": _format_count(excluded_count),
        "top_reasons": top_reasons,
        "guardrails": guardrails,
        "guardrail_count": len(guardrails),
        "guardrail_count_display": _format_count(len(guardrails)),
    }


def _build_job_artifact_summary(report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not report:
        return {
            "stage1_usage": _build_unavailable_usage_summary("stage1", "analysis_report_missing"),
            "stage2_usage": _build_unavailable_usage_summary("stage2", "analysis_report_missing"),
            "filtered_reasons": {"found": False, "reason": "analysis_report_missing"},
        }

    try:
        stage1_payload = _load_artifact_json(_resolve_report_artifact_path(report, "stage1_result"))
    except HTTPException:
        stage1_payload = None
    try:
        stage2_payload = _load_artifact_json(_resolve_report_artifact_path(report, "stage2_report"))
    except HTTPException:
        stage2_payload = None
    try:
        filtered_payload = _load_artifact_json(_resolve_report_artifact_path(report, FILTERED_REASONS_ARTIFACT_KEY))
        filtered_href = True
    except HTTPException:
        filtered_payload = None
        filtered_href = False

    stage1_usage = _build_usage_summary("stage1", stage1_payload)
    stage2_usage = _build_usage_summary("stage2", stage2_payload)
    filtered_summary = _build_filtered_reasons_summary(filtered_payload)
    filtered_summary["artifact_available"] = filtered_href
    return {
        "llm_usage_total": _build_combined_usage_summary(stage1_usage, stage2_usage),
        "stage1_usage": stage1_usage,
        "stage2_usage": stage2_usage,
        "filtered_reasons": filtered_summary,
    }


def _build_job_viewer_payload_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    summary = dict(payload.get("summary")) if isinstance(payload.get("summary"), dict) else {}
    if payload.get("schema_version") and not summary.get("schema_version"):
        summary["schema_version"] = str(payload.get("schema_version"))

    policies = payload.get("policies") if isinstance(payload.get("policies"), dict) else {}
    if "guardrails" not in summary and isinstance(policies.get("guardrails"), list):
        summary["guardrails"] = policies.get("guardrails")

    return sanitize_viewer_payload_summary(summary)


def _build_job_viewer_report_context(job_id: int, report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "report_id": f"job-{job_id}",
        "filename": "viewer_payload.json",
        "run_id": f"job-{job_id}",
        "storage_type": "db_job",
        "viewer_payload_path": str(report.get("viewer_payload_path") or ""),
    }


def _is_no_data_job(events: Any, report: Optional[Dict[str, Any]]) -> bool:
    for event in events if isinstance(events, list) else []:
        event_type = event.get("event_type") if isinstance(event, dict) else getattr(event, "event_type", "")
        if str(event_type or "").upper() == "JOB_NO_DATA":
            return True

    summary = str((report or {}).get("summary") or "").strip().lower()
    return summary.startswith("no logs found")


@app.get("/")
def job_dashboard(request: Request):
    error = ""
    jobs = []
    status_counts = dict(DEFAULT_STATUS_COUNTS)
    dashboard_filters = _build_dashboard_filters(request)
    try:
        status_counts = job_repository.count_by_status()
        jobs = [
            serialize_job_for_dashboard(row)
            for row in job_repository.list_jobs(
                status=dashboard_filters["status"],
                time_from=dashboard_filters["time_from"],
                time_to=dashboard_filters["time_to"],
                stale_only=dashboard_filters["stale_only"],
                limit=100,
            )
        ]
    except Exception as exc:
        error = _public_error(exc)

    return templates.TemplateResponse(
        request=request,
        name="job_dashboard.html",
        context={
            "jobs": jobs,
            "status_counts": status_counts,
            "error": error,
            "status_options": ALLOWED_JOB_STATUSES,
            "filter_state": dashboard_filters["filter_state"],
            "filter_warnings": dashboard_filters["filter_warnings"],
            "active_filter_chips": dashboard_filters["active_filter_chips"],
            "has_active_filters": dashboard_filters["has_active_filters"],
            "result_count": len(jobs),
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
                "artifact_summary": _build_job_artifact_summary(None),
            },
        )

    job = serialize_job_for_dashboard(job_row)
    events = job_repository.get_job_events(job_id)
    report = job_repository.get_latest_report_for_job(job_id)
    return templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context={
            "job": job,
            "events": events,
            "report": report,
            "is_no_data_job": _is_no_data_job(events, report),
            "artifact_summary": _build_job_artifact_summary(report),
        },
    )


@app.get("/job/{job_id}/artifact/{artifact_key}")
def job_artifact(job_id: int, artifact_key: str) -> Response:
    report = job_repository.get_latest_report_for_job(job_id)
    if report is None:
        raise _artifact_not_found()

    artifact_path = _resolve_report_artifact_path(report, artifact_key)
    try:
        content = artifact_path.read_bytes()
    except OSError:
        raise _artifact_not_found() from None
    return Response(content=content, media_type=_artifact_media_type(artifact_path))


@app.get("/job/{job_id}/viewer")
def job_viewer_payload(request: Request, job_id: int):
    report = job_repository.get_latest_report_for_job(job_id)
    if report is None:
        raise _artifact_not_found()

    viewer_payload_path = _resolve_report_artifact_path(report, "viewer_payload")
    payload_obj = _load_viewer_payload_json(viewer_payload_path)
    payload_summary = _build_job_viewer_payload_summary(payload_obj)
    mask_src_ip = _is_mask_src_ip_enabled(request.query_params.get("mask_src_ip"))

    findings = sanitize_payload_findings(payload_obj.get("findings"), payload_summary.get("findings_preview"))
    findings = sort_payload_findings_for_timeline(findings)
    contexts_preview = sanitize_payload_contexts(payload_obj.get("contexts"), payload_summary.get("contexts_preview"))
    findings_display = _apply_src_ip_display_mode(findings, mask_src_ip)
    contexts_preview_display = _apply_src_ip_display_mode(contexts_preview, mask_src_ip)
    payload_report = payload_obj.get("report") if isinstance(payload_obj.get("report"), dict) else {}
    report_source_ips = [
        {
            "src_ip": str(row.get("src_ip") or row.get("source_ip") or "-"),
            "reason": str(row.get("reason") or "-"),
        }
        for row in payload_report.get("notable_source_ips", [])
        if isinstance(row, dict)
    ]
    report_source_ips_display = _apply_src_ip_display_mode(report_source_ips, mask_src_ip)

    return templates.TemplateResponse(
        request=request,
        name="payload_detail.html",
        context={
            "report": _build_job_viewer_report_context(job_id, report),
            "qa_result": None,
            "payload": payload_obj,
            "payload_summary": payload_summary,
            "payload_error": "",
            "findings": findings,
            "findings_display": findings_display,
            "contexts_preview": contexts_preview,
            "contexts_preview_display": contexts_preview_display,
            "report_source_ips_display": report_source_ips_display,
            "mask_src_ip": mask_src_ip,
            "back_url": f"/job/{job_id}",
            "back_label": "Back To Job Detail",
        },
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
