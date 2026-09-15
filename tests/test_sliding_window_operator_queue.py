from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "src" / "sliding_window_operator_queue.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sliding_window_operator_queue", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["sliding_window_operator_queue"] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def rollup_payloads(
    *,
    rollup_id: str,
    start: str = "2026-05-24T02:00:00+09:00",
    end: str = "2026-05-24T03:00:00+09:00",
    candidate_index_count: int = 0,
    candidate_rows_total: int | None = None,
    windows_missing_or_failed: int = 0,
    incomplete_analysis: bool = False,
    distributions: dict | None = None,
    source_windows: list[dict] | None = None,
):
    counts = {
        "window_count": 1,
        "windows_successfully_loaded": 1 if windows_missing_or_failed == 0 else 0,
        "windows_missing_or_failed": windows_missing_or_failed,
        "candidate_rows_total": candidate_rows_total if candidate_rows_total is not None else candidate_index_count,
        "candidate_index_count": candidate_index_count,
        "dedup_removed_by_request_id": 0,
        "possible_duplicate_count": 0,
        "noise_group_count_total": 0,
    }
    rollup = {
        "rollup_id": rollup_id,
        "start": start,
        "end_exclusive": end,
        "timezone": "Asia/Seoul",
        "duration_minutes": 60,
    }
    rollup_input = {
        "schema": "sliding_window_rollup_input_v1",
        "rollup": rollup,
        "source_windows": source_windows or [
            {
                "window_id": "sw_0200_0300",
                "path": "data/windowed/2026-05-24/sw_0200_0300/window_summary.json",
                "status": "loaded",
            }
        ],
        "counts": counts,
        "dedup": {"possible_duplicates": []},
        "distributions": distributions
        or {
            "candidate_status_code": {},
            "candidate_src_ip": {},
            "candidate_uri": {},
            "candidate_reason_hint_prefix": {},
        },
        "candidate_index": [],
        "guardrails": {"summary_only": True},
    }
    rollup_summary = {
        "schema": "sliding_window_rollup_summary_v1",
        "rollup": rollup,
        "counts": counts,
        "source_windows": source_windows or rollup_input["source_windows"],
        "incomplete_analysis": incomplete_analysis,
        "guardrails": {"summary_only": True},
    }
    return rollup_input, rollup_summary


def write_rollup(tmp_path: Path, *, rollup_id: str, **kwargs) -> Path:
    rollup_input, rollup_summary = rollup_payloads(rollup_id=rollup_id, **kwargs)
    out_dir = tmp_path / "data/rollups/2026-05-24" / rollup_id
    write_json(out_dir / "rollup_input.json", rollup_input)
    write_json(out_dir / "rollup_summary.json", rollup_summary)
    return out_dir


def build_queue(module, tmp_path: Path, **kwargs):
    params = {
        "work_dir": tmp_path,
        "date": "2026-05-24",
        "rollup_root": "data/rollups",
        "out_root": "data/operator_queue",
        "timezone": "Asia/Seoul",
        "pretty": True,
    }
    params.update(kwargs)
    return module.build_and_write_queue(**params)


def load_queue_payload(tmp_path: Path):
    path = tmp_path / "data/operator_queue/2026-05-24/queue_items.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_queue_items(tmp_path: Path):
    return load_queue_payload(tmp_path)["items"]


def load_queue_summary(tmp_path: Path):
    path = tmp_path / "data/operator_queue/2026-05-24/queue_summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_queue_marks_quiet_rollup(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_20260524_0200_0300", candidate_index_count=0)

    result = build_queue(module, tmp_path)
    items = load_queue_items(tmp_path)

    assert result["status"] == "written"
    assert len(items) == 1
    item = items[0]
    assert item["data_quality_status"] == "complete"
    assert item["review_status"] == "quiet"
    assert item["operator_state"] == "unreviewed"
    assert item["llm_eligible"] is False
    assert item["llm_required"] is False
    assert item["recommended_action"] == "skip_no_candidates"
    assert item["signals"]["is_quiet"] is True


