from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.prepare_llm_input import evaluate_row


def build_row(
    *,
    method: str,
    uri: str,
    query_string: str,
    status_code: int,
    raw_request: str,
    req_content_type: str = "",
    error_link_id: str = "",
    user_agent: str = "sqlmap/1.8",
    referer: str = "",
) -> dict:
    return {
        "id": 1,
        "time": "2026-05-20T10:00:00+09:00",
        "src_ip": "10.10.10.10",
        "method": method,
        "uri": uri,
        "query_string": query_string,
        "status_code": status_code,
        "raw_request": raw_request,
        "req_content_type": req_content_type,
        "error_link_id": error_link_id,
        "user_agent": user_agent,
        "referer": referer,
        "response_body_bytes": 128,
        "resp_content_type": "text/html",
    }


def test_upload_like_post_with_sql_comment_only_is_not_forced_to_sqli() -> None:
    row = build_row(
        method="POST",
        uri="/upload.php",
        query_string="",
        status_code=400,
        raw_request=(
            "POST /upload.php HTTP/1.1\n"
            "Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW"
        ),
        req_content_type="multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW",
        error_link_id="err-upload-1",
    )
    candidate, noise = evaluate_row(row, source_table="security", min_score=4)

    assert noise is None
    assert candidate is not None
    assert candidate.score >= 4
    assert candidate.verdict_hint != "sqli"
    assert "sqli:sql_comment(+2)" not in candidate.reason_hints
    assert "sqli:sql_comment_upload_context_weak_signal" in candidate.reason_hints
    assert "sqli:sql_comment_only_upload_context_no_strong_sqli_structure" in candidate.reason_hints
    assert "upload:multipart_or_upload_like_context" in candidate.reason_hints
    assert "upload:no_upload_success_inference" in candidate.reason_hints


def test_upload_like_post_with_strong_sqli_target_stays_sqli_candidate() -> None:
    query = "name=1%27%20OR%20%271%27%3D%271--"
    row = build_row(
        method="POST",
        uri="/upload.php",
        query_string=query,
        status_code=400,
        raw_request=f"POST /upload.php?{query} HTTP/1.1",
        req_content_type="multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW",
        error_link_id="err-upload-2",
    )
    candidate, noise = evaluate_row(row, source_table="security", min_score=4)

    assert noise is None
    assert candidate is not None
    assert candidate.verdict_hint == "sqli"
    assert "sqli:or_true(+4)" in candidate.reason_hints
    assert "sqli:quote_termination(+4)" in candidate.reason_hints
    assert "sqli:sql_comment_upload_context_weak_signal" not in candidate.reason_hints


def test_normal_search_sqli_with_sql_comment_keeps_sqli_candidate() -> None:
    query = "q=%27%20OR%20%271%27%3D%271--"
    row = build_row(
        method="GET",
        uri="/search.php",
        query_string=query,
        status_code=200,
        raw_request=f"GET /search.php?{query} HTTP/1.1",
        req_content_type="",
        error_link_id="",
        user_agent="Mozilla/5.0",
    )
    candidate, noise = evaluate_row(row, source_table="security", min_score=4)

    assert noise is None
    assert candidate is not None
    assert candidate.verdict_hint == "sqli"
    assert "sqli:or_true(+4)" in candidate.reason_hints
    assert "sqli:quote_termination(+4)" in candidate.reason_hints
