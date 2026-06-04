from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from web.config import QA_OUTPUT_DIR, QA_SCRIPT_PATH, QA_TIMEOUT_SEC


class QARunner:
    def __init__(
        self,
        script_path: Path = QA_SCRIPT_PATH,
        output_dir: Path = QA_OUTPUT_DIR,
        timeout_sec: int = QA_TIMEOUT_SEC,
        python_exec: str = "python3",
    ) -> None:
        self.script_path = script_path
        self.output_dir = output_dir
        self.timeout_sec = timeout_sec
        self.python_exec = python_exec

    def run_quality_lint(self, report_id: str, report_path: Path) -> Dict[str, Any]:
        if not report_path.exists():
            return self._error_result("Report file missing")
        if not self.script_path.exists():
            return self._error_result("Lint script missing")

        output_path = self._output_path(report_id)
        cached = self._read_cached_if_fresh(output_path, report_path)
        if cached is not None:
            return cached

        self.output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            self.python_exec,
            str(self.script_path),
            "--input",
            str(report_path),
            "--output",
            str(output_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
        except subprocess.TimeoutExpired:
            return self._error_result(f"Lint timeout after {self.timeout_sec}s")
        except OSError as exc:
            return self._error_result(f"Failed to execute lint script: {exc}")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            message = stderr or stdout or f"Lint script exited with code {result.returncode}"
            return self._error_result(message)

        try:
            with output_path.open("r", encoding="utf-8") as handle:
                parsed = json.load(handle)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return self._error_result(f"Failed to parse lint output JSON: {exc}")

        if not isinstance(parsed, dict):
            return self._error_result("Lint output must be a JSON object")

        return self._normalize_qa_output(parsed)

    def lint_summary(self, report_id: str, report_path: Path) -> Dict[str, Any]:
        result = self.run_quality_lint(report_id, report_path)
        return {
            "verdict": result.get("verdict", "UNKNOWN"),
            "checked_fields": result.get("checked_fields", 0),
            "blocker_count": result.get("blocker_count", 0),
            "warning_count": result.get("warning_count", 0),
            "info_count": result.get("info_count", 0),
            "is_error": bool(result.get("is_error", False)),
        }

    def _output_path(self, report_id: str) -> Path:
        return self.output_dir / f"{report_id}.json"

    def _read_cached_if_fresh(self, output_path: Path, report_path: Path) -> Optional[Dict[str, Any]]:
        if not output_path.exists():
            return None
        try:
            output_mtime = output_path.stat().st_mtime
            report_mtime = report_path.stat().st_mtime
        except OSError:
            return None

        if output_mtime < report_mtime:
            return None

        try:
            with output_path.open("r", encoding="utf-8") as handle:
                parsed = json.load(handle)
        except (OSError, json.JSONDecodeError, ValueError):
            return None

        if not isinstance(parsed, dict):
            return None

        return self._normalize_qa_output(parsed)

    def _normalize_qa_output(self, data: Dict) -> Dict:
        summary = data.get("summary", {})
        if not isinstance(summary, dict):
            summary = {}

        return {
            "verdict": str(data.get("verdict", "UNKNOWN") or "UNKNOWN"),
            "checked_fields": int(summary.get("checked_fields", 0) or 0),
            "blocker_count": int(summary.get("blocker_count", 0) or 0),
            "warning_count": int(summary.get("warning_count", 0) or 0),
            "info_count": int(summary.get("info_count", 0) or 0),
            "blockers": self._normalize_issue_list(data.get("blockers", [])),
            "warnings": self._normalize_issue_list(data.get("warnings", [])),
            "info": self._normalize_issue_list(data.get("info", [])),
            "is_error": False,
            "error": None,
        }

    def _normalize_issue_list(self, rows: Any) -> List[Dict[str, str]]:
        if not isinstance(rows, list):
            return []

        normalized: List[Dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized.append(
                {
                    "rule": str(row.get("rule") or "-"),
                    "path": str(row.get("path") or "-"),
                    "excerpt": str(row.get("excerpt") or "-"),
                    "source_text": str(row.get("source_text") or ""),
                    "suggestion": str(row.get("suggestion") or "-"),
                }
            )
        return normalized

    def _error_result(self, message: str) -> Dict[str, Any]:
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
            "error": message,
        }
