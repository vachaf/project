from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from run_analysis_pipeline import resolve_prepare_source_tables


def write_export(tmp_path: Path, payload: object, name: str = "export.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_requested_security_wins_over_export(tmp_path: Path) -> None:
    export_path = write_export(
        tmp_path,
        {"meta": {"table_option": "all"}, "counts": {"access": 10, "security": 0, "error": 0}, "data": {}},
    )
    resolved, reason = resolve_prepare_source_tables(str(export_path), "security", "export")
    assert resolved == "security"
    assert reason == "user_requested_explicit"


def test_requested_access_security_is_used_as_is(tmp_path: Path) -> None:
    export_path = write_export(
        tmp_path,
        {"meta": {"table_option": "security"}, "counts": {"access": 0, "security": 10, "error": 0}, "data": {}},
    )
    resolved, reason = resolve_prepare_source_tables(str(export_path), "access,security", "export")
    assert resolved == "access,security"
    assert reason == "user_requested_explicit"


def test_auto_table_option_security(tmp_path: Path) -> None:
    export_path = write_export(tmp_path, {"meta": {"table_option": "security"}, "counts": {}, "data": {}})
    resolved, reason = resolve_prepare_source_tables(str(export_path), "auto", "export")
    assert resolved == "security"
    assert reason == "resolved_from_table_option_security"


def test_auto_table_option_access(tmp_path: Path) -> None:
    export_path = write_export(tmp_path, {"meta": {"table_option": "access"}, "counts": {}, "data": {}})
    resolved, reason = resolve_prepare_source_tables(str(export_path), "auto", "export")
    assert resolved == "access"
    assert reason == "resolved_from_table_option_access"


def test_auto_all_counts_access_only(tmp_path: Path) -> None:
    export_path = write_export(
        tmp_path,
        {
            "meta": {"table_option": "all"},
            "counts": {"security": 0, "access": 3, "error": 0},
            "data": {"security": [], "access": [], "error": []},
        },
    )
    resolved, reason = resolve_prepare_source_tables(str(export_path), "auto", "export")
    assert resolved == "access"
    assert reason == "resolved_from_table_option_all_counts_or_data"


def test_auto_all_counts_security_and_access(tmp_path: Path) -> None:
    export_path = write_export(
        tmp_path,
        {
            "meta": {"table_option": "all"},
            "counts": {"security": 4, "access": 2, "error": 0},
            "data": {"security": [], "access": [], "error": []},
        },
    )
    resolved, reason = resolve_prepare_source_tables(str(export_path), "auto", "export")
    assert resolved == "security,access"
    assert reason == "resolved_from_table_option_all_counts_or_data"


def test_auto_all_fallback_to_data_rows(tmp_path: Path) -> None:
    export_path = write_export(
        tmp_path,
        {
            "meta": {"table_option": "all"},
            "data": {"security": [], "access": [{"id": 1}], "error": [{"id": 2}]},
        },
    )
    resolved, reason = resolve_prepare_source_tables(str(export_path), "auto", "export")
    assert resolved == "access,error"
    assert reason == "resolved_from_table_option_all_counts_or_data"


def test_auto_malformed_export_fallback_security(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not-json", encoding="utf-8")
    resolved, reason = resolve_prepare_source_tables(str(bad_path), "auto", "export")
    assert resolved == "security"
    assert reason == "export_json_unreadable_fallback_security"
