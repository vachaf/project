from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from web.config import PROJECT_ROOT, REPORT_GLOBS


STAGE2_SUFFIX = "_stage2_report.json"
TIMEFRAME_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}_[0-9-]+_to_\d{4}-\d{2}-\d{2}_[0-9-]+(?:_[a-zA-Z0-9-]+)*"
)
SEVERITY_BUCKETS = ("critical", "high", "medium", "low", "info", "unknown")


@dataclass
class Report:
    report_id: str
    file_path: Path
    filename: str
    repo_relative_path: str
    provider: str
    model: str
    scenario: str
    scenario_key: str
    timeframe: str
    timeframe_key: str
    timeframe_label: str
    timeframe_id: str
    generated_at: str
    incident_count: int
    severity_counts: Dict[str, int]
    verdict_counts: Dict[str, int]
    lint: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    report: Dict[str, Any] = field(default_factory=dict)
    viewer_payload_available: bool = False
    viewer_payload_error: Optional[str] = None
    viewer_payload_path: Optional[str] = None
    viewer_payload_summary: Dict[str, Any] = field(default_factory=dict)

    def to_summary(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "filename": self.filename,
            "repo_relative_path": self.repo_relative_path,
            "provider": self.provider,
            "model": self.model,
            "scenario": self.scenario,
            "scenario_key": self.scenario_key,
            "timeframe": self.timeframe,
            "timeframe_key": self.timeframe_key,
            "timeframe_label": self.timeframe_label,
            "timeframe_id": self.timeframe_id,
            "generated_at": self.generated_at,
            "incident_count": self.incident_count,
            "severity_counts": dict(self.severity_counts),
            "verdict_counts": dict(self.verdict_counts),
            "lint": dict(self.lint),
            "is_valid": self.is_valid,
            "error": self.error,
            "viewer_payload_available": self.viewer_payload_available,
            "viewer_payload_error": self.viewer_payload_error,
        }

    def to_detail(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "filename": self.filename,
            "repo_relative_path": self.repo_relative_path,
            "provider": self.provider,
            "model": self.model,
            "scenario": self.scenario,
            "scenario_key": self.scenario_key,
            "timeframe": self.timeframe,
            "timeframe_key": self.timeframe_key,
            "timeframe_label": self.timeframe_label,
            "timeframe_id": self.timeframe_id,
            "generated_at": self.generated_at,
            "meta": dict(self.meta),
            "report": dict(self.report),
            "is_valid": self.is_valid,
            "error": self.error,
            "viewer_payload_available": self.viewer_payload_available,
            "viewer_payload_error": self.viewer_payload_error,
            "viewer_payload_path": self.viewer_payload_path,
            "viewer_payload_summary": dict(self.viewer_payload_summary),
        }


