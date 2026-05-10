from __future__ import annotations

import sys
from pathlib import Path

import pytest

from web.services.report_loader import ReportLoader

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from helpers.web_loader_phase2_fixtures import build_web_loader_phase2_fixture_root


RUN_DIR_SCAN_NOT_IMPLEMENTED = pytest.mark.xfail(
    reason="run_dir manifest scan not implemented yet",
    strict=False,
)


def _build_loader_for_run_dir_manifest_scan(fixture_root: Path) -> ReportLoader:
    return ReportLoader(
        project_root=fixture_root,
        report_globs=["runs/*/manifest.json"],
    )


def _find_report_by_run_id(reports: list, run_id: str):
    for report in reports:
        if (report.meta or {}).get("run_id") == run_id:
            return report
    return None


def test_run_dir_scan_includes_valid_run_only(tmp_path: Path) -> None:
    fixture_root = build_web_loader_phase2_fixture_root(tmp_path)
    loader = _build_loader_for_run_dir_manifest_scan(fixture_root)

    reports = loader.scan_reports()
    run_ids = {(report.meta or {}).get("run_id") for report in reports}
    storage_types = {(report.meta or {}).get("storage_type") for report in reports}

    assert "run_dir_valid_basic" in run_ids
    assert "run_dir_missing_viewer_payload" in run_ids
    assert "run_dir_malformed_viewer_payload" in run_ids
    assert "run_dir_malformed_manifest" not in run_ids
    assert "run_dir_missing_stage2_report" not in run_ids
    assert storage_types == {"run_dir"}


@RUN_DIR_SCAN_NOT_IMPLEMENTED
def test_default_scan_excludes_legacy_archive_outputs(tmp_path: Path) -> None:
    fixture_root = build_web_loader_phase2_fixture_root(tmp_path)
    loader = ReportLoader(project_root=fixture_root)

    reports = loader.scan_reports()
    run_ids = {(report.meta or {}).get("run_id") for report in reports}

    assert "run_dir_valid_basic" in run_ids
    assert "flat_legacy_without_viewer_payload" not in run_ids
    assert all("archive/" not in report.repo_relative_path for report in reports)


@RUN_DIR_SCAN_NOT_IMPLEMENTED
def test_missing_viewer_payload_keeps_report_valid(tmp_path: Path) -> None:
    fixture_root = build_web_loader_phase2_fixture_root(tmp_path)
    loader = _build_loader_for_run_dir_manifest_scan(fixture_root)

    reports = loader.scan_reports()
    target = _find_report_by_run_id(reports, "run_dir_missing_viewer_payload")

    assert target is not None
    assert target.is_valid is True
    assert target.viewer_payload_available is False
    assert target.viewer_payload_error in (None, "MISSING_FILE")


@RUN_DIR_SCAN_NOT_IMPLEMENTED
def test_malformed_viewer_payload_is_fallback_safe(tmp_path: Path) -> None:
    fixture_root = build_web_loader_phase2_fixture_root(tmp_path)
    loader = _build_loader_for_run_dir_manifest_scan(fixture_root)

    reports = loader.scan_reports()
    target = _find_report_by_run_id(reports, "run_dir_malformed_viewer_payload")

    assert target is not None
    assert target.is_valid is True
    assert target.viewer_payload_available is False
    assert target.viewer_payload_error in ("MALFORMED_JSON", "INVALID_JSON")


@RUN_DIR_SCAN_NOT_IMPLEMENTED
def test_run_dir_report_id_resolves_detail_and_payload(tmp_path: Path) -> None:
    fixture_root = build_web_loader_phase2_fixture_root(tmp_path)
    loader = _build_loader_for_run_dir_manifest_scan(fixture_root)

    reports = loader.scan_reports()
    target = _find_report_by_run_id(reports, "run_dir_valid_basic")

    assert target is not None
    detail = loader.get_report_by_id(target.report_id)
    assert detail is not None
    assert (detail.meta or {}).get("run_id") == "run_dir_valid_basic"
    assert (detail.meta or {}).get("manifest_path")

    viewer_payload, error = loader.load_viewer_payload_by_report_id(target.report_id)
    assert error is None
    assert viewer_payload is not None
    assert viewer_payload.get("schema_version") == "viewer_payload.v1"