def test_queue_marks_needs_review_and_llm_eligible_for_payload_like_candidate(tmp_path: Path):
    module = load_module()
    write_rollup(
        tmp_path,
        rollup_id="rollup_20260524_0300_0400",
        candidate_index_count=3,
        distributions={
            "candidate_status_code": {"403": 2, "200": 1},
            "candidate_src_ip": {"192.168.56.114": 3},
            "candidate_uri": {"/search.php": 3},
            "candidate_reason_hint_prefix": {"sqli_hint": 2, "error_status": 1},
        },
    )

    build_queue(module, tmp_path)
    item = load_queue_items(tmp_path)[0]

    assert item["data_quality_status"] == "complete"
    assert item["review_status"] == "needs_review"
    assert item["llm_eligible"] is True
    assert item["llm_required"] is False
    assert item["recommended_action"] == "review_before_optional_briefing"
    assert item["signals"]["has_payload_like_reason_hint"] is True
    assert item["signals"]["has_repeated_src_ip"] is True
    assert item["top_observed"]["src_ip"] == [{"value": "192.168.56.114", "count": 3}]
    assert item["top_observed"]["status_code"] == [
        {"value": "403", "count": 2},
        {"value": "200", "count": 1},
    ]


def test_queue_treats_sqli_and_xss_prefix_variants_as_payload_like(tmp_path: Path):
    module = load_module()
    write_rollup(
        tmp_path,
        rollup_id="rollup_20260524_0300_0400",
        candidate_index_count=2,
        distributions={
            "candidate_status_code": {"403": 2},
            "candidate_src_ip": {"192.168.56.114": 1, "192.168.56.115": 1},
            "candidate_uri": {"/search.php": 1, "/comment.php": 1},
            "candidate_reason_hint_prefix": {"sqli": 1, "xss": 1},
        },
    )

    build_queue(module, tmp_path)
    item = load_queue_items(tmp_path)[0]

    assert item["signals"]["has_payload_like_reason_hint"] is True
    assert item["llm_eligible"] is True
    assert item["top_observed"]["reason_hint_prefix"] == [
        {"value": "sqli", "count": 1},
        {"value": "xss", "count": 1},
    ]


def test_queue_does_not_treat_context_prefixes_as_payload_like_by_themselves(tmp_path: Path):
    module = load_module()
    write_rollup(
        tmp_path,
        rollup_id="rollup_20260524_0300_0400",
        candidate_index_count=5,
        distributions={
            "candidate_status_code": {"500": 5},
            "candidate_src_ip": {"192.168.56.110": 1, "192.168.56.111": 1},
            "candidate_uri": {"/login.php": 1, "/upload.php": 1},
            "candidate_reason_hint_prefix": {
                "auth_payload_content_type": 1,
                "error_linked": 1,
                "error_status": 1,
                "login_endpoint": 1,
                "upload": 1,
            },
        },
    )

    build_queue(module, tmp_path)
    item = load_queue_items(tmp_path)[0]

    assert item["signals"]["has_payload_like_reason_hint"] is False
    assert item["signals"]["has_repeated_src_ip"] is False
    assert item["signals"]["has_repeated_uri"] is False
    assert item["signals"]["has_repeated_reason_hint_prefix"] is False
    assert item["llm_eligible"] is False
    assert item["recommended_action"] == "review_rollup_summary"


def test_queue_marks_data_quality_check_for_incomplete_rollup(tmp_path: Path):
    module = load_module()
    write_rollup(
        tmp_path,
        rollup_id="rollup_20260524_0400_0500",
        candidate_index_count=2,
        windows_missing_or_failed=1,
        incomplete_analysis=True,
    )

    build_queue(module, tmp_path)
    item = load_queue_items(tmp_path)[0]

    assert item["data_quality_status"] == "incomplete_missing_window"
    assert item["review_status"] == "data_quality_check"
    assert item["llm_eligible"] is False
    assert item["llm_required"] is False
    assert item["recommended_action"] == "data_quality_check"
    assert item["signals"]["has_missing_windows"] is True


def test_queue_marks_degraded_invalid_window_for_failed_source_window(tmp_path: Path):
    module = load_module()
    write_rollup(
        tmp_path,
        rollup_id="rollup_20260524_0500_0600",
        candidate_index_count=1,
        source_windows=[{"window_id": "sw_0500_0600", "status": "failed", "reason": "unsupported_schema"}],
    )

    build_queue(module, tmp_path)
    item = load_queue_items(tmp_path)[0]

    assert item["data_quality_status"] == "degraded_invalid_window"
    assert item["review_status"] == "data_quality_check"
    assert item["recommended_action"] == "data_quality_check"


