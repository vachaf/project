from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.external_benchmark_csic2010 import (
    RawHttpParseError,
    main,
    parse_raw_http_requests,
    scan_source_file,
    source_manifest,
    validate_source_manifest_contract,
)


def test_consecutive_lf_get_requests_keep_offsets_and_raw_target() -> None:
    raw = (
        b"GET /search?q=%00&tag=a&tag=b HTTP/1.1\n"
        b"Host: example.test\n"
        b"User-Agent: fixture-agent\n"
        b"\n\n"
        b"PATCH /next HTTP/1.1\nHost: example.test\n\n"
    )
    requests, accounting = parse_raw_http_requests(raw, source_file="fixture.txt")

    assert [request.method for request in requests] == ["GET", "PATCH"]
    assert requests[0].raw_target == b"/search?q=%00&tag=a&tag=b"
    assert requests[0].request_id == "csic2010:fixture.txt:000001"
    assert requests[0].headers[0].name == b"Host"
    assert requests[0].start_offset == 0
    assert requests[0].end_offset < requests[1].start_offset
    assert accounting.unaccounted_bytes == 0
    assert accounting.request_bytes + accounting.separator_bytes == len(raw)


def test_content_length_preserves_body_blank_lines_and_crlf() -> None:
    body = b"first=line\r\n\r\nsecond=line"
    raw = (
        b"POST http://example.test/form HTTP/1.1\r\n"
        b"Host: example.test\r\n"
        b"Content-Type: application/x-www-form-urlencoded\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"\r\n"
        + body
        + b"\r\n\r\nGET /after HTTP/1.1\r\nHost: example.test\r\n\r\n"
    )
    requests, accounting = parse_raw_http_requests(raw)

    assert len(requests) == 2
    assert requests[0].raw_target == b"http://example.test/form"
    assert requests[0].body_bytes == body
    assert requests[1].method == "GET"
    assert accounting.unaccounted_bytes == 0


def test_duplicate_headers_and_non_ascii_bytes_are_retained() -> None:
    raw = (
        b"GET /path?x=1&x=1 HTTP/1.1\n"
        b"X-Trace: one\n"
        b"X-Trace: two\n"
        b"X-Display: \xff\n"
        b"\n"
    )
    requests, _ = parse_raw_http_requests(raw)

    assert [header.raw_line for header in requests[0].headers] == [b"X-Trace: one", b"X-Trace: two", b"X-Display: \xff"]
    assert b"\xff" in requests[0].raw_request_bytes
    assert requests[0].raw_request_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    ("raw", "error_type"),
    [
        (b"POST /x HTTP/1.1\nContent-Length: nope\n\n", "invalid_content_length"),
        (b"POST /x HTTP/1.1\nContent-Length: -1\n\n", "negative_content_length"),
        (b"POST /x HTTP/1.1\nContent-Length: 4\nContent-Length: 4\n\nbody", "duplicate_content_length"),
        (b"POST /x HTTP/1.1\nContent-Length: 5\n\nno", "truncated_body"),
    ],
)
def test_invalid_content_length_is_never_silently_skipped(raw: bytes, error_type: str) -> None:
    with pytest.raises(RawHttpParseError, match=error_type):
        parse_raw_http_requests(raw)


def test_scan_source_file_reports_only_aggregate_diagnostics(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(
        b"GET /a HTTP/1.1\nCookie: one\n\n\n"
        b"POST /b HTTP/1.1\nContent-Length: 3\n\nabc\n\n"
    )
    result = scan_source_file(source, source_label="source_normal")

    assert result["parsed_requests"] == 2
    assert result["duplicate_raw_requests"] == 0
    assert result["methods"] == {"GET": 1, "POST": 1, "other": 0, "all": {"GET": 1, "POST": 1}}
    assert result["body"] == {"with_body": 1, "without_body": 1}
    assert result["headers"]["with_cookie"] == 1
    assert result["byte_consumption"]["unaccounted_bytes"] == 0
    assert result["parse_errors"] == []
    assert "raw_request_bytes" not in json.dumps(result)


def test_cli_refuses_network_acquire_without_explicit_opt_in(tmp_path: Path) -> None:
    assert main(["acquire", "--cache-dir", str(tmp_path)]) == 2


def test_source_manifest_contract_is_network_free_and_checks_statuses() -> None:
    inventory = {
        "complete": True,
        "mirror_consistency": "verified",
        "files": [
            {
                "filename": name,
                "source_label": "source_anomalous" if name.startswith("anomalous") else "source_normal",
                "role": "training" if name.endswith("Training.txt") else "test",
                "documented_request_count": count,
                "whole_file_matches_comparison": True,
                "primary": {"source_url": "https://example.test/primary/" + name, "retrieved_at": "2026-09-05T00:00:00Z", "http_status": 200, "byte_size": 1, "sha256": "a" * 64, "parsed_requests": count},
                "comparison": {"source_url": "https://example.test/comparison/" + name, "retrieved_at": "2026-09-05T00:00:01Z", "http_status": 200, "byte_size": 1, "sha256": "a" * 64},
            }
            for name, count in (("normalTrafficTraining.txt", 36000), ("normalTrafficTest.txt", 36000), ("anomalousTrafficTest.txt", 25065))
        ],
        "totals": {"total_requests": 97065, "total_parse_errors": 0, "cross_file_duplicate_raw_requests": 0, "cross_label_identical_requests": 0},
    }
    manifest = source_manifest(inventory)

    assert validate_source_manifest_contract(manifest) == []
    manifest["canonical_acquisition"]["files"][0]["http_status"] = 404
    assert "missing successful retrieval status" in "; ".join(validate_source_manifest_contract(manifest))