class ReportLoader:
    def __init__(
        self,
        report_globs: Optional[List[str]] = None,
        project_root: Path = PROJECT_ROOT,
    ) -> None:
        self.project_root = project_root
        self.report_globs = report_globs or list(REPORT_GLOBS)
        self._reports_by_id: Dict[str, Report] = {}
        self._ordered_ids: List[str] = []
        self._groups_by_timeframe_id: Dict[str, Dict[str, Any]] = {}

    def scan(self) -> List[Report]:
        return self.scan_reports()

    def scan_reports(self) -> List[Report]:
        reports: List[Report] = []
        reports_by_id: Dict[str, Report] = {}

        for file_path in self._iter_unique_report_paths():
            report = self._load_single_report(file_path)
            reports_by_id[report.report_id] = report
            reports.append(report)

        reports.sort(
            key=lambda item: (
                item.timeframe == "unknown",
                item.timeframe_key,
                item.generated_at,
                item.filename,
            ),
            reverse=True,
        )

        self._reports_by_id = reports_by_id
        self._ordered_ids = [report.report_id for report in reports]
        self._groups_by_timeframe_id = self.group_by_timeframe(reports)
        return reports

    def get_report_by_id(self, report_id: str) -> Optional[Report]:
        if report_id not in self._reports_by_id:
            self.scan_reports()
        return self._reports_by_id.get(report_id)

    def load_viewer_payload(self, report: Report) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        viewer_path = self._resolve_viewer_payload_path(report.file_path)
        if not viewer_path.exists():
            return None, "viewer_payload not available"

        try:
            with viewer_path.open("r", encoding="utf-8") as handle:
                viewer_payload = json.load(handle)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return None, f"viewer_payload load error: {exc}"

        if not isinstance(viewer_payload, dict):
            return None, "Invalid viewer_payload root: expected object"

        return viewer_payload, None

    def load_viewer_payload_by_report_id(self, report_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        report = self.get_report_by_id(report_id)
        if report is None:
            return None, "Report not found"
        return self.load_viewer_payload(report)

    def get_list_summary(self) -> Dict[str, Any]:
        reports = self.scan_reports()
        groups = self.group_by_timeframe(reports)
        return {
            "total_count": len(reports),
            "timeframe_count": len(groups),
            "groups": groups,
        }

    def group_by_timeframe(self, reports: Optional[Iterable[Report]] = None) -> Dict[str, Dict[str, Any]]:
        if reports is None:
            if not self._ordered_ids:
                self.scan_reports()
            source_reports = [self._reports_by_id[idx] for idx in self._ordered_ids if idx in self._reports_by_id]
        else:
            source_reports = list(reports)

        grouped: Dict[str, List[Report]] = defaultdict(list)
        for report in source_reports:
            grouped[report.timeframe_id].append(report)

        sorted_group_items = sorted(
            grouped.items(),
            key=lambda item: (
                item[1][0].timeframe_key == "unknown",
                item[1][0].timeframe_key,
                item[1][0].scenario_key,
            ),
            reverse=True,
        )

        result: Dict[str, Dict[str, Any]] = {}
        for timeframe_id, items in sorted_group_items:
            sorted_items = sorted(
                items,
                key=lambda item: (
                    item.generated_at == "unknown",
                    item.generated_at,
                    item.filename,
                ),
                reverse=True,
            )
            openai_item = next((item for item in sorted_items if item.provider == "openai"), None)
            anthropic_item = next((item for item in sorted_items if item.provider == "anthropic"), None)
            unknown_items = [item for item in sorted_items if item.provider == "unknown"]

            group_obj = {
                "timeframe_id": timeframe_id,
                "timeframe": sorted_items[0].timeframe_label if sorted_items else "unknown",
                "scenario": sorted_items[0].scenario if sorted_items else "unknown",
                "scenario_key": sorted_items[0].scenario_key if sorted_items else "unknown",
                "timeframe_key": sorted_items[0].timeframe_key if sorted_items else "unknown",
                "openai": openai_item.to_summary() if openai_item else None,
                "anthropic": anthropic_item.to_summary() if anthropic_item else None,
                "unknown_reports": [item.to_summary() for item in unknown_items],
                "reports": [item.to_summary() for item in sorted_items],
                "has_both": bool(openai_item and anthropic_item),
            }
            result[timeframe_id] = group_obj

        self._groups_by_timeframe_id = result
        return result

    def get_group_by_timeframe_id(self, timeframe_id: str) -> Dict[str, Any] | None:
        if timeframe_id not in self._groups_by_timeframe_id:
            self.scan_reports()
        return self._groups_by_timeframe_id.get(timeframe_id)

    def filter_groups(
        self,
        groups: Dict[str, Dict[str, Any]],
        filters: Dict[str, Optional[str]],
    ) -> Dict[str, Dict[str, Any]]:
        query = str(filters.get("q") or "").strip().lower()
        lint = str(filters.get("lint") or "").strip().lower()
        pair = str(filters.get("pair") or "").strip().lower()
        provider = str(filters.get("provider") or "").strip().lower()

        filtered: Dict[str, Dict[str, Any]] = {}
        for timeframe_id, group in groups.items():
            if query and not self._matches_query(group, query):
                continue
            if lint and not self._matches_lint(group, lint):
                continue
            if pair and not self._matches_pair(group, pair):
                continue
            if provider and not self._matches_provider(group, provider):
                continue
            filtered[timeframe_id] = group
        return filtered

    def _iter_group_reports(self, group: Dict[str, Any]) -> List[Dict[str, Any]]:
        reports = group.get("reports")
        if isinstance(reports, list):
            return [report for report in reports if isinstance(report, dict)]

        items: List[Dict[str, Any]] = []
        openai = group.get("openai")
        anthropic = group.get("anthropic")
        unknown_reports = group.get("unknown_reports")
        if isinstance(openai, dict):
            items.append(openai)
        if isinstance(anthropic, dict):
            items.append(anthropic)
        if isinstance(unknown_reports, list):
            items.extend([row for row in unknown_reports if isinstance(row, dict)])
        return items

    def _matches_query(self, group: Dict[str, Any], query: str) -> bool:
        # Group-level scenario fields are checked first per Phase 2A contract.
        if _contains_text(group.get("scenario"), query) or _contains_text(group.get("scenario_key"), query):
            return True

        for report in self._iter_group_reports(group):
            if _contains_text(report.get("filename"), query):
                return True
            if _contains_text(report.get("scenario"), query) or _contains_text(report.get("scenario_key"), query):
                return True
            if _contains_text(report.get("report_id"), query):
                return True
        return False

    def _matches_lint(self, group: Dict[str, Any], lint: str) -> bool:
        for report in self._iter_group_reports(group):
            verdict = str((report.get("lint") or {}).get("verdict") or "").strip().lower()
            if verdict == lint:
                return True
        return False

    def _matches_pair(self, group: Dict[str, Any], pair: str) -> bool:
        has_both = bool(group.get("has_both"))
        if pair == "both":
            return has_both
        if pair == "partial":
            return not has_both
        return True

    def _matches_provider(self, group: Dict[str, Any], provider: str) -> bool:
        if provider == "openai":
            return isinstance(group.get("openai"), dict)
        if provider == "anthropic":
            return isinstance(group.get("anthropic"), dict)
        if provider == "unknown":
            unknown_reports = group.get("unknown_reports")
            return isinstance(unknown_reports, list) and len(unknown_reports) > 0
        return True

    def _iter_unique_report_paths(self) -> List[Path]:
        unique: Dict[Path, Path] = {}
        for pattern in self.report_globs:
            for path in self.project_root.glob(pattern):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                unique[resolved] = path
        return [unique[key] for key in sorted(unique.keys())]

    def _load_single_report(self, file_path: Path) -> Report:
        report_id = make_report_id(file_path)
        filename = file_path.name
        repo_relative_path = to_repo_relative_path(file_path, self.project_root)

        scenario_key, filename_timeframe_key = parse_filename_scenario_timeframe(filename)
        timeframe_key = filename_timeframe_key
        timeframe_label = filename_timeframe_key

        if timeframe_key == "unknown":
            timeframe_key = repo_relative_path
            timeframe_label = filename

        scenario_label = scenario_key if scenario_key != "unknown" else "unknown"
        timeframe_id = make_timeframe_id(scenario_key, timeframe_key)

        default_lint = default_lint_summary()
        base_report = Report(
            report_id=report_id,
            file_path=file_path,
            filename=filename,
            repo_relative_path=repo_relative_path,
            provider=resolve_provider(filename=filename, meta_provider=None),
            model="unknown",
            scenario=scenario_label,
            scenario_key=scenario_key,
            timeframe=timeframe_label,
            timeframe_key=timeframe_key,
            timeframe_label=timeframe_label,
            timeframe_id=timeframe_id,
            generated_at="unknown",
            incident_count=0,
            severity_counts=zero_severity_counts(),
            verdict_counts={},
            lint=default_lint,
            is_valid=True,
            error=None,
            meta={},
            report={},
        )

        try:
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            base_report.is_valid = False
            base_report.error = f"Failed to read JSON: {exc}"
            return base_report

        if not isinstance(data, dict):
            base_report.is_valid = False
            base_report.error = "Invalid JSON root: expected object"
            return base_report

        meta = data.get("meta") or {}
        report_payload = data.get("report") or {}
        if not isinstance(meta, dict):
            meta = {}
        if not isinstance(report_payload, dict):
            report_payload = {}

        report_payload = normalize_report_payload(report_payload)

        base_report.meta = meta
        base_report.report = report_payload
        base_report.model = str(meta.get("selected_model") or "unknown")
        base_report.generated_at = str(meta.get("generated_at") or "unknown")
        base_report.provider = resolve_provider(filename=filename, meta_provider=meta.get("provider"))

        window_timeframe_key, window_timeframe_label = extract_timeframe_from_meta_window(meta)
        if window_timeframe_key != "unknown":
            base_report.timeframe_key = window_timeframe_key
            base_report.timeframe = window_timeframe_label
            base_report.timeframe_label = window_timeframe_label

        if base_report.scenario_key == "unknown":
            base_report.scenario = "unknown"

        if base_report.timeframe_key == "unknown":
            base_report.timeframe_key = repo_relative_path
            base_report.timeframe = filename
            base_report.timeframe_label = filename

        base_report.timeframe_id = make_timeframe_id(base_report.scenario_key, base_report.timeframe_key)

        notable_incidents = report_payload.get("notable_incidents") or []
        base_report.incident_count = len(notable_incidents)
        base_report.severity_counts = count_severity_values(notable_incidents, "severity")
        base_report.verdict_counts = count_named_values(notable_incidents, "verdict")

        viewer_path = self._resolve_viewer_payload_path(file_path)
        if viewer_path.exists():
            try:
                with viewer_path.open("r", encoding="utf-8") as handle:
                    viewer_payload = json.load(handle)
                if not isinstance(viewer_payload, dict):
                    base_report.viewer_payload_available = False
                    base_report.viewer_payload_error = "Invalid viewer_payload root: expected object"
                else:
                    base_report.viewer_payload_available = True
                    base_report.viewer_payload_path = to_repo_relative_path(viewer_path, self.project_root)
                    base_report.viewer_payload_summary = self._build_viewer_payload_summary(viewer_payload)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                # viewer_payload 로드 실패는 report detail 자체를 invalid 처리하지 않는다.
                base_report.viewer_payload_available = False
                base_report.viewer_payload_error = f"viewer_payload load error: {exc}"

        return base_report

    def _resolve_viewer_payload_path(self, stage2_report_path: Path) -> Path:
        base_name = stage2_report_path.name
        if base_name.endswith(STAGE2_SUFFIX):
            stem = base_name[: -len(STAGE2_SUFFIX)]
            return stage2_report_path.with_name(f"{stem}_viewer_payload.json")
        return stage2_report_path.with_name(stage2_report_path.stem + "_viewer_payload.json")

    def _build_viewer_payload_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        meta = payload.get("meta")
        summary = payload.get("summary")
        report = payload.get("report")
        integrity = payload.get("integrity")
        policies = payload.get("policies")

        meta_obj = meta if isinstance(meta, dict) else {}
        summary_obj = summary if isinstance(summary, dict) else {}
        report_obj = report if isinstance(report, dict) else {}
        integrity_obj = integrity if isinstance(integrity, dict) else {}
        policies_obj = policies if isinstance(policies, dict) else {}

        findings = payload.get("findings")
        contexts = payload.get("contexts")
        supporting_events = payload.get("supporting_events")

        finding_rows = findings if isinstance(findings, list) else []
        context_rows = contexts if isinstance(contexts, list) else []
        supporting_rows = supporting_events if isinstance(supporting_events, list) else []

        return {
            "schema_version": str(payload.get("schema_version") or "unknown"),
            "generated_at": first_non_empty(
                meta_obj.get("generated_at"),
                summary_obj.get("generated_at"),
            )
            or "unknown",
            "report_title": first_non_empty(
                summary_obj.get("report_title"),
                report_obj.get("report_title"),
                report_obj.get("title"),
            )
            or "N/A",
            "overall_assessment": first_non_empty(
                summary_obj.get("overall_assessment"),
                report_obj.get("overall_assessment"),
            )
            or "N/A",
            "finding_count": int(_safe_int(first_non_empty(summary_obj.get("finding_count")), len(finding_rows))),
            "context_count": int(_safe_int(first_non_empty(summary_obj.get("context_count")), len(context_rows))),
            "supporting_event_count": int(
                _safe_int(first_non_empty(summary_obj.get("supporting_event_count")), len(supporting_rows))
            ),
            "findings_preview": [self._build_finding_preview(row) for row in finding_rows[:5] if isinstance(row, dict)],
            "contexts_preview": [self._build_context_preview(row) for row in context_rows[:5] if isinstance(row, dict)],
            "integrity_warnings": self._ensure_str_list(integrity_obj.get("warnings")),
            "guardrails": self._ensure_str_list(policies_obj.get("guardrails")),
            "source_of_truth": meta_obj.get("source_of_truth") if isinstance(meta_obj.get("source_of_truth"), dict) else {},
        }

    def _build_finding_preview(self, row: Dict[str, Any]) -> Dict[str, Any]:
        request_obj = row.get("request") if isinstance(row.get("request"), dict) else {}
        raw_export_match_obj = row.get("raw_export_match") if isinstance(row.get("raw_export_match"), dict) else {}
        log_time = (
            first_non_empty(
                row.get("log_time"),
                row.get("timestamp"),
                request_obj.get("log_time"),
                request_obj.get("timestamp"),
            )
            or "unknown"
        )
        return {
            "log_time": log_time,
            "display_time": _format_display_time(log_time),
            "severity": str(row.get("severity") or "unknown"),
            "verdict": str(row.get("verdict") or row.get("verdict_hint") or "unknown"),
            "category": str(row.get("category") or "unknown"),
            "src_ip": str(row.get("src_ip") or "-"),
            "method": str(row.get("method") or "-"),
            "uri": str(row.get("uri") or "-"),
            "status_code": _safe_int(row.get("status_code"), 0) if row.get("status_code") not in (None, "") else "-",
            "request_id": str(row.get("request_id") or "-"),
            "confidence": str(row.get("confidence") or "unknown"),
            "context_only": bool(row.get("context_only")),
            "reasoning_summary": str(row.get("reasoning_summary") or "N/A"),
            "evidence_fields": self._ensure_str_listish(row.get("evidence_fields")),
            "reason_hints": self._ensure_str_listish(row.get("reason_hints")),
            "recommended_actions": self._ensure_str_listish(row.get("recommended_actions")),
            "raw_export_match": {
                "source_table": str(raw_export_match_obj.get("source_table") or "N/A"),
                "log_id": str(raw_export_match_obj.get("log_id") or "N/A"),
                "request_id": str(raw_export_match_obj.get("request_id") or "N/A"),
            },
        }

    def _build_context_preview(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "context_type": str(row.get("context_type") or row.get("category") or "unknown"),
            "src_ip": str(row.get("src_ip") or "-"),
            "request_count": _safe_int(row.get("request_count"), 0) if row.get("request_count") not in (None, "") else "-",
            "context_only": bool(row.get("context_only")),
            "should_promote_to_candidate": bool(row.get("should_promote_to_candidate")),
            "interpretation_limit": str(row.get("interpretation_limit") or "-"),
        }

    def _ensure_str_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    def _ensure_str_listish(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if value in (None, ""):
            return []
        text = str(value).strip()
        return [text] if text else []


def make_report_id(file_path: Path) -> str:
    try:
        relative_path = file_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        relative_path = file_path.resolve()
    return hashlib.sha256(str(relative_path).encode("utf-8")).hexdigest()[:16]


def make_timeframe_id(scenario: str, timeframe: str) -> str:
    return hashlib.sha256(f"{scenario}|{timeframe}".encode("utf-8")).hexdigest()[:16]


def _contains_text(value: Any, query: str) -> bool:
    if value is None:
        return False
    return query in str(value).lower()


def default_lint_summary() -> Dict[str, Any]:
    return {
        "verdict": "UNKNOWN",
        "checked_fields": 0,
        "blocker_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "is_error": False,
    }


def zero_severity_counts() -> Dict[str, int]:
    return {bucket: 0 for bucket in SEVERITY_BUCKETS}


def to_repo_relative_path(file_path: Path, project_root: Path) -> str:
    try:
        relative = file_path.resolve().relative_to(project_root.resolve())
        return str(relative)
    except ValueError:
        return file_path.name


def resolve_provider(filename: str, meta_provider: Any) -> str:
    lower = filename.lower()

    # 1) filename prefix
    if lower.startswith("op-") or lower.startswith("openai-"):
        return "openai"
    if lower.startswith("cl-") or lower.startswith("claude-"):
        return "anthropic"

    # 2) meta.provider
    meta_text = str(meta_provider or "").strip().lower()
    if meta_text == "openai":
        return "openai"
    if meta_text in {"anthropic", "claude"}:
        return "anthropic"

    # 3) filename token
    if "openai" in lower:
        return "openai"
    if "claude" in lower or "anthropic" in lower or "cl-" in lower:
        return "anthropic"

    return "unknown"


def parse_filename_scenario_timeframe(filename: str) -> Tuple[str, str]:
    stem = filename
    if stem.endswith(STAGE2_SUFFIX):
        stem = stem[: -len(STAGE2_SUFFIX)]

    timeframe_key = extract_timeframe_from_string(stem)

    working = stem
    for prefix in ("op-", "openai-", "cl-", "claude-"):
        if working.lower().startswith(prefix):
            working = working[len(prefix) :]
            break

    scenario = "unknown"
    if timeframe_key != "unknown":
        parts = working.split("_" + timeframe_key)
        if parts and parts[0].strip("_"):
            scenario = parts[0].strip("_")
    elif working.strip("_"):
        scenario = working.strip("_")

    return scenario or "unknown", timeframe_key


def extract_timeframe_from_meta_window(meta: Dict[str, Any]) -> Tuple[str, str]:
    for key in ("source_window", "analysis_window", "window"):
        raw_window = meta.get(key)
        if not isinstance(raw_window, dict):
            continue

        start = first_non_empty(raw_window.get("start"), raw_window.get("start_inclusive"))
        end = first_non_empty(
            raw_window.get("end_exclusive"),
            raw_window.get("end"),
            raw_window.get("end_inclusive"),
        )

        if start and end:
            timeframe = f"{start}_to_{end}"
            return timeframe, timeframe

    return "unknown", "unknown"


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_display_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"

    if text.lower() == "unknown":
        return "unknown"

    minute_fraction_match = re.search(r"[T ](\d{2}):(\d{2})\.\d+", text)
    if minute_fraction_match:
        hour, minute = minute_fraction_match.groups()
        return f"{hour}:{minute}"

    candidates = [text]

    # Normalize " ... 09:00" into "...+09:00" for permissive parsing.
    if not re.search(r"[+-]\d{2}:\d{2}$", text):
        spaced_tz = re.sub(r"\s+(\d{2}:\d{2})$", r"+\1", text)
        if spaced_tz != text:
            candidates.append(spaced_tz)

    normalized_candidates: List[str] = []
    for candidate in candidates:
        if candidate.endswith("Z"):
            normalized_candidates.append(candidate[:-1] + "+00:00")
        else:
            normalized_candidates.append(candidate)

        # Handle minute+fraction style like "2026-05-03T19:37.182+09:00".
        with_seconds = re.sub(
            r"(T\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})$",
            r"\1:00.\2\3",
            candidate,
        )
        if with_seconds != candidate:
            normalized_candidates.append(with_seconds)

    for candidate in normalized_candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue

    # Last fallback: extract readable HH:MM[:SS] token directly.
    match = re.search(r"(\d{2}):(\d{2})(?::(\d{2}))?", text)
    if match:
        hour, minute, second = match.groups()
        return f"{hour}:{minute}:{second}" if second is not None else f"{hour}:{minute}"

    return "unknown"


def extract_timeframe_from_string(text: str) -> str:
    match = TIMEFRAME_PATTERN.search(text)
    if not match:
        return "unknown"
    return match.group(0)


def normalize_report_payload(report_payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(report_payload)
    for key in ("notable_incidents", "recommended_actions", "key_findings", "notable_source_ips"):
        value = normalized.get(key)
        if not isinstance(value, list):
            normalized[key] = []
    return normalized


def count_severity_values(rows: List[Any], field_name: str) -> Dict[str, int]:
    counts = zero_severity_counts()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get(field_name) or "unknown").strip().lower()
        if key not in counts:
            key = "unknown"
        counts[key] += 1
    return counts


def count_named_values(rows: List[Any], field_name: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get(field_name) or "unknown").strip().lower()
        counts[key] = counts.get(key, 0) + 1
    return counts
