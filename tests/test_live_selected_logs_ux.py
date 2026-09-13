from __future__ import annotations

from pathlib import Path

import web.app as app_module


SCRIPT_PATH = Path(app_module.BASE_DIR) / "static" / "live-monitoring.js"


def _script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def _page() -> str:
    return app_module.templates.get_template("live_dashboard.html").render()


def test_live_selected_input_controls_and_boundary_copy_are_rendered() -> None:
    page = _page()
    for element_id in (
        "liveSelectedCount",
        "liveClearSelectionButton",
        "liveSubmitSelectionButton",
        "liveJobFeedback",
    ):
        assert f'id="{element_id}"' in page
    assert "선택 0 / 50건" in page
    assert "선택 로그로 분석 작업 만들기" in page
    assert "exact ID를 분석 입력으로 등록" in page
    assert "공격 성공, 침해 또는 위험도를 확정하지 않습니다" in page
    assert 'colspan="10"' in page


def test_checkbox_interaction_is_separate_from_detail_row_interaction() -> None:
    script = _script()
    assert 'checkbox.type = "checkbox"' in script
    assert "event.stopPropagation()" in script
    assert 'event.target.closest(".live-row-select")' in script
    assert "if (event.target !== row) return;" in script
    assert 'event.key === "Enter" || event.key === " "' in script
    assert "selectDetail();" in script


def test_ordered_selection_max_and_reselect_policy_are_explicit() -> None:
    script = _script()
    assert "const MAX_SELECTED_LOGS = 50;" in script
    assert "state.selectedOrder.push(rowId);" in script
    assert "state.selectedOrder = state.selectedOrder.filter" in script
    assert "state.selectedOrder.slice()" in script
    assert "selectedCount >= MAX_SELECTED_LOGS && !checked" in script
    assert "selectedCount === 0" in script


def test_selection_is_memory_only_and_snapshot_does_not_replace_it() -> None:
    script = _script()
    snapshot_body = script.split("async function snapshot", 1)[1].split(
        "function renderJobFeedback", 1
    )[0]
    assert "selectedOrder: []" in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "selectedOrder =" not in snapshot_body
    assert "renderRows();" in snapshot_body
    assert "checkbox.checked = checked;" in script


def test_submit_posts_ordered_ids_and_locks_every_live_interaction() -> None:
    script = _script()
    assert 'fetch("/api/live/jobs/create"' in script
    assert 'method: "POST"' in script
    assert '"Content-Type": "application/json"' in script
    assert "JSON.stringify({ selected_log_ids: selectedLogIds })" in script
    for expression in (
        "Array.from(el.form.elements)",
        "el.auto.disabled = locked",
        "el.refresh.disabled = locked",
        "el.latestButton.disabled = locked",
        "el.older.disabled = locked",
        "el.newer.disabled = locked",
        "checkbox.disabled = state.submitting",
        "state.loading || state.submitting",
        "!state.submitting) snapshot(null)",
    ):
        assert expression in script


def test_pending_success_links_without_redirect_and_clears_selection() -> None:
    script = _script()
    pending_body = script.split('payload.status === "PENDING"', 1)[1].split(
        'payload.code === "NO_DATA"', 1
    )[0]
    assert "state.selectedOrder = [];" in pending_body
    assert 'link.href = `/job/${encodeURIComponent(String(jobId))}`' in script
    assert "window.location" not in script
    assert "location.assign" not in script
    assert "location.replace" not in script
    assert "PENDING 작업 입력으로 등록되었습니다" in script


def test_partial_missing_duplicate_no_data_and_errors_keep_selection() -> None:
    script = _script()
    assert "missing_log_ids" in script
    assert "제출 시점에 확인되지 않은 항목" in script
    assert 'payload.code === "duplicate_active_job"' in script
    assert "같은 선택의 진행 중 작업이 있습니다" in script
    assert "payload.existing_job_id" in script
    assert 'payload.code === "NO_DATA"' in script
    for status in (400, 503, 500):
        assert f"status === {status}" in script
    assert "서버에 연결하지 못했습니다" in script

    # PENDING success and the explicit clear button are the only reset sites.
    assert script.count("state.selectedOrder = [];") == 2


def test_new_ux_does_not_invent_diagnostic_ids_or_use_certainty_wording() -> None:
    combined = _page() + _script()
    for forbidden_mechanism in ("crypto.randomUUID", "diagnosticRequestId", "clientRequestId"):
        assert forbidden_mechanism not in _script()
    for forbidden_wording in ("공격 확정", "침해 확정", "위험도 확정", "차단"):
        assert forbidden_wording not in combined


def test_existing_live_observation_and_navigation_contract_remains() -> None:
    script = _script()
    for required in (
        "/api/live/snapshot",
        "/api/live/logs/",
        "live-status-2xx",
        "live-status-5xx",
        "processing_status",
        "assessment",
        "raw_log 원문",
        "state.older",
        "state.newer",
        "이전 목록은 유지합니다",
    ):
        assert required in script
