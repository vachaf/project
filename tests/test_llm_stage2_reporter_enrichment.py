from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import llm_stage2_reporter as reporter


def test_build_incident_briefs_enriches_placeholder_from_candidate() -> None:
    stage1_results = [
        {
            "request_id": "rid-1",
            "incident_group_key": "igk-rid-1",
            "source_table": "security",
            "log_id": 101,
            "src_ip": "192.0.2.10",
            "method": "-",
            "uri": "/search.php",
            "query_string": "",
            "status_code": 200,
            "score": 55,
            "response_body_bytes": 0,
            "duration_us": 0,
            "ttfb_us": 0,
            "resp_content_type": "",
            "raw_request_target": "",
            "raw_request": "",
            "user_agent": "",
            "handler": "",
            "log_schema": "",
            "reason_hints": [],
            "evidence_fields": [],
            "verdict": "likely_xss",
            "severity": "high",
            "confidence": "medium",
        }
    ]
    llm_input_payload = {
        "analysis_candidates": [
            {
                "request_id": "rid-1",
                "incident_group_key": "igk-rid-1",
                "source_table": "security",
                "log_id": 101,
                "method": "GET",
                "query_string": "?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E",
                "raw_request": "GET /search.php?q=<script>alert(1)</script> HTTP/1.1",
                "raw_request_target": "/search.php?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E",
                "response_body_bytes": 75002,
                "duration_us": 28000,
                "ttfb_us": 13200,
                "resp_content_type": "text/html",
                "user_agent": "obs-test/S14 run=test",
                "handler": "php-handler",
                "log_schema": "apache_combined_plus",
                "reason_hints": ["xss:script_tag(+5)"],
                "status_code": 404,
                "score": 99,
            }
        ]
    }

    briefs = reporter.build_incident_briefs(
        stage1_results,
        top_n=5,
        known_asset_ips=[],
        candidate_lookup=reporter.build_candidate_evidence_lookup(llm_input_payload),
    )

    assert len(briefs) == 1
    brief = briefs[0]
    assert brief.method == "GET"
    assert brief.response_body_bytes == 75002
    assert brief.resp_content_type == "text/html"
    assert brief.raw_request_target == "/search.php?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E"
    assert "GET /search.php" in brief.raw_request
    assert brief.user_agent == "obs-test/S14 run=test"
    assert brief.query_string == "?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E"
    assert brief.duration_us == 28000
    assert brief.ttfb_us == 13200
    assert brief.handler == "php-handler"
    assert brief.log_schema == "apache_combined_plus"
    assert brief.reason_hints == ["xss:script_tag(+5)"]
    assert brief.evidence_fields == ["xss:script_tag(+5)"]

    # Keep Stage1 decisions/score context as-is.
    assert brief.verdict == "likely_xss"
    assert brief.severity == "high"
    assert brief.status_code == 200
    assert brief.score == 55
