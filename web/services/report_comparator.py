from __future__ import annotations

from typing import Any, Dict, List, Optional

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info", "unknown"]


def normalize_pair_values(openai_value: Optional[int], anthropic_value: Optional[int]) -> Dict[str, Any]:
    values = [value for value in (openai_value, anthropic_value) if isinstance(value, int)]
    max_value = max(values) if values else 1

    def width(value: Optional[int]) -> Optional[int]:
        if not isinstance(value, int):
            return None
        if max_value <= 0:
            return 0
        if value <= 0:
            return 0
        return max(2, int((value / max_value) * 100))

    return {
        "openai": {
            "value": openai_value,
            "width": width(openai_value),
            "is_missing": openai_value is None,
        },
        "anthropic": {
            "value": anthropic_value,
            "width": width(anthropic_value),
            "is_missing": anthropic_value is None,
        },
        "max_value": max_value,
    }


def normalize_lint_summary(lint_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(lint_data, dict):
        return None

    verdict = str(lint_data.get("verdict") or "UNKNOWN").upper()

    blockers = lint_data.get("blockers") if isinstance(lint_data.get("blockers"), list) else []
    warnings = lint_data.get("warnings") if isinstance(lint_data.get("warnings"), list) else []
    info = lint_data.get("info") if isinstance(lint_data.get("info"), list) else []

    return {
        "verdict": verdict,
        "checked_fields": int(lint_data.get("checked_fields") or 0),
        "blocker_count": int(lint_data.get("blocker_count") or 0),
        "warning_count": int(lint_data.get("warning_count") or 0),
        "info_count": int(lint_data.get("info_count") or 0),
        "blockers": blockers,
        "warnings": warnings,
        "info": info,
        "is_error": bool(lint_data.get("is_error", False)),
    }


def compare_reports(
    openai_report: Any,
    anthropic_report: Any,
    openai_lint: Optional[Dict[str, Any]] = None,
    anthropic_lint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    openai_metrics = extract_report_metrics(openai_report)
    anthropic_metrics = extract_report_metrics(anthropic_report)

    lint_openai = normalize_lint_summary(openai_lint)
    lint_anthropic = normalize_lint_summary(anthropic_lint)

    metrics = {
        "incident_count": {
            "openai": openai_metrics.get("incident_count"),
            "anthropic": anthropic_metrics.get("incident_count"),
        },
        "high_severity_count": {
            "openai": openai_metrics.get("high_severity_count"),
            "anthropic": anthropic_metrics.get("high_severity_count"),
        },
        "severity_counts": {
            "openai": openai_metrics.get("severity_counts"),
            "anthropic": anthropic_metrics.get("severity_counts"),
        },
        "verdict_counts": {
            "openai": openai_metrics.get("verdict_counts"),
            "anthropic": anthropic_metrics.get("verdict_counts"),
        },
        "key_finding_count": {
            "openai": openai_metrics.get("key_finding_count"),
            "anthropic": anthropic_metrics.get("key_finding_count"),
        },
        "recommended_action_count": {
            "openai": openai_metrics.get("recommended_action_count"),
            "anthropic": anthropic_metrics.get("recommended_action_count"),
        },
        "lint": {
            "openai": lint_openai,
            "anthropic": lint_anthropic,
        },
    }

    metrics["bars"] = {
        "incident_count": normalize_pair_values(
            metrics["incident_count"]["openai"], metrics["incident_count"]["anthropic"]
        ),
        "high_severity_count": normalize_pair_values(
            metrics["high_severity_count"]["openai"], metrics["high_severity_count"]["anthropic"]
        ),
        "key_finding_count": normalize_pair_values(
            metrics["key_finding_count"]["openai"], metrics["key_finding_count"]["anthropic"]
        ),
        "recommended_action_count": normalize_pair_values(
            metrics["recommended_action_count"]["openai"], metrics["recommended_action_count"]["anthropic"]
        ),
        "lint_blocker_count": normalize_pair_values(
            lint_openai.get("blocker_count") if lint_openai else None,
            lint_anthropic.get("blocker_count") if lint_anthropic else None,
        ),
        "lint_warning_count": normalize_pair_values(
            lint_openai.get("warning_count") if lint_openai else None,
            lint_anthropic.get("warning_count") if lint_anthropic else None,
        ),
        "lint_info_count": normalize_pair_values(
            lint_openai.get("info_count") if lint_openai else None,
            lint_anthropic.get("info_count") if lint_anthropic else None,
        ),
    }

    severity_rows = build_distribution_rows(
        openai_metrics.get("severity_counts"), anthropic_metrics.get("severity_counts"), SEVERITY_ORDER
    )
    verdict_rows = build_distribution_rows(
        openai_metrics.get("verdict_counts"), anthropic_metrics.get("verdict_counts")
    )

    differences = {
        "severity_delta": [
            {"label": row["label"], "openai": row["openai"], "anthropic": row["anthropic"], "delta": row["delta"]}
            for row in severity_rows
            if row["delta"] is not None and row["delta"] != 0
        ],
        "verdict_delta": [
            {"label": row["label"], "openai": row["openai"], "anthropic": row["anthropic"], "delta": row["delta"]}
            for row in verdict_rows
            if row["delta"] is not None and row["delta"] != 0
        ],
        "lint_delta": build_lint_delta(lint_openai, lint_anthropic),
        "missing_provider": [
            provider
            for provider, report in (("openai", openai_report), ("anthropic", anthropic_report))
            if report is None
        ],
    }

    return {
        "metrics": metrics,
        "differences": differences,
        "severity_rows": severity_rows,
        "verdict_rows": verdict_rows,
    }


def extract_report_metrics(report: Any) -> Dict[str, Any]:
    if report is None:
        return {
            "incident_count": None,
            "high_severity_count": None,
            "severity_counts": None,
            "verdict_counts": None,
            "key_finding_count": None,
            "recommended_action_count": None,
        }

    report_payload = report.report if isinstance(getattr(report, "report", None), dict) else {}
    key_findings = report_payload.get("key_findings") if isinstance(report_payload.get("key_findings"), list) else []
    actions = (
        report_payload.get("recommended_actions") if isinstance(report_payload.get("recommended_actions"), list) else []
    )

    severity_counts = dict(getattr(report, "severity_counts", {}) or {})
    for severity in SEVERITY_ORDER:
        severity_counts.setdefault(severity, 0)

    verdict_counts = dict(getattr(report, "verdict_counts", {}) or {})

    high_severity_count = int(severity_counts.get("critical", 0) or 0) + int(severity_counts.get("high", 0) or 0)

    return {
        "incident_count": int(getattr(report, "incident_count", 0)),
        "high_severity_count": high_severity_count,
        "severity_counts": severity_counts,
        "verdict_counts": verdict_counts,
        "key_finding_count": len(key_findings),
        "recommended_action_count": len(actions),
    }


def build_distribution_rows(
    openai_counts: Optional[Dict[str, int]],
    anthropic_counts: Optional[Dict[str, int]],
    fixed_order: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if openai_counts is None and anthropic_counts is None:
        return []

    keys: List[str]
    if fixed_order:
        keys = list(fixed_order)
    else:
        key_set = set()
        if isinstance(openai_counts, dict):
            key_set.update(str(key) for key in openai_counts.keys())
        if isinstance(anthropic_counts, dict):
            key_set.update(str(key) for key in anthropic_counts.keys())
        keys = sorted(key_set)

    rows: List[Dict[str, Any]] = []
    for key in keys:
        openai_value = None if openai_counts is None else int(openai_counts.get(key, 0) or 0)
        anthropic_value = None if anthropic_counts is None else int(anthropic_counts.get(key, 0) or 0)

        pair = normalize_pair_values(openai_value, anthropic_value)
        delta = None
        if isinstance(openai_value, int) and isinstance(anthropic_value, int):
            delta = openai_value - anthropic_value

        rows.append(
            {
                "label": key,
                "openai": openai_value,
                "anthropic": anthropic_value,
                "delta": delta,
                "pair": pair,
            }
        )
    return rows


def build_lint_delta(
    lint_openai: Optional[Dict[str, Any]], lint_anthropic: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for field_name in ("blocker_count", "warning_count", "info_count"):
        openai_value = lint_openai.get(field_name) if lint_openai else None
        anthropic_value = lint_anthropic.get(field_name) if lint_anthropic else None
        delta = None
        if isinstance(openai_value, int) and isinstance(anthropic_value, int):
            delta = openai_value - anthropic_value
        result.append(
            {
                "label": field_name,
                "openai": openai_value,
                "anthropic": anthropic_value,
                "delta": delta,
            }
        )
    return result
