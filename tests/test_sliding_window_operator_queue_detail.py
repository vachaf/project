from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "src" / "sliding_window_operator_queue_detail.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sliding_window_operator_queue_detail", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["sliding_window_operator_queue_detail"] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_queue_items(tmp_path: Path) -> None:
    rollup_dir = tmp_path / "data/rollups/2026-05-24/rollup_20260524_0200_0400"
    write_json(
        rollup_dir / "rollup_input.json",
        {
            "schema": "sliding_window_rollup_input_v1",
            "distributions": {
                "candidate_reason_hint_prefix": {
                    "error_linked": 5,
                    "error_status": 5,
                    "xss": 5,
                    "auth_payload_content_type": 1,
                    "login_endpoint": 1,
                    "sqli": 1,
                    "upload": 1,
                }
            },
        },
    )
    payload = {
        "schema": "sliding_window_operator_queue_items_v1",
        "queue_date": "2026-05-24",
        "generated_at": "2026-05-25T12:00:00+09:00",
        "source_rollup_root": "data/rollups/2026-05-24",
        "source_selection": {
            "rollup_root": "data/rollups/2026-05-24",
            "rollup_pattern": "rollup_*",
            "matched_rollup_count": 1,
        },
        "items": [
            {
                "schema": "sliding_window_operator_queue_item_v1",
                "queue_date": "2026-05-24",
                "generated_at": "2026-05-25T12:00:00+09:00",
                "rollup_id": "rollup_20260524_0200_0400",
                "rollup_path": "data/rollups/2026-05-24/rollup_20260524_0200_0400/rollup_input.json",
                "rollup_summary_path": "data/rollups/2026-05-24/rollup_20260524_0200_0400/rollup_summary.json",
                "time_range": {
                    "start": "2026-05-24T02:00:00+09:00",
                    "end_exclusive": "2026-05-24T04:00:00+09:00",
                    "timezone": "Asia/Seoul",
                    "duration_minutes": 120,
                },
                "data_quality_status": "complete",
                "review_status": "needs_review",
                "operator_state": "unreviewed",
                "llm_eligible": True,
                "llm_required": False,
                "recommended_action": "review_before_optional_briefing",
                "counts": {
                    "window_count": 2,
                    "windows_successfully_loaded": 2,
                    "windows_missing_or_failed": 0,
                    "candidate_rows_total": 5,
                    "candidate_index_count": 5,
                    "dedup_removed_by_request_id": 0,
                    "possible_duplicate_count": 0,
                    "noise_group_count_total": 0,
                },
                "signals": {
                    "has_candidates": True,
                    "has_missing_windows": False,
                    "has_possible_duplicates": False,
                    "has_repeated_src_ip": True,
                    "has_repeated_uri": True,
                    "has_repeated_reason_hint_prefix": True,
                    "has_payload_like_reason_hint": True,
                    "is_quiet": False,
                },
                "top_observed": {
                    "src_ip": [{"value": "192.168.56.114", "count": 5}],
                    "uri": [{"value": "/search.php", "count": 5}],
                    "reason_hint_prefix": [
                        {"value": "error_linked", "count": 5},
                        {"value": "error_status", "count": 5},
                        {"value": "xss", "count": 5},
                        {"value": "auth_payload_content_type", "count": 1},
                        {"value": "login_endpoint", "count": 1},
                    ],
                    "status_code": [{"value": "500", "count": 5}],
                },
                "guardrails": {
                    "summary_only": True,
                    "apache_logs_only": True,
                    "no_success_inference": True,
                    "no_body_inference": True,
                    "no_context_promotion": True,
                    "no_new_security_verdict": True,
                },
            }
        ],
        "guardrails": {"summary_only": True},
    }
    write_json(tmp_path / "data/operator_queue/2026-05-24/queue_items.json", payload)


def test_build_detail_for_rollup_contains_human_readable_sections(tmp_path: Path):
    module = load_module()
    write_queue_items(tmp_path)

    detail = module.build_detail_for_rollup(
        work_dir=tmp_path,
        date="2026-05-24",
        queue_root="data/operator_queue",
        rollup_id="rollup_20260524_0200_0400",
    )

    assert detail["schema"] == "sliding_window_operator_queue_item_detail_view_v1"
    assert detail["rollup_id"] == "rollup_20260524_0200_0400"
    assert detail["summary"]["review_status"] == "needs_review"
    assert detail["quality_assessment"]["status"] == "complete"
    assert detail["routing"]["llm_required"] is False
    assert detail["counts"]["candidate_index_count"] == 5
    assert detail["observed_signals"]["has_payload_like_reason_hint"] is True
    assert detail["observed_signals"]["matched_payload_like_reason_prefixes"] == [
        {"value": "xss", "count": 5},
        {"value": "sqli", "count": 1},
    ]
    assert detail["top_observed"]["reason_hint_prefix"] == [
        {"value": "error_linked", "count": 5},
        {"value": "error_status", "count": 5},
        {"value": "xss", "count": 5},
        {"value": "auth_payload_content_type", "count": 1},
        {"value": "login_endpoint", "count": 1},
    ]
    assert detail["source_selection"]["rollup_pattern"] == "rollup_*"


