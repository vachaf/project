from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.config import DEBUG, HOST, PORT
from web.services.qa_runner import QARunner
from web.services.report_comparator import compare_reports
from web.services.report_loader import Report, ReportLoader


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Security Intelligence Console", debug=DEBUG)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

loader = ReportLoader()
qa_runner = QARunner()

IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
LINT_OPTIONS = ("pass", "warn", "fail", "error")
PAIR_OPTIONS = ("both", "partial")
PROVIDER_OPTIONS = ("openai", "anthropic", "unknown")
SORT_OPTIONS = ("time_desc", "time_asc", "severity_desc")


@app.get("/")
def index(request: Request):
    reports = loader.scan_reports()

    for report in reports:
        report.lint = lint_for_report(report)

    groups = loader.group_by_timeframe(reports)
    filters = parse_filters(request)
    filtered_groups = loader.filter_groups(groups, filters)
    sorted_filtered_groups = sort_groups(filtered_groups, filters.get("sort", "time_desc"))
    result_count = len(sorted_filtered_groups)
    unfiltered_count = len(groups)

    summary = {
        "total_count": len(reports),
        "timeframe_count": len(groups),
        "groups": sorted_filtered_groups,
        "lint_aggregate": aggregate_lint_counts(reports),
    }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "summary": summary,
            "host": HOST,
            "port": PORT,
            "filters": filters,
            "filter_options": {
                "lint": list(LINT_OPTIONS),
                "pair": list(PAIR_OPTIONS),
                "provider": list(PROVIDER_OPTIONS),
                "sort": list(SORT_OPTIONS),
            },
            "result_count": result_count,
            "unfiltered_count": unfiltered_count,
        },
    )


@app.get("/report/{report_id}")
def report_detail(request: Request, report_id: str):
    report = loader.get_report_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    qa_result = lint_for_report(report)

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


