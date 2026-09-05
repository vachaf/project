from __future__ import annotations

import json

from src.external_benchmark_csic2010 import parse_raw_http_requests
from src.external_benchmark_csic2010_prepare import (
    DOCUMENTATION_IP,
    FIXED_LOG_TIME,
    evaluate_isolated_request,
    project_request,
)


def _one(raw: bytes):
    requests, _ = parse_raw_http_requests(raw, source_file="source.txt", source_label="source_anomalous")
    return requests[0]


def test_projection_preserves_request_line_observables_and_omits_sensitive_source_only_values() -> None:
    request = _one(
        b"POST http://example.test/path?x=%2F&x=two HTTP/1.1\r\n"
        b"Host: example.test\r\n"
        b"User-Agent: source-agent\r\n"
        b"Cookie: session=COOKIE_SECRET_SENTINEL\r\n"
        b"Content-Type: application/x-www-form-urlencoded\r\n"
        b"Content-Length: 24\r\n"
        b"X-Test-Secret: HEADER_SECRET_SENTINEL\r\n\r\n"
        b"BODY_SECRET_SENTINEL_123"
    )
    row, loss = project_request(request)
    serialized = json.dumps(row, sort_keys=True)

    assert row["method"] == "POST"
    assert row["raw_request"] == "POST http://example.test/path?x=%2F&x=two HTTP/1.1"
    assert row["raw_request_target"] == "http://example.test/path?x=%2F&x=two"
    assert row["uri"] == "/path"
    assert row["query_string"] == "?x=%2F&x=two"
    assert row["req_host"] == "example.test"
    assert row["user_agent"] == "source-agent"
    assert row["req_content_type"] == "application/x-www-form-urlencoded"
    assert row["req_content_length"] == "24"
    assert row["has_cookie"] is True
    assert row["has_authorization"] is False
    assert row["src_ip"] == DOCUMENTATION_IP
    assert row["log_time"] == FIXED_LOG_TIME
    assert row["status_code"] == 200 and row["response_body_bytes"] == 0 and row["resp_content_type"] == ""
    assert loss.body_omitted and loss.cookie_value_omitted and loss.unlogged_header_present
    for forbidden in ("BODY_SECRET_SENTINEL_123", "COOKIE_SECRET_SENTINEL", "HEADER_SECRET_SENTINEL", "source_anomalous"):
        assert forbidden not in serialized


def test_put_duplicate_query_and_percent_encoding_are_preserved() -> None:
    request = _one(b"PUT /api?tag=a&tag=a&q=%00 HTTP/1.1\nHost: example.test\n\n")
    row, loss = project_request(request)

    assert row["method"] == "PUT"
    assert row["raw_request_target"] == "/api?tag=a&tag=a&q=%00"
    assert row["query_string"] == "?tag=a&tag=a&q=%00"
    assert not loss.body_omitted


def test_isolated_prepare_invocation_is_one_per_request_and_order_independent() -> None:
    calls: list[str] = []

    def fake_builder(payload, **_kwargs):
        row = payload["data"]["security"][0]
        calls.append(row["raw_request_target"])
        candidate = {"request_id": row["request_id"], "score": 7, "verdict_hint": "suspicious", "reason_hints": ["fixture:hint"], "source_table": "security"}
        return {}, [candidate], [], {}, []

    first = _one(b"GET /a HTTP/1.1\nHost: example.test\n\n")
    second = _one(b"GET /b HTTP/1.1\nHost: example.test\n\n")
    a = evaluate_isolated_request(first, prepare_builder=fake_builder)
    b = evaluate_isolated_request(second, prepare_builder=fake_builder)
    assert calls == ["/a", "/b"]
    assert a["selected"] and b["selected"]
    assert a["score"] == b["score"] == 7
    assert a["source_label"] == "source_anomalous"