def test_render_text_orders_detail_for_human_review(tmp_path: Path):
    module = load_module()
    write_queue_items(tmp_path)
    detail = module.build_detail_for_rollup(
        work_dir=tmp_path,
        date="2026-05-24",
        queue_root="data/operator_queue",
        rollup_id="rollup_20260524_0200_0400",
    )

    rendered = module.render_text(detail)

    assert rendered.startswith("Operator Queue Item Detail\n")
    assert "1. Data quality" in rendered
    assert "2. Review routing" in rendered
    assert "3. Scope" in rendered
    assert "4. Counts" in rendered
    assert "5. Observed signals" in rendered
    assert "6. Top observed distributions" in rendered
    assert "7. Drilldown" in rendered
    assert "8. Source selection" in rendered
    assert "9. Apache logs-only notes" in rendered
    assert "10. Non-conclusions" in rendered
    assert "## 1. Data quality" not in rendered
    assert "- reason_hint_prefix: error_linked (5), error_status (5), xss (5), auth_payload_content_type (1), login_endpoint (1)" in rendered
    assert "- matched_payload_like_reason_prefixes: xss (5), sqli (1)" in rendered
    assert "- llm_required: no" in rendered


def test_render_markdown_has_markdown_headings(tmp_path: Path):
    module = load_module()
    write_queue_items(tmp_path)
    detail = module.build_detail_for_rollup(
        work_dir=tmp_path,
        date="2026-05-24",
        queue_root="data/operator_queue",
        rollup_id="rollup_20260524_0200_0400",
    )

    rendered = module.render_markdown(detail)

    assert rendered.startswith("# Operator Queue Item Detail\n")
    assert "## 1. Data quality" in rendered
    assert "## 10. Non-conclusions" in rendered


def test_missing_rollup_id_raises_helpful_error(tmp_path: Path):
    module = load_module()
    write_queue_items(tmp_path)

    with pytest.raises(module.QueueItemNotFoundError) as exc_info:
        module.build_detail_for_rollup(
            work_dir=tmp_path,
            date="2026-05-24",
            queue_root="data/operator_queue",
            rollup_id="rollup_missing",
        )

    assert "rollup_missing" in str(exc_info.value)
    assert "rollup_20260524_0200_0400" in str(exc_info.value)


def test_detail_preview_does_not_create_verdict_fields_or_success_claims(tmp_path: Path):
    module = load_module()
    write_queue_items(tmp_path)
    detail = module.build_detail_for_rollup(
        work_dir=tmp_path,
        date="2026-05-24",
        queue_root="data/operator_queue",
        rollup_id="rollup_20260524_0200_0400",
    )
    rendered = module.render_text(detail)
    serialized = json.dumps(detail, ensure_ascii=False)

    forbidden_fields = [
        "severity",
        "confidence_score",
        "threat_level",
        "confirmed_attack",
        "confirmed_intrusion",
        "exploit_success",
    ]
    for field in forbidden_fields:
        assert field not in serialized

    assert "does not conclude attack success" in rendered
    assert "routing signals, not security verdicts" in rendered


def test_cli_json_output(tmp_path: Path, capsys):
    module = load_module()
    write_queue_items(tmp_path)

    rc = module.main(
        [
            "--work-dir",
            str(tmp_path),
            "--date",
            "2026-05-24",
            "--rollup-id",
            "rollup_20260524_0200_0400",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert rc == 0
    assert payload["rollup_id"] == "rollup_20260524_0200_0400"
    assert payload["routing"]["llm_required"] is False
    assert payload["observed_signals"]["matched_payload_like_reason_prefixes"] == [
        {"value": "xss", "count": 5},
        {"value": "sqli", "count": 1},
    ]


def test_cli_missing_rollup_returns_error(tmp_path: Path, capsys):
    module = load_module()
    write_queue_items(tmp_path)

    rc = module.main(
        [
            "--work-dir",
            str(tmp_path),
            "--date",
            "2026-05-24",
            "--rollup-id",
            "missing",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "[QUEUE_DETAIL] ERROR" in captured.err
    assert "missing" in captured.err
