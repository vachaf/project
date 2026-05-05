from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from web.config import PROJECT_ROOT, REPORT_GLOBS


STAGE2_SUFFIX = "_stage2_report.json"
TIMEFRAME_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}_[0-9-]+_to_\d{4}-\d{2}-\d{2}_[0-9-]+(?:_[a-zA-Z0-9-]+)?"
)


@dataclass
class Report:
    report_id: str
    file_path: Path
    filename: str
    repo_relative_path: str
    provider: str
    model: str
    scenario: str
    timeframe: str
    generated_at: str
    incident_count: int
    severity_counts: Dict[str, int]
    verdict_counts: Dict[str, int]
    lint: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    report: Dict[str, Any] = field(default_factory=dict)

    def to_summary(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "filename": self.filename,
            "repo_relative_path": self.repo_relative_path,
            "provider": self.provider,
            "model": self.model,
            "scenario": self.scenario,
            "timeframe": self.timeframe,
            "generated_at": self.generated_at,
            "incident_count": self.incident_count,
            "severity_counts": dict(self.severity_counts),
            "verdict_counts": dict(self.verdict_counts),
            "lint": dict(self.lint),
            "is_valid": self.is_valid,
            "error": self.error,
        }

    def to_detail(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "filename": self.filename,
            "repo_relative_path": self.repo_relative_path,
            "provider": self.provider,
            "model": self.model,
            "scenario": self.scenario,
            "timeframe": self.timeframe,
            "generated_at": self.generated_at,
            "meta": dict(self.meta),
            "report": dict(self.report),
            "is_valid": self.is_valid,
            "error": self.error,
        }


class ReportLoader:
    def __init__(
        self,
        project_root: Path = PROJECT_ROOT,
        report_globs: Optional[List[str]] = None,
    ) -> None:
        self.project_root = project_root
        self.report_globs = report_globs or list(REPORT_GLOBS)
        self._reports_by_id: Dict[str, Report] = {}
        self._ordered_ids: List[str] = []

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
                item.timeframe,
                item.generated_at,
                item.filename,
            ),
            reverse=True,
        )

        self._reports_by_id = reports_by_id
        self._ordered_ids = [report.report_id for report in reports]
        return reports

    def get_report_by_id(self, report_id: str) -> Optional[Report]:
        if report_id not in self._reports_by_id:
            self.scan_reports()
        return self._reports_by_id.get(report_id)

    def get_list_summary(self) -> Dict[str, Any]:
        reports = self.scan_reports()
        groups = self.group_by_timeframe(reports)
        return {
            "total_count": len(reports),
            "timeframe_count": len(groups),
            "groups": groups,
        }

    def group_by_timeframe(self, reports: Optional[Iterable[Report]] = None) -> Dict[str, Dict[str, Any]]:
        source_reports = list(reports) if reports is not None else [self._reports_by_id[idx] for idx in self._ordered_ids]

        grouped: Dict[str, List[Report]] = defaultdict(list)
        for report in source_reports:
            grouped[report.timeframe].append(report)

        result: Dict[str, Dict[str, Any]] = {}
        for timeframe, items in sorted(grouped.items(), key=lambda kv: kv[0], reverse=True):
            openai_item = next((item for item in items if item.provider == "openai"), None)
            anthropic_item = next((item for item in items if item.provider == "anthropic"), None)
            result[timeframe] = {
                "timeframe": timeframe,
                "reports": [item.to_summary() for item in items],
                "openai": openai_item.to_summary() if openai_item else None,
                "anthropic": anthropic_item.to_summary() if anthropic_item else None,
                "has_both": bool(openai_item and anthropic_item),
            }
        return result

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
        parsed_provider, scenario, timeframe = parse_filename_metadata(filename)

        default_lint = default_lint_summary()
        base_report = Report(
            report_id=report_id,
            file_path=file_path,
            filename=filename,
            repo_relative_path=repo_relative_path,
            provider=parsed_provider,
            model="unknown",
            scenario=scenario,
            timeframe=timeframe,
            generated_at="unknown",
            incident_count=0,
            severity_counts={},
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

        provider_from_meta = normalize_provider(meta.get("provider"))
        if provider_from_meta != "unknown":
            base_report.provider = provider_from_meta

        if base_report.scenario == "unknown":
            scenario_from_meta = str(meta.get("mode") or "").strip()
            if scenario_from_meta:
                base_report.scenario = scenario_from_meta

        if base_report.timeframe == "unknown":
            timeframe_from_filename = extract_timeframe_from_string(repo_relative_path)
            if timeframe_from_filename != "unknown":
                base_report.timeframe = timeframe_from_filename

        notable_incidents = report_payload.get("notable_incidents") or []
        base_report.incident_count = len(notable_incidents)
        base_report.severity_counts = count_values(notable_incidents, "severity")
        base_report.verdict_counts = count_values(notable_incidents, "verdict")

        return base_report


def make_report_id(file_path: Path) -> str:
    try:
        relative_path = file_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        relative_path = file_path.resolve()
    return hashlib.sha256(str(relative_path).encode("utf-8")).hexdigest()[:16]


def default_lint_summary() -> Dict[str, Any]:
    return {
        "verdict": "UNKNOWN",
        "checked_fields": 0,
        "blocker_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "is_error": False,
    }


def to_repo_relative_path(file_path: Path, project_root: Path) -> str:
    try:
        relative = file_path.resolve().relative_to(project_root.resolve())
        return str(relative)
    except ValueError:
        return file_path.name


def normalize_provider(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"openai", "op", "op-security"}:
        return "openai"
    if text in {"anthropic", "cl", "cl-security"}:
        return "anthropic"
    return "unknown"


def parse_filename_metadata(filename: str) -> Tuple[str, str, str]:
    provider = "unknown"
    lower = filename.lower()
    if lower.startswith("op-"):
        provider = "openai"
    elif lower.startswith("cl-"):
        provider = "anthropic"
    elif lower.startswith("openai-"):
        provider = "openai"
    elif lower.startswith("anthropic-"):
        provider = "anthropic"

    stem = filename
    if stem.endswith(STAGE2_SUFFIX):
        stem = stem[: -len(STAGE2_SUFFIX)]

    timeframe = extract_timeframe_from_string(stem)

    scenario = "unknown"
    working = stem
    for prefix in ("op-", "cl-", "openai-", "anthropic-"):
        if working.lower().startswith(prefix):
            working = working[len(prefix) :]
            break

    if timeframe != "unknown":
        parts = working.split("_" + timeframe)
        if parts and parts[0].strip("_"):
            scenario = parts[0].strip("_")
    elif working.strip("_"):
        scenario = working.strip("_")

    return provider, scenario or "unknown", timeframe


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


def count_values(rows: List[Any], field_name: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get(field_name) or "unknown").strip().lower()
        counts[key] = counts.get(key, 0) + 1
    return counts
