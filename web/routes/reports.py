from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from web.services.qa_runner import QARunner
from web.services.report_comparator import compare_reports
from web.services.report_loader import Report, ReportLoader

router = APIRouter()
loader = ReportLoader()
qa_runner = QARunner()

templates: Optional[Jinja2Templates] = None

IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
LINT_OPTIONS = ("pass", "warn", "fail", "error")
PAIR_OPTIONS = ("both", "partial")
PROVIDER_OPTIONS = ("openai", "anthropic", "unknown")
SORT_OPTIONS = ("time_desc", "time_asc", "severity_desc")
NOTABLE_INCIDENT_COLUMNS: List[Dict[str, Any]] = [
    {"key": "severity", "label": "severity", "always_visible": True},
    {"key": "verdict", "label": "verdict", "always_visible": True},
    {"key": "incident_ref", "label": "incident_ref", "always_visible": True},
    {"key": "title", "label": "summary", "always_visible": False},
    {"key": "why_it_matters", "label": "why_it_matters", "always_visible": True},
    {"key": "source_ip", "label": "source_ip", "always_visible": True},
    {"key": "request_count", "label": "request_count", "always_visible": False},
    {"key": "recommended_action", "label": "recommended_action", "always_visible": False},
]


def init_templates(value: Jinja2Templates) -> None:
    global templates
    templates = value


def _templates() -> Jinja2Templates:
    if templates is None:
        raise RuntimeError("report routes templates are not initialized")
    return templates


@router.get("/reports")
def reports_index(request: Request):
    reports = loader.scan_reports()

    for report in reports:
        report.lint = lint_for_report(report)

    groups = loader.group_by_timeframe(reports)
    filters = parse_filters(request)
    filtered_groups = loader.filter_groups(groups, filters)
    sorted_filtered_groups = sort_groups(filtered_groups, filters.get("sort", "time_desc") or "time_desc")
    result_count = len(sorted_filtered_groups)
    unfiltered_count = len(groups)

    summary = {
        "total_count": len(reports),
        "timeframe_count": len(groups),
        "groups": sorted_filtered_groups,
        "lint_aggregate": aggregate_lint_counts(reports),
    }

    return _templates().TemplateResponse(
        request=request,
        name="index.html",
        context={
            "summary": summary,
            "filters": filters,
            "filter_options": {
                "lint": list(LINT_OPTIONS),
                "pair": list(PAIR_OPTIONS),
                "provider": list(PROVIDER_OPTIONS),
                "sort": list(SORT_OPTIONS),
            },
            "reports_index_url": "/reports",
            "result_count": result_count,
            "unfiltered_count": unfiltered_count,
        },
    )


@router.get("/report/{report_id}")
def report_detail(request: Request, report_id: str):
    all_reports = loader.scan_reports()
    report = next((r for r in all_reports if r.report_id == report_id), None)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    qa_result = lint_for_report(report)

    report_payload = report.report if isinstance(report.report, dict) else {}
    incidents = sanitize_incidents(report_payload.get("notable_incidents", []))
    visible_incident_columns = visible_columns_for_rows(incidents, NOTABLE_INCIDENT_COLUMNS)
    actions = sanitize_action_items(report_payload.get("recommended_actions", []))
    key_findings = sanitize_finding_items(report_payload.get("key_findings", []))
    source_ips = sanitize_source_ip_items(report_payload.get("notable_source_ips", []))

    detail = report.to_detail()
    detail["known_asset_ips"] = normalize_known_asset_ips(report.meta.get("known_asset_ips", []))
    detail["viewer_payload_summary"] = sanitize_viewer_payload_summary(detail.get("viewer_payload_summary", {}))
    if report.viewer_payload_error:
        detail["viewer_payload_error"] = str(mask_value(report.viewer_payload_error))

    nav_context = _calculate_navigation(all_reports, report_id)

    return _templates().TemplateResponse(
        request=request,
        name="detail.html",
        context={
            "report": detail,
            "qa_result": qa_result,
            "incidents": incidents,
            "visible_incident_columns": visible_incident_columns,
            "actions": actions,
            "key_findings": key_findings,
            "source_ips": source_ips,
            **nav_context,
        },
    )


