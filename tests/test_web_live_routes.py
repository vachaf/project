from pathlib import Path

import json

import web.app as app_module
import web.routes.live as routes
from web.services.live_log_repository import LiveLogRepositoryError


class Service:
    def __init__(self, error=None): self.error=error; self.request=None
    def snapshot(self, request):
        self.request=request
        if self.error: raise self.error
        return {"fetched_at":"2026-09-11T10:00:00+09:00","latest_log_time":"2026-09-01T10:00:00+09:00","items":[],"older_cursor":None,"newer_cursor":None,"has_older":False,"has_newer":False,"page_size":0}
    def raw_log(self, row_id): return {"row_id":row_id,"raw_log":'<img onerror="boom"> & 한글'}


def test_live_page_has_contract_and_old_log_is_not_diagnosed_as_failure():
    paths={route.path for route in routes.router.routes}
    assert {"/live","/api/live/snapshot","/api/live/logs/{row_id}/raw"} <= paths
    response=app_module.templates.get_template("live_dashboard.html").render()
    for text in (
        "기간 제한 없음 · 최신 50건",
        "HTTP status는 웹 서버 응답 상태 코드",
        "Apache 운영 상태를 설명하지 않습니다",
        "승인된 관찰 구조·처리 범위와 보안 판정은 서로 분리",
    ):
        assert text in response


def test_snapshot_keeps_status_class_and_filters(monkeypatch):
    fake=Service();monkeypatch.setattr(routes,"live_service",fake)
    response=routes.live_snapshot(period="1h",status_class="4xx",method="GET",src_ip="192.0.2.1",q="/login",limit=50,cursor=None)
    assert response.status_code == 200
    assert fake.request.status_class == "4xx" and fake.request.keyword == "/login"


def test_raw_detail_preserves_literal_value(monkeypatch):
    monkeypatch.setattr(routes,"live_service",Service())
    payload=json.loads(routes.live_raw_log(7).body)
    assert payload["raw_log"] == '<img onerror="boom"> & 한글'


def test_database_error_is_safe(monkeypatch):
    monkeypatch.setattr(routes,"live_service",Service(LiveLogRepositoryError("password=secret")))
    response=routes.live_snapshot(period="all",status_class=None,method=None,src_ip=None,q=None,limit=50,cursor=None)
    assert response.status_code == 503 and json.loads(response.body)["code"] == "live_db_unavailable"
    assert b"secret" not in response.body


def test_javascript_uses_text_sinks_and_has_no_analysis_pipeline_calls():
    script=(Path(app_module.BASE_DIR)/"static/live-monitoring.js").read_text()
    assert "textContent" in script
    for forbidden in ("innerHTML","outerHTML","insertAdjacentHTML","document.write","prepare_llm_input","stage1","stage2","analysis job","/api/jobs"):
        assert forbidden.lower() not in script.lower()
    assert "live-status-2xx" in script and "live-status-5xx" in script
    assert "risk" not in script.lower() and "severity" not in script.lower()
    for text in ("processing_status", "assessment", "관찰 정보 미제공", "정상 상태를 뜻하지 않습니다"):
        assert text in script