@app.get("/compare/{timeframe_id}")
def compare_view(request: Request, timeframe_id: str):
    group = loader.get_group_by_timeframe_id(timeframe_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Timeframe group not found")

    openai_report = resolve_group_report(group.get("openai"))
    anthropic_report = resolve_group_report(group.get("anthropic"))

    openai_lint = lint_for_report(openai_report) if openai_report else None
    anthropic_lint = lint_for_report(anthropic_report) if anthropic_report else None

    comparison = compare_reports(openai_report, anthropic_report, openai_lint, anthropic_lint)

    panels = {
        "openai": build_compare_panel("openai", openai_report, openai_lint),
        "anthropic": build_compare_panel("anthropic", anthropic_report, anthropic_lint),
    }

    return templates.TemplateResponse(
        request=request,
        name="compare.html",
        context={
            "group": group,
            "comparison": comparison,
            "panels": panels,
        },
    )


@app.get("/api/reports")
def api_reports() -> JSONResponse:
    reports = loader.scan_reports()
    payload: List[Dict[str, Any]] = []

    for report in reports:
        report.lint = lint_for_report(report)
        summary = report.to_summary()
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

    qa_result = lint_for_report(report)

    report_payload = report.report if isinstance(report.report, dict) else {}
    detail = {
        "report_id": report.report_id,
        "filename": report.filename,
        "repo_relative_path": report.repo_relative_path,
        "provider": report.provider,
        "model": report.model,
        "scenario": report.scenario,
        "timeframe": report.timeframe,
        "timeframe_id": report.timeframe_id,
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


@app.get("/api/compare/{timeframe_id}")
def api_compare(timeframe_id: str) -> JSONResponse:
    group = loader.get_group_by_timeframe_id(timeframe_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Timeframe group not found")

    openai_report = resolve_group_report(group.get("openai"))
    anthropic_report = resolve_group_report(group.get("anthropic"))

    openai_lint = lint_for_report(openai_report) if openai_report else None
    anthropic_lint = lint_for_report(anthropic_report) if anthropic_report else None

    comparison = compare_reports(openai_report, anthropic_report, openai_lint, anthropic_lint)

    response = {
        "group": {
            "timeframe_id": group.get("timeframe_id"),
            "timeframe": group.get("timeframe"),
            "scenario": group.get("scenario"),
            "has_both": bool(group.get("has_both")),
        },
        "providers": {
            "openai": build_compare_panel("openai", openai_report, openai_lint),
            "anthropic": build_compare_panel("anthropic", anthropic_report, anthropic_lint),
        },
        "comparison": comparison,
    }
    return JSONResponse(response)


def lint_for_report(report: Optional[Report]) -> Optional[Dict[str, Any]]:
    if report is None:
        return None

    if not report.is_valid:
        return {
            "verdict": "ERROR",
            "checked_fields": 0,
            "blocker_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "blockers": [],
            "warnings": [],
            "info": [],
            "is_error": True,
            "error": report.error or "Invalid report JSON",
        }

    return qa_runner.run_quality_lint(report.report_id, report.file_path)


def resolve_group_report(summary: Any) -> Optional[Report]:
    if not isinstance(summary, dict):
        return None
    report_id = str(summary.get("report_id") or "").strip()
    if not report_id:
        return None
    return loader.get_report_by_id(report_id)


def build_compare_panel(provider: str, report: Optional[Report], lint: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if report is None:
        return {
            "provider": provider,
            "report": None,
            "lint": None,
            "incident_count": None,
            "severity_counts": None,
            "verdict_counts": None,
            "overall_assessment": "N/A",
            "key_findings": [],
            "recommended_actions": [],
            "known_asset_ips": [],
            "source_ips": [],
            "is_missing": True,
        }

    report_payload = report.report if isinstance(report.report, dict) else {}
    incidents = sanitize_incidents(report_payload.get("notable_incidents", []))

    return {
        "provider": provider,
        "report": {
            "report_id": report.report_id,
            "filename": report.filename,
            "repo_relative_path": report.repo_relative_path,
            "provider": report.provider,
            "model": report.model,
            "scenario": report.scenario,
            "timeframe": report.timeframe,
            "timeframe_id": report.timeframe_id,
            "generated_at": report.generated_at,
            "is_valid": report.is_valid,
            "error": report.error,
        },
        "lint": lint,
        "incident_count": report.incident_count,
        "severity_counts": dict(report.severity_counts),
        "verdict_counts": dict(report.verdict_counts),
        "overall_assessment": report_payload.get("overall_assessment") or "N/A",
        "key_findings": sanitize_finding_items(report_payload.get("key_findings", [])),
        "recommended_actions": sanitize_action_items(report_payload.get("recommended_actions", [])),
        "known_asset_ips": normalize_known_asset_ips(report.meta.get("known_asset_ips", [])),
        "source_ips": sanitize_source_ip_items(report_payload.get("notable_source_ips", [])),
        "incident_preview": incidents[:5],
        "is_missing": False,
    }


def aggregate_lint_counts(reports: List[Report]) -> Dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}
    for report in reports:
        verdict = str((report.lint or {}).get("verdict", "UNKNOWN")).upper()
        if verdict in counts:
            counts[verdict] += 1
        elif (report.lint or {}).get("is_error"):
            counts["ERROR"] += 1
    return counts


def parse_filters(request: Request) -> Dict[str, Optional[str]]:
    query = request.query_params

    q_raw = query.get("q")
    q = q_raw.strip() if isinstance(q_raw, str) else ""
    q_value: Optional[str] = q or None

    lint = normalize_filter_value(query.get("lint"), LINT_OPTIONS)
    pair = normalize_filter_value(query.get("pair"), PAIR_OPTIONS)
    provider = normalize_filter_value(query.get("provider"), PROVIDER_OPTIONS)
    sort = normalize_filter_value(query.get("sort"), SORT_OPTIONS) or "time_desc"

    return {
        "q": q_value,
        "lint": lint,
        "pair": pair,
        "provider": provider,
        "sort": sort,
    }


def sort_groups(groups: Dict[str, Any], sort_val: str) -> Dict[str, Any]:
    """filtering 완료된 groups dict를 sort_val 기준으로 재정렬한다."""
    items = list(groups.items())

    def get_severity_score(group_dict: Dict[str, Any]) -> int:
        score = 0
        for r in group_dict.get("reports", []):
            counts = r.get("severity_counts") or {}
            score += int(counts.get("critical", 0)) + int(counts.get("high", 0))
        return score

    def get_latest_generated_at(group_dict: Dict[str, Any]) -> str:
        """group 내 가장 최근 generated_at 값을 반환 (큰 것이 최신)"""
        latest = "0000-00-00"  # 가장 작은 값으로 시작
        for r in group_dict.get("reports", []):
            generated = str(r.get("generated_at") or "")
            if generated and generated > latest:
                latest = generated
        return latest

    if sort_val == "severity_desc":
        items.sort(key=lambda x: (
            get_severity_score(x[1]),
            get_latest_generated_at(x[1]),
            x[1].get("scenario_key", ""),
        ), reverse=True)
    elif sort_val == "time_asc":
        items.sort(key=lambda x: (
            get_latest_generated_at(x[1]),
            x[1].get("scenario_key", ""),
        ))
    else:  # time_desc (기본값)
        items.sort(key=lambda x: (
            get_latest_generated_at(x[1]),
            x[1].get("scenario_key", ""),
        ), reverse=True)

    return dict(items)

def normalize_filter_value(value: Optional[str], allowed: tuple[str, ...]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized not in allowed:
        return None
    return normalized


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
                    "severity": str(row.get("severity") or "unknown"),
                }
            )
        elif row is not None:
            normalized.append({"title": "-", "detail": str(row), "severity": "unknown"})
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
