from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.prepare_llm_input import build_outputs, evaluate_row


def apache_v2_raw_log(
    *,
    request_id: str,
    raw_request: str,
    uri: str,
    query_string: str,
    status_code: int,
    location: str = "-",
) -> str:
    return (
        "log_schema=apache_security_io_v2 "
        f"log_time=2026-06-24T06:37:49.658+0000 request_id={request_id} "
        "error_link_id=- vhost=\"apache-v2-test.local\" server_name=\"apache-v2-test.local\" "
        "server_port=80 local_ip=192.168.56.115 client_ip_source=\"direct\" "
        "src_ip=192.168.56.120 peer_ip=192.168.56.120 "
        f"method=GET raw_request=\"{raw_request}\" request_target=\"{raw_request.split(' ', 2)[1]}\" "
        f"uri=\"{uri}\" query_string=\"{query_string}\" protocol=HTTP/1.1 "
        f"status_code={status_code} original_status_code={status_code} response_body_bytes=10 "
        "in_bytes=136 out_bytes=166 total_bytes=302 duration_us=323 ttfb_us=156 "
        "keepalive_count=0 connection_status=+ handler=\"application/x-httpd-php\" "
        "req_content_type=\"-\" req_content_length=\"-\" resp_content_type=\"text/plain\" "
        f"location=\"{location}\" referer=\"-\" origin=\"-\" "
        "user_agent=\"demo-path-traversal/1.0\" req_host=\"apache-v2-test.local\""
    )


def traversal_row(
    *,
    request_id: str,
    raw_request: str,
    query_string: str,
    status_code: int = 403,
    location: str = "-",
) -> dict:
    return {
        "id": 47,
        "log_time": "2026-06-24T15:37:49.658+09:00",
        "time": "2026-06-24T15:37:49.658+09:00",
        "src_ip": "192.168.56.120",
        "method": "GET",
        "uri": "/download.php",
        "query_string": query_string,
        "status_code": status_code,
        "raw_request": raw_request,
        "raw_log": apache_v2_raw_log(
            request_id=request_id,
            raw_request=raw_request,
            uri="/download.php",
            query_string=query_string,
            status_code=status_code,
            location=location,
        ),
        "request_id": request_id,
        "error_link_id": "",
        "user_agent": "demo-path-traversal/1.0",
        "referer": "",
        "response_body_bytes": 10,
        "resp_content_type": "text/plain",
    }


def test_apache_location_field_does_not_create_external_navigation_hint() -> None:
    row = traversal_row(
        request_id="rid-traversal",
        raw_request="GET /download.php?file=../../../../etc/passwd HTTP/1.1",
        query_string="?file=../../../../etc/passwd",
    )

    candidate, noise = evaluate_row(row, source_table="security", min_score=4)

    assert noise is None
    assert candidate is not None
    assert candidate.verdict_hint == "path_traversal"
    assert candidate.score == 13
    assert "traversal:dotdot_slash(+4)" in candidate.reason_hints
    assert "traversal:etc_passwd(+5)" in candidate.reason_hints
    assert "xss:external_navigation" not in candidate.reason_hints


def test_apache_location_header_values_do_not_create_external_navigation_hint() -> None:
    for location in ("-", "/login", "https://example.test/"):
        row = traversal_row(
            request_id=f"rid-location-{location}",
            raw_request="GET /download.php?file=../../../../etc/passwd HTTP/1.1",
            query_string="?file=../../../../etc/passwd",
            location=location,
        )

        candidate, _noise = evaluate_row(row, source_table="security", min_score=4)

        assert candidate is not None
        assert "xss:external_navigation" not in candidate.reason_hints


def test_javascript_external_navigation_hint_is_preserved() -> None:
    payloads = [
        "q=<script>window.location='https://example.test/'</script>",
        "q=<script>document.location = '/next'</script>",
        "q=<script>location.href = 'https://example.test/'</script>",
        "q=<script>window.location.assign('/next')</script>",
        "q=<script>window.location.replace('/next')</script>",
    ]
    for index, query_string in enumerate(payloads):
        row = {
            "id": index + 1,
            "log_time": "2026-06-24T15:37:49.658+09:00",
            "src_ip": "192.168.56.121",
            "method": "GET",
            "uri": "/search.php",
            "query_string": query_string,
            "status_code": 200,
            "raw_request": f"GET /search.php?{query_string} HTTP/1.1",
            "raw_log": "",
            "request_id": f"rid-xss-{index}",
            "error_link_id": "",
            "user_agent": "Mozilla/5.0",
            "referer": "https://example.test/",
            "response_body_bytes": 512,
            "resp_content_type": "text/html",
        }

        candidate, _noise = evaluate_row(row, source_table="security", min_score=4)

        assert candidate is not None
        assert "xss:external_navigation" in candidate.reason_hints


def test_ip_behavior_for_path_traversal_rows_does_not_include_xss_category() -> None:
    rows = [
        traversal_row(
            request_id="rid-trv-1",
            raw_request="GET /download.php?file=../../../../etc/passwd HTTP/1.1",
            query_string="?file=../../../../etc/passwd",
        ),
        traversal_row(
            request_id="rid-trv-2",
            raw_request="GET /download.php?file=%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd HTTP/1.1",
            query_string="?file=%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ),
        traversal_row(
            request_id="rid-trv-3",
            raw_request="GET /download.php?file=%252e%252e%252f%252e%252e%252fetc%252fpasswd HTTP/1.1",
            query_string="?file=%252e%252e%252f%252e%252e%252fetc%252fpasswd",
        ),
        traversal_row(
            request_id="rid-trv-4",
            raw_request="GET /download.php?file=../../../../etc/hosts HTTP/1.1",
            query_string="?file=../../../../etc/hosts",
        ),
    ]
    payload = {
        "meta": {
            "query_timezone": "Asia/Seoul",
            "start": "2026-06-24T15:37:00.000+09:00",
            "end_exclusive": "2026-06-24T15:40:00.000+09:00",
            "total_count": len(rows),
        },
        "data": {"security": rows},
    }

    llm_input, candidates, _noise, _filtered_reasons, _filtered_rows = build_outputs(
        payload,
        min_score=4,
        min_repeat_aggregate=3,
        source_tables=["security"],
    )

    assert len(candidates) == 4
    assert all("xss:external_navigation" not in item["reason_hints"] for item in candidates)
    aggregates = llm_input["ip_behavior_aggregates"]
    assert len(aggregates) == 1
    categories = aggregates[0]["attack_categories_attempted"]
    assert "xss" not in categories
    assert "path_traversal" in categories
    assert "dir_probe" in categories
    assert "ip_behavior:high_4xx_ratio" in aggregates[0]["reason_hints"]
    assert "ip_behavior:multiple_attack_categories" in aggregates[0]["reason_hints"]