@router.get("/report/{report_id}/payload")
def report_payload_detail(request: Request, report_id: str):
    all_reports = loader.scan_reports()
    report = next((r for r in all_reports if r.report_id == report_id), None)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    qa_result = lint_for_report(report)
    detail = report.to_detail()
    detail["known_asset_ips"] = normalize_known_asset_ips(report.meta.get("known_asset_ips", []))
    payload_summary = sanitize_viewer_payload_summary(detail.get("viewer_payload_summary", {}))
    detail["viewer_payload_summary"] = payload_summary

    payload_obj, payload_load_error = loader.load_viewer_payload(report)
    payload_error = payload_load_error or str(detail.get("viewer_payload_error") or "")
    if payload_obj is None:
        payload_obj = {}
    mask_src_ip = _is_mask_src_ip_enabled(request.query_params.get("mask_src_ip"))

    findings = sanitize_payload_findings(
        payload_obj.get("findings"),
        payload_summary.get("findings_preview"),
    )
    findings = sort_payload_findings_for_timeline(findings)
    contexts_preview = sanitize_payload_contexts(
        payload_obj.get("contexts"),
        payload_summary.get("contexts_preview"),
    )
    findings_display = _apply_src_ip_display_mode(findings, mask_src_ip)
    contexts_preview_display = _apply_src_ip_display_mode(contexts_preview, mask_src_ip)

    nav_context = _calculate_navigation(all_reports, report_id)

    return _templates().TemplateResponse(
        request=request,
        name="payload_detail.html",
        context={
            "report": detail,
            "qa_result": qa_result,
            "payload": payload_obj,
            "payload_summary": payload_summary,
            "payload_error": str(mask_value(payload_error)) if payload_error else "",
            "findings": findings,
            "findings_display": findings_display,
            "contexts_preview": contexts_preview,
            "contexts_preview_display": contexts_preview_display,
            "mask_src_ip": mask_src_ip,
            "is_legacy_report": True,
            **nav_context,
        },
    )


@router.get("/compare/{timeframe_id}")
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

    return _templates().TemplateResponse(
        request=request,
        name="compare.html",
        context={
            "group": group,
            "comparison": comparison,
            "panels": panels,
        },
    )


@router.get("/api/reports")
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


@router.get("/api/report/{report_id}")
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


@router.get("/api/compare/{timeframe_id}")
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
    items = list(groups.items())

    def get_severity_score(group_dict: Dict[str, Any]) -> int:
        score = 0
        for row in group_dict.get("reports", []):
            counts = row.get("severity_counts") or {}
            score += int(counts.get("critical", 0)) + int(counts.get("high", 0))
        return score

    def get_latest_generated_at(group_dict: Dict[str, Any]) -> str:
        latest = "0000-00-00"
        for row in group_dict.get("reports", []):
            generated = str(row.get("generated_at") or "")
            if generated and generated > latest:
                latest = generated
        return latest

    if sort_val == "severity_desc":
        items.sort(key=lambda x: (get_severity_score(x[1]), get_latest_generated_at(x[1]), x[1].get("scenario_key", "")), reverse=True)
    elif sort_val == "time_asc":
        items.sort(key=lambda x: (get_latest_generated_at(x[1]), x[1].get("scenario_key", "")))
    else:
        items.sort(key=lambda x: (get_latest_generated_at(x[1]), x[1].get("scenario_key", "")), reverse=True)

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


def _get_generated_at(report: Report) -> str:
    return str(report.generated_at or "")


def _report_to_nav_dict(report: Report) -> Dict[str, Any]:
    return {
        "report_id": report.report_id,
        "filename": report.filename,
        "scenario": report.scenario,
        "generated_at": report.generated_at,
    }


def _calculate_navigation(all_reports: List[Report], current_report_id: str) -> Dict[str, Any]:
    sorted_reports = sorted(all_reports, key=lambda report: (report.filename, report.report_id))
    sorted_reports = sorted(sorted_reports, key=_get_generated_at, reverse=True)

    current_index = next((index for index, report in enumerate(sorted_reports) if report.report_id == current_report_id), -1)

    if current_index < 0:
        return {
            "prev_report": None,
            "next_report": None,
            "current_index": 0,
            "total_reports": len(sorted_reports),
        }

    return {
        "prev_report": _report_to_nav_dict(sorted_reports[current_index - 1]) if current_index > 0 else None,
        "next_report": _report_to_nav_dict(sorted_reports[current_index + 1]) if current_index < len(sorted_reports) - 1 else None,
        "current_index": current_index,
        "total_reports": len(sorted_reports),
    }


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


