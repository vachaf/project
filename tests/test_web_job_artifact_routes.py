from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi import HTTPException

import web.app as web_app_module


class FakeArtifactRepository:
    def __init__(self, report: Optional[dict[str, Any]]) -> None:
        self.report = report

    def get_latest_report_for_job(self, job_id: int) -> Optional[dict[str, Any]]:
        return self.report


def make_report(**overrides: Any) -> dict[str, Any]:
    report = {
        "artifact_root": "runs/jobs/123",
        "export_path": "runs/jobs/123/export.json",
        "llm_input_path": "runs/jobs/123/llm_input.json",
        "analysis_candidates_path": "runs/jobs/123/analysis_candidates.json",
        "noise_summary_path": "runs/jobs/123/noise_summary.json",
        "stage1_result_path": "runs/jobs/123/stage1_results.json",
        "stage2_report_path": "runs/jobs/123/stage2_report.json",
        "stage2_report_md_path": "runs/jobs/123/stage2_report.md",
        "viewer_payload_path": "runs/jobs/123/viewer_payload.json",
        "lint_result_path": None,
    }
    report.update(overrides)
    return report


def write_artifact(project_root: Path, relative_path: str, content: str = "{}") -> Path:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def install_artifact_repo(monkeypatch: pytest.MonkeyPatch, project_root: Path, report: Optional[dict[str, Any]]) -> None:
    monkeypatch.setattr(web_app_module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(web_app_module, "job_repository", FakeArtifactRepository(report))


def assert_artifact_404() -> Any:
    return pytest.raises(HTTPException, match="artifact not found")


def test_allowed_artifact_key_returns_report_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_artifact(tmp_path, "runs/jobs/123/export.json", '{"ok": true}')
    install_artifact_repo(monkeypatch, tmp_path, make_report())

    response = web_app_module.job_artifact(123, "export")

    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert response.body == b'{"ok": true}'


def test_stage2_report_markdown_artifact_can_be_opened(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_artifact(tmp_path, "runs/jobs/123/stage2_report.md", "# report")
    install_artifact_repo(monkeypatch, tmp_path, make_report())

    response = web_app_module.job_artifact(123, "stage2_report_md")

    assert response.status_code == 200
    assert response.media_type == "text/markdown; charset=utf-8"
    assert response.body == b"# report"


def test_viewer_payload_artifact_can_be_opened(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_artifact(tmp_path, "runs/jobs/123/viewer_payload.json", '{"items": []}')
    install_artifact_repo(monkeypatch, tmp_path, make_report())

    response = web_app_module.job_artifact(123, "viewer_payload")

    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert response.body == b'{"items": []}'


def test_no_data_job_exposes_export_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_artifact(tmp_path, "runs/jobs/123/export.json", '{"meta": {"total_count": 0}}')
    install_artifact_repo(
        monkeypatch,
        tmp_path,
        make_report(
            llm_input_path=None,
            analysis_candidates_path=None,
            noise_summary_path=None,
            stage1_result_path=None,
            stage2_report_path=None,
            stage2_report_md_path=None,
            viewer_payload_path=None,
        ),
    )

    assert web_app_module.job_artifact(123, "export").status_code == 200
    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "stage2_report")
    assert exc_info.value.status_code == 404


def test_null_artifact_path_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install_artifact_repo(monkeypatch, tmp_path, make_report(viewer_payload_path=None))

    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "viewer_payload")

    assert exc_info.value.status_code == 404


def test_unknown_artifact_key_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install_artifact_repo(monkeypatch, tmp_path, make_report())

    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "manifest")

    assert exc_info.value.status_code == 404


def test_missing_analysis_report_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install_artifact_repo(monkeypatch, tmp_path, None)

    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "export")

    assert exc_info.value.status_code == 404


def test_missing_file_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install_artifact_repo(monkeypatch, tmp_path, make_report())

    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "export")

    assert exc_info.value.status_code == 404


def test_absolute_path_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    absolute_path = tmp_path / "runs" / "jobs" / "123" / "export.json"
    write_artifact(tmp_path, "runs/jobs/123/export.json")
    install_artifact_repo(monkeypatch, tmp_path, make_report(export_path=str(absolute_path)))

    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "export")

    assert exc_info.value.status_code == 404


def test_path_traversal_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_artifact(tmp_path, "runs/jobs/secret.json")
    install_artifact_repo(monkeypatch, tmp_path, make_report(export_path="runs/jobs/123/../secret.json"))

    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "export")

    assert exc_info.value.status_code == 404


def test_resolved_path_outside_project_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    outside_root = tmp_path.parent / "outside-artifact-route-test"
    outside_root.mkdir(exist_ok=True)
    outside_file = outside_root / "secret.json"
    outside_file.write_text("secret", encoding="utf-8")
    link_path = tmp_path / "runs" / "jobs" / "123" / "link.json"
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(outside_file)
    install_artifact_repo(monkeypatch, tmp_path, make_report(export_path="runs/jobs/123/link.json"))

    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "export")

    assert exc_info.value.status_code == 404


def test_artifact_outside_report_artifact_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_artifact(tmp_path, "runs/jobs/999/export.json")
    install_artifact_repo(monkeypatch, tmp_path, make_report(export_path="runs/jobs/999/export.json"))

    with assert_artifact_404() as exc_info:
        web_app_module.job_artifact(123, "export")

    assert exc_info.value.status_code == 404