def test_queue_marks_missing_rollup_artifact(tmp_path: Path):
    module = load_module()
    rollup_dir = tmp_path / "data/rollups/2026-05-24/rollup_20260524_0600_0700"
    rollup_dir.mkdir(parents=True)
    write_json(rollup_dir / "rollup_summary.json", {"schema": "sliding_window_rollup_summary_v1"})

    build_queue(module, tmp_path)
    item = load_queue_items(tmp_path)[0]

    assert item["data_quality_status"] == "missing_rollup_artifact"
    assert item["review_status"] == "data_quality_check"
    assert item["recommended_action"] == "data_quality_check"
    assert item["llm_eligible"] is False


def test_queue_summary_counts_statuses(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_20260524_0200_0300", candidate_index_count=0)
    write_rollup(
        tmp_path,
        rollup_id="rollup_20260524_0300_0400",
        candidate_index_count=2,
        distributions={
            "candidate_status_code": {"403": 1},
            "candidate_src_ip": {"192.168.56.114": 2},
            "candidate_uri": {"/search.php": 2},
            "candidate_reason_hint_prefix": {"sqli_hint": 1},
        },
    )
    write_rollup(
        tmp_path,
        rollup_id="rollup_20260524_0400_0500",
        candidate_index_count=1,
        windows_missing_or_failed=1,
        incomplete_analysis=True,
    )

    build_queue(module, tmp_path)
    summary = load_queue_summary(tmp_path)

    assert summary["schema"] == "sliding_window_operator_queue_summary_v1"
    assert summary["counts"] == {
        "rollup_items_total": 3,
        "quiet": 1,
        "needs_review": 1,
        "data_quality_check": 1,
        "complete": 2,
        "incomplete_missing_window": 1,
        "degraded_invalid_window": 0,
        "missing_rollup_artifact": 0,
        "llm_eligible": 1,
        "llm_required": 0,
        "unreviewed": 3,
        "reviewed": 0,
        "deferred": 0,
    }


def test_queue_does_not_create_security_verdict_fields(tmp_path: Path):
    module = load_module()
    write_rollup(
        tmp_path,
        rollup_id="rollup_20260524_0300_0400",
        candidate_index_count=1,
        distributions={
            "candidate_status_code": {"200": 1},
            "candidate_src_ip": {"192.168.56.114": 1},
            "candidate_uri": {"/search.php": 1},
            "candidate_reason_hint_prefix": {"sqli_hint": 1},
        },
    )

    build_queue(module, tmp_path)
    item = load_queue_items(tmp_path)[0]
    serialized = repr(item)

    assert item["guardrails"]["no_new_security_verdict"] is True
    assert item["llm_required"] is False
    assert "severity" not in serialized
    assert "confidence_score" not in serialized
    assert "threat_level" not in serialized
    assert "confirmed_attack" not in serialized
    assert "exploit_success" not in serialized


def test_queue_output_reuse_policy_skips_existing(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_20260524_0200_0300", candidate_index_count=0)
    first = build_queue(module, tmp_path)
    out_dir = tmp_path / first["out_dir"]
    marker = {"schema": "existing", "counts": {"rollup_items_total": 99}}
    write_json(out_dir / "queue_summary.json", marker)

    second = build_queue(module, tmp_path)

    assert second["status"] == "skipped_existing"
    assert second["counts"] == {"rollup_items_total": 99}
    assert json.loads((out_dir / "queue_summary.json").read_text(encoding="utf-8")) == marker


def test_queue_output_reuse_policy_fails_partial_existing(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_20260524_0200_0300", candidate_index_count=0)
    out_dir = tmp_path / "data/operator_queue/2026-05-24"
    write_json(out_dir / "queue_items.json", {"schema": "partial"})

    with pytest.raises(module.PartialExistingQueueArtifactsError) as exc_info:
        build_queue(module, tmp_path)

    assert exc_info.value.existing == ["queue_items.json"]
    assert exc_info.value.missing == ["queue_summary.json"]


def test_queue_output_reuse_policy_overwrite_recreates(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_20260524_0200_0300", candidate_index_count=0)
    first = build_queue(module, tmp_path)
    out_dir = tmp_path / first["out_dir"]
    write_json(out_dir / "queue_summary.json", {"schema": "existing"})

    second = build_queue(module, tmp_path, overwrite=True)

    assert second["status"] == "written"
    assert second["existing_outputs"] == ["queue_items.json", "queue_summary.json"]
    summary = json.loads((out_dir / "queue_summary.json").read_text(encoding="utf-8"))
    assert summary["schema"] == "sliding_window_operator_queue_summary_v1"
    assert summary["counts"]["rollup_items_total"] == 1


def test_atomic_write_does_not_leave_tmp_files(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_20260524_0200_0300", candidate_index_count=0)

    build_queue(module, tmp_path)

    out_dir = tmp_path / "data/operator_queue/2026-05-24"
    assert not list(out_dir.glob("*.tmp"))
    assert (out_dir / "queue_items.json").exists()
    assert (out_dir / "queue_summary.json").exists()


def test_rollup_pattern_includes_matching_rollups_only(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_ops_4h_0200_0600", candidate_index_count=1)
    write_rollup(tmp_path, rollup_id="rollup_ops_4h_0600_1000", candidate_index_count=0)
    write_rollup(tmp_path, rollup_id="rollup_smoke_single_0200_0300", candidate_index_count=1)

    result = build_queue(module, tmp_path, rollup_pattern="rollup_ops_*")
    payload = load_queue_payload(tmp_path)
    items = payload["items"]

    assert result["source_selection"] == {
        "rollup_root": "data/rollups/2026-05-24",
        "rollup_pattern": "rollup_ops_*",
        "matched_rollup_count": 2,
    }
    assert payload["source_selection"] == result["source_selection"]
    assert [item["rollup_id"] for item in items] == [
        "rollup_ops_4h_0200_0600",
        "rollup_ops_4h_0600_1000",
    ]


def test_default_rollup_pattern_keeps_existing_rollup_star_behavior(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_20260524_0200_0300", candidate_index_count=0)
    write_rollup(tmp_path, rollup_id="not_a_rollup_20260524_0200_0300", candidate_index_count=0)

    result = build_queue(module, tmp_path)
    items = load_queue_items(tmp_path)

    assert result["source_selection"]["rollup_pattern"] == "rollup_*"
    assert result["source_selection"]["matched_rollup_count"] == 1
    assert [item["rollup_id"] for item in items] == ["rollup_20260524_0200_0300"]


def test_empty_rollup_pattern_match_writes_empty_queue_not_quiet(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_smoke_single_0200_0300", candidate_index_count=0)

    result = build_queue(module, tmp_path, rollup_pattern="rollup_ops_*")
    items_payload = load_queue_payload(tmp_path)
    summary = load_queue_summary(tmp_path)

    assert result["status"] == "written"
    assert result["source_selection"] == {
        "rollup_root": "data/rollups/2026-05-24",
        "rollup_pattern": "rollup_ops_*",
        "matched_rollup_count": 0,
    }
    assert items_payload["items"] == []
    assert items_payload["source_selection"] == result["source_selection"]
    assert summary["source_selection"] == result["source_selection"]
    assert summary["counts"]["rollup_items_total"] == 0
    assert summary["counts"]["quiet"] == 0
    assert summary["counts"]["needs_review"] == 0
    assert summary["counts"]["data_quality_check"] == 0
    assert summary["counts"]["llm_eligible"] == 0
    assert summary["counts"]["llm_required"] == 0


def test_skipped_existing_preserves_source_selection_metadata(tmp_path: Path):
    module = load_module()
    write_rollup(tmp_path, rollup_id="rollup_ops_4h_0200_0600", candidate_index_count=0)

    first = build_queue(module, tmp_path, rollup_pattern="rollup_ops_*")
    second = build_queue(module, tmp_path, rollup_pattern="rollup_smoke_*")

    assert first["status"] == "written"
    assert second["status"] == "skipped_existing"
    assert second["source_selection"] == first["source_selection"]
    assert second["source_selection"]["rollup_pattern"] == "rollup_ops_*"
    assert second["source_selection"]["matched_rollup_count"] == 1