def is_display_value(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text not in {"", "-"}


def should_show_column(rows: List[Dict[str, Any]], key: str) -> bool:
    return any(is_display_value(row.get(key)) for row in rows if isinstance(row, dict))


def visible_columns_for_rows(rows: List[Dict[str, Any]], columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    visible: List[Dict[str, Any]] = []
    for column in columns:
        key = str(column.get("key") or "").strip()
        if not key:
            continue
        if bool(column.get("always_visible")) or should_show_column(rows, key):
            visible.append(column)
    return visible


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


def sanitize_viewer_payload_summary(summary: Any) -> Dict[str, Any]:
    if not isinstance(summary, dict):
        return {}

    normalized = dict(summary)

    findings_preview = normalized.get("findings_preview")
    if isinstance(findings_preview, list):
        safe_findings: List[Dict[str, Any]] = []
        for row in findings_preview[:5]:
            if not isinstance(row, dict):
                continue
            safe_row = dict(row)
            safe_row["src_ip"] = str(row.get("src_ip") or "-")
            safe_findings.append(safe_row)
        normalized["findings_preview"] = safe_findings
    else:
        normalized["findings_preview"] = []

    contexts_preview = normalized.get("contexts_preview")
    if isinstance(contexts_preview, list):
        safe_contexts: List[Dict[str, Any]] = []
        for row in contexts_preview[:5]:
            if not isinstance(row, dict):
                continue
            safe_row = dict(row)
            safe_row["src_ip"] = str(row.get("src_ip") or "-")
            safe_contexts.append(safe_row)
        normalized["contexts_preview"] = safe_contexts
    else:
        normalized["contexts_preview"] = []

    if "overall_assessment" in normalized:
        normalized["overall_assessment"] = str(mask_value(normalized.get("overall_assessment") or "N/A"))
    if "report_title" in normalized:
        normalized["report_title"] = str(mask_value(normalized.get("report_title") or "N/A"))

    guardrails = normalized.get("guardrails")
    normalized["guardrails"] = [str(item) for item in guardrails] if isinstance(guardrails, list) else []

    warnings = normalized.get("integrity_warnings")
    normalized["integrity_warnings"] = [str(item) for item in warnings] if isinstance(warnings, list) else []

    return normalized


def sanitize_payload_findings(rows: Any, fallback_rows: Any = None) -> List[Dict[str, Any]]:
    source_rows = rows if isinstance(rows, list) else fallback_rows if isinstance(fallback_rows, list) else []

    findings: List[Dict[str, Any]] = []
    for row in source_rows[:200]:
        if not isinstance(row, dict):
            continue

        request_obj = row.get("request") if isinstance(row.get("request"), dict) else {}
        raw_match_obj = row.get("raw_export_match") if isinstance(row.get("raw_export_match"), dict) else {}
        log_time = _first_non_empty_text(
            row.get("log_time"),
            row.get("timestamp"),
            request_obj.get("log_time"),
            request_obj.get("timestamp"),
        ) or "unknown"

        findings.append(
            {
                "display_time": _format_payload_display_time(log_time),
                "log_time": str(log_time),
                "severity": str(row.get("severity") or "unknown"),
                "verdict": str(row.get("verdict") or row.get("verdict_hint") or "unknown"),
                "category": str(row.get("category") or "unknown"),
                "src_ip": str(row.get("src_ip") or "-"),
                "method": str(row.get("method") or "-"),
                "uri": str(row.get("uri") or "-"),
                "status_code": str(row.get("status_code")) if row.get("status_code") not in (None, "") else "-",
                "request_id": str(row.get("request_id") or "-"),
                "confidence": str(row.get("confidence") or "unknown"),
                "reasoning_summary": str(row.get("reasoning_summary") or "N/A"),
                "evidence_fields": _normalize_text_list(row.get("evidence_fields")),
                "reason_hints": _normalize_text_list(row.get("reason_hints")),
                "recommended_actions": _normalize_text_list(row.get("recommended_actions")),
                "related_context_ids": _normalize_relation_id_list(row.get("related_context_ids")),
                "supporting_event_ids": _normalize_relation_id_list(row.get("supporting_event_ids")),
                "raw_export_match": {
                    "source_table": str(raw_match_obj.get("source_table") or "N/A"),
                    "log_id": str(raw_match_obj.get("log_id") or "N/A"),
                    "request_id": str(raw_match_obj.get("request_id") or "N/A"),
                },
            }
        )
    return findings


def _normalize_relation_id_list(value: Any, limit: int = 50) -> List[str]:
    if not isinstance(value, list):
        return []
    normalized: List[str] = []
    for item in value:
        if isinstance(item, (dict, list, tuple, set)):
            continue
        text = str(item or "").strip()
        if text:
            normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def sanitize_payload_contexts(rows: Any, fallback_rows: Any = None) -> List[Dict[str, Any]]:
    source_rows = rows if isinstance(rows, list) else fallback_rows if isinstance(fallback_rows, list) else []

    contexts: List[Dict[str, Any]] = []
    for row in source_rows[:15]:
        if not isinstance(row, dict):
            continue

        contexts.append(
            {
                "context_type": str(row.get("context_type") or row.get("category") or "unknown"),
                "src_ip": str(row.get("src_ip") or "-"),
                "request_count": str(row.get("request_count")) if row.get("request_count") not in (None, "") else "-",
                "context_only": bool(row.get("context_only")),
                "should_promote_to_candidate": bool(row.get("should_promote_to_candidate")),
            }
        )
    return contexts


def sort_payload_findings_for_timeline(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    indexed_rows = [(index, row) for index, row in enumerate(rows) if isinstance(row, dict)]
    indexed_rows.sort(key=lambda item: _payload_timeline_sort_key(item[0], item[1]))
    return [dict(row) for _, row in indexed_rows]


def _payload_timeline_sort_key(index: int, row: Dict[str, Any]) -> tuple:
    log_time = str(row.get("log_time") or "").strip()
    display_time = str(row.get("display_time") or "").strip()
    primary = log_time if log_time.lower() != "unknown" else ""
    fallback = display_time if display_time.lower() != "unknown" else ""
    candidate = primary or fallback

    if not candidate:
        return (1, "", index)

    parsed = _parse_payload_timeline_sort_value(candidate)
    if parsed is None:
        return (1, "", index)
    return (0, parsed, index)


def _parse_payload_timeline_sort_value(text: str) -> Optional[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return None

    candidates = [normalized]
    if normalized.endswith("Z"):
        candidates.append(normalized[:-1] + "+00:00")
    if not re.search(r"[+-]\d{2}:\d{2}$", normalized):
        spaced_tz = re.sub(r"\s+(\d{2}:\d{2})$", r"+\1", normalized)
        if spaced_tz != normalized:
            candidates.append(spaced_tz)

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.isoformat(timespec="microseconds")
        except ValueError:
            continue

    time_match = re.search(r"^(\d{2}):(\d{2})(?::(\d{2}))?$", normalized)
    if time_match:
        hour, minute, second = time_match.groups()
        second = second or "00"
        return f"1970-01-01T{hour}:{minute}:{second}.000000"
    return None


def _first_non_empty_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _is_mask_src_ip_enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _apply_src_ip_display_mode(rows: List[Dict[str, Any]], mask_src_ip: bool) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    if not mask_src_ip:
        return [dict(row) for row in rows if isinstance(row, dict)]

    displayed: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        copied = dict(row)
        copied["src_ip"] = str(mask_value(copied.get("src_ip") or "-"))
        displayed.append(copied)
    return displayed


def _normalize_text_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    text = str(value).strip()
    return [text] if text else []


def _format_payload_display_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "unknown":
        return "unknown"

    minute_fraction_match = re.search(r"[T ](\d{2}):(\d{2})\.\d+", text)
    if minute_fraction_match:
        hour, minute = minute_fraction_match.groups()
        return f"{hour}:{minute}"

    candidates = [text]
    if not re.search(r"[+-]\d{2}:\d{2}$", text):
        spaced_tz = re.sub(r"\s+(\d{2}:\d{2})$", r"+\1", text)
        if spaced_tz != text:
            candidates.append(spaced_tz)

    for candidate in candidates:
        normalized = candidate[:-1] + "+00:00" if candidate.endswith("Z") else candidate
        normalized = re.sub(r"(T\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})$", r"\1:00.\2\3", normalized)
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue

    match = re.search(r"(\d{2}):(\d{2})(?::(\d{2}))?", text)
    if match:
        hour, minute, second = match.groups()
        return f"{hour}:{minute}:{second}" if second is not None else f"{hour}:{minute}"
    return "unknown"


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
