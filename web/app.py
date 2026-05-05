from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.config import DEBUG, HOST, PORT
from web.services.qa_runner import QARunner
from web.services.report_loader import Report, ReportLoader


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Security Intelligence Console", debug=DEBUG)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

loader = ReportLoader()
qa_runner = QARunner()

IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@app.get("/")
def index(request: Request):
    reports = loader.scan_reports()

    for report in reports:
        if report.is_valid:
            report.lint = qa_runner.lint_summary(report.report_id, report.file_path)
        else:
            report.lint = {
                "verdict": "ERROR",
                "checked_fields": 0,
                "blocker_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "is_error": True,
            }

    groups = loader.group_by_timeframe(reports)
    summary = {
        "total_count": len(reports),
        "timeframe_count": len(groups),
        "groups": groups,
        "lint_aggregate": aggregate_lint_counts(reports),
    }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "summary": summary,
            "host": HOST,
            "port": PORT,
        },
    )


@app.get("/report/{report_id}")
def report_detail(request: Request, report_id: str):
    report = loader.get_report_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    qa_result = qa_runner.run_quality_lint(report.report_id, report.file_path)

    report_payload = report.report if isinstance(report.report, dict) else {}
    incidents = sanitize_incidents(report_payload.get("notable_incidents", []))
    actions = sanitize_action_items(report_payload.get("recommended_actions", []))
    key_findings = sanitize_finding_items(report_payload.get("key_findings", []))
    source_ips = sanitize_source_ip_items(report_payload.get("notable_source_ips", []))

    detail = report.to_detail()
    detail["known_asset_ips"] = normalize_known_asset_ips(report.meta.get("known_asset_ips", []))

    return templates.TemplateResponse(
        request=request,
        name="detail.html",
        context={
            "report": detail,
            "qa_result": qa_result,
            "incidents": incidents,
            "actions": actions,
            "key_findings": key_findings,
            "source_ips": source_ips,
        },
    )


@app.get("/api/reports")
def api_reports() -> JSONResponse:
    reports = loader.scan_reports()
    payload: List[Dict[str, Any]] = []

    for report in reports:
        summary = report.to_summary()
        if report.is_valid:
            report.lint = qa_runner.lint_summary(report.report_id, report.file_path)
        else:
            report.lint = {
                "verdict": "ERROR",
                "checked_fields": 0,
                "blocker_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "is_error": True,
            }
        summary["lint"] = report.lint
        payload.append(summary)

    response = {
        "total_count": len(payload),
        "timeframe_count": len(loader.group_by_timeframe(reports)),
        "lint_aggregate": aggregate_lint_counts(reports),
        "reports": payload,
    }
    return JSONResponse(response)


@app.get("/api/report/{report_id}")
def api_report_detail(report_id: str) -> JSONResponse:
    report = loader.get_report_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    qa_result = qa_runner.run_quality_lint(report.report_id, report.file_path)

    report_payload = report.report if isinstance(report.report, dict) else {}
    detail = {
        "report_id": report.report_id,
        "filename": report.filename,
        "repo_relative_path": report.repo_relative_path,
        "provider": report.provider,
        "model": report.model,
        "scenario": report.scenario,
        "timeframe": report.timeframe,
        "generated_at": report.generated_at,
        "is_valid": report.is_valid,
        "error": report.error,
        "known_asset_ips": normalize_known_asset_ips(report.meta.get("known_asset_ips", [])),
        "overall_assessment": report_payload.get("overall_assessment") or "N/A",
        "executive_summary": report_payload.get("executive_summary") or [],
        "key_findings": sanitize_finding_items(report_payload.get("key_findings", [])),
        "notable_incidents": sanitize_incidents(report_payload.get("notable_incidents", [])),
        "notable_source_ips": sanitize_source_ip_items(report_payload.get("notable_source_ips", [])),
        "recommended_actions": sanitize_action_items(report_payload.get("recommended_actions", [])),
        "confidence_and_limitations": report_payload.get("confidence_and_limitations") or "N/A",
        "presentation_takeaway": report_payload.get("presentation_takeaway") or "N/A",
    }

    return JSONResponse({"report": detail, "qa_result": qa_result})


def aggregate_lint_counts(reports: List[Report]) -> Dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}
    for report in reports:
        verdict = str((report.lint or {}).get("verdict", "UNKNOWN")).upper()
        if verdict in counts:
            counts[verdict] += 1
        elif (report.lint or {}).get("is_error"):
            counts["ERROR"] += 1
    return counts


def sanitize_incidents(rows: Any) -> List[Dict[str, str]]:
    if not isinstance(rows, list):
        return []

    normalized: List[Dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "incident_ref": str(row.get("incident_ref") or "-"),
                "severity": str(row.get("severity") or "unknown"),
                "verdict": str(row.get("verdict") or "unknown"),
                "title": str(row.get("title") or row.get("summary") or "-"),
                "why_it_matters": str(row.get("why_it_matters") or "-"),
                "source_ip": mask_value(row.get("src_ip") or row.get("source_ip") or "-"),
                "request_count": str(row.get("request_count") or "-"),
                "recommended_action": str(row.get("recommended_action") or "-"),
            }
        )
    return normalized


def sanitize_action_items(rows: Any) -> List[Dict[str, str]]:
    if not isinstance(rows, list):
        return []

    normalized: List[Dict[str, str]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append(
                {
                    "priority": str(row.get("priority") or "unknown"),
                    "action": str(row.get("action") or "-"),
                    "why": str(row.get("why") or "-"),
                }
            )
        elif row is not None:
            normalized.append({"priority": "unknown", "action": str(row), "why": "-"})
    return normalized


def sanitize_finding_items(rows: Any) -> List[Dict[str, str]]:
    if not isinstance(rows, list):
        return []

    normalized: List[Dict[str, str]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append(
                {
                    "title": str(row.get("title") or "-"),
                    "detail": str(row.get("detail") or "-"),
                }
            )
        elif row is not None:
            normalized.append({"title": "-", "detail": str(row)})
    return normalized


def sanitize_source_ip_items(rows: Any) -> List[Dict[str, str]]:
    if not isinstance(rows, list):
        return []

    normalized: List[Dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "source_ip": mask_value(row.get("src_ip") or row.get("source_ip") or "-"),
                "reason": str(row.get("reason") or "-"),
            }
        )
    return normalized


def mask_value(value: Any) -> Any:
    if isinstance(value, list):
        return [mask_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): mask_value(item) for key, item in value.items()}
    text = str(value)
    return IP_PATTERN.sub(lambda m: _mask_ipv4(m.group(0)), text)


def _mask_ipv4(ip_text: str) -> str:
    parts = ip_text.split(".")
    if len(parts) != 4:
        return ip_text
    return f"{parts[0]}.{parts[1]}.{parts[2]}.***"


def normalize_known_asset_ips(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(mask_value(item)) for item in value]
    if value in (None, ""):
        return []
    return [str(mask_value(value))]
