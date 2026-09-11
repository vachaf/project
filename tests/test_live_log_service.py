from datetime import datetime, timezone

import pytest

from web.services.live_log_repository import LiveLogPage
from web.services.live_log_service import LiveLogService, LiveSnapshotRequest, LiveSnapshotValidationError

NOW = datetime(2026, 9, 11, 1, tzinfo=timezone.utc)


class Repository:
    def __init__(self, page=None, raw=None):
        self.page = page or LiveLogPage(None, [], False, False)
        self.raw = raw
        self.query = None
        self.raw_id = None
    def fetch_page(self, query): self.query=query; return self.page
    def fetch_raw_log(self, row_id): self.raw_id=row_id; return self.raw


def row(row_id, second=0):
    return {"id":row_id,"log_time":datetime(2026,9,1,1,1,second),"request_id":None,"src_ip":"192.0.2.1","method":"GET","uri":"/x","request_target":"/x?a=1","status_code":200,"response_body_bytes":1,"user_agent":"ua","client_ip_source":"direct","log_schema":"v2"}


def service(repository): return LiveLogService(repository, now_factory=lambda:NOW)


def test_snapshot_max_50_desc_and_separates_times_and_raw_log():
    rows=[row(i, i % 60) for i in range(50,0,-1)]
    repo=Repository(LiveLogPage(datetime(2026,9,10,1),rows,False,False))
    payload=service(repo).snapshot(LiveSnapshotRequest())
    assert len(payload["items"]) == payload["page_size"] == 50
    assert "raw_log" not in payload["items"][0]
    assert payload["latest_log_time"] == "2026-09-10T10:00:00.000+09:00"
    assert payload["fetched_at"] == "2026-09-11T10:00:00+09:00"
    assert repo.query.from_time is None


def test_filters_period_cursor_and_validation():
    repo=Repository(); live=service(repo)
    live.snapshot(LiveSnapshotRequest(period="30m",status_class="4XX",method="get",src_ip="2001:db8::1",keyword="/login"))
    assert repo.query.status_class == "4xx" and repo.query.method == "GET"
    assert repo.query.src_ip == "2001:db8::1" and repo.query.keyword == "/login"
    assert repo.query.from_time == datetime(2026,9,11,0,30)
    for request, code in [(LiveSnapshotRequest(limit=51),"invalid_limit"),(LiveSnapshotRequest(src_ip="partial"),"invalid_src_ip"),(LiveSnapshotRequest(status_class="high"),"invalid_status")]:
        with pytest.raises(LiveSnapshotValidationError) as error: live.snapshot(request)
        assert error.value.code == code


def test_older_newer_cursors_use_page_edges_for_lossless_adjacency():
    rows=[row(30,30),row(29,29)]
    repo=Repository(LiveLogPage(NOW.replace(tzinfo=None),rows,True,True))
    payload=service(repo).snapshot(LiveSnapshotRequest())
    from web.services.live_log_service import LiveCursorCodec
    assert (LiveCursorCodec.decode(payload["newer_cursor"]).row_id, LiveCursorCodec.decode(payload["older_cursor"]).row_id) == (30,29)
    assert LiveCursorCodec.decode(payload["newer_cursor"]).direction == "newer"
    assert LiveCursorCodec.decode(payload["older_cursor"]).direction == "older"


def test_raw_log_is_preserved_byte_for_character_without_normalizing():
    raw='a\r\n<script>x</script> & "quoted" 한글\x00'
    repo=Repository(raw={"id":9,"raw_log":raw})
    assert service(repo).raw_log(9) == {"row_id":9,"raw_log":raw}
    assert repo.raw_id == 9
    with pytest.raises(LiveSnapshotValidationError): service(repo).raw_log(0)
